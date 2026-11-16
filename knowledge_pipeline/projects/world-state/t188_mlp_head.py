"""T188 (B4): one-hidden-layer network on the joined embeddings (v6b + bge-small + e5-small), time-shifted protocol with all 51,067 training rows (ledger L2276 baseline: linear head 0.617). Prediction in ledger L2277.
Run (from projects/world-state): /workspace/models/embed-zs/.venv/bin/python -I t188_mlp_head.py"""
import json, sqlite3, numpy as np, pathlib, time
OUT = pathlib.Path("runs/pulse/t172")
ct = [r for r in json.load(open("runs/pulse/t170/t170_function_subjective.json"))["rows"] if "error" not in r]; q = [json.loads(l) for l in open(OUT / "t172_rows.jsonl")]; q2 = [json.loads(l) for l in open(OUT / "t187_rows.jsonl")]
def load(path): z = np.load(path); return np.vstack([z["q"], z["c"]])
E6 = load(OUT / "t173_embeddings.npz"); EB = load(OUT / "t176_emb_bge_small.npz"); EE = load(OUT / "t176_emb_e5_small.npz"); z = np.load(OUT / "t187_new_embeddings.npz")
p = np.concatenate([[r["p"] for r in q], [r["noul"]["function_subjective"] for r in ct]]); y0 = (p >= 0.5).astype(int); sid = [r["id"].split(":")[1] for r in q]
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); pub = {}
for i in set(sid): r = db.execute("select published from items where id=?", (i,)).fetchone(); pub[i] = r[0] if r and r[0] else None
ok = sorted([i for i in pub if pub[i]], key=lambda i: pub[i]); cut = ok[int(0.7 * len(ok))]; newest = set(i for i in ok if pub[i] > pub[cut])
is_test = np.array([s in newest for s in sid] + [False] * len(ct)); has_date = np.array([pub.get(s) is not None for s in sid] + [True] * len(ct)); tr = (~is_test) & has_date; te = is_test
grp0 = np.array(sid + [r["id"] for r in ct]); g2 = np.array([r["id"].split(":")[1] for r in q2]); y2 = np.array([r["p"] >= 0.5 for r in q2]).astype(int)
X0 = np.hstack([E6, EB, EE]); X2 = np.hstack([z["v6b"], z["bge"], z["e5"]]); Xt = np.vstack([X0[tr], X2]); yt = np.concatenate([y0[tr], y2]); gt = np.concatenate([grp0[tr], g2]); print("train", Xt.shape, "test", int(te.sum()), flush=True)
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import GroupKFold
def net(): return MLPClassifier(hidden_layer_sizes=(256,), activation="relu", early_stopping=True, validation_fraction=0.1, n_iter_no_change=3, max_iter=40, random_state=0)
def fit(s, yy, fp=0.0025, fn=0.05):
    neg = np.sort(s[yy == 0])[::-1]; hi = neg[int(np.floor(fp * len(neg)))]; pos = np.sort(s[yy == 1]); lo = pos[int(np.floor(fn * len(pos)))]; return lo, hi
t0 = time.time(); oof = np.zeros(len(yt))
for a, b in GroupKFold(5).split(Xt, yt, gt): oof[b] = net().fit(Xt[a], yt[a]).predict_proba(Xt[b])[:, 1]; print("fold", round(time.time() - t0), flush=True)
lo, hi = fit(oof, yt); h = net().fit(Xt, yt).predict_proba(X0[te])[:, 1]; yy = y0[te]; yes = h > hi; no = h < lo
res = {"rows": int(len(yt)), "test_rows": int(te.sum()), "mlp": {"coverage": round(float((yes | no).mean()), 3), "eff_tpr": round(1 - float(np.sum(no & (yy == 1))) / int((yy == 1).sum()), 3), "eff_fpr": round(float(np.sum(yes & (yy == 0))) / int((yy == 0).sum()), 4), "fp": int(np.sum(yes & (yy == 0))), "fn": int(np.sum(no & (yy == 1)))}, "linear_baseline_coverage": 0.617, "seconds": round(time.time() - t0)}
json.dump(res, open("runs/pulse/t179/t188_mlp_head.json", "w"), indent=1); print(json.dumps(res))
