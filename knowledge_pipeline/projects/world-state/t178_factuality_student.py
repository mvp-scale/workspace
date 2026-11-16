"""T178: CPU Factuality student: sentence embedding -> logistic head on Jev 'happened' (p>=0.5, never gold), grouped 5-fold CV by document; scored vs MAVEN-FACT gold yes. Prediction in ledger L2248.
Run (from projects/world-state): OUT=runs/pulse/t178 /workspace/models/embed-zs/.venv/bin/python -I t178_factuality_student.py"""
import json, os, sys, pathlib, time, numpy as np
sys.path.insert(0, ".")
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t178")); OUT.mkdir(parents=True, exist_ok=True)
rows = json.load(open("runs/pulse/t152/t152_factuality_maven.json"))["rows"]; text = {json.loads(l)["id"]: json.loads(l)["text"] for l in open("/workspace/data/anchors/maven_fact/items_T33b.jsonl")}
rows = [r for r in rows if r["id"] in text]; T = [text[r["id"]] for r in rows]; y_gold = np.array([r["yes"] for r in rows]).astype(int); p = np.array([r["happened"] for r in rows]); yj = (p >= 0.5).astype(int); doc = np.array([r["id"].split(":")[1] for r in rows])
from expert1_runtime import ExpertS
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); t0 = time.time(); X6 = np.array([e.student(t) for t in T], dtype=np.float32); print("v6b embed s", round(time.time() - t0), flush=True)
from sentence_transformers import SentenceTransformer
m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 128; Xb = m.encode(T, batch_size=64, normalize_embeddings=True, show_progress_bar=False); print("bge embed s", round(time.time() - t0), flush=True)
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
def auc(sc, y): P = sc[y == 1]; Nn = sc[y == 0]; return float(sum((a > b) + 0.5 * (a == b) for a in P for b in Nn) / (len(P) * len(Nn)))
def bal(sc, y, t): return float((np.mean(sc[y == 1] >= t) + np.mean(sc[y == 0] < t)) / 2)
res = {"n": len(rows), "jev_auc_vs_gold": round(auc(p, y_gold), 3), "jev_bal_at_0_5": round(bal(p, y_gold, 0.5), 3), "variants": {}}
for name, X in (("v6b", X6), ("bge_small", Xb), ("v6b_plus_bge", np.hstack([X6, Xb]))):
    for C in (1.0, 10.0):
        oof = np.zeros(len(rows)); lines = []
        for tr, te in GroupKFold(5).split(X, yj, doc):
            h = LogisticRegression(C=C, max_iter=3000).fit(X[tr], yj[tr]); oof[te] = h.predict_proba(X[te])[:, 1]
            ptr = h.predict_proba(X[tr])[:, 1]; lines.append((te, max(np.arange(0.05, 0.96, 0.01), key=lambda t: np.mean(((ptr >= t) == (yj[tr] == 1))))))
        bals = []   # line chosen on the training folds to copy Jev (no gold), applied to the held-out fold
        for te, t in lines: bals.append(bal(oof[te], y_gold[te], t))
        res["variants"][f"{name}_C{C}"] = {"auc_vs_gold": round(auc(oof, y_gold), 3), "bal_at_0_5": round(bal(oof, y_gold, 0.5), 3), "bal_at_train_line_mean_over_folds": round(float(np.mean(bals)), 3), "auc_vs_jev_label": round(auc(oof, yj), 3)}
json.dump(res, open(OUT / "t178_factuality_student.json", "w"), indent=1); print(json.dumps(res))
