"""R6: fix for MM3-0005. Refit the two sparse heads with 3,000 random Sonnet-labelled store items held out as a CALIBRATION set (sealed ids also excluded); each head's confidence threshold = median on the calibration set; then score the chain (sparse when both confident, else v6b) on the sealed set once. Saves runs/expert1/sparse_heads_v2.pkl and writes runs/pulse/r6_calibrated.json. Judge: agreement with Sonnet on the sealed set, not outside truth.
    /workspace/models/embed-zs/.venv/bin/python -u r6_calibrated_heads.py   (from projects/world-state)"""
import json, glob, math, pickle, random, sys, time
import numpy as np
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
S = {r["item_id"]: r["label"] for r in J("runs/pulse/sealed/labels.jsonl")}; sealed = set(S); sid = sorted(i for i in S if i in txt)
RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}; bt = {}; bs = {}
for r in J("runs/label_store/labels.jsonl"):
    i = r["item_id"]
    if r["family"] != "sonnet" or i not in txt or i in sealed: continue
    rk = RANK.get(r["version"], 2)
    if r.get("topic") and (i not in bt or rk < bt[i][0]): bt[i] = (rk, r["topic"])
    if r.get("story_type") and (i not in bs or rk < bs[i][0]): bs[i] = (rk, r["story_type"])
allids = sorted(set(bt) & set(bs)); rng = random.Random(20261109); rng.shuffle(allids); cal = allids[:3000]; calset = set(cal)
def fit(best):
    tr = sorted(i for i in best if i not in calset); y = np.array([best[i][1] for i in tr]); v = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=150000, sublinear_tf=True); A = v.fit_transform([txt[i] for i in tr])
    return v, SGDClassifier(loss="log_loss", alpha=2e-6, max_iter=12, tol=None, n_jobs=6, random_state=7).fit(A, y), len(tr)
vs, ms, ns = fit(bs); vt, mt, nt = fit(bt)
def conf(X):
    ps = ms.predict_proba(vs.transform(X)); pt = mt.predict_proba(vt.transform(X)); o = np.argsort(-pt, 1)[:, :2]; return ps.max(1), ps, pt, o, pt[np.arange(len(pt))[:, None], o].sum(1)
cs_c, _, _, _, mass_c = conf([txt[i] for i in cal]); s_thr = float(np.median(cs_c)); t_thr = float(np.median(mass_c))
pickle.dump({"story_vec": vs, "story_model": ms, "topic_vec": vt, "topic_model": mt, "story_thr": s_thr, "topic_thr": t_thr, "train_story": ns, "train_topic": nt, "built": time.strftime("%Y-%m-%d"), "calibration_items": len(cal), "judge": "runs/pulse/r6_calibrated.json"}, open("runs/expert1/sparse_heads_v2.pkl", "wb"))
X = [txt[i] for i in sid]; cs, ps, pt, o, mass = conf(X); cl_s = np.array(ms.classes_); cl_t = np.array(mt.classes_)
sst = np.array([S[i]["story_type"] for i in sid]); stop = np.array([S[i]["topic"] for i in sid])
sp_s = cl_s[ps.argmax(1)] == sst; sp_t = np.array([stop[k] in cl_t[o[k]] for k in range(len(sid))])
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); R = [e.read(x) for x in X]
vb_s = np.array([r["story_type"]["status"] == "answered" and r["story_type"]["answer"] == sst[k] for k, r in enumerate(R)]); vb_t = np.array([stop[k] in (r["topic_top2"]["answer"] or []) and r["topic_top2"]["status"] == "answered" for k, r in enumerate(R)])
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [round(c - h, 3), round(c + h, 3)]
n = len(sid); a_s = cs >= s_thr; a_both = a_s & (mass >= t_thr)
f = lambda a: {"rate": round(float(a.mean()), 4), "ci95": wil(int(a.sum()), n)}
res = {"judge": "agreement with Sonnet on the sealed set, not outside truth", "n": n, "calibration_items": len(cal), "train_story": ns, "train_topic": nt, "story_thr": round(s_thr, 3), "topic_thr": round(t_thr, 3),
       "v6b_alone_story": f(vb_s), "v6b_alone_topic_top2": f(vb_t), "sparse_alone_story": f(sp_s), "story_chain_by_story_head_share": {"share": round(float(a_s.mean()), 3), **f(np.where(a_s, sp_s, vb_s))},
       "joint": {"share": round(float(a_both.mean()), 3), "chain_story": f(np.where(a_both, sp_s, vb_s)), "chain_topic_top2": f(np.where(a_both, sp_t, vb_t))}}
json.dump(res, open("runs/pulse/r6_calibrated.json", "w"), indent=1); print(json.dumps(res))
