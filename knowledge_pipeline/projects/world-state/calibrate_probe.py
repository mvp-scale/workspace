#!/usr/bin/env python3
"""Free CPU probe 2: is a small static-embedding classifier's confidence trustworthy, and where can it work alone?
Train W1-5 (teacher-consensus labels), calibrate temperature on W6, test W7+W8 against Sonnet. Never touches the frozen 300.
Run with models/embed-zs/.venv/bin/python."""
import json, os, pathlib
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import softmax
from sklearn.linear_model import LogisticRegression
from model2vec import StaticModel
W = pathlib.Path(__file__).resolve().parent / "runs" / "waves"
J = lambda p: [json.loads(l) for l in open(p) if l.strip()]
def load(n):
    items = {r["id"]: r["text"] for r in J(W / f"w{n}_items.jsonl")}
    H = {r["item_id"]: r["label"] for r in J(W / f"w{n}/haiku/labels.jsonl")}; S = {r["item_id"]: r["label"] for r in J(W / f"w{n}/sonnet/labels.jsonl")}
    return [(items[i], H[i], S[i]) for i in items if i in H and i in S]
m = StaticModel.from_pretrained("minishlab/potion-base-8M")
tr = [x for n in range(1, 6) for x in load(n)]; cal = load(6); te = load(7) + load(8)
def ece(conf, ok, bins=10):
    e = 0
    for b in range(bins):
        k = (conf >= b / bins) & (conf < (b + 1) / bins + (b == bins - 1))
        if k.sum(): e += k.mean() * abs(conf[k].mean() - ok[k].mean())
    return e
for key in ("topic", "story_type"):
    keep = [(t, h[key]) for t, h, s in tr if h[key] == s[key]]
    clf = LogisticRegression(max_iter=500, C=10).fit(m.encode([t for t, _ in keep]), [l for _, l in keep])
    def logits(rows): return clf.decision_function(m.encode([t for t, _, _ in rows]))
    Lc, Lt = logits(cal), logits(te)
    yc = np.array([clf.classes_.tolist().index(s[key]) if s[key] in clf.classes_ else -1 for _, h, s in cal])
    ok_c = (yc >= 0)
    nll = lambda T: -np.mean(np.log(softmax(Lc[ok_c] / T, axis=1)[np.arange(ok_c.sum()), yc[ok_c]] + 1e-9))
    T = minimize_scalar(nll, bounds=(0.05, 20), method="bounded").x
    truth = np.array([s[key] for _, h, s in te]); pred = clf.classes_[Lt.argmax(1)]; ok = pred == truth
    print(f"\n== {key}: test {len(te)} items vs Sonnet; accuracy overall {ok.mean():.3f}; fitted temperature T={T:.2f}")
    for name, P in (("raw", softmax(Lt, axis=1)), ("calibrated", softmax(Lt / T, axis=1))):
        conf = P.max(1); print(f"  {name:<10} mean confidence {conf.mean():.3f}  (true accuracy {ok.mean():.3f})  calibration error {ece(conf, ok):.3f}")
    conf = softmax(Lt / T, axis=1).max(1)
    print("  calibrated confidence >= c : share of items handled alone, accuracy on them (teachers agree with each other at .81 topic / .88 story)")
    for c in (0.3, 0.5, 0.7, 0.9):
        k = conf >= c; print(f"    >= {c:.1f}: {k.mean():5.1%} of items, accuracy {ok[k].mean() if k.sum() else float('nan'):.3f}")
