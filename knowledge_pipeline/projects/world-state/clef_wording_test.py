"""Wording test for Clef (port 8018, /v1/systemone) on clear cases (Haiku == Sonnet). Run with /workspace/models/embed-zs/.venv/bin/python"""
import json, random, sys, time, urllib.request, concurrent.futures as cf, pathlib, os
sys.path.insert(0, "../../kit/live"); import heartbeat as hb
import numpy as np
from sklearn.metrics import roc_auc_score
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; V = J("runs/clef_vote.jsonl")
Q = {"A_original": "Is the main subject of this item a change in a real-world condition, such as prices, unrest, health, weather, jobs or conflict? A passing mention does not count.",
     "B_changed": "Does this item report that something in the real world has risen, fallen, or changed?",
     "D_main": "Is a real-world change the main subject of this news item?",
     "E_specific": "Does this item name a specific thing that changed, such as a price, a count, or a rate?"}
assert all(len(v) <= 170 for v in Q.values())
cons = [r for r in V if r["haiku"] == r["sonnet"]]; random.Random(11).shuffle(cons)
pos = [r for r in cons if r["haiku"] == 1][:300]; neg = [r for r in cons if r["haiku"] == 0][:300]; S = pos + neg
def call(r, qs):
    d = pool[r["id"]]["date"] or "2026-10-25"; body = {"state": f"News item (published {d}; today is {d}):\n{pool[r['id']]['text'][:700]}", "questions": {k: {"type": "noul", "instructions": q} for k, q in qs.items()}, "model": "clef-flash-q4km"}
    a = json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8018/v1/systemone", json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=600))["answers"]
    return {k: v["noul"] for k, v in a.items()}
hb.beat("clef-wording-test", where="[5090]", task="T10", state="running", why="Was the Clef question worded wrong? Test narrow wordings on clear cases", success="A narrow wording reaches AUC 0.80+ on clear cases", next="Score; redo the third-vote test if good", need="Nothing", progress="4 wordings x 600 clear items", spent=0.0, cap=0.0)
t0 = time.time()
with cf.ThreadPoolExecutor(6) as ex: P = list(ex.map(lambda r: call(r, Q), S))
y = np.array([r["haiku"] for r in S]); res = {"n_clear_items": len(S), "seconds": round(time.time() - t0)}
cols = {k: np.array([p[k] for p in P]) for k in Q}; cols["F_two_of_three(B,D,E)"] = ((cols["B_changed"] > .5).astype(int) + (cols["D_main"] > .5) + (cols["E_specific"] > .5) >= 2).astype(float) * 0.5 + np.mean([cols["B_changed"], cols["D_main"], cols["E_specific"]], axis=0) * 0.5
for k, v in cols.items(): res[k] = {"auc_vs_clear_label": round(float(roc_auc_score(y, v)), 3), "agree_at_0.5": round(float(((v > .5).astype(int) == y).mean()), 3), "yes_rate": round(float((v > .5).mean()), 3)}
# engine screen (C) on 120 of the same items
sys.path[:0] = ["/workspace/probes/world-engine"]; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ.setdefault("WORLD_GPU", "0")
import classify as C
SCR = {f"s2|{d}|{dr}": "Does the story report any of these: " + "; ".join(f"{x['attribute']} ({x['definition'].strip().rstrip('.')})" for x in C.ATTRS[(d, dr)]) + "?" for (d, dr) in C.ATTRS}
S2 = S[:60] + S[300:360]; t1 = time.time()
with cf.ThreadPoolExecutor(3) as ex: P2 = list(ex.map(lambda r: call(r, SCR), S2))
y2 = np.array([r["haiku"] for r in S2]); mx = np.array([max(p.values()) for p in P2])
res["C_engine_screen_120_items"] = {"auc_vs_clear_label": round(float(roc_auc_score(y2, mx)), 3), "agree_at_0.20": round(float(((mx >= 0.20).astype(int) == y2).mean()), 3), "agree_at_0.5": round(float(((mx >= 0.5).astype(int) == y2).mean()), 3), "seconds": round(time.time() - t1)}
res["A_on_same_120"] = round(float(roc_auc_score(y2, np.array([p["A_original"] for p in P])[[S.index(r) for r in S2]])), 3)
json.dump(res, open(H0 / "runs/snapshots/clef_wording.json", "w"), indent=1); print(json.dumps(res, indent=1))
hb.finish("clef-wording-test", "done", last="; ".join(f"{k[:1]} {v['auc_vs_clear_label']}" for k, v in res.items() if isinstance(v, dict) and 'auc_vs_clear_label' in v), progress="600 clear items")
