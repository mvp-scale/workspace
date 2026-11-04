"""T20 round 1a (ledger L446): raw presence and condition-chain scores for every item (encoder on all items), then the cut frontier offline. Local, CPU. Output runs/pulse/raw_<set>.npz style json and runs/pulse/reach_frontier.json
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python reach_curve.py v5-leaf"""
import json, glob, re, sys, math, numpy as np, scipy.sparse as sp, pickle
sys.path.insert(0, "."); from expert1_runtime import Expert3, _lg
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; LV = ["minor", "notable", "major", "severe", "extreme"]
ver = sys.argv[1]; reg = {r["version"]: r for r in json.load(open("engine_versions.json"))}[ver]; e = Expert3(reg["path"]); M = e.M; Hc = e.H["cond"]
def raw(text):
    t = re.sub(r"\s+", " ", text); xwc = sp.hstack([M["vw"].transform([t]), M["vc"].transform([t])]).tocsr()
    pph = float(M["ph"].predict_proba(xwc)[:, 1][0]); pps = float(M["ps"].predict_proba(xwc)[:, 1][0]); v = e.embed(text)
    xc = xwc[:, M["keepc"]]; P = e._soft(np.asarray(xc @ Hc["W"]).ravel() + v @ Hc["V"] + Hc["b"]); c2 = np.argsort(-P)[:2]; top = Hc["classes"][c2[0]]
    xd = sp.hstack([xc, sp.csr_matrix(([2.0], ([0], [e.cond_idx[top]])), shape=(1, len(e.cond_idx)))]).tocsr()
    return {"ph": pph, "ps": pps, "top1": str(top), "top2": str(Hc["classes"][c2[1]]), "cconf": float(P.max()), "dir": str(M["dirm"].predict(xd)[0]), "size": M["LV"][int(M["sizem"].predict(xd)[0])]}
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; out = {}
for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r
sn = {r["item_id"]: r["label"] for r in J("runs/pulse/devq/labels.jsonl")}; ids = sorted(i for i in sn if i in pool); out["devq"] = [{"id": i, **raw(pool[i]["text"]), "S": sn[i]} for i in ids]; print("devq", len(ids), flush=True)
hk = {}; old = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
    for r in J(f): hk[r["item_id"]] = r["label"]
sno = {}
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sno[r["item_id"]] = r["label"]
oi = sorted(hk); dt = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dt, kind="stable"); o = o[dt[o] != ""]; test = [oi[k] for k in np.array_split(o, 5)[4]]; vt = [i for i in test if i in sno]
hn_t = sum(1 for i in test if not hk[i]["conditions"]); hn_v = sum(1 for i in vt if not hk[i]["conditions"]); hp_t = len(test) - hn_t; hp_v = len(vt) - hn_v
out["old"] = [{"id": i, **raw(pool[i]["text"]), "S": sno[i], "w": (hp_t / hp_v if hk[i]["conditions"] else hn_t / hn_v)} for i in vt]; print("old", len(vt), flush=True)
json.dump(out, open(f"runs/pulse/raw_{ver}.json", "w"))
