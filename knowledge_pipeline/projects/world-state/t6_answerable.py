"""T6: does saying 'unknown' on the least confident items lift Haiku-Sonnet agreement on the rest? Run with /workspace/models/embed-zs/.venv/bin/python"""
import json, glob, re, pathlib, warnings
warnings.filterwarnings("ignore")
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from model2vec import StaticModel
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
hk, sn = {}, {}
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): hk[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): sn[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J(H0 / "data/pool_train.jsonl")}; ids = sorted(hk)
F = np.load(H0 / "runs/structure/feat_all.npz", allow_pickle=True)["F"]
txt = [re.sub(r"\s+", " ", pool[i]["text"]) for i in ids]; X = np.hstack([F, StaticModel.from_pretrained("minishlab/potion-base-8M").encode(txt)])
y = np.array([1 if hk[i]["conditions"] else 0 for i in ids])
p = cross_val_predict(make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, C=0.1)), X, y, cv=StratifiedKFold(5, shuffle=True, random_state=0), method="predict_proba")[:, 1]
conf = np.maximum(p, 1 - p)
v = np.array([i in sn for i in ids]); ix = np.where(v)[0]
sy = np.array([1 if (ids[k] in sn and sn[ids[k]]["conditions"]) else 0 for k in range(len(ids))])
cs = lambda i, S: {c["condition"] for c in S[i]["conditions"]}
same = np.array([len(cs(ids[k], hk) & cs(ids[k], sn)) > 0 if (y[k] and sy[k]) else False for k in range(len(ids))])
def curve(sel, metric):
    o = sel[np.argsort(-conf[sel])]; out = {}
    for cov in (1.0, .8, .6, .5, .4, .3, .2, .1): out[f"{int(cov*100)}%"] = round(float(metric(o[:max(1, int(len(o) * cov))])), 3)
    return out
pos = ix[y[ix] == 1]; both = pos[sy[pos] == 1]
res = {"n_voted": len(ix), "all_voted_presence_agree": curve(ix, lambda s: (sy[s] == y[s]).mean()),
       "haiku_positive_presence_agree": curve(pos, lambda s: (sy[s] == y[s]).mean()),
       "haiku_positive_same_condition_share": curve(pos, lambda s: same[s].mean()),
       "both_positive_same_condition_agree": curve(both, lambda s: same[s].mean())}
json.dump(res, open(H0 / "runs/structure/t6_answerable.json", "w"), indent=1); print(json.dumps(res, indent=1))
