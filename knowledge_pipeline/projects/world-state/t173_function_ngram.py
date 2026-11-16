"""T173: Function student on word 1-2 + char 3-5 gram TF-IDF (and stacked with the v6b embedding), trained on Jev function_subjective labels (p>=0.5, never gold), scored on CheckThat gold of the 300 test rows. Prediction in ledger L2233. Saves the embeddings so later cards can reuse them.
Run (from projects/world-state): OUT=runs/pulse/t172 /workspace/models/embed-zs/.venv/bin/python -I t173_function_ngram.py"""
import json, csv, os, sys, time, pathlib, numpy as np
sys.path.insert(0, ".")
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t172")); D = "/workspace/data/anchors/checkthat_subj/"; split = {}
for f, name in (("train_en.tsv", "train"), ("dev_en.tsv", "dev"), ("dev_test_en.tsv", "devtest"), ("test_en_labeled.tsv", "test")):
    for r in csv.DictReader(open(D + f), delimiter="\t"): split["ct:" + r["sentence_id"]] = name
text = {json.loads(l)["id"]: json.loads(l)["text"] for l in open(D + "items_T30.jsonl")}
ct = [r for r in json.load(open("runs/pulse/t170/t170_function_subjective.json"))["rows"] if "error" not in r and r["id"] in text]
q = [json.loads(l) for l in open(OUT / "t172_rows.jsonl")]
tc = [text[r["id"]] for r in ct]; tq = [r["text"] for r in q]
pc = np.array([r["noul"]["function_subjective"] for r in ct]); pq = np.array([r["p"] for r in q]); S = np.array([split[r["id"]] for r in ct]); g = np.array([r["gold"] == "SUBJ" for r in ct]).astype(int)
tr = np.isin(S, ["train", "dev", "devtest"]); te = S == "test"
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import scipy.sparse as sp
emb = OUT / "t173_embeddings.npz"
if emb.exists(): z = np.load(emb); Xc, Xq = z["c"], z["q"]
else:
    from expert1_runtime import ExpertS
    e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); t0 = time.time(); Xc = np.array([e.student(t) for t in tc], dtype=np.float32); Xq = np.array([e.student(t) for t in tq], dtype=np.float32); np.savez(emb, c=Xc, q=Xq); print("embed s", round(time.time() - t0), flush=True)
trainT = tq + [t for t, m in zip(tc, tr) if m]; trainY = np.concatenate([(pq >= 0.5), (pc[tr] >= 0.5)]).astype(int); trainE = np.vstack([Xq, Xc[tr]])
wv = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, lowercase=True); cv = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3, sublinear_tf=True, lowercase=True)
W = sp.hstack([wv.fit_transform(trainT), cv.fit_transform(trainT)]).tocsr(); Wc = sp.hstack([wv.transform(tc), cv.transform(tc)]).tocsr()
def auc(sc, y): P = sc[y == 1]; Nn = sc[y == 0]; return float(sum((a > b) + 0.5 * (a == b) for a in P for b in Nn) / (len(P) * len(Nn)))
def bal(sc, y, t): return float((np.mean(sc[y == 1] >= t) + np.mean(sc[y == 0] < t)) / 2)
res = {"n_train": len(trainT), "n_test": int(te.sum()), "jev_auc_vs_gold_test": round(auc(pc[te], g[te]), 3), "variants": {}}
for name, A, Ac in (("ngram", W, Wc), ("ngram_plus_embedding", sp.hstack([W, sp.csr_matrix(trainE)]).tocsr(), sp.hstack([Wc, sp.csr_matrix(Xc)]).tocsr())):
    for C in (1.0, 10.0):
        m = LogisticRegression(C=C, max_iter=4000).fit(A, trainY); h = m.predict_proba(Ac)[:, 1]
        line = max(np.arange(0.05, 0.96, 0.01), key=lambda t: np.mean(((h[tr] >= t) == (pc[tr] >= 0.5))))   # line copies Jev on the training rows, no gold
        res["variants"][f"{name}_C{C}"] = {"auc_vs_gold_test": round(auc(h[te], g[te]), 3), "bal_at_0_5": round(bal(h[te], g[te], 0.5), 3), "bal_at_line": round(bal(h[te], g[te], line), 3), "line": round(float(line), 2), "auc_vs_jev_label_test": round(auc(h[te], (pc[te] >= 0.5).astype(int)), 3)}
json.dump(res, open(OUT / "t173_function_ngram.json", "w"), indent=1); print(json.dumps(res)[:1500])
