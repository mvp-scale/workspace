"""T187 phase 2: extend the time-shifted learning curve (t186) with the newly labelled sentences (t187_rows.jsonl): embed them with v6b, bge-small and e5-small, then coverage vs training rows at the L2254 rule, test set unchanged (newest 30% of stories). Prediction in ledger L2270 (training grows to about 51,000 rows instead of 75,000, see the note after it).
Run (from projects/world-state): /workspace/models/embed-zs/.venv/bin/python -I t187_scaled_curve.py"""
import json, sqlite3, time, numpy as np, pathlib, sys
sys.path.insert(0, ".")
OUT = pathlib.Path("runs/pulse/t172")
ct = [r for r in json.load(open("runs/pulse/t170/t170_function_subjective.json"))["rows"] if "error" not in r]; q = [json.loads(l) for l in open(OUT / "t172_rows.jsonl")]; q2 = [json.loads(l) for l in open(OUT / "t187_rows.jsonl")]
def load(path): z = np.load(path); return np.vstack([z["q"], z["c"]])
E6 = load(OUT / "t173_embeddings.npz"); EB = load(OUT / "t176_emb_bge_small.npz"); EE = load(OUT / "t176_emb_e5_small.npz")
emb2 = OUT / "t187_new_embeddings.npz"
if emb2.exists(): z = np.load(emb2); N6, NB, NE = z["v6b"], z["bge"], z["e5"]
else:
    from expert1_runtime import ExpertS; from sentence_transformers import SentenceTransformer
    T = [r["text"] for r in q2]; t0 = time.time(); e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); N6 = np.array([e.student(t) for t in T], dtype=np.float32); print("v6b", round(time.time() - t0), flush=True)
    m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 128; NB = m.encode(T, batch_size=64, normalize_embeddings=True, show_progress_bar=False); print("bge", round(time.time() - t0), flush=True)
    m = SentenceTransformer("intfloat/e5-small-v2", device="cpu"); m.max_seq_length = 128; NE = m.encode(["query: " + t for t in T], batch_size=64, normalize_embeddings=True, show_progress_bar=False); print("e5", round(time.time() - t0), flush=True)
    np.savez(emb2, v6b=N6, bge=NB, e5=NE)
# same train/test as t185/t186: old queue sentences + CheckThat rows, test = newest 30% of stories; plus the new sentences (all from stories at or before the cut)
p = np.concatenate([[r["p"] for r in q], [r["noul"]["function_subjective"] for r in ct]]); y0 = (p >= 0.5).astype(int); sid = [r["id"].split(":")[1] for r in q]
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); pub = {}
for i in set(sid): r = db.execute("select published from items where id=?", (i,)).fetchone(); pub[i] = r[0] if r and r[0] else None
ok = sorted([i for i in pub if pub[i]], key=lambda i: pub[i]); cut = ok[int(0.7 * len(ok))]; newest = set(i for i in ok if pub[i] > pub[cut])
is_test = np.array([s in newest for s in sid] + [False] * len(ct)); has_date = np.array([pub.get(s) is not None for s in sid] + [True] * len(ct)); tr = (~is_test) & has_date; te = is_test
grp0 = np.array(sid + [r["id"] for r in ct]); y2 = np.array([r["p"] >= 0.5 for r in q2]).astype(int); g2 = np.array([r["id"].split(":")[1] for r in q2])
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
def fit(s, yy, fp=0.0025, fn=0.05):
    neg = np.sort(s[yy == 0])[::-1]; hi = neg[int(np.floor(fp * len(neg)))]; pos = np.sort(s[yy == 1]); lo = pos[int(np.floor(fn * len(pos)))]; return lo, hi
res = {"train_up_to": pub[cut], "test_rows": int(te.sum()), "new_sentences": len(q2), "points": []}
sets = {"v6b": (E6, N6), "joined": (np.hstack([E6, EB, EE]), np.hstack([N6, NB, NE]))}
for extra in (0, 10000, 20000, len(q2)):
    row = {"rows": int(tr.sum()) + extra}
    for name, (X0, X2) in sets.items():
        Xt = np.vstack([X0[tr], X2[:extra]]) if extra else X0[tr]; yt = np.concatenate([y0[tr], y2[:extra]]); gt = np.concatenate([grp0[tr], g2[:extra]]); oof = np.zeros(len(yt))
        for a, b in GroupKFold(5).split(Xt, yt, gt): oof[b] = LogisticRegression(C=1.0, max_iter=2000).fit(Xt[a], yt[a]).predict_proba(Xt[b])[:, 1]
        lo, hi = fit(oof, yt); h = LogisticRegression(C=1.0, max_iter=2000).fit(Xt, yt).predict_proba(X0[te])[:, 1]; yy = y0[te]; yes = h > hi; no = h < lo
        row[name] = {"coverage": round(float((yes | no).mean()), 3), "eff_tpr": round(1 - float(np.sum(no & (yy == 1))) / int((yy == 1).sum()), 3), "eff_fpr": round(float(np.sum(yes & (yy == 0))) / int((yy == 0).sum()), 4)}
    res["points"].append(row); print(row, flush=True)
json.dump(res, open("runs/pulse/t179/t187_scaled_curve.json", "w"), indent=1)
