"""Triage: how much of the field can the CPU cascade skip? Run with /workspace/models/embed-zs/.venv/bin/python triage.py"""
import json, os, re, glob, pathlib, warnings, sys
warnings.filterwarnings("ignore"); os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, spacy
sys.argv = ["x"]; H0 = pathlib.Path(__file__).resolve().parent
src = open(H0 / "structure.py").read(); pre = src[:src.index("H = {}; S = {}")]; exec(pre)                 # reuse regexes and feat() definitions
exec(src[src.index("nlp = spacy.load"):src.index("txts = [re.sub")])
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score
from model2vec import StaticModel
H = {}
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): H[r["item_id"]] = r["label"]
pool = {r["id"]: r["text"] for r in J(H0 / "data/pool_train.jsonl")}; ids = sorted(H); txts = [re.sub(r"\s+", " ", pool[i]) for i in ids]
F = np.array([feat(d, t) for d, t in zip(nlp.pipe(txts, batch_size=128), txts)], float); E = StaticModel.from_pretrained("minishlab/potion-base-8M").encode(txts)
y = np.array([1 if H[i]["conditions"] else 0 for i in ids]); gate = set(open(H0 / "runs/p4/gate_flagged_ids.txt").read().split()); g = np.array([i in gate for i in ids])
p = cross_val_predict(make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, C=0.1)), np.hstack([F, E]), y, cv=StratifiedKFold(5, shuffle=True, random_state=0), method="predict_proba")[:, 1]
def share_read(score, recall):                                                                       # smallest share of items to read (highest scores first) to keep `recall` of positives
    order = np.argsort(-score); cum = np.cumsum(y[order]) / y.sum(); return float((np.argmax(cum >= recall) + 1) / len(y))
out = {"items": len(ids), "haiku_positive_rate": round(float(y.mean()), 3), "auc_cpu": round(float(roc_auc_score(y, p)), 3), "gate_flags_share": round(float(g.mean()), 3), "gate_recall_of_positives": round(float((g & (y == 1)).sum() / y.sum()), 3)}
comb = np.where(g, 1.0 + p, p)                                                                       # gate first, CPU score ranks the rest and the flagged
for r in (0.90, 0.95, 0.98): out[f"read_share_for_{int(r*100)}pct_recall"] = {"cpu_only": round(share_read(p, r), 3), "gate_then_cpu": round(share_read(comb, r), 3), "random": r}
json.dump(out, open(H0 / "runs/structure/triage.json", "w"), indent=1); print(json.dumps(out, indent=1))
