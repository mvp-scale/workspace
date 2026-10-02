"""Layers of evidence: does combining several different questions about one image beat a single question?

    /workspace/kev/.venv/bin/python layers.py run [task_id ...]     # ask the battery, store every probability
    /workspace/kev/.venv/bin/python layers.py report                # compare single question vs layered answers

Everything combined here is computable WITHOUT knowing the right answer, so it could run in production:
  yes/no tasks  five wordings of the same fact (the opposite wording is flipped back before combining)
  pick-one      the original question, the options reversed, and a yes/no check of EVERY option ("is the answer X?")
Combination is a plain average of probabilities. Nothing is fitted, so 25 images cannot overfit it.
(consistency.py asks about the true option on purpose, to test understanding; this file never does.)

Stored per item in /workspace/data/image-lab/runs/winnow-layers/<task>.jsonl:
  yes/no   {"id", "kind": "yn", "p": {angle: P(yes)}, "expected"}
  pick-one {"id", "kind": "pick", "base": {label: p}, "rev": {label: p}, "verify": {label: P(yes)}, "expected"}
"""
import json, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from run_winnow import data_url
from consistency import wordings

HERE = Path(__file__).parent
OUT = Path("/workspace/data/image-lab/runs/winnow-layers")
ENDPOINT, MODEL = "http://127.0.0.1:8091", "Winnow-12B"


def post(item, imgs, q):
    body = {"model": MODEL, "state": item["state"], "winnow": {"images": imgs}, "questions": {"q": q}}
    req = urllib.request.Request(ENDPOINT + "/v1/systemone", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)["answers"]["q"]


def p_yes(a):
    return float(a["noul"])


def probs(a):
    return {k: float(v) for k, v in a["probabilities"].items()}


def ask(item):
    imgs = [data_url(p) for p in item["images"]]
    q, crit = item["question"]["instructions"], item["question"].get("criteria") or {}
    if item["question"]["type"] == "noul":
        opp, para = wordings(q)
        flipped = {"true": crit.get("false", ""), "false": crit.get("true", "")} if crit else None
        mk = lambda text, c: {"type": "noul", "instructions": text, **({"criteria": c} if c else {})}
        pick = lambda order: {"type": "choice", "instructions": q, "criteria": {k: None for k in order}}
        p = {"base": p_yes(post(item, imgs, item["question"])), "opposite": p_yes(post(item, imgs, mk(opp, flipped))), "paraphrase": p_yes(post(item, imgs, mk(para, crit or None)))}
        p["pick yes,no"] = probs(post(item, imgs, pick(["yes", "no"])))["yes"]
        p["pick no,yes"] = probs(post(item, imgs, pick(["no", "yes"])))["yes"]
        return {"id": item["id"], "kind": "yn", "p": p, "expected": item["expected"]}
    labels = item["labels"]
    base = probs(post(item, imgs, item["question"]))
    rev = probs(post(item, imgs, {"type": "choice", "instructions": q, "criteria": {l: crit[l] for l in reversed(labels)}}))
    verify = {l: p_yes(post(item, imgs, {"type": "noul", "instructions": f'{q} Is the answer "{l}"?'})) for l in labels}
    return {"id": item["id"], "kind": "pick", "base": base, "rev": rev, "verify": verify, "expected": item["expected"]}


