import os, sys, json, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import torch; torch.set_num_threads(8)
import classify as C
from mh_common import load, predict
R = [json.loads(l) for l in open("data/clef-labels/test.jsonl")]
model, tok, K = load("data/kaggle/mh_r6c1/out/mh"); model.cond_cuts = None
H = np.asarray(predict(model, tok, [r["state_text"] for r in R])["cond"])
A = [k.split("|") for k in K["cond"]]
Y = np.array([[(r["P"][f"a|{d}|{dr}|{i}|0"] + r["P"][f"a|{d}|{dr}|{i}|1"]) / 2 for d, dr, i in A] for r in R])
E = H - Y; hi = Y >= C.ATTR_MIN
print(f"attributes {Y.shape[1]}, stories {Y.shape[0]}, ATTR_MIN {C.ATTR_MIN}")
print(f"all cells:     mean error {E.mean():+.3f}, typical size (std) {E.std():.3f}, mean |error| {np.abs(E).mean():.3f}")
print(f"cells where Clef's answer triggers (>= ATTR_MIN, {hi.sum()} cells): mean error {E[hi].mean():+.3f}, std {E[hi].std():.3f}; BitMob also >= ATTR_MIN on {(H[hi] >= C.ATTR_MIN).mean():.1%}")
lo = Y < 0.1
print(f"cells where Clef is clearly no (< 0.1): mean error {E[lo].mean():+.3f}; BitMob wrongly >= ATTR_MIN on {(H[lo] >= C.ATTR_MIN).mean():.3%}")
for q in (0.5, 0.7, 0.9):
    m = (Y >= q); print(f"  Clef >= {q}: BitMob mean {H[m].mean():.2f} vs Clef {Y[m].mean():.2f} (n={m.sum()})")
# --- re-stretch test: isotonic map BitMob score -> Clef probability, pooled over all attributes; fit on one half of the stories, read the other half
from sklearn.isotonic import IsotonicRegression
keys = lambda rd: {(x["dial"], x["direction"]) for x in rd["readings"] if x["direction"] != "conflict"}
idx = np.arange(len(R)); halves = (idx % 2 == 0, idx % 2 == 1)
def read_with(n, vals):
    P = dict(R[n]["P"])
    for j, (d, dr, i) in enumerate(A): P[f"a|{d}|{dr}|{i}|0"] = P[f"a|{d}|{dr}|{i}|1"] = float(vals[j])
    return keys(C.read(P))
for name, mapper in (("raw BitMob", None), ("re-stretched (pooled map)", "iso")):
    tp = fp = pos = 0; neg = 0
    for fit, ev in (halves, halves[::-1]):
        if mapper:
            ir = IsotonicRegression(out_of_bounds="clip").fit(H[fit].ravel(), Y[fit].ravel()); Hm = ir.predict(H.ravel()).reshape(H.shape)
        else: Hm = H
        for n in np.where(ev)[0]:
            b = keys(R[n]["read"]); m = read_with(n, Hm[n]); tp += len(m & b); fp += len(m - b); pos += len(b); neg += 78 - len(b)
    print(f"{name:28s} conditions caught {tp/pos:6.1%}   false alarms {fp/neg:.4%}")
from sklearn.metrics import roc_auc_score
yb = (Y >= C.ATTR_MIN).ravel(); print(f"ranking: AUC of BitMob score for 'Clef triggers' = {roc_auc_score(yb, H.ravel()):.3f}")
for name in ("distribution-matched (pooled)", "distribution-matched (per attribute)"):
    tp = fp = pos = neg = 0
    for fit, ev in (halves, halves[::-1]):
        Hm = np.empty_like(H)
        cols = [slice(None)] if "pooled" in name else [[j] for j in range(H.shape[1])]
        for c in cols:
            hs = np.sort(H[fit][:, c].ravel()); ys = np.sort(Y[fit][:, c].ravel())
            q = np.searchsorted(hs, H[:, c].ravel(), side="right") / len(hs)
            Hm[:, c] = np.quantile(ys, np.clip(q, 0, 1)).reshape(H[:, c].shape)
        for n in np.where(ev)[0]:
            b = keys(R[n]["read"]); m = read_with(n, Hm[n]); tp += len(m & b); fp += len(m - b); pos += len(b); neg += 78 - len(b)
    print(f"{name:38s} conditions caught {tp/pos:6.1%}   false alarms {fp/neg:.4%}")
yc = (Y >= C.ATTR_MIN)
for rec in (0.90, 0.95, 0.98):
    s = np.sort(H[yc])[::-1]; thr = s[int(rec * len(s)) - 1]
    flag = H >= thr; per = flag.sum(1)
    qs = 2 * per.mean()
    print(f"shortlist catching {rec:.0%} of Clef's trigger answers: {per.mean():.1f} candidate answers per story (median {np.median(per):.0f}) -> Clef asks ~{qs:.0f} of its 318 condition questions ({qs/318:.0%})")
for rec in (0.90, 0.95, 0.98):
    s = np.sort(H[yc])[::-1]; thr = s[int(rec * len(s)) - 1]; flag = H >= thr
    tp = fp = pos = neg = 0
    for n in range(len(R)):
        vals = np.where(flag[n], Y[n], H[n])          # Clef answers the shortlisted questions; BitMob keeps the rest
        b = keys(R[n]["read"]); m = read_with(n, vals); tp += len(m & b); fp += len(m - b); pos += len(b); neg += 78 - len(b)
    print(f"screen-then-check ({rec:.0%} shortlist, Clef asks {2*flag.sum(1).mean():.0f}/318): conditions caught {tp/pos:6.1%}, false alarms {fp/neg:.4%}  -> {'PASS' if tp/pos >= .9 and fp/neg <= .001 else 'fail'} (bar: >=90% caught, <=0.1% false alarms)")
