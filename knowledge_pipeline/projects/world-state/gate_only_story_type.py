"""Gate-only story type (pre-registered L949): story type from G1 spot-class counts and G2 fragment factuality counts only. Depth-3 decision tree over 14 counts, read as rules; a leaf answers only when its calibration purity >= 0.80 and support >= 30, else unknown. Same grouped split as g3_spec.py.
    /workspace/models/embed-zs/.venv/bin/python gate_only_story_type.py   (from projects/world-state)"""
import json, re, pickle, numpy as np
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.model_selection import GroupShuffleSplit
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
S = {}
for r in J("runs/label_store/labels.jsonl"):
    if r["family"] == "sonnet" and r["version"] == "ws-v2-frozen": S[r["item_id"]] = r
pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}
for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r["text"]
ids = sorted(i for i in S if i in pool); T = [re.sub(r"\s+", " ", pool[i])[:600] for i in ids]
GZ = pickle.load(open("runs/pulse/g2_tokens.pkl", "rb")); assert GZ["ids"] == ids
FACT = ["F_asserted", "F_reported", "F_planned", "F_predicted", "F_denied"]; CL = GZ["classes"]
X = np.array([[t.split().count(f) for f in FACT] + list(c) for t, c in zip(GZ["tokens"], GZ["counts"])], dtype=float); names = FACT + ["spots_" + c for c in CL]
y = np.array([S[i]["story_type"] for i in ids]); grp = {}; gid = np.array([grp.setdefault(re.sub(r"\W+", "", t.lower())[:60], len(grp)) for t in T])
tr, va = next(GroupShuffleSplit(1, test_size=0.2, random_state=0).split(T, groups=gid)); rs = np.random.RandomState(1); va = rs.permutation(va); cal, te = va[: len(va) // 2], va[len(va) // 2:]
tree = DecisionTreeClassifier(max_depth=3, min_samples_leaf=40, class_weight="balanced", random_state=0).fit(X[tr], y[tr])
leaf_c = tree.apply(X[cal]); leaf_t = tree.apply(X[te]); ok = {}
for lf in np.unique(leaf_c):
    m = leaf_c == lf; lab = tree.classes_[tree.predict(X[cal][m][:1])[0] == tree.classes_ if False else 0]
    pred = tree.predict(X[cal][m])[0]; pur = float((y[cal][m] == pred).mean())
    if m.sum() >= 30 and pur >= 0.80: ok[lf] = pred
ans = np.array([lf in ok for lf in leaf_t]); pred = np.array([ok.get(lf, "unknown") for lf in leaf_t]); yt = y[te]
res = {"test_items": int(len(te)), "coverage": round(float(ans.mean()), 3), "precision_when_answered": round(float((pred[ans] == yt[ans]).mean()), 3) if ans.sum() else None, "always_fact": round(float((yt == "fact").mean()), 3), "per_class": {}}
for c in ["fact", "forecast", "opinion", "unclear"]:
    real = yt == c; got = ans & (pred == c); tp = int((got & real).sum())
    res["per_class"][c] = {"real_in_test": int(real.sum()), "answered_as": int(got.sum()), "precision": round(tp / max(int(got.sum()), 1), 3) if got.sum() else None, "share_of_real_found": round(tp / max(int(real.sum()), 1), 3)}
res["rules"] = export_text(tree, feature_names=names, max_depth=3); json.dump(res, open("runs/pulse/gate_only_story_type.json", "w"), indent=1); print(json.dumps({k: v for k, v in res.items() if k != "rules"}, indent=1)); print(res["rules"])
