"""CPU time head: v6b student embedding (title + body windows, as sparse_topic_embed.py) -> logistic head trained on Jev time_recent (p>=0.5), 5-fold out-of-fold, scored on the strict publish-date truth of t164_time_judge_strict.py.
Run (from projects/world-state): N=40 for a smoke test; OUT=runs/pulse/t165 /workspace/models/embed-zs/.venv/bin/python -I t165_time_head.py  -> t165_time_head.json"""
import json, os, sys, time, sqlite3, pathlib, random, numpy as np
sys.path.insert(0, "."); sys.path.insert(0, "/workspace/knowledge_pipeline/projects/world-state")
from expert1_runtime import ExpertS; from article_reader import ArticleReader
import importlib.util
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t165")); OUT.mkdir(parents=True, exist_ok=True); N = int(os.environ.get("N", "0"))
src = open("t164_time_judge_strict.py").read().split("db = sqlite3.connect")[0]; ns = {"__name__": "x"}; exec(src, ns)
import datetime as dt
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True)
rows = []
for i, p in ns["p_of"].items():
    q = db.execute("select title, body, published from items where id=?", (i,)).fetchone()
    if not q or not q[1] or not q[2]: continue
    pub = dt.datetime.fromisoformat(q[2].replace("Z", "+00:00"))
    ds = [x for x in (ns["days_before"](s, pub) for s in ns["PAT"].findall(q[1])) if x is not None]
    truth = (1 if min(ds) <= 7 else (0 if min(ds) > 30 else None)) if ds else None
    rows.append({"id": i, "title": q[0] or "", "body": q[1], "p": p, "truth": truth})
random.Random(0).shuffle(rows); rows = rows[:N] if N else rows
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); A = ArticleReader(e); t0 = time.time(); X = []
for k, r in enumerate(rows):
    X.append(np.mean([e.student(r["title"] + ". " + w) for w in A.windows(r["body"])], 0))
    if k % 100 == 0: print(k, round(time.time() - t0), flush=True)
X = np.array(X, dtype=np.float32); sec = time.time() - t0; print("embed seconds", round(sec), "per story", round(sec / len(rows), 3), flush=True)
if N: sys.exit()
from sklearn.linear_model import LogisticRegression
y = np.array([r["p"] >= 0.5 for r in rows]).astype(int); oof = np.zeros(len(rows)); folds = np.arange(len(rows)) % 5
for f in range(5):
    m = LogisticRegression(C=1.0, max_iter=2000).fit(X[folds != f], y[folds != f]); oof[folds == f] = m.predict_proba(X[folds == f])[:, 1]
def auc(ps, ts):
    pos = [p for p, t in zip(ps, ts) if t == 1]; neg = [p for p, t in zip(ps, ts) if t == 0]
    return sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))
d = [k for k, r in enumerate(rows) if r["truth"] is not None]
res = {"stories": len(rows), "decidable": len(d), "jev_positive_share": float(y.mean()), "auroc_head_vs_truth": auc([oof[k] for k in d], [rows[k]["truth"] for k in d]), "auroc_jev_vs_truth": auc([rows[k]["p"] for k in d], [rows[k]["truth"] for k in d]), "auroc_head_vs_jev_label": auc(list(oof), list(y)), "embed_seconds": round(sec)}
json.dump(res, open(OUT / "t165_time_head.json", "w"), indent=1); print(res)
