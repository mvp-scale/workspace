"""T210 (plan step P0b, ledger L2429): fit and SAVE the sentence-level Function head (opinion or fact) as a loadable model. Features: v6b + bge-small + e5-small embeddings joined (1,792 dimensions) of 51,000 sentences (queue sentences labelled by Jev, 15,700 old plus 35,351 new) plus CheckThat train, dev and devtest sentences labelled by Jev; the CheckThat TEST split (human gold) is held out of training. Label = Jev subjectivity probability at least 0.5. The yes and no lines are fitted at false-positive quota 0.0010 and 5% misses on out-of-fold scores grouped by story. Then the hybrid (head answers when sure, otherwise Jev's label) is scored against the CheckThat human gold on the held-out test split and compared with Jev alone. Saves runs/pulse/t210/function_head.pkl. Prediction in card T148-L.
Run (from projects/world-state): OUT=runs/pulse/t210 /workspace/models/embed-zs/.venv/bin/python -u t210_save_function_head.py   (N=3000 for a smoke run)"""
import json, os, csv, pickle, pathlib, time, numpy as np
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t210")); OUT.mkdir(parents=True, exist_ok=True); N = int(os.environ.get("N", 0)); T0 = time.time(); D = "/workspace/data/anchors/checkthat_subj/"; P = pathlib.Path("runs/pulse/t172")
split = {}
for f, name in (("train_en.tsv", "train"), ("dev_en.tsv", "dev"), ("dev_test_en.tsv", "devtest"), ("test_en_labeled.tsv", "test")):
    for r in csv.DictReader(open(D + f), delimiter="\t"): split["ct:" + r["sentence_id"]] = name
ct = [r for r in json.load(open("runs/pulse/t170/t170_function_subjective.json"))["rows"] if "error" not in r]; q = [json.loads(l) for l in open(P / "t172_rows.jsonl")]; q2 = [json.loads(l) for l in open(P / "t187_rows.jsonl")]
def load(path): z = np.load(path); return np.vstack([z["q"], z["c"]])
E = np.hstack([load(P / "t173_embeddings.npz"), load(P / "t176_emb_bge_small.npz"), load(P / "t176_emb_e5_small.npz")]); z = np.load(P / "t187_new_embeddings.npz"); X2 = np.hstack([z["v6b"], z["bge"], z["e5"]])
X = np.vstack([E, X2]).astype(np.float32); pj = np.concatenate([[r["p"] for r in q], [r["noul"]["function_subjective"] for r in ct], [r["p"] for r in q2]]); y = (pj >= 0.5).astype(int)
grp = np.array([r["id"].split(":")[1] for r in q] + [r["id"] for r in ct] + [r["id"].split(":")[1] for r in q2]); S = np.array(["queue"] * len(q) + [split.get(r["id"], "?") for r in ct] + ["queue"] * len(q2))
gold = np.array([-1] * len(q) + [1 if r["gold"] == "SUBJ" else 0 for r in ct] + [-1] * len(q2)); te = S == "test"; tr = ~te & (S != "?")
idx = np.where(tr)[0]; idx = idx[:N] if N else idx
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
def fitline(s, yy, fp=0.0010, fn=0.05):
    neg = np.sort(s[yy == 0])[::-1]; hi = neg[int(np.floor(fp * len(neg)))]; pos = np.sort(s[yy == 1]); lo = pos[int(np.floor(fn * len(pos)))]; return lo, hi
Xt, yt, gt = X[idx], y[idx], grp[idx]; oof = np.zeros(len(yt))
for a, b in GroupKFold(5).split(Xt, yt, gt): oof[b] = LogisticRegression(C=1.0, max_iter=400).fit(Xt[a], yt[a]).predict_proba(Xt[b])[:, 1]; print("fold", round(time.time() - T0), flush=True)
lo, hi = fitline(oof, yt); m = LogisticRegression(C=1.0, max_iter=400).fit(Xt, yt); h = m.predict_proba(X[te])[:, 1]; g = gold[te]; teacher = (pj[te] >= 0.5).astype(int)
yes = h > hi; no = h < lo; ans = yes | no; hybrid = np.where(yes, 1, np.where(no, 0, teacher))
bal = lambda pred: float((np.mean(pred[g == 1] == 1) + np.mean(pred[g == 0] == 0)) / 2)
res = {"trained_on": int(len(idx)), "heldout_checkthat_test": int(te.sum()), "lo": float(lo), "hi": float(hi), "oof_coverage": round(float(((oof > hi) | (oof < lo)).mean()), 3), "test_coverage": round(float(ans.mean()), 3),
       "teacher_bal_acc_vs_human": round(bal(teacher), 3), "head_alone_bal_acc_vs_human": round(bal((h >= 0.5).astype(int)), 3), "hybrid_bal_acc_vs_human": round(bal(hybrid), 3), "answered_bal_acc_vs_human": round(float((np.mean(((h > hi)[ans & (g == 1)])) + np.mean((h < lo)[ans & (g == 0)])) / 2), 3) if (ans & (g == 1)).any() and (ans & (g == 0)).any() else None, "seconds": round(time.time() - T0)}
res["hybrid_minus_teacher"] = round(res["hybrid_bal_acc_vs_human"] - res["teacher_bal_acc_vs_human"], 3)
if not N: pickle.dump({"model": m, "lo": float(lo), "hi": float(hi), "encoders": ["v6b student (runs/embeds/student_v6b-student.onnx)", "BAAI/bge-small-en-v1.5", "intfloat/e5-small-v2 ('query: ' prefix)"], "dims": 1792, "label": "Jev subjectivity probability >= 0.5", "fit_fp_quota": 0.0010, "metrics": res}, open(OUT / "function_head.pkl", "wb"))
json.dump(res, open(OUT / ("t210_smoke.json" if N else "t210_function_head.json"), "w"), indent=1); print(json.dumps(res))
