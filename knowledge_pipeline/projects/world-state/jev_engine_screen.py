import json, sys, time, urllib.request, concurrent.futures as cf, pathlib, os, threading
sys.path[:0] = ["/workspace/demo", "/workspace/knowledge_pipeline/kit/live", "/workspace/probes/world-engine"]
os.environ.setdefault("WE_RULES", "rules_v2"); os.environ.setdefault("WORLD_GPU", "0")
import heartbeat as hb, backends, classify as C, numpy as np
from sklearn.metrics import roc_auc_score
H0 = pathlib.Path("/workspace/knowledge_pipeline/projects/world-state"); os.chdir(H0); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
B = backends.BACKENDS["jev"]; PRICE = 0.042 / 1e6; CAP = 0.30
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; V = {r["id"]: r for r in J("runs/clef_vote.jsonl")}; ids = json.load(open("runs/jev_wording_probs.json"))["ids"]
SCR = {f"s2|{d}|{dr}": "Does the story report any of these: " + "; ".join(f"{x['attribute']} ({x['definition'].strip().rstrip('.')})" for x in C.ATTRS[(d, dr)]) + "?" for (d, dr) in C.ATTRS}
tok = [0]; lock = threading.Lock()
def call(i):
    if tok[0] * PRICE > CAP: raise RuntimeError("cap")
    d = pool[i]["date"] or "2026-10-25"; body = {"state": f"News item (published {d}; today is {d}):\\n{pool[i]['text'][:450]}", "questions": {k: {"type": "noul", "instructions": q} for k, q in SCR.items()}, **({"model": B["model"]} if B["model"] else {})}
    hdr = {"Content-Type": "application/json", "User-Agent": "jev-demo/0.1", **({"Authorization": f"Bearer {B['key']}"} if B["key"] else {})}
    for a in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(B["url"].rstrip("/") + "/v1/systemone", json.dumps(body).encode(), hdr), timeout=300) as resp: dd = json.load(resp)
            with lock: tok[0] += (dd.get("usage") or {}).get("input_tokens", 0)
            return {k: v["noul"] for k, v in dd["answers"].items()}
        except Exception:
            if a == 2: raise
            time.sleep(3)
hb.beat("jev-engine-screen", where="[HOST]", task="T10", state="running", why="Is Jev a strong voter when asked the engine's own condition screens?", success="AUC 0.88+ on clear cases", next="Standing third voter if yes", need="Nothing", progress="600 clear items x 78 screens", spent=0.0, cap=CAP)
t0 = time.time()
with cf.ThreadPoolExecutor(6) as ex: P = list(ex.map(call, ids))
y = np.array([V[i]["haiku"] for i in ids]); mx = np.array([max(p.values()) for p in P]); n20 = np.array([sum(v >= 0.2 for v in p.values()) for p in P]); mean = np.array([np.mean(list(p.values())) for p in P])
res = {"n": len(ids), "seconds": round(time.time() - t0), "input_tokens": tok[0], "spend_usd": round(tok[0] * PRICE, 4), "auc_max_flag": round(float(roc_auc_score(y, mx)), 3), "auc_count_flags_at_0.2": round(float(roc_auc_score(y, n20)), 3), "auc_mean_flag": round(float(roc_auc_score(y, mean)), 3)}
for t in (0.2, 0.5, 0.8): res[f"agree_max_flag_at_{t}"] = round(float(((mx >= t).astype(int) == y).mean()), 3)
json.dump({"ids": ids, "flags": [{k: round(float(v), 4) for k, v in p.items()} for p in P]}, open(H0 / "runs/jev_engine_screen_600.json", "w")); json.dump(res, open(H0 / "runs/snapshots/jev_engine_screen.json", "w"), indent=1); print(json.dumps(res, indent=1))
hb.finish("jev-engine-screen", "done", spent=res["spend_usd"], last=f"AUC max flag {res['auc_max_flag']}", progress="600 clear items")
