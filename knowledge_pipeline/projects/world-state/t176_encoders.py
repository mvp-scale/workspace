"""T176: encoder comparison for the Function student. Same rows and labels as t172/t173; encoders from the local HF cache only. Saves embeddings per encoder; time-capped.
Run (from projects/world-state): CAP_MIN=50 OUT=runs/pulse/t172 /workspace/models/embed-zs/.venv/bin/python -I t176_encoders.py   Prediction in ledger L2238."""
import json, csv, os, time, pathlib, numpy as np
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t172")); CAP = float(os.environ.get("CAP_MIN", 50)) * 60; T0 = time.time(); D = "/workspace/data/anchors/checkthat_subj/"; split = {}
for f, name in (("train_en.tsv", "train"), ("dev_en.tsv", "dev"), ("dev_test_en.tsv", "devtest"), ("test_en_labeled.tsv", "test")):
    for r in csv.DictReader(open(D + f), delimiter="\t"): split["ct:" + r["sentence_id"]] = name
text = {json.loads(l)["id"]: json.loads(l)["text"] for l in open(D + "items_T30.jsonl")}
ct = [r for r in json.load(open("runs/pulse/t170/t170_function_subjective.json"))["rows"] if "error" not in r and r["id"] in text]
q = [json.loads(l) for l in open(OUT / "t172_rows.jsonl")]; tc = [text[r["id"]] for r in ct]; tq = [r["text"] for r in q]
pc = np.array([r["noul"]["function_subjective"] for r in ct]); pq = np.array([r["p"] for r in q]); S = np.array([split[r["id"]] for r in ct]); g = np.array([r["gold"] == "SUBJ" for r in ct]).astype(int)
tr = np.isin(S, ["train", "dev", "devtest"]); te = S == "test"; y = np.concatenate([(pq >= 0.5), (pc[tr] >= 0.5)]).astype(int)
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
def auc(sc, yy): P = sc[yy == 1]; Nn = sc[yy == 0]; return float(sum((a > b) + 0.5 * (a == b) for a in P for b in Nn) / (len(P) * len(Nn)))
def bal(sc, yy, t): return float((np.mean(sc[yy == 1] >= t) + np.mean(sc[yy == 0] < t)) / 2)
res = {"jev_auc_vs_gold_test": round(auc(pc[te], g[te]), 3), "encoders": {}}
for name, mid, pre in (("bge_small", "BAAI/bge-small-en-v1.5", ""), ("e5_small", "intfloat/e5-small-v2", "query: "), ("qwen3_0_6b", "Qwen/Qwen3-Embedding-0.6B", "")):
    if time.time() - T0 > CAP: res["encoders"][name] = "skipped: time cap"; continue
    f = OUT / f"t176_emb_{name}.npz"
    if f.exists(): z = np.load(f); Ec, Eq = z["c"], z["q"]; sec = None
    else:
        t1 = time.time(); m = SentenceTransformer(mid, device="cpu"); m.max_seq_length = 128
        Ec = m.encode([pre + t for t in tc], batch_size=64, normalize_embeddings=True, show_progress_bar=False); Eq = m.encode([pre + t for t in tq], batch_size=64, normalize_embeddings=True, show_progress_bar=False)
        sec = time.time() - t1; np.savez(f, c=Ec, q=Eq); print(name, "embed s", round(sec), flush=True)
    X = np.vstack([Eq, Ec[tr]]); a = LogisticRegression(C=1.0, max_iter=3000).fit(X, y); h = a.predict_proba(Ec)[:, 1]
    line = max(np.arange(0.05, 0.96, 0.01), key=lambda t: np.mean(((h[tr] >= t) == (pc[tr] >= 0.5))))
    res["encoders"][name] = {"auc_vs_gold_test": round(auc(h[te], g[te]), 3), "bal_at_0_5": round(bal(h[te], g[te], 0.5), 3), "bal_at_line": round(bal(h[te], g[te], line), 3), "auc_vs_jev_label_test": round(auc(h[te], (pc[te] >= 0.5).astype(int)), 3), "embed_seconds": None if sec is None else round(sec), "sentences_per_second": None if sec is None else round((len(tc) + len(tq)) / sec, 1)}
    json.dump(res, open(OUT / "t176_encoders.json", "w"), indent=1); print(name, res["encoders"][name], flush=True)
print("done", round(time.time() - T0))
