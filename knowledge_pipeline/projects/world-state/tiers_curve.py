"""T20: reach-versus-precision curve for the presence call (the owner's 'condition tiers' question) for two engine versions on the clean holdout DEVQ2 (1,593 natural items, 166 real conditions). Precision = share of 'yes' calls that are real conditions; recall = share of real conditions found. Bootstrap 400. CPU, local. Registers heartbeat t20-tiers.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python tiers_curve.py v5-leaf v6b-student"""
import json, sys, os, numpy as np
sys.path.insert(0, "."); sys.path.insert(0, "../../kit/live"); import heartbeat as hb
from expert1_runtime import Expert3, ExpertS
hb.beat("t20-tiers", pid=os.getpid(), where="[CPU]", task="T20", state="running", progress="presence reach-versus-precision curve on the holdout", why="Owner's condition-tiers decision should be read from a curve, not two guesses (ledger plan step 1).", success="Table of precision targets vs real conditions found, both versions, with intervals", next="Put the table on the page / in the morning summary", need="Nothing", cap=3600)
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; reg = {r["version"]: r for r in json.load(open("engine_versions.json"))}; cls = {"Expert3": Expert3, "ExpertS": ExpertS}
pool = {r["id"]: r["text"] for r in J("runs/pulse/more/devq2_items.jsonl")}; S = {r["item_id"]: r["label"] for r in J("runs/pulse/more/devq2/labels.jsonl")}; ids = sorted(i for i in S if i in pool); y = np.array([bool(S[i]["conditions"]) for i in ids]); out = {"n": len(ids), "real": int(y.sum()), "versions": {}}
def probs(v):
    e = cls[reg[v]["class"]](reg[v]["path"]); P = []
    for i in ids:
        c = e.read(pool[i])["condition_present"]; P.append(c["probability"] if "probability" in c else (c["confidence"] if c["answer"] else 1 - c["confidence"]))
    return np.array(P)
def at(p, yy, prec):
    o = np.argsort(-p); tp = np.cumsum(yy[o]); n = np.arange(1, len(o) + 1); ok = np.where(tp / n >= prec)[0]
    return (float(tp[ok.max()] / yy.sum()), int(ok.max() + 1)) if len(ok) else (0.0, 0)
rng = np.random.RandomState(0)
for v in sys.argv[1:]:
    p = probs(v); r = {}
    for prec in (0.95, 0.90, 0.83, 0.75, 0.60):
        rec, k = at(p, y, prec); bs = [at(p[ix], y[ix], prec)[0] for ix in (rng.randint(0, len(y), len(y)) for _ in range(400))]
        r[str(prec)] = {"found_share": round(rec, 3), "ci95": [round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)], "yes_calls_per_1000_items": round(1000 * k / len(y), 1)}
    out["versions"][v] = r; print(v, json.dumps(r), flush=True)
json.dump(out, open("runs/pulse/tiers_curve.json", "w"), indent=1); hb.finish("t20-tiers", "done", last="curve written: runs/pulse/tiers_curve.json")
