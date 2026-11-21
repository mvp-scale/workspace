"""T158-H1: re-score the saved function head (runs/pulse/function_head_v1/function_head.pkl) on the CheckThat test_en_labeled split (human gold), using the same cached features and split code as t210_save_function_head.py. Run: /workspace/models/embed-zs/.venv/bin/python -I h1-eval-function.py"""
import json, csv, pickle, pathlib, numpy as np
D = "/workspace/data/anchors/checkthat_subj/"; P = pathlib.Path("runs/pulse/t172")
split = {}
for f, name in (("train_en.tsv", "train"), ("dev_en.tsv", "dev"), ("dev_test_en.tsv", "devtest"), ("test_en_labeled.tsv", "test")):
    for r in csv.DictReader(open(D + f), delimiter="\t"): split["ct:" + r["sentence_id"]] = name
ct = [r for r in json.load(open("runs/pulse/t170/t170_function_subjective.json"))["rows"] if "error" not in r]; q = [json.loads(l) for l in open(P / "t172_rows.jsonl")]; q2 = [json.loads(l) for l in open(P / "t187_rows.jsonl")]
def load(path): z = np.load(path); return np.vstack([z["q"], z["c"]])
E = np.hstack([load(P / "t173_embeddings.npz"), load(P / "t176_emb_bge_small.npz"), load(P / "t176_emb_e5_small.npz")]); z = np.load(P / "t187_new_embeddings.npz"); X2 = np.hstack([z["v6b"], z["bge"], z["e5"]]); X = np.vstack([E, X2]).astype(np.float32)
pj = np.concatenate([[r["p"] for r in q], [r["noul"]["function_subjective"] for r in ct], [r["p"] for r in q2]])
S = np.array(["queue"] * len(q) + [split.get(r["id"], "?") for r in ct] + ["queue"] * len(q2)); gold = np.array([-1] * len(q) + [1 if r["gold"] == "SUBJ" else 0 for r in ct] + [-1] * len(q2))
def auc(sc, y):
    P_, N_ = sc[y == 1], sc[y == 0]; return float(sum((a > b) + 0.5 * (a == b) for a in P_ for b in N_) / (len(P_) * len(N_)))
def bal(sc, y, t): return float((np.mean(sc[y == 1] >= t) + np.mean(sc[y == 0] < t)) / 2)
d = pickle.load(open("runs/pulse/function_head_v1/function_head.pkl", "rb")); res = {}
for nm in ("test", "dev", "devtest"):
    m = S == nm; h = d["model"].predict_proba(X[m])[:, 1]; g = gold[m]; res[nm] = {"n": int(m.sum()), "n_subj": int((g == 1).sum()), "head_auc_vs_human": round(auc(h, g), 3), "head_bal_0_5": round(bal(h, g, 0.5), 3), "head_bal_0_8": round(bal(h, g, 0.8), 3), "head_auc_vs_jev_label": round(auc(h, (pj[m] >= 0.5).astype(int)), 3), "jev_auc_vs_human": round(auc(pj[m], g), 3), "jev_bal_0_5": round(bal(pj[m], g, 0.5), 3), "in_training": nm != "test"}
print(json.dumps(res, indent=1)); json.dump(res, open("runs/pulse/function_head_v1/h1_eval.json", "w"), indent=1)
