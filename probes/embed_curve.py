#!/usr/bin/env python3
"""Learning curve: how close does each embedding model get to Clef Flash and Jev as its heads get more examples?

For the seven tone/text-type sets, a logistic head is trained on N examples from data/embed-zs/pools/<set>.jsonl
(probes/tone_pools.py: same labelling rule and sources as the probe set, probe texts excluded) and tested on every
probe item, which no head ever sees. N = 80, 250, 1000 and the whole pool; three random draws below the whole pool.
The head's strength (C) is picked by 3-fold cross-validation inside the training examples only.

Two inputs:
  text  the transcript text alone: one encode per window can feed every detector's head (the deployment design)
  ask   the question plus the text, as the earlier tests did
Writes data/embed-zs/curve/<model>.json.

    python probes/embed_curve.py BAAI/bge-small-en-v1.5 Qwen/Qwen3-Embedding-0.6B ...
"""
import json, sys
from pathlib import Path

import numpy as np
import torch
from sklearn.linear_model import LogisticRegressionCV
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).parent))
from embed_sweep import PROBES, fmt, load

POOLS, OUT = Path("/workspace/data/embed-zs/pools"), Path("/workspace/data/embed-zs/curve")
SETS = ["emotion_anger", "emotion_fear", "politeness_deference", "threat_civil", "phishing", "sarcasm_headlines", "sarcasm_isarcasm"]
NS = [80, 250, 1000, None]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for model in sys.argv[1:]:
        fq, _ = fmt(model); m = load(model, "cuda")
        enc = lambda xs: np.asarray(m.encode(xs, batch_size=32, normalize_embeddings=True), dtype=np.float32)
        res = {}
        for s in SETS:
            items = [json.loads(l) for l in open(PROBES / f"{s}.jsonl")]; q = items[0]["question"]["instructions"]
            pool = [json.loads(l) for l in open(POOLS / f"{s}.jsonl")]
            y_te = np.array([i["expected"] == "yes" for i in items]); y_pool = np.array([p["label"] == "yes" for p in pool])
            res[s] = {}
            for mode, f in (("text", lambda t: t), ("ask", lambda t: fq(q, t))):
                X_te, X_pool = enc([f(i["state"]) for i in items]), enc([f(p["text"]) for p in pool])
                res[s][mode] = {}
                for n in NS:
                    accs, aucs = [], []
                    for seed in ([0] if n is None else [0, 1, 2]):
                        rng = np.random.default_rng(seed)
                        if n is None: idx = np.arange(len(pool))
                        else:
                            pos, neg = np.where(y_pool)[0], np.where(~y_pool)[0]
                            idx = np.concatenate([rng.choice(pos, min(n // 2, len(pos)), replace=False), rng.choice(neg, min(n // 2, len(neg)), replace=False)])
                        clf = make_pipeline(StandardScaler(), LogisticRegressionCV(Cs=[0.003, 0.01, 0.03, 0.1, 0.3, 1.0], cv=3, max_iter=3000, scoring="accuracy"))
                        clf.fit(X_pool[idx], y_pool[idx]); sc = clf.decision_function(X_te)
                        accs.append(float(np.mean((sc > 0) == y_te))); aucs.append(float(roc_auc_score(y_te, sc)))
                    res[s][mode][str(n or len(pool))] = {"acc": round(float(np.mean(accs)), 4), "auc": round(float(np.mean(aucs)), 4), "n": int(n or len(pool))}
        tag = model.split("/")[-1]
        json.dump({"model": model, "sets": res}, open(OUT / f"{tag}.json", "w"), indent=1)
        for mode in ("text", "ask"):
            line = "  ".join(f"N={k:<5} {np.mean([list(res[s][mode].values())[j]['acc'] for s in SETS]):.3f}" for j, k in enumerate(["80", "250", "1000", "all"]))
            print(f"{tag:<34} {mode:<4} tone avg acc  {line}", flush=True)
        del m; torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
