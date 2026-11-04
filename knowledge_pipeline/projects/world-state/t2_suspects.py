"""T2: does a label-error ranking (low out-of-fold confidence in Haiku's label) point at items Sonnet disagrees on?"""
import json, glob, re, pathlib, warnings
warnings.filterwarnings("ignore")
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score
from model2vec import StaticModel
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hk, sn = {}, {}
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): sn[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J(H0 / "data/pool_train.jsonl")}; ids = sorted(hk)
z = np.load(H0 / "runs/structure/feat_all.npz", allow_pickle=True); F = z["F"]
txt = [re.sub(r"\s+", " ", pool[i]["text"]) for i in ids]; X = np.hstack([F, StaticModel.from_pretrained("minishlab/potion-base-8M").encode(txt)])
y = np.array([1 if hk[i]["conditions"] else 0 for i in ids])
p = cross_val_predict(make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, C=0.1)), X, y, cv=StratifiedKFold(5, shuffle=True, random_state=0), method="predict_proba")[:, 1]
conf = np.where(y == 1, p, 1 - p)                                   # confidence in Haiku's own label (self-confidence, as in Confident Learning)
v = np.array([i in sn for i in ids]); out = {"voted_items": int(v.sum())}
sy = np.array([1 if (i in sn and sn[i]["conditions"]) else 0 for i in ids]); dis = (sy != y)    # Sonnet disagrees on presence
base = dis[v].mean(); out["sonnet_disagree_rate_all_voted"] = round(float(base), 3)
for name, m in (("haiku_positive", v & (y == 1)), ("haiku_negative", v & (y == 0))):
    ix = np.where(m)[0]; o = ix[np.argsort(conf[ix])]
    out[name] = {"n": len(ix), "base_disagree": round(float(dis[ix].mean()), 3), "auc_lowconf_predicts_disagree": round(float(roc_auc_score(dis[ix], 1 - conf[ix])), 3), "top100_lowest_conf_disagree": round(float(dis[o[:100]].mean()), 3), "top500_lowest_conf_disagree": round(float(dis[o[:500]].mean()), 3)}
json.dump(out, open(H0 / "runs/structure/t2_suspects.json", "w"), indent=1); print(json.dumps(out, indent=1))