def run(tasks):
    OUT.mkdir(parents=True, exist_ok=True)
    for f in ([HERE / f"{t}.jsonl" for t in tasks] if tasks else sorted(HERE.glob("t[0-9][0-9]_*.jsonl"))):
        if (OUT / f"{f.stem}.jsonl").exists() and "--force" not in sys.argv:
            print(f"{f.stem}: exists, skipped", flush=True); continue
        items = [json.loads(l) for l in f.read_text().split("\n") if l.strip()]
        t0 = time.time()

        def safe(it):
            try:
                return ask(it)
            except Exception as e:  # recorded, never scored as wrong
                return {"id": it["id"], "error": f"{type(e).__name__}: {e}"[:200]}
        with ThreadPoolExecutor(4) as ex:
            rows = list(ex.map(safe, items))
        (OUT / f"{f.stem}.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        print(f"{f.stem}: {time.time() - t0:.0f}s", flush=True)


# ---- combination ----
def norm(d):
    s = sum(d.values()) or 1.0
    return {k: v / s for k, v in d.items()}


def answers(r):
    """{method: (predicted label, confidence)} for one stored item."""
    out = {}
    if r["kind"] == "yn":
        p = r["p"]
        out["single"] = ("yes" if p["base"] >= .5 else "no", max(p["base"], 1 - p["base"]))
        aligned = [p["base"], 1 - p["opposite"], p["paraphrase"], p["pick yes,no"], p["pick no,yes"]]
        m = sum(aligned) / len(aligned)
        out["layered"] = ("yes" if m >= .5 else "no", max(m, 1 - m))
        return out
    b, rv, v = r["base"], r["rev"], norm(r["verify"])
    top = lambda d: max(d, key=d.get)
    out["single"] = (top(b), b[top(b)])
    two = {k: (b[k] + rv[k]) / 2 for k in b}
    out["reorder"] = (top(two), two[top(two)])
    out["verify only"] = (top(v), v[top(v)])
    allm = {k: (b[k] + rv[k] + v[k]) / 3 for k in b}
    out["layered"] = (top(allm), allm[top(allm)])
    return out


def handled(rows, method, bar=0.95):
    """Share of images handled (most confident first) while precision on the handled set stays at or above the bar."""
    s = sorted(((answers(r)[method][1], answers(r)[method][0] == r["expected"]) for r in rows), key=lambda x: -x[0])
    best = 0
    for k in range(1, len(s) + 1):
        if sum(c for _, c in s[:k]) / k >= bar:
            best = k
    return best / len(s)


def false_pos(rows, method, conf_bar=0.90):
    """yes/no tasks: answered yes when the truth is no. Pick-one tasks: confident wrong answers (confidence at or above the bar)."""
    n = 0
    for r in rows:
        pred, conf = answers(r)[method]
        n += (pred == "yes" and r["expected"] == "no") if r["kind"] == "yn" else (pred != r["expected"] and conf >= conf_bar)
    return n


def report():
    tot = {"single": 0, "layered": 0}; h = {"single": 0, "layered": 0}; fps = {"single": 0, "layered": 0}; better = worse = same = 0; n = 0
    lines, data = [], []
    head = f"{'task':28s} {'single':>7s} {'layered':>8s} {'change':>7s}  {'handled@95%':>16s}  {'false pos / confident errors':>30s}"
    lines.append(head)
    for f in sorted(OUT.glob("t*.jsonl")):
        rows = [r for r in map(json.loads, f.read_text().split("\n")[:-1]) if "kind" in r]
        if not rows: continue
        meths = list(answers(rows[0]))
        acc = {m: sum(answers(r)[m][0] == r["expected"] for r in rows) for m in meths}
        a, b = acc["single"], acc["layered"]
        hs, hl = handled(rows, "single"), handled(rows, "layered")
        fs, fl = false_pos(rows, "single"), false_pos(rows, "layered")
        better += b > a; worse += b < a; same += b == a; n += 1
        for k, x in (("single", a / len(rows)), ("layered", b / len(rows))): tot[k] += x
        h["single"] += hs; h["layered"] += hl; fps["single"] += fs; fps["layered"] += fl
        kind = "yes/no" if rows[0]["kind"] == "yn" else "pick-one"
        lines.append(f"{f.stem:28s} {a:>4d}/{len(rows)} {b:>5d}/{len(rows)} {b - a:>+7d}  {hs * 100:>6.0f}% -> {hl * 100:>3.0f}%  {fs:>12d} -> {fl:<3d} ({kind})")
        data.append({"task": f.stem, "kind": kind, "n": len(rows), "single_correct": a, "layered_correct": b, "handled95_single": round(hs, 3), "handled95_layered": round(hl, 3), "false_pos_single": fs, "false_pos_layered": fl, "by_method": acc})
    summ = {"tasks": n, "mean_acc_single": round(tot["single"] / n, 4), "mean_acc_layered": round(tot["layered"] / n, 4), "layered_better": better, "layered_worse": worse, "equal": same,
            "mean_handled95_single": round(h["single"] / n, 4), "mean_handled95_layered": round(h["layered"] / n, 4), "false_pos_single": fps["single"], "false_pos_layered": fps["layered"]}
    lines.append(f"\n{n} tasks. Mean accuracy single {tot['single'] / n * 100:.1f}% -> layered {tot['layered'] / n * 100:.1f}%. Layered better on {better}, worse on {worse}, equal on {same}.")
    lines.append(f"Mean share handled at 95% precision: single {h['single'] / n * 100:.1f}% -> layered {h['layered'] / n * 100:.1f}%.")
    lines.append(f"False positives (yes/no) plus confident errors (pick-one, confidence >= 90%): single {fps['single']} -> layered {fps['layered']}.")
    print("\n".join(lines))
    if "--save" in sys.argv:
        snap = Path("/workspace/data/image-lab/snapshots"); snap.mkdir(parents=True, exist_ok=True)
        (snap / "after-layers.json").write_text(json.dumps({"summary": summ, "tasks": data}, indent=1))
        (HERE / "LAYERS-RESULTS.md").write_text("# Layers of evidence: single question vs layered\n\nGenerated by `layers.py report --save`. Before = the single original question (the main Winnow run); after = the average of several wordings, reordered options and a yes/no check of every option. No weights were fitted.\n\n```\n" + "\n".join(lines) + "\n```\n")
        print("saved snapshots/after-layers.json and LAYERS-RESULTS.md")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    args = [a for a in sys.argv[2:] if not a.startswith("--")]
    run(args) if cmd == "run" else report()
