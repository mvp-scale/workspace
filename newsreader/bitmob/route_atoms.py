"""GPU relief from the atoms: the CPU student settles the (story, atom) pairs it is sure about and sends the rest to Clef.
Bars: settled "no" may lose at most 10% of Clef's yes (recall, set on validation; the first version's 99%-precision bar for "no" was
nearly always-no because yes is ~2%, so it was replaced), settled "yes" must be >= 90% right (precision against Clef);
both cut-offs are chosen on validation stories (hash % 5 == 1), then measured on test stories (hash % 5 == 0), full text and teasers together.
Clef's label per atom: both wordings yes (evidence batteries) or states and concrete yes (first battery's four conditions).
Reports per atom and overall: share settled on CPU, agreement with Clef on what it settled, recall of Clef's yes kept (settled yes + sent to Clef).
Student: potion-base-32M frozen + logistic (3 ms per story). Run: models/embed-zs/.venv/bin/python -I newsreader/bitmob/route_atoms.py"""
import json, glob, hashlib, numpy as np
from sklearn.linear_model import LogisticRegression
from model2vec import StaticModel

D = "/workspace/data/mm3-train"; Q = {"first": {r["id"]: r for r in map(json.loads, open(f"{D}/queue.jsonl"))}}
ATOMS = {c: ("first", (f"{c}|states", f"{c}|concrete")) for c in ("civil_unrest|up", "war_terror|up", "crime|up", "cyber_insecurity|up")}
for f in sorted(glob.glob("/workspace/newsreader/bitmob/batteries/evidence-v*.json")):
    B = json.load(open(f)); Q[B["name"]] = {r["id"]: r for r in map(json.loads, open(f"{D}/queue-{B['name']}.jsonl"))}
    ATOMS.update({c["atom"]: (B["name"], (f"{c['atom']}|a", f"{c['atom']}|b")) for c in B["concerns"]})
ids = sorted(set.intersection(*[set(q) for q in Q.values()])); rows = [Q["first"][i] for i in ids]
Y = np.array([[all(Q[w][i]["answers"][k] >= .5 for k in ks) for (w, ks) in ATOMS.values()] for i in ids])
h = np.array([int(hashlib.sha256(i.encode()).hexdigest(), 16) % 5 for i in ids]); fit, val, test = h >= 2, h == 1, h == 0
X = StaticModel.from_pretrained("minishlab/potion-base-32M").encode([r["title"] + ". " + r["text"] for r in rows])
print(f"{len(ids)} stories in every queue ({fit.sum()} fit, {val.sum()} val, {test.sum()} test), {len(ATOMS)} atoms")
out, settled, agree, pairs, kept, clef_yes = {}, 0, 0, 0, 0, 0
for j, n in enumerate(ATOMS):
    y = Y[:, j]
    if y[fit].sum() < 3:                                           # too few examples to learn: every pair goes to Clef
        lo, hi, p = -1, 2, np.zeros(len(ids))
    else:
        p = LogisticRegression(C=4, class_weight="balanced", max_iter=4000).fit(X[fit], y[fit]).predict_proba(X)[:, 1]
        pv, yv = p[val], y[val]
        # settle "no" only below a cut that loses at most 10% of Clef's yes on validation (recall bar: a 99% "no is right" bar is ~ always-no)
        lo = max([t for t in np.linspace(0, 1, 201) if yv.sum() >= 3 and (yv & (pv <= t)).sum() <= 0.10 * yv.sum()] or [-1])
        hi = min([t for t in np.linspace(0, 1, 201) if (pv >= t).sum() >= 3 and yv[pv >= t].mean() >= .90] or [2])
    pt, yt = p[test], y[test]; no, ye = pt <= lo, pt >= hi; s = no | ye
    a = (no & ~yt).sum() + (ye & yt).sum(); k = (ye & yt).sum() + (~s & yt).sum()
    out[n] = {"settled": round(float(s.mean()), 3), "agree_settled": round(float(a / max(1, s.sum())), 3), "clef_yes_test": int(yt.sum()),
              "yes_kept": round(float(k / max(1, yt.sum())), 3), "cut_no": round(float(lo), 3), "cut_yes": None if hi > 1 else round(float(hi), 3)}
    settled += s.sum(); agree += a; pairs += len(yt); kept += k; clef_yes += yt.sum()
    print(f"  {n:34s} CPU settles {s.mean():5.0%}  agrees {a / max(1, s.sum()):5.1%}  Clef yes kept {k / max(1, yt.sum()):5.0%} (of {yt.sum()})")
tot = {"pairs": int(pairs), "settled_on_cpu": round(settled / pairs, 3), "agree_on_settled": round(agree / max(1, settled), 4), "clef_yes_kept": round(kept / max(1, clef_yes), 3),
       "gpu_work_left": round(1 - settled / pairs, 3), "clef_questions_per_story_before": 2 * len(ATOMS), "note": "gpu_work_left = share of (story, atom) pairs still sent to Clef"}
print(json.dumps(tot)); json.dump({"total": tot, "atoms": out}, open(f"{D}/route-atoms-recall.json", "w"), indent=1)
