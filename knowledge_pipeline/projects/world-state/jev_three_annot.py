import json, random, sys, time, urllib.request, concurrent.futures as cf, pathlib, os, threading
sys.path[:0] = ["/workspace/demo", "/workspace/knowledge_pipeline/kit/live"]
import heartbeat as hb, backends, numpy as np
H0 = pathlib.Path("/workspace/knowledge_pipeline/projects/world-state"); os.chdir(H0); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
B = backends.BACKENDS["jev"]; PRICE = 0.042 / 1e6; CAP = 0.25
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; V = J("runs/clef_vote.jsonl"); random.Random(5).shuffle(V); S = V[:1500]
Qa = "Is the main subject of this item a change in a real-world condition, such as prices, unrest, health, weather, jobs or conflict? A passing mention does not count."
tok = [0]; lock = threading.Lock()
def call(r):
    if tok[0] * PRICE > CAP: raise RuntimeError("cap")
    d = pool[r["id"]]["date"] or "2026-10-25"; body = {"state": f"News item (published {d}; today is {d}):\\n{pool[r['id']]['text'][:450]}", "questions": {"q": {"type": "noul", "instructions": Qa}}, **({"model": B["model"]} if B["model"] else {})}
    hdr = {"Content-Type": "application/json", "User-Agent": "jev-demo/0.1", **({"Authorization": f"Bearer {B['key']}"} if B["key"] else {})}
    for a in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(B["url"].rstrip("/") + "/v1/systemone", json.dumps(body).encode(), hdr), timeout=120) as resp: dd = json.load(resp)
            with lock: tok[0] += (dd.get("usage") or {}).get("input_tokens", 0)
            return dd["answers"]["q"]["noul"]
        except Exception:
            if a == 2: raise
            time.sleep(2)
hb.beat("jev-three-annotators", where="[HOST]", task="T10", state="running", why="Estimate who is right between Haiku, Sonnet and Jev from their agreements", success="Per-voter accuracy estimates with intervals", next="Use the weights for training labels", need="Nothing", progress="1,500 items", spent=0.0, cap=CAP)
with cf.ThreadPoolExecutor(6) as ex: pj = np.array(list(ex.map(call, S)))
h = np.array([r["haiku"] for r in S]); s = np.array([r["sonnet"] for r in S]); pc = np.array([r["raw"]["noul"] for r in S])
def to_bin(p, rate): t = np.quantile(p, 1 - rate); return (p >= t).astype(int)
rate = (h.mean() + s.mean()) / 2; j = to_bin(pj, rate); c = to_bin(pc, rate)
def acc3(a, b, d):
    x = lambda u, v: 2 * (u == v).mean() - 1
    ab, ad, bd = x(a, b), x(a, d), x(b, d)
    if min(ab, ad, bd) <= 0: return None
    return [float((1 + np.sqrt(ab * ad / bd)) / 2), float((1 + np.sqrt(ab * bd / ad)) / 2), float((1 + np.sqrt(ad * bd / ab)) / 2)]
def boot(a, b, d, n=1000):
    rng = np.random.RandomState(0); out = []
    for _ in range(n):
        i = rng.randint(0, len(a), len(a)); r = acc3(a[i], b[i], d[i])
        if r: out.append(r)
    out = np.array(out); return [[round(float(np.percentile(out[:, k], 2.5)), 3), round(float(np.percentile(out[:, k], 97.5)), 3)] for k in range(3)]
res = {"n": len(S), "spend_usd": round(tok[0] * PRICE, 4), "positive_rate_H_S_Jev_Clef": [round(float(v.mean()), 3) for v in (h, s, j, c)],
       "pairwise_agreement": {"H-S": round(float((h == s).mean()), 3), "H-J": round(float((h == j).mean()), 3), "S-J": round(float((s == j).mean()), 3), "H-C": round(float((h == c).mean()), 3), "S-C": round(float((s == c).mean()), 3), "J-C": round(float((j == c).mean()), 3)}}
a = acc3(h, s, j); res["H_S_Jev_estimated_accuracy"] = {k: round(v, 3) for k, v in zip(("Haiku", "Sonnet", "Jev"), a)} if a else None; res["H_S_Jev_95ci"] = dict(zip(("Haiku", "Sonnet", "Jev"), boot(h, s, j)))
a = acc3(h, s, c); res["H_S_Clef_estimated_accuracy"] = {k: round(v, 3) for k, v in zip(("Haiku", "Sonnet", "Clef"), a)} if a else None; res["H_S_Clef_95ci"] = dict(zip(("Haiku", "Sonnet", "Clef"), boot(h, s, c)))
a = acc3(h, j, c); res["H_Jev_Clef_estimated_accuracy"] = {k: round(v, 3) for k, v in zip(("Haiku", "Jev", "Clef"), a)} if a else None
json.dump(res, open(H0 / "runs/snapshots/three_annot.json", "w"), indent=1); json.dump({"ids": [r["id"] for r in S], "jev": [round(float(x), 4) for x in pj]}, open(H0 / "runs/jev_vote_1500.json", "w")); print(json.dumps(res, indent=1))
hb.finish("jev-three-annotators", "done", spent=res["spend_usd"], last=str(res["H_S_Jev_estimated_accuracy"]), progress="1,500 items")
