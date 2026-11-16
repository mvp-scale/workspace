"""CPU Function student: v6b student embedding of a sentence -> logistic head trained on Jev function_subjective (p>=0.5, train+dev+devtest rows) -> scored on CheckThat gold of the test rows (scoring-only use of gold). Prediction in ledger L2229.
Run (from projects/world-state): OUT=runs/pulse/t171 /workspace/models/embed-zs/.venv/bin/python -I t171_function_head.py"""
import json, csv, os, sys, time, pathlib, numpy as np
sys.path.insert(0, ".")
from expert1_runtime import ExpertS
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t171")); OUT.mkdir(parents=True, exist_ok=True); N = int(os.environ.get("N", 0))
D = "/workspace/data/anchors/checkthat_subj/"; split = {}
for f, name in (("train_en.tsv", "train"), ("dev_en.tsv", "dev"), ("dev_test_en.tsv", "devtest"), ("test_en_labeled.tsv", "test")):
    for r in csv.DictReader(open(D + f), delimiter="\t"): split["ct:" + r["sentence_id"]] = name
text = {json.loads(l)["id"]: json.loads(l)["text"] for l in open(D + "items_T30.jsonl")}
rows = [r for r in json.load(open("runs/pulse/t170/t170_function_subjective.json"))["rows"] if "error" not in r and r["id"] in text]
rows = rows[:N] if N else rows
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); t0 = time.time(); X = np.array([e.student(text[r["id"]]) for r in rows], dtype=np.float32); print("embed s", round(time.time() - t0))
if N: sys.exit()
from sklearn.linear_model import LogisticRegression
p = np.array([r["noul"]["function_subjective"] for r in rows]); S = np.array([split[r["id"]] for r in rows]); g = np.array([r["gold"] == "SUBJ" for r in rows]).astype(int)
tr = np.isin(S, ["train", "dev", "devtest"]); te = S == "test"
m = LogisticRegression(C=1.0, max_iter=3000).fit(X[tr], (p[tr] >= 0.5).astype(int)); h = m.predict_proba(X)[:, 1]
def auc(sc, y):
    P = sc[y == 1]; Nn = sc[y == 0]; return float(sum((a > b) + 0.5 * (a == b) for a in P for b in Nn) / (len(P) * len(Nn)))
def bal(sc, y, t): return float((np.mean(sc[y == 1] >= t) + np.mean(sc[y == 0] < t)) / 2)
trh = tr & (np.arange(len(rows)) % 1 == 0)
line = max(np.arange(0.05, 0.96, 0.01), key=lambda t: np.mean(((h[tr] >= t) == (p[tr] >= 0.5))))   # line copies Jev's own call on training rows, no gold used
res = {"n_rows": len(rows), "n_train": int(tr.sum()), "n_test": int(te.sum()), "head_auc_vs_gold_test": round(auc(h[te], g[te]), 3), "jev_auc_vs_gold_test": round(auc(p[te], g[te]), 3), "head_bal_at_line": round(bal(h[te], g[te], line), 3), "line": round(float(line), 2), "head_bal_at_0_5": round(bal(h[te], g[te], 0.5), 3), "jev_bal_at_0_5": round(bal(p[te], g[te], 0.5), 3), "head_auc_vs_jev_label_test": round(auc(h[te], (p[te] >= 0.5).astype(int)), 3)}
json.dump(res, open(OUT / "t171_function_head.json", "w"), indent=1); print(json.dumps(res))
