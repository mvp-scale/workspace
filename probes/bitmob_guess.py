"""How good are BitMob's untrained guesses? Measured through the live endpoint (127.0.0.1:8020), so it is exactly what is served.

Items   every item of the 15 published sets in probes/v2/ (none of their questions is trained in BitMob, so every answer is a
        guess) and 20 questions per MMLU subject (1,140, seeded), sent as TypeSafe requests (state + the set's question).
Report  per question type: accuracy of the guess vs chance, per set; and the scale that turns closeness into probabilities,
        fitted on half the items (log-loss) and checked on the other half (the live default, BITMOB_GUESS_SCALE, is set from this fit: 10).
Writes  data/bitmob/live/guess_accuracy.json, which the engine quotes next to every untrained guess.
Run: models/embed-zs/.venv/bin/python probes/bitmob_guess.py   (BitMob must be running: ./service.sh start classifier)
"""
import json, random, pathlib, urllib.request, collections
from concurrent.futures import ThreadPoolExecutor
import numpy as np

V2 = pathlib.Path("/workspace/probes/v2"); OUT = pathlib.Path("/workspace/data/bitmob/live/guess_accuracy.json"); SEED = 20261016


def ask(item):
    q = item["question"]; body = json.dumps({"state": item["state"], "questions": {"q": q}}).encode()
    r = json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8020/v1/systemone", body, {"Content-Type": "application/json"}), timeout=60))
    t = r["engine"]["trace"]["q"]; assert t["basis"] == "untrained guess", (item["id"], t["basis"])
    return t["cosines"]


def label_of(item, labels_out):
    """The expected answer as one of the engine's option labels (noul -> no/yes; choice -> key; MMLU -> A-D)."""
    e = item["expected"]
    return {"yes": "yes", "no": "no"}.get(e, e) if item["question"]["type"] == "noul" else e


def main():
    rng = random.Random(SEED); items = []
    for f in sorted(V2.glob("*.jsonl")):
        rows = [json.loads(l) for l in open(f)]
        if f.stem.startswith("mmlu_"): rng.shuffle(rows); rows = rows[:20]
        for r in rows: r["_set"] = "mmlu" if f.stem.startswith("mmlu_") else f.stem; items.append(r)
    with ThreadPoolExecutor(4) as ex: cos = list(ex.map(ask, items))
    rows = []
    for it, c in zip(items, cos):
        labs = list(c); y = labs.index(label_of(it, labs)); rows.append((it["_set"], it["question"]["type"], np.array(list(c.values())), y))
    # scale: fit on half, check on the other half
    half = np.array([rng.random() < 0.5 for _ in rows])
    def nll(s, m):
        t = 0.0
        for (st, ty, c, y), k in zip(rows, m):
            if not k: continue
            z = c * s; z = z - z.max(); t -= z[y] - np.log(np.exp(z).sum())
        return t / m.sum()
    grid = [1, 2, 5, 10, 20, 30, 50, 75, 100, 150, 200, 300]; best = min(grid, key=lambda s: nll(s, half))
    res = {"note": "untrained guesses through the live endpoint: closeness of the text to each option (e5-small), no training on these questions",
           "scale": {"fitted_on_half": best, "held_out_log_loss": {str(s): round(nll(s, ~half), 4) for s in (best, 50)}}}
    for ty in ("noul", "choice"):
        rs = [r for r in rows if r[1] == ty]; ok = [int(np.argmax(c) == y) for _, _, c, y in rs]
        chance = float(np.mean([1 / len(c) for _, _, c, _ in rs]))
        per = collections.defaultdict(list)
        for (st, _, c, y), o in zip(rs, ok): per[st].append(o)
        res[ty] = {"accuracy": round(float(np.mean(ok)), 3), "chance": round(chance, 3), "n": len(rs),
                   "per_set": {st: round(float(np.mean(v)), 3) for st, v in sorted(per.items())},
                   "summary": f"untrained guesses were right {np.mean(ok):.0%} of the time on {len(rs)} labelled {ty} questions (chance {chance:.0%})"}
        print(res[ty]["summary"]); print("   " + ", ".join(f"{k} {v:.0%}" for k, v in res[ty]["per_set"].items()))
    res["score"] = {"accuracy": None, "summary": "not measured: we have no labelled score sets yet"}
    print(f"scale fitted on half: {best} (held-out log-loss {res['scale']['held_out_log_loss']})")
    OUT.write_text(json.dumps(res, indent=1)); print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
