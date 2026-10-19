"""Second approach to Grammar: tense and negation scoped to the sentences that mention the atom (its own lexicon from Sieve), instead of whole-part
counts. Per atom and story: number of matching sentences, and among them the share negated, with a modal (could/may/might/would), with "will",
in past tense. Added as features to Glance's head (the approach that worked for Sieve); scored against Glance alone, same split and cut-off rule.
Run: models/embed-zs/.venv/bin/python -I newsreader/bitmob/grammar_scoped.py"""
import json, glob, hashlib, re, numpy as np, spacy
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
D = "/workspace/data/mm3-train"; F = f"{D}/features"; ids = json.load(open(f"{F}/ids.json")); first = {r["id"]: r for r in map(json.loads, open(f"{D}/queue.jsonl"))}; rows = [first[i] for i in ids]
SN = json.load(open(f"{F}/sieve_names.json")); LEXRE = {a: re.compile(r"\b(" + "|".join(map(re.escape, ws)) + r")\w*", re.I) for a, ws in SN["lexicon"].items()}
Q = {"first": first}; ANG = {}
for c in ("civil_unrest|up", "war_terror|up", "crime|up", "cyber_insecurity|up"): ANG[c] = ("first", f"{c}|states", f"{c}|concrete")
for f in sorted(glob.glob("/workspace/newsreader/bitmob/batteries/evidence-v*.json")):
    B = json.load(open(f)); Q[B["name"]] = {r["id"]: r for r in map(json.loads, open(f"{D}/queue-{B['name']}.jsonl"))}
    for c in B["concerns"]: ANG[c["atom"]] = (B["name"], f"{c['atom']}|a", f"{c['atom']}|b")
ANG = {k: v for k, v in ANG.items() if k in json.load(open(f"{D}/route-current.json"))["atoms_used"] and k in LEXRE}
nlp = spacy.load("en_core_web_sm", disable=["lemmatizer", "ner"])
docs = list(nlp.pipe([r["title"] + ". " + " ".join(r["text"].split()[:1200]) for r in rows], n_process=12, batch_size=32))
SENTS = [[(s.text, any(t.dep_ == "neg" for t in s), any(t.tag_ == "MD" and t.lower_ != "will" for t in s), any(t.lower_ == "will" for t in s), sum(t.tag_ == "VBD" for t in s) > 0) for s in d.sents] for d in docs]
def feats(atom):
    out = []
    for ss in SENTS:
        m = [s for s in ss if LEXRE[atom].search(s[0])]; k = len(m)
        out.append([np.log1p(k)] + ([np.mean([s[j] for s in m]) for j in (1, 2, 3, 4)] if k else [0, 0, 0, 0]))
    return np.array(out, float)
h = np.array([int(hashlib.sha256(i.encode()).hexdigest(), 16) % 5 for i in ids]); fit, val, test = h >= 2, h == 1, h == 0; G = np.load(f"{F}/glance_full.npy")
def run(X, y):
    p = LogisticRegression(C=4, class_weight="balanced", max_iter=5000).fit(X[fit], y[fit]).predict_proba(X)[:, 1]; c = max(np.linspace(.02, .98, 49), key=lambda t: f1_score(y[val], p[val] >= t)); return p >= c
tot = {"Glance": [0, 0, 0], "Glance + sentence count only": [0, 0, 0], "Glance + scoped Grammar": [0, 0, 0]}
for n, (w, ka, kb) in ANG.items():
    a = np.array([Q[w][i]["answers"][ka] >= .5 for i in ids]); b = np.array([Q[w][i]["answers"][kb] >= .5 for i in ids]); y = a & b
    if y[fit].sum() < 3 or y[val].sum() < 2: continue
    T = test & (a == b); Xg = np.hstack([G, feats(n) * 0.5])
    for name, X in (("Glance", G), ("Glance + sentence count only", np.hstack([G, feats(n)[:, :1] * 0.5])), ("Glance + scoped Grammar", Xg)):
        p = run(X, y)[T]; yt = y[T]; tot[name][0] += (p & yt).sum(); tot[name][1] += (p & ~yt).sum(); tot[name][2] += (~p & yt).sum()
for name, (tp, fp, fn) in tot.items(): print(f"{name:26s} precision {tp / max(1, tp + fp):.3f} recall {tp / max(1, tp + fn):.3f} false positives/100 {100 * fp / test.sum():.1f}")
