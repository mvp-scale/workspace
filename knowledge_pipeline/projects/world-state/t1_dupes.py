"""T1: do near-duplicates inflate the triage AUC? Run with /workspace/models/embed-zs/.venv/bin/python t1_dupes.py"""
import json, glob, re, pathlib, warnings, collections
warnings.filterwarnings("ignore")
import numpy as np, scipy.sparse as sp
from scipy.sparse.csgraph import connected_components
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, GroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score
from model2vec import StaticModel
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hk = {}
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J(H0 / "data/pool_train.jsonl")}; ids = sorted(hk)
z = np.load(H0 / "runs/structure/feat_all.npz", allow_pickle=True); assert list(z["ids"]) == ids; F = z["F"]
txt = [re.sub(r"\s+", " ", pool[i]["text"]).lower() for i in ids]; y = np.array([1 if hk[i]["conditions"] else 0 for i in ids])
E_ = StaticModel.from_pretrained("minishlab/potion-base-8M").encode(txt); X = np.hstack([F, E_])
T = TfidfVectorizer(analyzer="word", ngram_range=(3, 3), min_df=2, max_df=50, sublinear_tf=True, dtype=np.float32).fit_transform(txt)
res = {"n": len(ids)}
for thr in (0.5, 0.8):
    rows, cols = [], []
    for s in range(0, T.shape[0], 2000):
        S = (T[s:s + 2000] @ T.T).tocoo(); m = (S.data >= thr) & (S.row + s != S.col)
        rows += list(S.row[m] + s); cols += list(S.col[m])
    A = sp.coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(ids),) * 2); nc, lab = connected_components(A, directed=False)
    sz = collections.Counter(lab); inn = np.array([sz[l] > 1 for l in lab])
    res[f"thr{thr}"] = {"items_with_twin": round(float(inn.mean()), 4), "groups_over1": sum(1 for v in sz.values() if v > 1), "biggest_group": max(sz.values()), "positive_rate_twins": round(float(y[inn].mean()), 3) if inn.any() else None, "positive_rate_others": round(float(y[~inn].mean()), 3)}
    res[f"_lab{thr}"] = lab
def cv(splits):
    p = np.zeros(len(y)); msk = np.zeros(len(y), bool)
    for a, b in splits:
        m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, C=0.1)).fit(X[a], y[a]); p[b] = m.predict_proba(X[b])[:, 1]; msk[b] = True
    return round(float(roc_auc_score(y[msk], p[msk])), 4)
res["auc_random_cv"] = cv(StratifiedKFold(5, shuffle=True, random_state=0).split(X, y))
for thr in (0.5, 0.8): res[f"auc_grouped_cv_{thr}"] = cv(GroupKFold(5).split(X, y, res[f"_lab{thr}"]))
dt = np.array([pool[i]["date"] or "" for i in ids]); src = np.array([i.split(":")[0] for i in ids])
res["auc_random_by_prefix"] = {}; res["auc_time_forward_by_prefix"] = {}
for pre in ("cc", "nq"):
    ix = np.where(src == pre)[0]; o = ix[np.argsort(dt[ix], kind="stable")]; k = int(len(o) * 0.7)
    res["auc_time_forward_by_prefix"][pre] = cv([(o[:k], o[k:])])
    rs = list(StratifiedKFold(5, shuffle=True, random_state=0).split(X[ix], y[ix])); res["auc_random_by_prefix"][pre] = cv([(ix[a], ix[b]) for a, b in rs])
res = {k: v for k, v in res.items() if not k.startswith("_")}
json.dump(res, open(H0 / "runs/structure/t1_dupes.json", "w"), indent=1); print(json.dumps(res, indent=1), flush=True)
