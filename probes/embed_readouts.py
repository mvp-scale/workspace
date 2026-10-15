#!/usr/bin/env python3
"""Is the answer in the embedding's vector space, and how much of it can each readout extract?

Every item becomes one query vector q = emb("Instruct: <question>\nQuery:<state>") and one vector o_k per option
(its description). Four readouts, from no learning to the per-task ceiling:

  cosine     score_k = cos(q, o_k)                              no labels, no training (what we ran before)
  whitened   cosine after removing the space's shared bias      no labels: mean/covariance from unlabelled vectors
  universal  score_k = w . [q * o_k, o_k]  (learned diagonal     trained ONCE on the other sets' questions, never on
             bilinear map, a stripped-down kev pointer head)     this set; zero labels from the task being tested
  ceiling    same readout, 5-fold cross-validated inside the     how much answer is in the vectors at all, given
             set                                                 plenty of labels from this task

    python probes/embed_readouts.py --model Qwen/Qwen3-Embedding-4B
"""
import argparse, json
from pathlib import Path

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

PROBES = Path("/workspace/probes/v2")
SETS = ("emotion_anger emotion_fear politeness_deference threat_civil phishing sarcasm_headlines sarcasm_isarcasm "
        "nli_snli persuasion_appeals fallacy_logic darkpatterns checklist_contractnli manipulation_dialogue memsafety websec "
        "mmlu_global_facts mmlu_high_school_geography mmlu_marketing mmlu_high_school_psychology mmlu_nutrition "
        "mmlu_high_school_us_history").split()


def options(it):
    q, c = it["question"], it["question"].get("criteria") or {}
    if q["type"] == "noul":
        return [(l, c.get({"yes": "true", "no": "false"}[l], l)) for l in it["labels"]]
    return [(l, c.get(l, l)) for l in it["labels"]]


def encode(m, s, cache):
    f = cache / f"{s}.npz"
    items = [json.loads(l) for l in open(PROBES / f"{s}.jsonl")]
    if f.exists():
        z = np.load(f, allow_pickle=True); return items, z["q"], [np.asarray(x, dtype=np.float32) for x in z["o"]]
    q = m.encode([f"Instruct: {i['question']['instructions']}\nQuery:{i['state']}" for i in items], batch_size=16, normalize_embeddings=True)
    o = [m.encode([d for _, d in options(i)], normalize_embeddings=True) for i in items]
    np.savez(f, q=q, o=np.array(o, dtype=object)); return items, q, o


def feats(q, o): return np.hstack([q[None, :] * o, o])  # one row per option


def rows(items, Q, O, idx):
    X, y = [], []
    for i in idx:
        labs = [l for l, _ in options(items[i])]
        X.append(feats(Q[i], O[i])); y += [l == items[i]["expected"] for l in labs]
    return np.vstack(X), np.array(y)


def predict(clf, items, Q, O, idx):
    ok = []
    for i in idx:
        s = clf.decision_function(feats(Q[i], O[i])); labs = [l for l, _ in options(items[i])]
        ok.append(labs[int(np.argmax(s))] == items[i]["expected"])
    return float(np.mean(ok))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--model", default="Qwen/Qwen3-Embedding-4B"); ap.add_argument("--device", default="cuda")
    a = ap.parse_args()
    tag = a.model.split("/")[-1]; cache = Path("/workspace/data/embed-zs/vectors") / tag; cache.mkdir(parents=True, exist_ok=True)
    m = SentenceTransformer(a.model, device=a.device, model_kwargs={"torch_dtype": torch.bfloat16} if a.device == "cuda" else {})
    D = {s: encode(m, s, cache) for s in SETS}

    # whitening statistics from every query and option vector, labels unused
    allv = np.vstack([np.vstack([D[s][1]] + list(D[s][2])) for s in SETS])
    mu = allv.mean(0); U, S, _ = np.linalg.svd(np.cov((allv - mu).T)); W = U @ np.diag(1 / np.sqrt(S + 1e-3)) @ U.T
    wh = lambda v: (lambda x: x / np.linalg.norm(x, axis=-1, keepdims=True))((v - mu) @ W)

    fam = lambda s: "mmlu" if s.startswith("mmlu_") else s
    out = {}
    for s in SETS:
        items, Q, O = D[s]; n = len(items); idx = np.arange(n)
        cos = np.mean([options(items[i])[int(np.argmax(O[i] @ Q[i]))][0] == items[i]["expected"] for i in idx])
        Qw = wh(Q); wcos = np.mean([options(items[i])[int(np.argmax(wh(O[i]) @ Qw[i]))][0] == items[i]["expected"] for i in idx])
        Xtr, ytr = [], []
        for t in SETS:
            if fam(t) == fam(s): continue
            it2, Q2, O2 = D[t]; X, y = rows(it2, Q2, O2, range(len(it2))); Xtr.append(X); ytr.append(y)
        uni = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=3000, class_weight="balanced")).fit(np.vstack(Xtr), np.concatenate(ytr))
        universal = predict(uni, items, Q, O, idx)
        accs = []
        for tr, te in KFold(5, shuffle=True, random_state=0).split(idx):
            X, y = rows(items, Q, O, tr)
            accs.append(predict(make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=3000, class_weight="balanced")).fit(X, y), items, Q, O, te) * len(te))
        ceiling = sum(accs) / n
        out[s] = {"n": n, "cosine": round(float(cos), 3), "whitened": round(float(wcos), 3), "universal": round(universal, 3), "ceiling": round(ceiling, 3)}
        print(f"{s:<30} n={n:<4} cosine {cos:.2f}  whitened {wcos:.2f}  universal {universal:.2f}  ceiling {ceiling:.2f}", flush=True)
    json.dump(out, open(cache.parent.parent / f"readouts-{tag}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
