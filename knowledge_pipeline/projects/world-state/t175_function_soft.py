"""T175: Function student on Jev soft probabilities (ridge on logit p) and on confident rows only, saved v6b embeddings from t173, scored on CheckThat gold of the 300 test rows. Prediction in ledger L2237.
Run (from projects/world-state): OUT=runs/pulse/t172 /workspace/models/embed-zs/.venv/bin/python -I t175_function_soft.py"""
import json, csv, os, pathlib, numpy as np
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t172")); D = "/workspace/data/anchors/checkthat_subj/"; split = {}
for f, name in (("train_en.tsv", "train"), ("dev_en.tsv", "dev"), ("dev_test_en.tsv", "devtest"), ("test_en_labeled.tsv", "test")):
    for r in csv.DictReader(open(D + f), delimiter="\t"): split["ct:" + r["sentence_id"]] = name
text = {json.loads(l)["id"] for l in open(D + "items_T30.jsonl")}
ct = [r for r in json.load(open("runs/pulse/t170/t170_function_subjective.json"))["rows"] if "error" not in r and r["id"] in text]
q = [json.loads(l) for l in open(OUT / "t172_rows.jsonl")]; z = np.load(OUT / "t173_embeddings.npz"); Xc, Xq = z["c"], z["q"]
pc = np.array([r["noul"]["function_subjective"] for r in ct]); pq = np.array([r["p"] for r in q]); S = np.array([split[r["id"]] for r in ct]); g = np.array([r["gold"] == "SUBJ" for r in ct]).astype(int)
tr = np.isin(S, ["train", "dev", "devtest"]); te = S == "test"
from sklearn.linear_model import Ridge, LogisticRegression
def auc(sc, y): P = sc[y == 1]; Nn = sc[y == 0]; return float(sum((a > b) + 0.5 * (a == b) for a in P for b in Nn) / (len(P) * len(Nn)))
def bal(sc, y, t): return float((np.mean(sc[y == 1] >= t) + np.mean(sc[y == 0] < t)) / 2)
X = np.vstack([Xq, Xc[tr]]); p = np.concatenate([pq, pc[tr]]); lg = np.log(np.clip(p, 0.01, 0.99) / (1 - np.clip(p, 0.01, 0.99))); res = {"jev_auc_vs_gold_test": round(auc(pc[te], g[te]), 3), "variants": {}}
for a in (1.0, 10.0, 100.0):
    h = Ridge(alpha=a).fit(X, lg).predict(Xc); t = float(np.median(h[tr])); line = max(np.percentile(h[tr], np.arange(5, 96)), key=lambda t: np.mean(((h[tr] >= t) == (pc[tr] >= 0.5))))
    res["variants"][f"soft_ridge_a{a}"] = {"auc": round(auc(h[te], g[te]), 3), "bal_at_line": round(bal(h[te], g[te], line), 3)}
keep = (p <= 0.2) | (p >= 0.8)
for C in (1.0, 10.0):
    m = LogisticRegression(C=C, max_iter=3000).fit(X[keep], (p[keep] >= 0.5).astype(int)); h = m.predict_proba(Xc)[:, 1]
    res["variants"][f"confident_only_C{C}"] = {"n_rows": int(keep.sum()), "auc": round(auc(h[te], g[te]), 3), "bal_at_0_5": round(bal(h[te], g[te], 0.5), 3)}
json.dump(res, open(OUT / "t175_function_soft.json", "w"), indent=1); print(json.dumps(res))
