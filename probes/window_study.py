"""Which trailing window best detects manipulation in a running conversation?

Replays each labelled dialogue turn by turn. At every turn boundary it asks the same yes/no manipulation question over a
trailing window (last N words, last N sentences, last N turns, or everything so far). A dialogue counts as flagged if the
window ever scores high. We report, per window definition, AUC of "max score over the stream" and of "score at the end"
against the dataset's dialogue-level label. The label is not localised to a turn, so this measures alarm quality, not
timing.

    python3 probes/window_study.py --backend kev-4b [--windows w5,w10,...] [--limit 200]

Needs the demo server (python3 demo/server.py) for /api/batch, and probes/v2/manipulation_windows.json.
"""
import argparse, json, math, random, re, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WINDOWS = "w5,w10,w20,w40,s1,s2,s3,t1,t2,t3,full"


def question():
    """The exact question object validated on the published manipulation set."""
    first = json.loads((ROOT / "probes/v2/manipulation_dialogue.jsonl").read_text().splitlines()[0])
    return first["question"]


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def render(turns):
    return "\n".join(f'{t["speaker"]}: {t["text"]}' for t in turns)


def window_text(turns, spec):
    """Trailing window of the transcript so far, built from the turns revealed up to now."""
    if spec == "full":
        return render(turns)
    kind, n = spec[0], int(spec[1:])
    if kind == "t":
        return render(turns[-n:])
    flat = " ".join(f'{t["speaker"]}: {t["text"]}' for t in turns)
    if kind == "w":
        return " ".join(flat.split()[-n:])
    if kind == "s":
        return " ".join(sentences(flat)[-n:])
    raise ValueError(spec)


def auc(scores, labels):
    """Rank AUC with ties averaged; labels are 1 for manipulative."""
    pos = [s for s, l in zip(scores, labels) if l]
    neg = [s for s, l in zip(scores, labels) if not l]
    if not pos or not neg:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def boot_ci(scores, labels, reps=300, seed=1):
    rng, n, out = random.Random(seed), len(scores), []
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        a = auc([scores[i] for i in idx], [labels[i] for i in idx])
        if not math.isnan(a):
            out.append(a)
    out.sort()
    return (out[int(0.025 * len(out))], out[int(0.975 * len(out)) - 1]) if out else (float("nan"),) * 2


def batch(backend, items, base):
    req = urllib.request.Request(base + "/api/batch", json.dumps({"backend": backend, "items": items}).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True, help='demo backend name, e.g. kev-4b or "jev (typesafe)"')
    ap.add_argument("--windows", default=DEFAULT_WINDOWS)
    ap.add_argument("--limit", type=int, default=0, help="use only the first N dialogues (balanced by construction)")
    ap.add_argument("--base", default="http://127.0.0.1:8100")
    ap.add_argument("--out", default=str(ROOT / "data/window-study"))
    a = ap.parse_args()
    data = json.loads((ROOT / "probes/v2/manipulation_windows.json").read_text())
    dialogues = data["dialogues"] if isinstance(data, dict) else data
    if a.limit:  # seeded sample, so a small pilot stays balanced whatever the file order
        dialogues = random.Random(20260921).sample(dialogues, min(a.limit, len(dialogues)))
    q, specs = question(), a.windows.split(",")
    jobs = []  # (dialogue index, turn end, window spec, state)
    for di, d in enumerate(dialogues):
        for k in range(1, len(d["turns"]) + 1):
            for spec in specs:
                jobs.append((di, k, spec, window_text(d["turns"][:k], spec)))
    print(f"{len(dialogues)} dialogues, {len(specs)} windows, {len(jobs)} calls on {a.backend}", flush=True)
    probs, t0 = {}, time.time()
    for i in range(0, len(jobs), 200):
        chunk = jobs[i : i + 200]
        res = batch(a.backend, [{"state": s, "questions": {"m": q}} for _, _, _, s in chunk], a.base)
        for (di, k, spec, _), r in zip(chunk, res):
            if "error" in r:
                sys.exit(f"call failed: {r['error']}")
            probs[(di, k, spec)] = r["answers"]["m"]["noul"]
        print(f"  {min(i + 200, len(jobs))}/{len(jobs)} ({time.time() - t0:.0f}s)", flush=True)
    labels = [1 if d["manipulative"] else 0 for d in dialogues]
    report = {"backend": a.backend, "n_dialogues": len(dialogues), "n_calls": len(jobs), "windows": {}}
    for spec in specs:
        mx, end, first = [], [], []
        for di, d in enumerate(dialogues):
            series = [probs[(di, k, spec)] for k in range(1, len(d["turns"]) + 1)]
            mx.append(max(series)); end.append(series[-1]); first.append(series[0])
        lo, hi = boot_ci(mx, labels)
        report["windows"][spec] = {"auc_max": auc(mx, labels), "auc_max_ci": [lo, hi], "auc_end": auc(end, labels),
                                   "mean_max_pos": sum(m for m, l in zip(mx, labels) if l) / max(1, sum(labels)),
                                   "mean_max_neg": sum(m for m, l in zip(mx, labels) if not l) / max(1, len(labels) - sum(labels))}
    Path(a.out).mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", a.backend.lower()).strip("-")
    (Path(a.out) / f"{slug}.json").write_text(json.dumps(report, indent=2))
    print(f"\n{'window':7}{'AUC max':>9}{'95% CI':>16}{'AUC end':>9}{'mean max: manip':>17}{'others':>8}")
    for spec, r in sorted(report["windows"].items(), key=lambda kv: -kv[1]["auc_max"]):
        print(f"{spec:7}{r['auc_max']:9.3f}   [{r['auc_max_ci'][0]:.3f},{r['auc_max_ci'][1]:.3f}]{r['auc_end']:9.3f}{r['mean_max_pos']:17.2f}{r['mean_max_neg']:8.2f}")


if __name__ == "__main__":
    main()
