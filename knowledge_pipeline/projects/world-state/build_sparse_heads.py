"""Train the two sparse heads of Rounds 1 and 2 on Sonnet labels (sealed ids excluded) and save them for analyze2.py.
Story head: TF-IDF + SGD log loss on story_type. Topic head: same on topic, answers its top two. Thresholds = median confidence on the sealed set, as in round2_story_cascade.py.
Writes runs/expert1/sparse_heads_v1.pkl. Judge, scores and caveats: runs/pulse/round2_story_cascade.json.
    /workspace/models/embed-zs/.venv/bin/python -u build_sparse_heads.py   (from projects/world-state)"""
import json, glob, pickle, time, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")})
for f in glob.glob("runs/**/items*.jsonl", recursive=True):
    try:
        for r in J(f):
            if r.get("id") and r.get("text"): txt.setdefault(r["id"], r["text"])
    except Exception: pass
S = {r["item_id"]: r["label"] for r in J("runs/pulse/sealed/labels.jsonl")}; sealed = set(S); ids = sorted(i for i in S if i in txt)
RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}; bt = {}; bs = {}
for r in J("runs/label_store/labels.jsonl"):
    i = r["item_id"]
    if r["family"] != "sonnet" or i not in txt or i in sealed: continue
    rk = RANK.get(r["version"], 2)
    if r.get("topic") and (i not in bt or rk < bt[i][0]): bt[i] = (rk, r["topic"])
    if r.get("story_type") and (i not in bs or rk < bs[i][0]): bs[i] = (rk, r["story_type"])
def fit(best):
    tr = sorted(best); y = np.array([best[i][1] for i in tr]); v = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=150000, sublinear_tf=True); A = v.fit_transform([txt[i] for i in tr])
    return v, SGDClassifier(loss="log_loss", alpha=2e-6, max_iter=12, tol=None, n_jobs=6, random_state=7).fit(A, y), len(tr)
vs, ms, ns = fit(bs); vt, mt, nt = fit(bt); X = [txt[i] for i in ids]
conf = ms.predict_proba(vs.transform(X)).max(1); Pt = mt.predict_proba(vt.transform(X)); o = np.argsort(-Pt, 1)[:, :2]; mass = Pt[np.arange(len(Pt))[:, None], o].sum(1)
H = {"story_vec": vs, "story_model": ms, "topic_vec": vt, "topic_model": mt, "story_thr": float(np.median(conf)), "topic_thr": float(np.median(mass)), "train_story": ns, "train_topic": nt, "built": time.strftime("%Y-%m-%d"), "judge": "runs/pulse/round2_story_cascade.json"}
pickle.dump(H, open("runs/expert1/sparse_heads_v1.pkl", "wb")); print("saved", ns, nt, round(H["story_thr"], 3), round(H["topic_thr"], 3))
