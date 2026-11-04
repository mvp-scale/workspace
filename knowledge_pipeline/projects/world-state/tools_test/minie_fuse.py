"""Does MinIE add to the CPU cascade? Run: /workspace/models/embed-zs/.venv/bin/python minie_fuse.py (after out*.txt exist). Baseline = triage.py model; plus 9 MinIE features."""
import json, os, re, glob, pathlib, warnings, sys
warnings.filterwarnings("ignore"); os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np
H0 = pathlib.Path(__file__).resolve().parent.parent; T = H0 / "tools_test"
R = {}
for f in sorted(glob.glob(str(T / "out*.txt"))):
    cur = None
    for l in open(f, encoding="utf-8"):
        if l.startswith("#"):
            cur = l[1:].split("\t")[0].split("|")[0]; v = R.setdefault(cur, np.zeros(9)); v[0] += 1; v[8] += float(l.split("\t")[1].rstrip("ms"))
        elif cur and l.startswith("  "):
            v[1] += 1; v[2] += "Source:(" in l; v[3] += "Modality:POSSIBILITY" in l; v[4] += "POLARITY:  NEGATIVE" in l
            v[5] += "Quantifiers:" in l; v[6] += "QUANT_S" in l; v[7] += "Source:(" in l and "Modality:POSSIBILITY" in l
json.dump({k: v.tolist() for k, v in R.items()}, open(T / "minie_feat.json", "w"))
src = open(H0 / "triage.py").read(); sys.argv = ["x"]; __file__ = str(H0 / "triage.py")
exec(src[:src.index("p = cross_val_predict")])
M = np.array([R.get(i, np.zeros(9)) for i in ids], float); print("items with MinIE output", sum(i in R for i in ids), "of", len(ids))
cv = StratifiedKFold(5, shuffle=True, random_state=0); mk = lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, C=0.1))
pb = cross_val_predict(mk(), np.hstack([F, E]), y, cv=cv, method="predict_proba")[:, 1]
pm = cross_val_predict(mk(), np.hstack([F, E, M[:, :8]]), y, cv=cv, method="predict_proba")[:, 1]
po = cross_val_predict(mk(), M[:, :8], y, cv=cv, method="predict_proba")[:, 1]
sh = lambda s, r: round(float((np.argmax(np.cumsum(y[np.argsort(-s)]) / y.sum() >= r) + 1) / len(y)), 3)
out = {"auc_baseline": round(roc_auc_score(y, pb), 4), "auc_plus_minie": round(roc_auc_score(y, pm), 4), "auc_minie_only": round(roc_auc_score(y, po), 4),
       "read_share_90_base": sh(pb, .9), "read_share_90_plus": sh(pm, .9), "read_share_95_base": sh(pb, .95), "read_share_95_plus": sh(pm, .95),
       "ms_per_item_mean": round(float(M[:, 8].mean()), 1), "ms_per_sentence": round(float(M[:, 8].sum() / M[:, 0].sum()), 1), "sentences_per_item": round(float(M[:, 0].mean()), 2),
       "items_with_source_prop_pct": round(float((M[:, 2] > 0).mean() * 100, ), 1)}
# does MinIE's 'Source' (attribution) separate story types?  forecast/opinion vs fact
st = np.array([H[i].get("story_type") or H[i].get("type") or "" for i in ids]) if isinstance(next(iter(H.values())), dict) else None
if st is not None:
    for c in sorted(set(st)):
        if c: out[f"source_prop_rate_{c}"] = round(float((M[st == c, 2] > 0).mean()), 3); out[f"possibility_rate_{c}"] = round(float((M[st == c, 3] > 0).mean()), 3)
json.dump(out, open(T / "minie_fuse.json", "w"), indent=1); print(json.dumps(out, indent=1))
