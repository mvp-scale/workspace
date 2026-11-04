"""Wording test for hosted Jev on the same 600 clear items as the Clef test. Headline + description only (first 450 chars). Run with /workspace/kev/.venv/bin/python"""
import json, random, sys, time, urllib.request, concurrent.futures as cf, pathlib, os, threading
sys.path[:0] = ["/workspace/demo", "/workspace/knowledge_pipeline/kit/live"]
import heartbeat as hb, backends
import numpy as np
from sklearn.metrics import roc_auc_score
H0 = pathlib.Path("/workspace/knowledge_pipeline/projects/world-state"); os.chdir(H0); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
B = backends.BACKENDS["jev"]; PRICE = 0.042 / 1e6; CAP = 0.50
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; V = J("runs/clef_vote.jsonl")
Q = {"A_original": "Is the main subject of this item a change in a real-world condition, such as prices, unrest, health, weather, jobs or conflict? A passing mention does not count.",
     "B_changed": "Does this item report that something in the real world has risen, fallen, or changed?", "D_main": "Is a real-world change the main subject of this news item?", "E_specific": "Does this item name a specific thing that changed, such as a price, a count, or a rate?"}
cons = [r for r in V if r["haiku"] == r["sonnet"]]; random.Random(11).shuffle(cons)
S = [r for r in cons if r["haiku"] == 1][:300] + [r for r in cons if r["haiku"] == 0][:300]
tok = [0]; lock = threading.Lock()
def call(r):
    if tok[0] * PRICE > CAP: raise RuntimeError("cap reached")
    d = pool[r["id"]]["date"] or "2026-10-25"; body = {"state": f"News item (published {d}; today is {d}):\n{pool[r['id']]['text'][:450]}", "questions": {k: {"type": "noul", "instructions": q} for k, q in Q.items()}, **({"model": B["model"]} if B["model"] else {})}
    hdr = {"Content-Type": "application/json", "User-Agent": "jev-demo/0.1", **({"Authorization": f"Bearer {B['key']}"} if B["key"] else {})}
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(B["url"].rstrip("/") + "/v1/systemone", json.dumps(body).encode(), hdr), timeout=120) as resp: dd = json.load(resp)
            with lock: tok[0] += (dd.get("usage") or {}).get("input_tokens", 0)
            return {k: v["noul"] for k, v in dd["answers"].items()}
        except Exception as e:
            if attempt == 2: raise
            time.sleep(2)
hb.beat("jev-wording-test", where="[HOST]", task="T10", state="running", why="Is hosted Jev a better presence voter than local Clef?", success="Best wording AUC 0.80+ on clear cases", next="Score, then redo the third-vote test with Jev if good", need="Nothing", progress="600 clear items", spent=0.0, cap=CAP)
t0 = time.time()
with cf.ThreadPoolExecutor(6) as ex: P = list(ex.map(call, S))
y = np.array([r["haiku"] for r in S]); res = {"n": len(S), "seconds": round(time.time() - t0), "input_tokens": tok[0], "spend_usd": round(tok[0] * PRICE, 4)}
cols = {k: np.array([p[k] for p in P]) for k in Q}; cols["F_two_of_three(B,D,E)"] = ((cols["B_changed"] > .5).astype(int) + (cols["D_main"] > .5) + (cols["E_specific"] > .5) >= 2).astype(float) * 0.5 + np.mean([cols["B_changed"], cols["D_main"], cols["E_specific"]], axis=0) * 0.5
for k, v in cols.items(): res[k] = {"auc_vs_clear_label": round(float(roc_auc_score(y, v)), 3), "agree_at_0.5": round(float(((v > .5).astype(int) == y).mean()), 3), "yes_rate": round(float((v > .5).mean()), 3)}
json.dump({"ids": [r["id"] for r in S], "probs": {k: [round(float(x), 4) for x in v] for k, v in cols.items()}}, open(H0 / "runs/jev_wording_probs.json", "w"))
json.dump(res, open(H0 / "runs/snapshots/jev_wording.json", "w"), indent=1); print(json.dumps(res, indent=1))
hb.finish("jev-wording-test", "done", spent=res["spend_usd"], last="; ".join(f"{k[:1]} {v['auc_vs_clear_label']}" for k, v in res.items() if isinstance(v, dict)), progress="600 clear items")
