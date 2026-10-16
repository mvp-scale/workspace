#!/usr/bin/env python3
"""Does a STAR-framed state help the CPU classifier (encoder + one logistic head per question)? Only the encoder's input
text changes, for training and test alike; the encoder, the head and the human labels stay fixed.

Inputs:  bare    the text
         star    "Situation: ... Task: ... Text: <the text>"   (frozen per set in probes/v2/star_states.json)
         filler  the same frame with generic words (the control for length and shape)
Encoders: e5-small-v2 (the CPU engine's; fp32 here, the engine runs it at int8) and potion-base-8M (static: it averages word
vectors, so a fixed frame should dilute the text rather than enrich it, which tests the mechanism).
Training: anger, politeness, phishing train on their ~2,000-example pools (data/embed-zs/pools, probe texts excluded) at
N = 80, 250 and the whole pool (3 draws below the pool) and are tested on the published items; manipulation, persuasion
(7 options) and contract clauses (3 options) have no pools, so 5-fold cross-validation inside the set, 3 shuffles.
Scored against the human labels; paired difference vs bare with a bootstrap 95% interval over test items.

    python probes/star_cpu_test.py     # writes data/embed-zs/star_cpu.json
"""
import json, random, sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

V2, POOLS = Path("/workspace/probes/v2"), Path("/workspace/data/embed-zs/pools")
POOL_SETS = ["emotion_anger", "politeness_deference", "phishing"]
CV_SETS = ["manipulation_dialogue", "persuasion_appeals", "checklist_contractnli"]
STAR = json.load(open(V2 / "star_states.json"))


def frame(kind, s, text):
    if kind == "bare": return text
    f = STAR["sets"][s] if kind == "star" else STAR["filler"]
    return f"Situation: {f['situation']} Task: {f['task']} Text: {text}"


def head(): return LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced")


def boot(d, rng):
    b = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(2000)); return [round(b[50], 4), round(b[1949], 4)]


def main():
    import torch
    from sentence_transformers import SentenceTransformer
    from model2vec import StaticModel
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    e5 = SentenceTransformer("intfloat/e5-small-v2", device=dev); st = StaticModel.from_pretrained("minishlab/potion-base-8M")
    ENC = {"e5-small": lambda xs: e5.encode(["query: " + x for x in xs], batch_size=64, normalize_embeddings=True),
           "static": lambda xs: (lambda v: v / np.linalg.norm(v, axis=1, keepdims=True))(st.encode(xs))}
    rng = random.Random(0); out = {}
    for ename, enc in ENC.items():
        out[ename] = {}
        for s in POOL_SETS + CV_SETS:
            items = [json.loads(l) for l in open(V2 / f"{s}.jsonl")]
            y_te = np.array([i["expected"] for i in items])
            X_te = {k: enc([frame(k, s, i["state"]) for i in items]) for k in ("bare", "star", "filler")}
            res = {}
            if s in POOL_SETS:
                pool = [json.loads(l) for l in open(POOLS / f"{s}.jsonl")]; y_pool = np.array([p["label"] for p in pool])
                X_pool = {k: enc([frame(k, s, p["text"]) for p in pool]) for k in X_te}
                for n in (80, 250, len(pool)):
                    right = {k: [] for k in X_te}
                    for d in range(3 if n < len(pool) else 1):
                        r = np.random.default_rng(d); pos, neg = np.where(y_pool == "yes")[0], np.where(y_pool != "yes")[0]
                        idx = np.arange(len(pool)) if n >= len(pool) else np.concatenate([r.choice(pos, n // 2, replace=False), r.choice(neg, n - n // 2, replace=False)])
                        for k in X_te: right[k].append(head().fit(X_pool[k][idx], y_pool[idx]).predict(X_te[k]) == y_te)
                    res[f"train {n}"] = {k: np.mean(right[k], axis=0) for k in right}   # per test item: share of draws right
            else:
                right = {k: [] for k in X_te}
                for sh in range(3):
                    pred = {k: np.empty(len(items), dtype=object) for k in X_te}
                    for a, b in StratifiedKFold(5, shuffle=True, random_state=sh).split(X_te["bare"], y_te):
                        for k in X_te: pred[k][b] = head().fit(X_te[k][a], y_te[a]).predict(X_te[k][b])
                    for k in X_te: right[k].append(pred[k] == y_te)
                res["5-fold"] = {k: np.mean(right[k], axis=0) for k in right}
            out[ename][s] = {}
            for setting, r in res.items():
                row = {k: round(float(r[k].mean()), 4) for k in r}
                for k in ("star", "filler"):
                    d = list(r[k] - r["bare"]); row[k + "_vs_bare"] = {"diff": round(float(np.mean(d)), 4), "ci95": boot(d, rng)}
                out[ename][s][setting] = row
                print(f"{ename:9s} {s:22s} {setting:11s} bare {row['bare']:.3f}  star {row['star']:.3f}  filler {row['filler']:.3f}  "
                      f"star-bare {row['star_vs_bare']['diff']:+.3f} {row['star_vs_bare']['ci95']}  filler-bare {row['filler_vs_bare']['diff']:+.3f}", flush=True)
    json.dump(out, open("/workspace/data/embed-zs/star_cpu.json", "w"), indent=1)


if __name__ == "__main__":
    main()
