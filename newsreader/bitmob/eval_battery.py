"""Score a labelling battery: is each atom clear to the teacher, and can a CPU model learn it?
Per atom: yes counts for wordings a and b, teacher self-agreement (F1 of a vs b), contradiction rate (a and reversed both yes),
and CPU learnability: potion-32M + logistic, label = a and b both yes, cut-off chosen on training stories, F1 on held-out stories
(id hash % 5 == 0, the same split as train_mm3.py). Per condition: atoms OR-ed, compared with the first battery's states/concrete.
Run: models/embed-zs/.venv/bin/python -I newsreader/bitmob/eval_battery.py data/mm3-train/queue-evidence-v1.jsonl"""
import json, sys, hashlib, numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import cross_val_predict, StratifiedKFold
from model2vec import StaticModel

path = sys.argv[1]; B = json.load(open(f"/workspace/newsreader/bitmob/batteries/{path.split('queue-')[1][:-6]}.json"))
rows = list({r["id"]: r for r in map(json.loads, open(path))}.values())
first = {r["id"]: r for r in map(json.loads, open("/workspace/data/mm3-train/queue.jsonl"))}
test = np.array([int(hashlib.sha256(r["id"].encode()).hexdigest(), 16) % 5 == 0 for r in rows]); tr = ~test
X = StaticModel.from_pretrained("minishlab/potion-base-32M").encode([r["title"] + ". " + r["text"] for r in rows])
yes = lambda atom, ang: np.array([r["answers"][f"{atom}|{ang}"] >= .5 for r in rows])


def learn(y):
    if y[tr].sum() < 5 or y[test].sum() < 3: return None
    mk = lambda: LogisticRegression(C=4, class_weight="balanced", max_iter=3000)
    oof = cross_val_predict(mk(), X[tr], y[tr], cv=StratifiedKFold(5, shuffle=True, random_state=0), method="predict_proba")[:, 1]
    t = max(np.linspace(.05, .95, 37), key=lambda t: f1_score(y[tr], oof >= t))
    return round(float(f1_score(y[test], mk().fit(X[tr], y[tr]).predict_proba(X[test])[:, 1] >= t)), 2)


out = {"battery": B["name"], "stories": len(rows), "atoms": {}, "conditions": {}}
print(f"{len(rows)} stories, battery {B['name']}\n{'atom':26s} {'a yes':>5s} {'b yes':>5s} {'teacher a~b':>11s} {'contradict':>10s} {'CPU F1':>6s}")
for c in B["concerns"]:
    a, b, rv = yes(c["atom"], "a"), yes(c["atom"], "b"), yes(c["atom"], "reversed")
    f = f1_score(a, b) if a.sum() + b.sum() else float("nan"); con = (a & rv).sum() / max(1, a.sum()); cpu = learn(a & b)
    out["atoms"][c["atom"]] = {"a_yes": int(a.sum()), "b_yes": int(b.sum()), "both_yes": int((a & b).sum()), "teacher_self_f1": round(float(f), 2), "contradiction": round(float(con), 2), "cpu_f1": cpu}
    print(f"{c['atom']:26s} {a.sum():5d} {b.sum():5d} {f:11.2f} {con:10.0%} {cpu if cpu is not None else '-':>6}")
print(f"\n{'condition':24s} {'new: atoms a~b':>14s} {'new CPU F1':>10s} {'old states~concrete':>19s}")
for cond in sorted({c["condition"] for c in B["concerns"]}):
    atoms = [c["atom"] for c in B["concerns"] if c["condition"] == cond]
    a = np.any([yes(x, "a") for x in atoms], 0); b = np.any([yes(x, "b") for x in atoms], 0)
    ids = [r["id"] for r in rows]; old = None
    if f"{cond}|states" in first[ids[0]]["answers"]:
        s = np.array([first[i]["answers"][f"{cond}|states"] >= .5 for i in ids]); k = np.array([first[i]["answers"][f"{cond}|concrete"] >= .5 for i in ids]); old = round(float(f1_score(s, k)), 2)
    out["conditions"][cond] = {"teacher_self_f1": round(float(f1_score(a, b)), 2) if a.sum() + b.sum() else None, "cpu_f1": learn(a & b), "first_battery_self_f1": old, "both_yes": int((a & b).sum())}
    o = out["conditions"][cond]; print(f"{cond:24s} {o['teacher_self_f1'] if o['teacher_self_f1'] is not None else '-':>14} {o['cpu_f1'] if o['cpu_f1'] is not None else '-':>10} {old if old is not None else '-':>19}")
json.dump(out, open(path.replace("queue-", "eval-").replace(".jsonl", ".json"), "w"), indent=1)
