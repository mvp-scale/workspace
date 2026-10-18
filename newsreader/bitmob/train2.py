"""Round 2. Same encoder, same held-out split, same pass bar as train.py (readings recall >= 0.85 and precision >= 0.85 against Clef).
Change: Clef says yes to ~1.4% of the 318 wording questions, so per-wording heads learn "always no". Here the target is what the engine uses:
for each (condition, direction), Clef's score = max over that pair's attributes of the mean of the two wordings (exactly read()'s number).
A ridge regression per target learns that graded score (rare conditions still give a signal); a story moves a condition when the predicted score
passes a cut-off chosen on the training stories (5-fold, best F1), the same rule for every target. Story-type questions keep logistic heads."""
import sys, os, json, time, hashlib, numpy as np
os.environ.setdefault("WE_RULES", "rules_v2"); sys.path.insert(0, "/workspace/probes/world-engine"); sys.path.insert(0, os.path.dirname(__file__))
import classify as C
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold
import importlib.util
spec = importlib.util.spec_from_file_location("t1", os.path.join(os.path.dirname(__file__), "train.py"))
rows = [json.loads(l) for l in open("/workspace/data/newsreader/labels/clef-q4km.jsonl")]
# reuse the encoder from round 1 without running its experiments
src = open(os.path.join(os.path.dirname(__file__), "train.py")).read(); src = src[:src.index("test = [r for r in rows")]
ns = {}; exec(compile(src.replace('rows = [json.loads(l) for l in open(LAB)]', 'rows = []'), "train_enc", "exec"), ns); vectors = ns["vectors"]
PAIRS = sorted({(d, dirn) for (d, dirn) in C.ATTRS})
def score(P, d, dirn): return max((P[f"a|{d}|{dirn}|{i}|0"] + P[f"a|{d}|{dirn}|{i}|1"]) / 2 for i in range(len(C.ATTRS[(d, dirn)])))
key = lambda rd: {(x["dial"], x["direction"]) for x in rd if x["direction"] != "conflict"}
test = [r for r in rows if int(hashlib.sha256(r["id"].encode()).hexdigest(), 16) % 5 == 0]; train = [r for r in rows if r not in test]
S = lambda rs: np.array([[score(r["P"], d, dirn) for d, dirn in PAIRS] for r in rs])
Str, Ste = S(train), S(test); Ytr = Str >= C.ATTR_MIN
print(f"{len(rows)} stories ({len(train)} train, {len(test)} test); targets {len(PAIRS)}; Clef readings per story {Ytr.sum(1).mean():.2f}", flush=True)
out = {}
for chunks in (1, 4):
    Xtr, _ = vectors(train, chunks); Xte, ms = vectors(test, chunks)
    oof = np.zeros_like(Str)                                       # out-of-fold predictions on the training stories, to choose the cut-off honestly
    for a, b in KFold(5, shuffle=True, random_state=0).split(Xtr): oof[b] = Ridge(alpha=1.0).fit(Xtr[a], Str[a]).predict(Xtr[b])
    best = max(((t, (2 * ((oof >= t) & Ytr).sum()) / max(1, (oof >= t).sum() + Ytr.sum())) for t in np.linspace(0.05, 0.8, 76)), key=lambda x: x[1])
    pred = Ridge(alpha=1.0).fit(Xtr, Str).predict(Xte) >= best[0]
    rec, pre, n = [], [], 0
    for k, r in enumerate(test):
        mine = {PAIRS[j] for j in np.where(pred[k])[0]}; clef = key(r["readings"])
        if clef: n += 1; rec.append(len(mine & clef) / len(clef)); pre.append(len(mine & clef) / len(mine) if mine else 0.0)
    R, Pp = float(np.mean(rec)), float(np.mean(pre)); prec_all = (pred & (Ste >= C.ATTR_MIN)).sum() / max(1, pred.sum())
    out[f"chunks{chunks}"] = {"train": len(train), "test": len(test), "stories_scored": n, "cutoff": round(float(best[0]), 3), "train_cv_f1": round(float(best[1]), 3),
                              "recall": round(R, 3), "precision": round(Pp, 3), "readings_per_story_mine": round(float(pred.sum(1).mean()), 2), "readings_per_story_clef": round(float((Ste >= C.ATTR_MIN).sum(1).mean()), 2),
                              "cpu_ms_per_story": round(ms, 1), "PASS": R >= .85 and Pp >= .85}
    print(f"chunks={chunks}: {out[f'chunks{chunks}']}", flush=True)
json.dump(out, open("/workspace/data/newsreader/bitmob/results2.json", "w"), indent=1)
