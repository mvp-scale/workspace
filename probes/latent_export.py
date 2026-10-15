#!/usr/bin/env python3
"""Export what the Latent lab page (/latent) draws, from the cached Qwen3-Embedding vectors of probes/embed_readouts.py.

Per set, data/embed-zs/latent/<model>/<set>.json holds, for every item:
  map        2-D position of the item's vector (principal components of the raw space, and of the whitened space)
  scores     one score per option for each readout: cosine, whitened cosine, learned (5-fold, item always held out),
             plus Clef Flash's and Jev's stored probabilities on the same item
and, for the first DRILL items, the full vectors needed to show the arithmetic dimension by dimension.
Run after probes/embed_readouts.py or probes/embed_sweep.py (which cache the vectors).

    python probes/latent_export.py --model Qwen3-Embedding-4B
"""
import argparse, json
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

PROBES, VEC, RUNS = Path("/workspace/probes/v2"), Path("/workspace/data/embed-zs/vectors"), Path("/workspace/data/probe-runs-v2")
OUT = Path("/workspace/data/embed-zs/latent")
DRILL = 12
NAMES = {"emotion_anger": "Anger", "emotion_fear": "Fear", "politeness_deference": "Politeness", "threat_civil": "Threat",
         "phishing": "Phishing email", "sarcasm_headlines": "Sarcasm (headlines)", "sarcasm_isarcasm": "Sarcasm (tweets)",
         "nli_snli": "Does B follow from A", "persuasion_appeals": "Persuasion strategy", "fallacy_logic": "Logical fallacy",
         "darkpatterns": "Dark pattern type", "checklist_contractnli": "Contract clause check", "manipulation_dialogue": "Manipulation in dialogue",
         "memsafety": "C memory bug", "websec": "Web vulnerability", "mmlu_global_facts": "Global facts", "mmlu_high_school_geography": "Geography",
         "mmlu_marketing": "Marketing", "mmlu_high_school_psychology": "Psychology", "mmlu_nutrition": "Nutrition", "mmlu_high_school_us_history": "US history"}
GROUP = lambda s: ("World knowledge" if s.startswith("mmlu_") else "Code security" if s in ("memsafety", "websec")
                   else "Reading and judging" if s in ("nli_snli", "persuasion_appeals", "fallacy_logic", "darkpatterns", "checklist_contractnli", "manipulation_dialogue")
                   else "Tone and text type")


def options(it):
    q, c = it["question"], it["question"].get("criteria") or {}
    if q["type"] == "noul":
        return [(l, c.get({"yes": "true", "no": "false"}[l], l)) for l in it["labels"]]
    return [(l, c.get(l, l)) for l in it["labels"]]


def q8(v):
    """int8 with one scale per vector: compact and close enough to draw."""
    s = float(np.abs(v).max()) or 1.0
    return {"s": round(s / 127, 8), "v": np.round(v / s * 127).astype(int).tolist()}


