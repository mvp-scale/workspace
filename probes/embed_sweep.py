#!/usr/bin/env python3
"""Same pipeline, many embedding models: how accurate and how fast on CPU can each one be made?

For every model, on the 21 published probe sets:
  cosine      option with the highest cosine to the item (no labels)
  calibrated  cosine minus the option's score for content-free states "N/A", "", "[MASK]" (Zhao et al. 2021; no labels)
  whitened    cosine after whitening with this model's own unlabelled vectors (no labels)
  learned     logistic head on [q * o, o], 5-fold, every item scored by a fit that never saw it (labels)
and the CPU time for one call (option vectors cached): a short comment and a dialogue, median of 12.
Vectors are cached in data/embed-zs/vectors/<model>/ (same format as embed_readouts.py); results in data/embed-zs/sweep/.

    python probes/embed_sweep.py BAAI/bge-small-en-v1.5 intfloat/e5-small-v2 ...
"""
import json, statistics, sys, time
from pathlib import Path

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

PROBES, VEC, OUT = Path("/workspace/probes/v2"), Path("/workspace/data/embed-zs/vectors"), Path("/workspace/data/embed-zs/sweep")
SETS = ("emotion_anger emotion_fear politeness_deference threat_civil phishing sarcasm_headlines sarcasm_isarcasm "
        "nli_snli persuasion_appeals fallacy_logic darkpatterns checklist_contractnli manipulation_dialogue memsafety websec "
        "mmlu_global_facts mmlu_high_school_geography mmlu_marketing mmlu_high_school_psychology mmlu_nutrition "
        "mmlu_high_school_us_history").split()
FREE = ["N/A", "", "[MASK]"]


def fmt(model):
    """How each family expects its input; options get the same treatment so both sides live in one space."""
    n = model.lower()
    if "qwen3-embedding" in n: return (lambda q, s: f"Instruct: {q}\nQuery:{s}"), (lambda d: d)
    if "e5-" in n: return (lambda q, s: f"query: {q}\n{s}"), (lambda d: f"query: {d}")
    return (lambda q, s: f"{q}\n{s}"), (lambda d: d)


def options(it):
    q, c = it["question"], it["question"].get("criteria") or {}
    if q["type"] == "noul":
        return [(l, c.get({"yes": "true", "no": "false"}[l], l)) for l in it["labels"]]
    return [(l, c.get(l, l)) for l in it["labels"]]


def load(model, device):
    if "potion" in model.lower() or "model2vec" in model.lower():
        from sentence_transformers.models import StaticEmbedding
        return SentenceTransformer(modules=[StaticEmbedding.from_model2vec(model)], device=device)
    kw = {"torch_dtype": torch.bfloat16} if device == "cuda" and "qwen3" in model.lower() else {}
    m = SentenceTransformer(model, device=device, model_kwargs=kw)
    m.max_seq_length = min(m.max_seq_length or 512, 4096)
    return m


def run(model):
    tag = model.split("/")[-1]; cache = VEC / tag; cache.mkdir(parents=True, exist_ok=True)
    fq, fo = fmt(model)
    m = load(model, "cuda")
    enc = lambda xs: np.asarray(m.encode(xs, batch_size=32, normalize_embeddings=True), dtype=np.float32)
    D = {}
    for s in SETS:
        items = [json.loads(l) for l in open(PROBES / f"{s}.jsonl")]
        f = cache / f"{s}.npz"
        if f.exists():
            z = np.load(f, allow_pickle=True); Q, O = z["q"].astype(np.float32), [np.asarray(x, np.float32) for x in z["o"]]
        else:
            Q = enc([fq(i["question"]["instructions"], i["state"]) for i in items])
            O = [enc([fo(d) for _, d in options(i)]) for i in items]
            np.savez(f, q=Q, o=np.array(O, dtype=object))
        cf = {qq: enc([fq(qq, t) for t in FREE]) for qq in {i["question"]["instructions"] for i in items}}
        D[s] = (items, Q, O, cf)
    allv = np.vstack([np.vstack([D[s][1]] + D[s][2]) for s in SETS]); mu = allv.mean(0)
    U, S_, _ = np.linalg.svd(np.cov((allv - mu).T)); W = U @ np.diag(1 / np.sqrt(S_ + 1e-3)) @ U.T
    wh = lambda v: (lambda x: x / np.linalg.norm(x, axis=-1, keepdims=True))((v - mu) @ W)
    feats = lambda q, o: np.hstack([q[None, :] * o, o])
    res = {}
    for s in SETS:
        items, Q, O, cf = D[s]; n = len(items); labs = [[l for l, _ in options(i)] for i in items]
        right = lambda sc: float(np.mean([labs[k][int(np.argmax(sc[k]))] == items[k]["expected"] for k in range(n)]))
        cos = [O[k] @ Q[k] for k in range(n)]
        cal = [O[k] @ Q[k] - (O[k] @ cf[items[k]["question"]["instructions"]].T).mean(1) for k in range(n)]
        Qw = wh(Q); whit = [wh(O[k]) @ Qw[k] for k in range(n)]
        learned = [None] * n
        for tr, te in KFold(5, shuffle=True, random_state=0).split(np.arange(n)):
            X = np.vstack([feats(Q[k], O[k]) for k in tr]); y = np.concatenate([[l == items[k]["expected"] for l in labs[k]] for k in tr])
            clf = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=3000, class_weight="balanced")).fit(X, y)
            for k in te: learned[k] = clf.decision_function(feats(Q[k], O[k]))
        res[s] = {"cosine": right(cos), "calibrated": right(cal), "whitened": right(whit), "learned": right(learned)}
    del m; torch.cuda.empty_cache()
    # CPU timing: one call = encode the question + text; option vectors are cached
    mc = load(model, "cpu"); timing = {}
    for s in ("emotion_anger", "manipulation_dialogue"):
        items = [json.loads(l) for l in open(PROBES / f"{s}.jsonl")][:12]
        qs = [fq(i["question"]["instructions"], i["state"]) for i in items]; mc.encode(qs[:2]); ts = []
        for q in qs:
            t = time.perf_counter(); mc.encode([q]); ts.append((time.perf_counter() - t) * 1000)
        timing[s] = round(statistics.median(ts), 2)
    dim = int(allv.shape[1]); params = sum(p.numel() for p in mc.parameters())
    out = {"model": model, "dim": dim, "params": params, "cpu_ms": timing, "sets": res}
    OUT.mkdir(parents=True, exist_ok=True); json.dump(out, open(OUT / f"{tag}.json", "w"), indent=1)
    g = lambda keys, k: np.mean([res[s][k] for s in keys])
    tone = SETS[:7]; judge = SETS[7:13]; mmlu = SETS[15:]
    print(f"{tag:<34} {params/1e6:7.0f}M dim {dim:<5} cpu {timing['emotion_anger']:7.1f}/{timing['manipulation_dialogue']:7.1f} ms | "
          f"tone cos {g(tone,'cosine'):.2f} cal {g(tone,'calibrated'):.2f} wh {g(tone,'whitened'):.2f} learned {g(tone,'learned'):.2f} | "
          f"judge learned {g(judge,'learned'):.2f} | mmlu learned {g(mmlu,'learned'):.2f}", flush=True)


if __name__ == "__main__":
    for mdl in sys.argv[1:]:
        try: run(mdl)
        except Exception as e: print(f"{mdl}: FAILED {type(e).__name__}: {str(e)[:200]}", flush=True)
