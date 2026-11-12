"""Round 1 of the improvement loop: does a sparse topic head trained only on Sonnet labels, answering first, keep the chain's topic score on MN-DS human labels?
Sparse head: TF-IDF + logistic loss trained by SGD (the lbfgs fit ran over 28 minutes and was stopped) on Sonnet topic labels in the label store (MN-DS is never trained on). Chain: if the sparse head's top-two probability mass is at or above the median mass, its two topics answer; otherwise BitMob Domain v6b answers.
Scoring is as in score_anchor_v6b.py (any of the two answers maps to the human category). Writes runs/pulse/round1_cascade.json.
    /workspace/models/embed-zs/.venv/bin/python round1_cascade.py   (from projects/world-state)"""
import json, glob, sys, math, time, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
sys.path.insert(0, "."); from expert1_runtime import ExpertS
J = lambda p: [json.loads(l) for l in open(p)]
txt = {r["id"]: r["text"] for r in J("data/pool.jsonl")}; txt.update({r["id"]: r["text"] for r in J("runs/pulse/queue_texts.jsonl")})
for f in glob.glob("runs/**/items*.jsonl", recursive=True):
    try:
        for r in J(f):
            if r.get("id") and r.get("text"): txt.setdefault(r["id"], r["text"])
    except Exception: pass
RANK = {"ws-v3b-nosize": 0, "ws-v2-frozen": 1}; best = {}
for r in J("runs/label_store/labels.jsonl"):
    if r["family"] != "sonnet" or not r.get("topic") or r["item_id"] not in txt: continue
    rk = RANK.get(r["version"], 2)
    if r["item_id"] not in best or rk < best[r["item_id"]][0]: best[r["item_id"]] = (rk, r["topic"])
tr = sorted(best); Xtr = [txt[i] for i in tr]; ytr = np.array([best[i][1] for i in tr])
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; G = json.load(open("/workspace/data/anchors/mn_ds/gold_T28b.json"))
items = {x["id"]: x["text"] for x in J("/workspace/data/anchors/mn_ds/items_T28b.jsonl")}; ids = [i for i in items if i in G]; print("train", len(tr), "test", len(ids), flush=True)
t0 = time.time(); v = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=150000, sublinear_tf=True); A = v.fit_transform(Xtr); m = SGDClassifier(loss="log_loss", alpha=2e-6, max_iter=12, tol=None, n_jobs=6, random_state=7).fit(A, ytr); print("sparse fit s", round(time.time() - t0), flush=True)
P = m.predict_proba(v.transform([items[i] for i in ids])); cl = np.array(m.classes_); o = np.argsort(-P, 1)[:, :2]; mass = P[np.arange(len(P))[:, None], o].sum(1)
hit = lambda gi, tops: any(G[gi]["l1"] in M.get(t, []) for t in tops)
sp = np.array([hit(i, cl[o[k]]) for k, i in enumerate(ids)])
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); vb = np.array([hit(i, e.read(items[i])["topic_top2"]["answer"] or []) for i in ids])
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [round(c - h, 3), round(c + h, 3)]
n = len(ids); res = {"n": n, "train_items": len(tr), "sparse_alone": {"top2": round(float(sp.mean()), 4), "ci95": wil(int(sp.sum()), n)}, "v6b_alone": {"top2": round(float(vb.mean()), 4), "ci95": wil(int(vb.sum()), n)}, "lines": {}}
for q in (0.25, 0.5, 0.75):
    t = float(np.quantile(mass, 1 - q)); a = mass >= t; c = np.where(a, sp, vb); k = int(c.sum())
    res["lines" if q != 0.5 else "cascade_at_share50"] if False else None
    r = {"sparse_share": round(float(a.mean()), 3), "threshold_mass": round(t, 3), "top2": round(k / n, 4), "ci95": wil(k, n), "sparse_right_when_answering": round(float(sp[a].mean()), 4), "v6b_right_on_those": round(float(vb[a].mean()), 4), "v6b_right_on_rest": round(float(vb[~a].mean()), 4)}
    res["lines"][str(q)] = r
    if q == 0.5: res["cascade_at_share50"] = r
json.dump(res, open("runs/pulse/round1_cascade.json", "w"), indent=1); print(json.dumps(res, indent=1))
