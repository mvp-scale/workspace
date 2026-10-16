#!/usr/bin/env python3
"""Precompute the Latent lab walkthrough: one TypeSafe yes/no question, from no examples to answered locally.

Uses the intake corpus (data/embed-zs/intake/corpus: 4,322 one-speaker conversation windows, e5-small vectors, split by
dialogue) and Clef's labels for one question (data/embed-zs/intake/labels/<id>.jsonl). Steps:
  validate  checks on the way in: the question is yes/no with true/false criteria; Clef says yes to the question's own
            example; a random sample has enough positives; Clef is consistent (low entropy) on it
  N = 0     no labels: zero-shot e5 similarity to the question; Clef answers every request
  N = 25 .. 800  logistic head on the first N Clef-labelled windows of the stream; asymmetric gate set on the stream's
            out-of-fold scores (>= 97% agreement and yes-F1 >= 0.90 with Clef); measured on held-out dialogues
Every step records metrics (mean over 3 stream orders), the 2-D map of held-out windows coloured by the model's P(yes),
and two featured requests answered at that step. Writes data/embed-zs/intake/journey-<id>.json.

    python probes/latent_journey.py --id pack-price
"""
import argparse, json, urllib.request
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

import sys; sys.path.insert(0, str(Path(__file__).parent))
from latent_intake import gate, f1, AGREE, F1MIN

BASE = Path("/workspace/data/embed-zs/intake"); NS = [0, 25, 50, 100, 200, 300, 400, 800]; SEEDS = [0, 1, 2]


