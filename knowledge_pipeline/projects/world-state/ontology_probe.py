#!/usr/bin/env python3
"""Free CPU probe 4: the whole reader contract, not just topic. For each ontology output, how far do cheap local tools get, against the
majority baseline and against how well Haiku and Sonnet agree with each other? Train W1-5 (teacher-consensus), test W7+W8 vs Sonnet.
Frozen 300 untouched. Run with models/embed-zs/.venv/bin/python."""
import json, os, pathlib, re, warnings
warnings.filterwarnings("ignore"); os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np
from collections import Counter
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer
from model2vec import StaticModel
HERE = pathlib.Path(__file__).resolve().parent; W = HERE / "runs" / "waves"
J = lambda p: [json.loads(l) for l in open(p) if l.strip()]
def load(n):
    items = {r["id"]: r["text"] for r in J(W / f"w{n}_items.jsonl")}
    H = {r["item_id"]: r["label"] for r in J(W / f"w{n}/haiku/labels.jsonl")}; S = {r["item_id"]: r["label"] for r in J(W / f"w{n}/sonnet/labels.jsonl")}
    return [(items[i], H[i], S[i]) for i in items if i in H and i in S]
tr = [x for n in range(1, 6) for x in load(n)]; te = load(7) + load(8)
m = StaticModel.from_pretrained("minishlab/potion-base-8M"); Etr = m.encode([t for t, _, _ in tr]); Ete = m.encode([t for t, _, _ in te])
ids = lambda l: {c["condition"] for c in l["conditions"]}; prs = lambda l: {(c["condition"], c["direction"]) for c in l["conditions"]}
print(f"train {len(tr)} items (W1-5), test {len(te)} items (W7+W8)\n")
# 1. is anything changing?
ytr = np.array([bool(ids(h) & ids(s)) or (bool(ids(h)) and bool(ids(s))) for _, h, s in tr]); yte = np.array([bool(s["conditions"]) for _, _, s in te]); yh = np.array([bool(h["conditions"]) for _, h, _ in te])
clf = LogisticRegression(max_iter=500, C=10, class_weight="balanced").fit(Etr, ytr); p = clf.predict_proba(Ete)[:, 1]
print(f"1. ANY CONDITION? positives (Sonnet) {yte.mean():.0%} of items; majority baseline accuracy {1-yte.mean():.3f}; Haiku-vs-Sonnet agreement on yes/no {np.mean(yh==yte):.3f}")
print(f"   static embedding AUC {roc_auc_score(yte, p):.3f}  (0.5 = chance)")
for rec in (0.95, 0.90):
    t = np.quantile(p[yte], 1 - rec); skip = (p < t); print(f"   keep {rec:.0%} of true positives: the cheap model clears {skip[~yte].mean():.0%} of the 'none' items, so the LLM would read {1-skip.mean():.0%} of all items")
# 2. which conditions
mlb = MultiLabelBinarizer(); Ytr = mlb.fit_transform([ids(h) & ids(s) for _, h, s in tr]); keep = Ytr.sum(0) >= 8
oc = OneVsRestClassifier(LogisticRegression(max_iter=300, C=10, class_weight="balanced")).fit(Etr, Ytr[:, keep]); cls = mlb.classes_[keep]
Pt = oc.predict_proba(Ete)
for thr in (0.5, 0.7):
    tp = fp = fn = 0
    for i, (_, h, s) in enumerate(te):
        pr = {cls[j] for j in np.where(Pt[i] >= thr)[0]}; ref = ids(s); tp += len(pr & ref); fp += len(pr - ref); fn += len(ref - pr)
    print(f"2. CONDITION IDS ({keep.sum()} of {len(mlb.classes_)} have >=8 training examples) threshold {thr}: F1 vs Sonnet {2*tp/max(2*tp+fp+fn,1):.3f} (precision {tp/max(tp+fp,1):.2f}, recall {tp/max(tp+fn,1):.2f})")
