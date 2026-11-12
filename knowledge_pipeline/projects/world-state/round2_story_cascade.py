"""Round 2: sparse story-type head (TF-IDF + SGD log loss, Sonnet story_type labels only) answering the surest half, BitMob v6b answering the rest. Judge: agreement with Sonnet on the sealed set (1,499 items, runs/pulse/sealed/labels.jsonl), NOT human truth. Sealed ids are excluded from all training. Also the joint skip with the Round 1 sparse topic head (top-two mass >= median).
    /workspace/models/embed-zs/.venv/bin/python -u round2_story_cascade.py   (from projects/world-state)"""
import json, glob, sys, math, time, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
sys.path.insert(0, "."); from expert1_runtime import ExpertS
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")})
for f in glob.glob("runs/**/items*.jsonl", recursive=True):
    try:
        for r in J(f):
            if r.get("id") and r.get("text"): txt.setdefault(r["id"], r["text"])
    except Exception: pass
S = {r["item_id"]: r["label"] for r in J("runs/pulse/sealed/labels.jsonl")}; sealed = set(S); ids = sorted(i for i in S if i in txt); print("sealed", len(ids), flush=True)
RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}; bt = {}; bs = {}
for r in J("runs/label_store/labels.jsonl"):
    i = r["item_id"]
    if r["family"] != "sonnet" or i not in txt or i in sealed: continue
    rk = RANK.get(r["version"], 2)
    if r.get("topic") and (i not in bt or rk < bt[i][0]): bt[i] = (rk, r["topic"])
    if r.get("story_type") and (i not in bs or rk < bs[i][0]): bs[i] = (rk, r["story_type"])
def fit(best):
    tr = sorted(best); y = np.array([best[i][1] for i in tr]); v = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=150000, sublinear_tf=True); A = v.fit_transform([txt[i] for i in tr])
    t0 = time.time(); m = SGDClassifier(loss="log_loss", alpha=2e-6, max_iter=12, tol=None, n_jobs=6, random_state=7).fit(A, y); print("fit", len(tr), round(time.time() - t0), "s", flush=True); return v, m, len(tr)
X = [txt[i] for i in ids]
vs, ms, ns = fit(bs); Ps = ms.predict_proba(vs.transform(X)); cs = np.array(ms.classes_); ps = cs[Ps.argmax(1)]; cs_conf = Ps.max(1)
vt, mt, nt = fit(bt); Pt = mt.predict_proba(vt.transform(X)); ct = np.array(mt.classes_); o = np.argsort(-Pt, 1)[:, :2]; mass = Pt[np.arange(len(Pt))[:, None], o].sum(1)
sst = np.array([S[i]["story_type"] for i in ids]); stop = np.array([S[i]["topic"] for i in ids])
sp_s = ps == sst; sp_t = np.array([stop[k] in ct[o[k]] for k in range(len(ids))])
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); R = [e.read(x) for x in X]
vb_s = np.array([r["story_type"]["status"] == "answered" and r["story_type"]["answer"] == sst[k] for k, r in enumerate(R)])
vb_t = np.array([stop[k] in (r["topic_top2"]["answer"] or []) and r["topic_top2"]["status"] == "answered" for k, r in enumerate(R)])
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [round(c - h, 3), round(c + h, 3)]
n = len(ids); f = lambda a: {"rate": round(float(a.mean()), 4), "ci95": wil(int(a.sum()), n)}
res = {"judge": "agreement with Sonnet on sealed set, not human truth", "n": n, "train_story": ns, "train_topic": nt, "v6b_alone_story": f(vb_s), "sparse_alone_story": f(sp_s), "v6b_alone_topic_top2": f(vb_t), "sparse_alone_topic_top2": f(sp_t), "story_lines": {}, "joint": {}}
for q in (0.25, 0.5, 0.75):
    t = float(np.quantile(cs_conf, 1 - q)); a = cs_conf >= t; c = np.where(a, sp_s, vb_s)
    res["story_lines"][str(q)] = {"sparse_share": round(float(a.mean()), 3), "threshold_prob": round(t, 3), **f(c), "sparse_right_when_answering": round(float(sp_s[a].mean()), 4), "v6b_right_on_those": round(float(vb_s[a].mean()), 4), "v6b_right_on_rest": round(float(vb_s[~a].mean()), 4)}
a = (cs_conf >= np.median(cs_conf)) & (mass >= np.median(mass)); m = int(a.sum())
res["joint"] = {"share": round(m / n, 3), "n": m, "story_sparse_on_joint": round(float(sp_s[a].mean()), 4), "story_v6b_on_joint": round(float(vb_s[a].mean()), 4), "topic_sparse_on_joint": round(float(sp_t[a].mean()), 4), "topic_v6b_on_joint": round(float(vb_t[a].mean()), 4),
  "chain_story_overall": f(np.where(a, sp_s, vb_s)), "chain_topic_overall": f(np.where(a, sp_t, vb_t))}
rec = {}
for c_ in cs:
    mk = sst == c_; rec[str(c_)] = {"n": int(mk.sum()), "sparse_recall": round(float(sp_s[mk].mean()), 3) if mk.any() else None, "v6b_recall": round(float(vb_s[mk].mean()), 3) if mk.any() else None}
res["per_class_recall"] = rec
json.dump(res, open("runs/pulse/round2_story_cascade.json", "w"), indent=1); print(json.dumps(res, indent=1))