def clef(text, spec):
    body = json.dumps({"state": text, "questions": {"q": {"type": "noul", "instructions": spec["instructions"], "criteria": spec["criteria"]}}}).encode()
    with urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8018/v1/systemone", body, {"Content-Type": "application/json"}), timeout=60) as r:
        return float(json.loads(r.read())["answers"]["q"]["noul"])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--id", default="pack-price"); a = ap.parse_args()
    spec = json.load(open(BASE / "labels" / f"{a.id}.spec.json"))
    P = {int(r["id"]): float(r["p"]) for r in map(json.loads, open(BASE / "labels" / f"{a.id}.jsonl"))}
    W = json.load(open(BASE / "corpus" / "windows.json")); E = np.load(BASE / "corpus" / "emb_e5.npy")
    split = json.load(open(BASE / "corpus" / "split.json")); stream0, test = np.array(split["stream"]), np.array(split["test"])
    yt = np.array([P[i] > 0.5 for i in test]); pt_clef = np.array([P[i] for i in test])
    from sentence_transformers import SentenceTransformer
    enc = SentenceTransformer("intfloat/e5-small-v2", device="cpu")
    qv = enc.encode(["query: " + spec["what"] + " " + spec.get("example", "")], normalize_embeddings=True)[0]

    # validation on the way in
    rnd = np.random.default_rng(0).choice(stream0, 200, replace=False); pr = np.array([P[i] for i in rnd]); pc = np.clip(pr, 1e-6, 1 - 1e-6)
    ex_p = clef(spec["example"], spec)
    checks = [
        {"check": "Typed yes/no question with true and false criteria", "ok": bool(spec.get("type") == "noul" and spec["criteria"].get("true") and spec["criteria"].get("false")), "value": "noul"},
        {"check": "Clef says yes to the question's own example", "ok": ex_p > 0.5, "value": f'P(yes) = {ex_p:.2f} for "{spec["example"]}"'},
        {"check": "Enough positives in real traffic (random 200 windows)", "ok": bool((pr > 0.5).mean() >= 0.02), "value": f"{(pr > 0.5).mean():.1%} yes"},
        {"check": "Clef answers it consistently (mean entropy below 0.5)", "ok": bool(np.mean(-(pc * np.log2(pc) + (1 - pc) * np.log2(1 - pc))) < 0.5), "value": f"{np.mean(-(pc * np.log2(pc) + (1 - pc) * np.log2(1 - pc))):.2f}"},
    ]

    # 2-D map of held-out windows (fixed projection), and two featured requests
    rng = np.random.default_rng(1); show = rng.choice(len(test), min(600, len(test)), replace=False)
    Xs = E[test[show]]; mu = Xs.mean(0); _, _, Vt = np.linalg.svd(Xs - mu, full_matrices=False); xy = (Xs - mu) @ Vt[:2].T
    zs_test = E[test] @ qv
    feat = None  # chosen after the steps, from what the trained model does (an illustration, not a metric)

    steps = []
    for n in NS:
        rows = []; per_seed_p = None
        for sd in SEEDS:
            stream = np.random.default_rng(sd).permutation(stream0)
            if n == 0:
                p = zs_test; thr = np.quantile(p, 1 - (pr > 0.5).mean())  # zero-shot: flag the top share equal to the yes-rate seen at intake
                pred = p > thr; row = {"auc": roc_auc_score(yt, p), "agree": float((pred == yt).mean()), "yes_f1": f1(pred, yt), "clef_share": 1.0, "positives": 0}
                pl = 1 / (1 + np.exp(-(p - thr) * 25))
            else:
                idx = stream[:n]; y = np.array([P[i] > 0.5 for i in idx])
                if y.sum() < 2:
                    rows.append({"auc": None, "agree": None, "yes_f1": None, "clef_share": 1.0, "positives": int(y.sum())}); continue
                clf = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(E[idx], y)
                pl = clf.predict_proba(E[test])[:, 1]; pred = pl > 0.5
                share, lo, hi = 0.0, -1.0, 2.0
                k = int(min(5, y.sum(), (~y).sum()))
                if k >= 2 and y.sum() >= 5:  # too few positives: keep the gate shut, Clef answers everything
                    oof = np.zeros(n)
                    for tr, te in StratifiedKFold(k, shuffle=True, random_state=0).split(E[idx], y):
                        c = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(E[idx][tr], y[tr]) if y[tr].sum() >= 1 and (~y[tr]).sum() >= 1 else None
                        oof[te] = c.predict_proba(E[idx][te])[:, 1] if c is not None else 0.5
                    share, lo, hi = gate(oof, y)
                loc = (pl < lo) | (pl > hi); casc = np.where(loc, pl > hi, yt)
                row = {"auc": roc_auc_score(yt, pl), "agree": float((pred == yt).mean()), "yes_f1": f1(pred, yt), "clef_share": float(1 - loc.mean()),
                       "cascade_agree": float((casc == yt).mean()), "cascade_f1": f1(casc, yt), "positives": int(y.sum()), "lo": lo, "hi": hi}
            rows.append(row)
            if sd == 0: per_seed_p = pl; gate0 = (row.get("lo", -1.0), row.get("hi", 2.0))
        ok = [r for r in rows if r.get("auc") is not None]
        mean = {k: (round(float(np.mean([r[k] for r in ok if r.get(k) is not None])), 4) if ok and any(r.get(k) is not None for r in ok) else None)
                for k in ("auc", "agree", "yes_f1", "clef_share", "cascade_agree", "cascade_f1", "positives")}
        if not ok: mean["clef_share"] = 1.0
        spread = {k: round(float(np.std([r[k] for r in ok])), 4) if len(ok) > 1 and all(r.get(k) is not None for r in ok) else None for k in ("auc", "yes_f1", "clef_share")}
        lo, hi = gate0
        steps.append({"n": n, "metrics": mean, "spread": spread, "positives_seed0": rows[0].get("positives"), "gate": {"no_below": round(float(lo), 3), "yes_above": round(float(hi), 3)},
                      "map_p": [round(float(v), 3) for v in per_seed_p[show]] if per_seed_p is not None else None, "_p": per_seed_p})
        print(n, mean, flush=True)
    # featured requests: a clear yes the model learns, a trap that fools the untrained model, a hard case that stays with Clef
    pf, g = steps[-1]["_p"], steps[-1]["gate"]
    clear = [j for j in np.argsort(-pf) if pt_clef[j] > 0.8 and pf[j] > g["yes_above"]]
    trap = [j for j in np.argsort(-zs_test) if pt_clef[j] < 0.1 and pf[j] < g["no_below"] and steps[0]["_p"][j] > 0.5]
    hard = [j for j in np.argsort(-pt_clef) if pt_clef[j] > 0.5 and g["no_below"] < pf[j] < g["yes_above"]]
    feat = {k: int(v[min(2, len(v) - 1)]) for k, v in (("clear", clear), ("trap", trap), ("hard", hard)) if v}
    for st in steps:
        lo, hi = st["gate"]["no_below"], st["gate"]["yes_above"]; fe = {}
        for name, j in feat.items():
            lp = float(st["_p"][j])
            route = "clef" if st["n"] == 0 or (lo < lp < hi) else "local"
            fe[name] = {"local_p": round(lp, 3), "route": route, "answer": round(float(pt_clef[j]) if route == "clef" else lp, 3),
                        "local_yes": bool(lp > 0.5), "agrees": bool((lp > 0.5) == (pt_clef[j] > 0.5))}
        st["featured"] = fe; del st["_p"]
    out = {"spec": spec, "validate": checks, "map_xy": np.round(xy, 4).tolist(), "map_clef": [round(float(v), 3) for v in pt_clef[show]],
           "featured": {k: {"text": W[int(test[j])]["text"], "clef_p": round(float(pt_clef[j]), 3), "zero_shot_sim": round(float(zs_test[j]), 3)} for k, j in feat.items()},
           "steps": steps, "n_test": int(len(test)), "bar": {"agree": AGREE, "yes_f1": F1MIN}, "seeds": len(SEEDS)}
    json.dump(out, open(BASE / f"journey-{a.id}.json", "w"))


if __name__ == "__main__":
    main()