hs = [(ids(h), ids(s)) for _, h, s in te]; tp = sum(len(a & b) for a, b in hs); fp = sum(len(a - b) for a, b in hs); fn = sum(len(b - a) for a, b in hs)
print(f"   reference: Haiku vs Sonnet on the same test, condition-id F1 {2*tp/max(2*tp+fp+fn,1):.3f}")
# 3. direction on conditions both teachers tagged
pairs = [(c_h["direction"], c_s["direction"], t) for t, h, s in te for c_h in h["conditions"] for c_s in s["conditions"] if c_h["condition"] == c_s["condition"]]
UP = re.compile(r"\b(rise|rises|rose|rising|increase\w*|surge\w*|soar\w*|jump\w*|spike\w*|grow\w*|higher|record|more|shortage\w*|worsen\w*|climb\w*|hike\w*)\b", re.I)
DOWN = re.compile(r"\b(fall|falls|fell|falling|decrease\w*|drop\w*|declin\w*|plunge\w*|slump\w*|lower|less|cut\w*|ease\w*|improv\w*|reduc\w*|ceasefire|recover\w*|restor\w*)\b", re.I)
sc = lambda t: len(UP.findall(t)) - len(DOWN.findall(t)); sconn = [(s, sc(t)) for h, s, t in pairs]
dec = [(s, "up" if v > 0 else "down" if v < 0 else None) for s, v in sconn]; hit = [a == b for a, b in dec if b]; share = np.mean([b is not None for _, b in dec])
mj = Counter(s for _, s, _ in pairs).most_common(1)[0]
print(f"3. DIRECTION on {len(pairs)} conditions both teachers tagged: majority baseline '{mj[0]}' {mj[1]/len(pairs):.3f}; Haiku vs Sonnet agree {np.mean([a==b for a,b,_ in pairs]):.3f}; verb lexicon decides {share:.0%} of them and is right {np.mean(hit):.3f} of those")
# 4. level
lv = [(c_h["level"], c_s["level"]) for _, h, s in te for c_h in h["conditions"] for c_s in s["conditions"] if c_h["condition"] == c_s["condition"]]
mjl = Counter(b for _, b in lv).most_common(1)[0]
trl = [(t, c_s["level"]) for t, h, s in tr for c_h in h["conditions"] for c_s in s["conditions"] if c_h["condition"] == c_s["condition"] and c_h["level"] == c_s["level"]]
lc = LogisticRegression(max_iter=500, C=10).fit(m.encode([t for t, _ in trl]), [l for _, l in trl])
tl = [(t, c_s["level"]) for t, h, s in te for c_h in h["conditions"] for c_s in s["conditions"] if c_h["condition"] == c_s["condition"]]
pl = lc.predict(m.encode([t for t, _ in tl])); near = np.mean([abs(["minor","notable","major","severe","extreme"].index(a)-["minor","notable","major","severe","extreme"].index(b)) <= 1 for a, (_, b) in zip(pl, tl)])
print(f"4. SIZE LEVEL on {len(lv)} matched conditions: majority '{mjl[0]}' {mjl[1]/len(lv):.3f}; Haiku vs Sonnet exact {np.mean([a==b for a,b in lv]):.3f}; static embedding exact {np.mean([a==b for a,(_,b) in zip(pl,tl)]):.3f}, within one level {near:.3f}")
# 5. place
doc = (HERE.parents[1].parent / "docs/reference/2026-10-29 World engine ontology and information flow.md").read_text().split("## I. Countries (100)")[1]
names = [r.split("|")[2].strip() for r in doc.splitlines() if re.match(r"\|\s*[a-z]{3}\s*\|", r)]
alias = {"United States": ["U.S.", "US", "America", "American", "Washington"], "United Kingdom": ["UK", "U.K.", "Britain", "British"], "Russia": ["Russian", "Moscow", "Kremlin"], "China": ["Chinese", "Beijing"], "India": ["Indian", "New Delhi"]}
pat = re.compile(r"\b(" + "|".join(re.escape(x) for n in names for x in [n] + alias.get(n, [])) + r")\b")
hits = [bool(pat.search(t)) for t, _, _ in te]
print(f"5. PLACE: {len(names)} countries from the ontology; a plain name/alias lookup finds one in {np.mean(hits):.0%} of items (no truth labels for place yet, so this is coverage only)")
ex = [t for (t, _, _), h in zip(te, hits) if not h][:3]; print("   items with no country found, e.g.:", " | ".join(x[:70] for x in ex))
