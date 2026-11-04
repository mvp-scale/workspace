"""Independent recomputation for the T10 review: load only the saved artefact, read the 1,466 voted later items from raw text, recompute agreement with Sonnet. Does not import build_expert.py."""
import json, glob, re, pickle, pathlib, numpy as np, scipy.sparse as sp, warnings
warnings.filterwarnings("ignore")
from model2vec import StaticModel
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
art = pickle.load(open(H0 / "runs/expert1/expert1_v1.pkl", "rb")); sm = StaticModel.from_pretrained(art["static"])
old = {}; sn = {}
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): old[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): sn[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J(H0 / "data/pool_train.jsonl")}; oi = sorted(old); dt = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dt, kind="stable"); o = o[dt[o] != ""]
test = [oi[k] for k in np.array_split(o, 5)[4]]; vt = [i for i in test if i in sn]
txt = [re.sub(r"\s+", " ", pool[i]["text"]) for i in vt]; head = [re.split(r"(?<=[.!?])\s", t, 1)[0] for t in txt]
E = np.hstack([sm.encode(txt), sm.encode(head)]); lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
xwc = sp.hstack([art["vw"].transform(txt), art["vc"].transform(txt)]).tocsr(); xt = sp.hstack([art["vt"].transform(txt), sp.csr_matrix(art["ss"].transform(E) * 0.1)]).tocsr()
ps = art["story"].predict_proba(xwc); pt = art["topic"].predict_proba(xt); pr = 1 / (1 + np.exp(-(lg(art["ph"].predict_proba(xwc)[:, 1]) + lg(art["ps"].predict_proba(xwc)[:, 1])) / 2))
ys = np.array([sn[i]["story_type"] for i in vt]); yt = np.array([sn[i]["topic"] for i in vt]); yp = np.array([1 if sn[i]["conditions"] else 0 for i in vt])
t2 = np.argsort(-pt, 1)[:, :2]; c = art["topic"].classes_
out = {"n": len(vt), "story_forced": round(float((art["story"].classes_[ps.argmax(1)] == ys).mean()), 3), "topic_top2_forced": round(float(np.mean([yt[i] in set(c[t2[i]]) for i in range(len(vt))])), 3), "presence_forced": round(float(((pr > .5).astype(int) == yp).mean()), 3)}
cp_ = np.maximum(pr, 1 - pr); a = cp_ >= art["cuts"]["condition_present"]; out["presence_answered_share"] = round(float(a.mean()), 3); out["presence_agree_on_answered"] = round(float(((pr > .5).astype(int) == yp)[a].mean()), 3)
a2 = np.sort(pt, 1)[:, -2:].sum(1) >= art["cuts"]["topic_top2"]; out["topic_answered_share"] = round(float(a2.mean()), 3)
print(json.dumps(out)); json.dump(out, open(H0 / "runs/expert1/verify_recompute.json", "w"), indent=1)
