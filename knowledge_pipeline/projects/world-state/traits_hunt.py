"""T36 step 4 part A: rank the pool per HUNT trait and select 40 top + 40 random items per trait. Writes runs/xtest/B13_selection.json.
    /workspace/models/embed-zs/.venv/bin/python traits_hunt.py   (from projects/world-state)"""
import json, random, numpy as np, hashlib
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import cross_val_predict, StratifiedKFold
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
E = np.load("runs/embeds/leaf_64_fp32.npy"); ids = json.load(open("runs/embeds/bge_small_ids.json")); pos = {i: k for k, i in enumerate(ids)}
tr = {r["item_id"]: r["label"] for r in J("runs/pulse/traits_main/train/labels.jsonl")}; ev = {r["item_id"]: r["label"] for r in J("runs/pulse/traits_main/eval/labels.jsonl")}
tri = [i for i in tr if i in pos]; evi = [i for i in ev if i in pos]; Xtr = E[[pos[i] for i in tri]]; Xev = E[[pos[i] for i in evi]]
b4 = {json.loads(l)["id"] for l in open("runs/xtest/B4/items.jsonl")}; used = set(tri) | set(evi) | b4
G = json.load(open("runs/pulse/traits_gate_provisional.json"))["traits"]; hunt = [t for t, v in G.items() if v["provisional"] == "HUNT-positives"]
cand = np.array([k for k, i in enumerate(ids) if i not in used]); rng = random.Random(20261106); sel = {}; aucs = {}
for t in hunt:
    q = t[2:]  # t_x005 -> x005
    ytr = np.array([int(tr[i].get(q, "not at all") != "not at all") for i in tri]); yev = np.array([int(ev[i].get(q, "not at all") != "not at all") for i in evi])
    if ytr.sum() < 5: aucs[t] = {"auc_cv5": None, "train_pos": int(ytr.sum())}; top = []
    else:
        m = LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000)
        cv = cross_val_predict(m, Xtr, ytr, cv=StratifiedKFold(5, shuffle=True, random_state=0), method="decision_function"); auc = roc_auc_score(ytr, cv) if 0 < ytr.sum() < len(ytr) else None
        aucs[t] = {"auc_cv5": None if auc is None else round(float(auc), 3), "train_pos": int(ytr.sum())}; m.fit(Xtr, ytr)
        s = m.decision_function(E[cand]); top = [ids[cand[k]] for k in np.argsort(-s)[:40]]
    rest = [ids[k] for k in cand if ids[k] not in set(top)]; rnd = rng.sample(rest, 40)
    sel[t] = {"top": top, "random": rnd}
json.dump({"hunt": hunt, "auc": aucs, "selection": sel}, open("runs/xtest/B13_selection.json", "w"))
print(len(hunt), "hunt traits;", "AUC>=0.80:", sum(1 for v in aucs.values() if v["auc_cv5"] is not None and v["auc_cv5"] >= 0.80), "| AUC None:", sum(1 for v in aucs.values() if v["auc_cv5"] is None))
for t, v in aucs.items(): print(t, v)
