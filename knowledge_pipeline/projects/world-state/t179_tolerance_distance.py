"""T179: TPR at fixed FPR for each teacher and CPU student against its public truth (CheckThat Function test split; MAVEN-FACT factuality events), to compare with the Step 1 tolerance (F-0020: TPR .90-.95 at FPR .001-.0025). Prediction in ledger L2251.
Run (from projects/world-state): /workspace/models/embed-zs/.venv/bin/python -I t179_tolerance_distance.py -> runs/pulse/t179/t179_tolerance_distance.json"""
import json, csv, os, sys, pathlib, numpy as np
sys.path.insert(0, "."); OUT = pathlib.Path("runs/pulse/t179"); OUT.mkdir(parents=True, exist_ok=True)
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
def tpr_at(sc, y, fpr):
    neg = np.sort(sc[y == 0])[::-1]; k = int(np.floor(fpr * len(neg))); t = neg[k] if k < len(neg) else neg[-1] - 1; return float(np.mean(sc[y == 1] > t)), int((y == 0).sum())
res = {"function_checkthat_test": {}, "factuality_maven": {}}
D = "/workspace/data/anchors/checkthat_subj/"; split = {}
for f, name in (("train_en.tsv", "train"), ("dev_en.tsv", "dev"), ("dev_test_en.tsv", "devtest"), ("test_en_labeled.tsv", "test")):
    for r in csv.DictReader(open(D + f), delimiter="\t"): split["ct:" + r["sentence_id"]] = name
ct = [r for r in json.load(open("runs/pulse/t170/t170_function_subjective.json"))["rows"] if "error" not in r]
q = [json.loads(l) for l in open("runs/pulse/t172/t172_rows.jsonl")]; z = np.load("runs/pulse/t173_embeddings.npz") if os.path.exists("runs/pulse/t173_embeddings.npz") else np.load("runs/pulse/t172/t173_embeddings.npz")
Xc, Xq = z["c"], z["q"]; pc = np.array([r["noul"]["function_subjective"] for r in ct]); pq = np.array([r["p"] for r in q]); S = np.array([split[r["id"]] for r in ct]); g = np.array([r["gold"] == "SUBJ" for r in ct]).astype(int)
tr = np.isin(S, ["train", "dev", "devtest"]); te = S == "test"; h = LogisticRegression(C=1.0, max_iter=3000).fit(np.vstack([Xq, Xc[tr]]), np.concatenate([(pq >= 0.5), (pc[tr] >= 0.5)]).astype(int)).predict_proba(Xc)[:, 1]
for name, sc in (("jev", pc), ("cpu_student_v6b", h)):
    res["function_checkthat_test"][name] = {f"tpr_at_fpr_{f}": round(tpr_at(sc[te], g[te], f)[0], 3) for f in (0.05, 0.01)}
res["function_checkthat_test"]["n_negatives_test"] = int((g[te] == 0).sum())
rows = json.load(open("runs/pulse/t152/t152_factuality_maven.json"))["rows"]; text = {json.loads(l)["id"]: json.loads(l)["text"] for l in open("/workspace/data/anchors/maven_fact/items_T33b.jsonl")}
rows = [r for r in rows if r["id"] in text]; y = np.array([r["yes"] for r in rows]).astype(int); pj = np.array([r["happened"] for r in rows]); doc = np.array([r["id"].split(":")[1] for r in rows])
from sentence_transformers import SentenceTransformer
m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 128; Xb = m.encode([text[r["id"]] for r in rows], batch_size=64, normalize_embeddings=True, show_progress_bar=False)
oof = np.zeros(len(rows))
for a, b in GroupKFold(5).split(Xb, y, doc): oof[b] = LogisticRegression(C=1.0, max_iter=3000).fit(Xb[a], (pj[a] >= 0.5).astype(int)).predict_proba(Xb[b])[:, 1]
for name, sc in (("jev", pj), ("cpu_student_bge", oof)): res["factuality_maven"][name] = {f"tpr_at_fpr_{f}": round(tpr_at(sc, y, f)[0], 3) for f in (0.05, 0.01)}
res["factuality_maven"]["n_negatives"] = int((y == 0).sum()); res["tolerance_target"] = "F-0020: TPR 0.90-0.95 at FPR 0.001-0.0025 (all-keys target); the test sets cannot resolve FPR below about 0.005"
json.dump(res, open(OUT / "t179_tolerance_distance.json", "w"), indent=1); print(json.dumps(res))
