#!/usr/bin/env python3
"""Batch performance: one state, N questions in one request.

Question q0 is the labelled question of a probe item; the other N-1 are filler questions taken
from other probe sets (unlabelled here, they only add load). Accuracy is scored on q0 alone, so
the curve shows whether a model degrades as the battery grows. Records are per item and per size,
resumable, and never written to data/bench/.

  python3 probes/lab_batch.py --model kev-4b --set manipulation_dialogue --n 40 --sizes 1 5 10 20 40 80 160

Local models only: the hosted backend is refused here (spend goes through the UI).
"""
import argparse, json, random, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "demo"))
import server  # noqa: E402  (reuses BACKENDS and call; no side effects on import)

PROBES = ROOT / "probes" / "v2"
OUT = ROOT / "data" / "probe-runs-v2" / "_batch"


def load(set_id):
    return [json.loads(l) for l in (PROBES / f"{set_id}.jsonl").read_text().splitlines() if l.strip()]


def fillers(exclude_set, seed):
    pool = []
    for f in sorted(PROBES.glob("*.jsonl")):
        if f.stem != exclude_set:
            pool += [r["question"] for r in load(f.stem) if r["question"]["type"] == "noul"][:40]
    random.Random(seed).shuffle(pool)
    return pool


def p_yes(ans):
    return ans.get("noul")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--set", default="manipulation_dialogue")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--sizes", type=int, nargs="+", default=[1, 5, 10, 20, 40, 80, 160])
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    cfg = server.BACKENDS[a.model]
    if cfg.get("hosted"):
        sys.exit("refusing: hosted model runs only through the UI")
    items = load(a.set)
    rnd = random.Random(a.seed)
    rnd.shuffle(items)
    items = items[: a.n]
    fill = fillers(a.set, a.seed)
    d = OUT / a.set / a.model
    d.mkdir(parents=True, exist_ok=True)
    path = d / "results.jsonl"
    done = set()
    if path.exists():
        done = {(r["item"], r["size"]) for r in map(json.loads, path.read_text().splitlines()) if not r.get("error")}
    with path.open("a") as out:
        for size in a.sizes:
            for it in items:
                if (it["id"], size) in done:
                    continue
                qs = {"q0": it["question"], **{f"f{i}": fill[i % len(fill)] for i in range(size - 1)}}
                t0 = time.perf_counter()
                r = server.call(a.model, cfg, {"state": it["state"], "model": "jev-latest", "questions": qs}, whole=True)
                rec = {"set": a.set, "model": a.model, "item": it["id"], "size": size, "expected": it["expected"],
                       "wall_ms": round((time.perf_counter() - t0) * 1000), "seed": a.seed}
                ans = (r.get("answers") or {}).get("q0")
                if "error" in r or not ans or p_yes(ans) is None:
                    rec["error"] = r.get("error") or "no q0 answer"
                else:
                    rec.update(p_yes=p_yes(ans), answered=len(r["answers"]), latency_ms=r["latency_ms"],
                               correct=(p_yes(ans) >= 0.5) == (it["expected"] == "yes"))
                out.write(json.dumps(rec) + "\n"); out.flush()
    recs = [json.loads(l) for l in path.read_text().splitlines()]
    print(f"{'size':>5} {'ok':>4} {'fail':>4} {'acc':>6} {'p50 ms':>7} {'answered':>8}")
    for size in a.sizes:
        rs = [r for r in recs if r["size"] == size]
        ok = [r for r in rs if not r.get("error")]
        lat = sorted(r["latency_ms"] for r in ok)
        print(f"{size:>5} {len(ok):>4} {len(rs) - len(ok):>4} {sum(r['correct'] for r in ok) / max(1, len(ok)):>6.2f} "
              f"{lat[len(lat) // 2] if lat else 0:>7} {min((r['answered'] for r in ok), default=0):>8}")


if __name__ == "__main__":
    main()
