"""T177: Qwen3-Embedding-0.6B vs v6b/bge-small/e5-small on the SAME reduced training set (3,000 queue sentences + 1,776 CheckThat Jev-labelled rows), scored on the 300 CheckThat test gold rows. Chunked with a progress file and a hard stop. Design in ledger.
Run: CAP_MIN=45 OUT=<runs/pulse/t172> /workspace/models/embed-zs/.venv/bin/python -I t177_qwen_reduced.py  (from projects/world-state)"""
import json, csv, os, time, pathlib, numpy as np
OUT = pathlib.Path(os.environ["OUT"]); CAP = float(os.environ.get("CAP_MIN", 45)) * 60; T0 = time.time(); D = "/workspace/data/anchors/checkthat_subj/"; split = {}
for f, name in (("train_en.tsv", "train"), ("dev_en.tsv", "dev"), ("dev_test_en.tsv", "devtest"), ("test_en_labeled.tsv", "test")):
    for r in csv.DictReader(open(D + f), delimiter="\t"): split["ct:" + r["sentence_id"]] = name
text = {json.loads(l)["id"]: json.loads(l)["text"] for l in open(D + "items_T30.jsonl")}
ct = [r for r in json.load(open("runs/pulse/t170/t170_function_subjective.json"))["rows"] if "error" not in r and r["id"] in text]
q = [json.loads(l) for l in open(OUT / "t172_rows.jsonl")]; NQ = 3000; tc = [text[r["id"]] for r in ct]; tq = [r["text"] for r in q][:NQ]
pc = np.array([r["noul"]["function_subjective"] for r in ct]); pq = np.array([r["p"] for r in q])[:NQ]; S = np.array([split[r["id"]] for r in ct]); g = np.array([r["gold"] == "SUBJ" for r in ct]).astype(int)
tr = np.isin(S, ["train", "dev", "devtest"]); te = S == "test"; y = np.concatenate([(pq >= 0.5), (pc[tr] >= 0.5)]).astype(int)
from sentence_transformers import SentenceTransformer
m = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B", device="cpu"); m.max_seq_length = 128
allt = tc + tq; E = []; prog = OUT / "t177_progress.txt"
for i in range(0, len(allt), 200):
    if time.time() - T0 > CAP: open(prog, "w").write(f"STOPPED at {i} of {len(allt)} after {round(time.time() - T0)} s"); raise SystemExit("time cap")
    E.append(m.encode(allt[i:i + 200], batch_size=32, normalize_embeddings=True, show_progress_bar=False)); open(prog, "w").write(f"{i + 200} of {len(allt)} at {round(time.time() - T0)} s")
E = np.vstack(E); Ec, Eq = E[:len(tc)], E[len(tc):]; np.savez(OUT / "t177_qwen_reduced_emb.npz", c=Ec, q=Eq)
from sklearn.linear_model import LogisticRegression
def auc(sc, yy): P = sc[yy == 1]; Nn = sc[yy == 0]; return float(sum((a > b) + 0.5 * (a == b) for a in P for b in Nn) / (len(P) * len(Nn)))
def bal(sc, yy, t): return float((np.mean(sc[yy == 1] >= t) + np.mean(sc[yy == 0] < t)) / 2)
res = {"n_train": int(len(y)), "n_test": int(te.sum()), "jev_auc_vs_gold_test": round(auc(pc[te], g[te]), 3), "encoders": {}}
srcs = {"qwen3_0_6b": (Ec, Eq)}
z = np.load(OUT / "t173_embeddings.npz"); srcs["v6b"] = (z["c"], z["q"][:NQ])
for nm, f in (("bge_small", "t176_emb_bge_small.npz"), ("e5_small", "t176_emb_e5_small.npz")):
    z = np.load(OUT / f); srcs[nm] = (z["c"], z["q"][:NQ])
for nm, (C_, Q_) in srcs.items():
    for Cc in (1.0, 10.0):
        h = LogisticRegression(C=Cc, max_iter=3000).fit(np.vstack([Q_, C_[tr]]), y).predict_proba(C_)[:, 1]
        res["encoders"][f"{nm}_C{Cc}"] = {"auc_vs_gold_test": round(auc(h[te], g[te]), 3), "bal_at_0_5": round(bal(h[te], g[te], 0.5), 3), "auc_vs_jev_label_test": round(auc(h[te], (pc[te] >= 0.5).astype(int)), 3)}
res["seconds"] = round(time.time() - T0); json.dump(res, open(OUT / "t177_qwen_reduced.json", "w"), indent=1); print(json.dumps(res))