def pca2(X):
    mu = X.mean(0); _, _, Vt = np.linalg.svd(X - mu, full_matrices=False)
    return mu, Vt[:2]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--model", default="Qwen3-Embedding-4B"); a = ap.parse_args()
    out_dir = OUT / a.model
    sets = [p.stem for p in sorted((VEC / a.model).glob("*.npz"))]
    data = {}
    for s in sets:
        z = np.load(VEC / a.model / f"{s}.npz", allow_pickle=True)
        data[s] = ([json.loads(l) for l in open(PROBES / f"{s}.jsonl")], z["q"].astype(np.float32), [np.asarray(x, np.float32) for x in z["o"]])
    allv = np.vstack([np.vstack([data[s][1]] + data[s][2]) for s in sets])
    mu = allv.mean(0); U, S, _ = np.linalg.svd(np.cov((allv - mu).T)); Wh = U @ np.diag(1 / np.sqrt(S + 1e-3)) @ U.T
    wh = lambda v: (lambda x: x / np.linalg.norm(x, axis=-1, keepdims=True))((v - mu) @ Wh)
    rf = VEC.parent / f"readouts-{a.model}.json"
    readouts = json.load(open(rf)) if rf.exists() else {}
    out_dir.mkdir(parents=True, exist_ok=True); index = []

    for s in sets:
        items, Q, O = data[s]; n = len(items); labs = [[l for l, _ in options(i)] for i in items]
        Qw = wh(Q); Ow = [wh(o) for o in O]
        # learned readout, every item scored by a model that never saw it
        feats = lambda q, o: np.hstack([q[None, :] * o, o])
        learned = [None] * n
        for tr, te in KFold(5, shuffle=True, random_state=0).split(np.arange(n)):
            X = np.vstack([feats(Q[i], O[i]) for i in tr]); y = np.concatenate([[l == items[i]["expected"] for l in labs[i]] for i in tr])
            clf = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=3000, class_weight="balanced")).fit(X, y)
            for i in te: learned[i] = clf.decision_function(feats(Q[i], O[i])).tolist()
        # one readout fit on the whole set, only to show which dimensions it leans on (drill-down view)
        X = np.vstack([feats(Q[i], O[i]) for i in range(n)]); y = np.concatenate([[l == items[i]["expected"] for l in labs[i]] for i in range(n)])
        full = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=3000, class_weight="balanced")).fit(X, y)
        sc, lr = full[0], full[1]; d = Q.shape[1]; w = lr.coef_[0] / sc.scale_  # weight on raw features
        ref = {}
        for m, k in (("clef-flash", "clef"), ("jev", "jev")):
            f = RUNS / f"{m}-{s}" / "results.jsonl"
            ref[k] = {r["task_id"]: r.get("probs") for r in map(json.loads, open(f)) if r.get("ok")} if f.exists() else {}
        mr, Vr = pca2(Q); mw, Vw = pca2(Qw)
        out_items = []
        for i, it in enumerate(items):
            row = {"id": it["id"], "state": it["state"][:600], "question": it["question"]["instructions"], "expected": it["expected"],
                   "options": [{"label": l, "desc": dsc[:160]} for l, dsc in options(it)],
                   "map": {"raw": np.round((Q[i] - mr) @ Vr.T, 4).tolist(), "white": np.round((Qw[i] - mw) @ Vw.T, 4).tolist(),
                           "opts_raw": np.round((O[i] - mr) @ Vr.T, 4).tolist(), "opts_white": np.round((Ow[i] - mw) @ Vw.T, 4).tolist()},
                   "scores": {"cosine": np.round(O[i] @ Q[i], 5).tolist(), "whitened": np.round(Ow[i] @ Qw[i], 5).tolist(),
                              "learned": np.round(learned[i], 4).tolist()}}
            for k in ("clef", "jev"):
                p = ref[k].get(it["id"])
                if p: row["scores"][k] = [round(float(p.get(l, 0.0)), 4) for l in labs[i]]
            if i < DRILL:
                row["drill"] = {"q": q8(Q[i]), "o": [q8(o) for o in O[i]], "qw": q8(Qw[i]), "ow": [q8(o) for o in Ow[i]],
                                "contrib": [q8(w[:d] * Q[i] * o) for o in O[i]], "bias": [round(float(w[d:] @ o + lr.intercept_[0] - (sc.mean_ / sc.scale_) @ lr.coef_[0]), 4) for o in O[i]]}
            out_items.append(row)
        acc = lambda k: (lambda xs: round(float(np.mean(xs)), 3) if xs else None)(
            [labs[i][int(np.argmax(r["scores"][k]))] == items[i]["expected"] for i, r in enumerate(out_items) if k in r["scores"]])
        meta = {"set": s, "name": NAMES.get(s, s), "group": GROUP(s), "type": items[0]["question"]["type"], "n": n, "dim": int(d),
                "chance": (max(sum(i["expected"] == l for i in items) for l in labs[0]) / n) if items[0]["question"]["type"] == "noul" else 1 / len(labs[0]),
                "source": items[0]["provenance"]["source"],
                "acc": {"cosine": acc("cosine"), "whitened": acc("whitened"), "learned": acc("learned"), "universal": readouts.get(s, {}).get("universal"), "clef": acc("clef"), "jev": acc("jev")}}
        json.dump({"meta": meta, "items": out_items}, open(out_dir / f"{s}.json", "w"), separators=(",", ":"))
        index.append(meta); print(s, meta["acc"], flush=True)
    json.dump({"model": a.model, "sets": index}, open(out_dir / "index.json", "w"), indent=1)


if __name__ == "__main__":
    main()
