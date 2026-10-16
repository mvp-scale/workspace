#!/usr/bin/env python3
"""Latent lab live run: the walkthrough on YOUR texts, step by step while you watch.

Input: a TypeSafe yes/no question and a list of texts (conversation lines or windows). The texts are encoded once with
the frozen e5-small encoder (CPU). 30% are held out for measurement (at most 400), the rest form the training stream.
The local Clef (:8018, never a hosted model) labels the held-out texts first, then the stream in order; at each
checkpoint (25, 50, 100, 200, 300, 400, 800, 1600 labelled texts) a logistic head is trained, the asymmetric gate is set
on the stream's out-of-fold scores, and the held-out texts are scored. Each finished step is written immediately to
data/embed-zs/intake/results/<id>.json in the same format as the precomputed walkthrough, so the page fills in live.

    python probes/latent_live.py --spec spec.json --texts texts.json
"""
import argparse, json, time
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

import sys; sys.path.insert(0, str(Path(__file__).parent))
from latent_intake import gate, f1, clef_label, save, AGREE, F1MIN

BASE = Path("/workspace/data/embed-zs/intake"); CHECKS = [25, 50, 100, 200, 300, 400, 800, 1600]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--spec", required=True); ap.add_argument("--texts", required=True); a = ap.parse_args()
    spec = json.load(open(a.spec)); texts = json.load(open(a.texts))
    out_path = BASE / "results" / f"{spec['id']}.json"
    res = {"spec": spec, "kind": "live", "status": "starting", "started": time.time(), "steps": [], "n_texts": len(texts)}
    status = lambda m: (res.update(status=m), save(out_path, res))

    status(f"encoding {len(texts)} texts with e5-small (CPU)")
    from sentence_transformers import SentenceTransformer
    enc = SentenceTransformer("intfloat/e5-small-v2", device="cpu")
    E = enc.encode(["query: " + t for t in texts], batch_size=64, normalize_embeddings=True)
    qv = enc.encode(["query: " + (spec.get("what") or spec["instructions"]) + (" " + spec["example"] if spec.get("example") else "")], normalize_embeddings=True)[0]

    rng = np.random.default_rng(0); order = rng.permutation(len(texts))
    n_test = min(400, max(20, int(len(texts) * 0.3))); test, stream = order[:n_test], order[n_test:n_test + 1600]
    zs_test = E[test] @ qv

    status("asking Clef about the question's own example")
    ex_p = clef_label([spec["example"]], spec, lambda m: None)[0] if spec.get("example") else None
    pt_clef = np.array([p if p is not None else 0.0 for p in clef_label([texts[i] for i in test], spec, lambda m: status("Clef labelling held-out texts: " + m.split("labelling ")[-1]))])
    yt = pt_clef > 0.5; pc = np.clip(pt_clef, 1e-6, 1 - 1e-6); ent = float(np.mean(-(pc * np.log2(pc) + (1 - pc) * np.log2(1 - pc))))
    res["validate"] = [
        {"check": "Typed yes/no question with true and false criteria", "ok": True, "value": "noul"},
        {"check": "Clef says yes to the question's own example", "ok": ex_p is None or ex_p > 0.5, "value": "no example given" if ex_p is None else f'P(yes) = {ex_p:.2f} for "{spec["example"]}"'},
        {"check": "Enough positives in your texts (held-out sample)", "ok": bool(yt.mean() >= 0.02 and yt.sum() >= 5), "value": f"{yt.mean():.1%} yes ({int(yt.sum())} of {len(yt)})"},
        {"check": "Clef answers it consistently (mean entropy below 0.5)", "ok": ent < 0.5, "value": f"{ent:.2f}"},
    ]
    show = np.arange(len(test)); Xs = E[test]; mu = Xs.mean(0); _, _, Vt = np.linalg.svd(Xs - mu, full_matrices=False)
    res.update(map_xy=np.round((Xs - mu) @ Vt[:2].T, 4).tolist(), map_clef=[round(float(v), 3) for v in pt_clef], n_test=int(len(test)),
               bar={"agree": AGREE, "yes_f1": F1MIN}, seeds=1, featured={})
    thr0 = np.quantile(zs_test, 1 - max(yt.mean(), 0.01))
    p0 = 1 / (1 + np.exp(-(zs_test - thr0) * 25))
    res["steps"].append({"n": 0, "metrics": {"auc": round(float(roc_auc_score(yt, zs_test)), 4) if 0 < yt.sum() < len(yt) else None, "agree": round(float(((zs_test > thr0) == yt).mean()), 4),
                         "yes_f1": round(float(f1(zs_test > thr0, yt)), 4), "clef_share": 1.0, "cascade_agree": None, "cascade_f1": None, "positives": 0},
                         "gate": {"no_below": -1.0, "yes_above": 2.0}, "map_p": [round(float(v), 3) for v in p0]})
    save(out_path, res)

    ys_all, done, probs = [], 0, {}
    for cp in [c for c in CHECKS if c <= len(stream)] + ([len(stream)] if len(stream) not in CHECKS and len(stream) > 25 else []):
        need = stream[done:cp]
        got = clef_label([texts[i] for i in need], spec, lambda m: status(f"Clef labelling training texts: {done}+{m.split('labelling ')[-1]} (next step at {cp})"))
        ys_all += [(p or 0.0) > 0.5 for p in got]; done = cp
        idx = stream[:cp]; y = np.array(ys_all[:cp])
        status(f"training on {cp} labelled texts")
        row = {"positives": int(y.sum())}; lo, hi = -1.0, 2.0; pl = None
        if y.sum() >= 2 and (~y).sum() >= 2:
            clf = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(E[idx], y)
            pl = clf.predict_proba(E[test])[:, 1]
            k = int(min(5, y.sum(), (~y).sum()))
            if k >= 2 and y.sum() >= 5:
                oof = np.zeros(cp)
                for tr, te in StratifiedKFold(k, shuffle=True, random_state=0).split(E[idx], y):
                    c = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(E[idx][tr], y[tr]); oof[te] = c.predict_proba(E[idx][te])[:, 1]
                _, lo, hi = gate(oof, y)
            loc = (pl < lo) | (pl > hi); casc = np.where(loc, pl > hi, yt)
            row.update(auc=round(float(roc_auc_score(yt, pl)), 4) if 0 < yt.sum() < len(yt) else None, agree=round(float(((pl > 0.5) == yt).mean()), 4),
                       yes_f1=round(float(f1(pl > 0.5, yt)), 4), clef_share=round(float(1 - loc.mean()), 4),
                       cascade_agree=round(float((casc == yt).mean()), 4), cascade_f1=round(float(f1(casc, yt)), 4))
        else:
            row.update(auc=None, agree=None, yes_f1=None, clef_share=1.0, cascade_agree=None, cascade_f1=None)
        probs[cp] = pl
        res["steps"].append({"n": int(cp), "metrics": row, "gate": {"no_below": round(float(lo), 3), "yes_above": round(float(hi), 3)},
                             "map_p": None if pl is None else [round(float(v), 3) for v in pl]})
        save(out_path, res)

    # featured requests from the final model (illustration): a clear yes, a trap, a hard case
    last = res["steps"][-1]; pf = probs.get(last["n"]); g = last["gate"]; feat = {}
    if pf is not None:
        clear = [j for j in np.argsort(-pf) if pt_clef[j] > 0.8 and pf[j] > g["yes_above"]]
        trap = [j for j in np.argsort(-zs_test) if pt_clef[j] < 0.2 and pf[j] < g["no_below"]]
        hard = [j for j in np.argsort(-pt_clef) if pt_clef[j] > 0.5 and g["no_below"] < pf[j] < g["yes_above"]]
        feat = {k: int(v[0]) for k, v in (("clear", clear), ("trap", trap), ("hard", hard)) if v}
    res["featured"] = {k: {"text": texts[int(test[j])], "clef_p": round(float(pt_clef[j]), 3)} for k, j in feat.items()}
    for st in res["steps"]:
        lo, hi = st["gate"]["no_below"], st["gate"]["yes_above"]; fe = {}
        for k, j in feat.items():
            src = p0 if st["n"] == 0 else probs.get(st["n"])
            if src is None: continue
            lp = float(src[j]); route = "clef" if st["n"] == 0 or lo < lp < hi or lo < 0 else "local"
            fe[k] = {"local_p": round(lp, 3), "route": route, "answer": round(float(pt_clef[j]) if route == "clef" else lp, 3), "agrees": bool((lp > 0.5) == (pt_clef[j] > 0.5))}
        st["featured"] = fe
    res.update(status="done", finished=time.time()); save(out_path, res)


if __name__ == "__main__":
    main()
