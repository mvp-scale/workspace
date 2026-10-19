"""Attack A4 (docs/value-indicators.md): building blocks judged per sentence. Targets: prices.consumer_up, energy.price_up, energy.supply_cut,
trust.wrongdoing. Building-block heads (support-v1, Clef agreed labels) are cross-fitted on Glance story vectors with the baselines' folds; each
fold model also scores every sentence (title + sentence, Glance). Rules from support-v1.json (AND = lowest, OR = highest).
  A direct head (story)   B story-level rule   Bs per-sentence rule (story = best sentence)   Br per-sentence relaxed rule
Scored on test stories against R1 (Clef agreed, clear) and R2 (Clef and Winnow agree, clear): average precision minus A, 95% interval (300 draws).
Run: models/embed-zs/.venv/bin/python -I newsreader/bitmob/attack_a4_sentence.py"""
import sys, os, json, re, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import value_eval as V
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.model_selection import KFold
from model2vec import StaticModel
D = V.D; ids = V.ids; first = {r["id"]: r for r in map(json.loads, open(f"{D}/queue.jsonl"))}; rows = [first[i] for i in ids]
SUP = {r["id"]: r["answers"] for r in map(json.loads, open(f"{D}/queue-support-v1.jsonl"))}
EV = {r["id"]: r["answers"] for r in map(json.loads, open(f"{D}/queue-evidence-v1.jsonl"))}
WIN = {r["id"]: r["answers"] for r in map(json.loads, open(f"{D}/queue-evidence-v1-winnow-12b.jsonl"))}
B = json.load(open("/workspace/newsreader/bitmob/batteries/support-v1.json")); NM = {c["atom"].split(".")[1]: c["atom"] for c in B["concerns"]}
SH = {"price": "price_mentioned", "change": "amount_changed", "up": "direction_up", "payer": "payer_consumer", "everyday": "good_everyday", "energy": "energy_mentioned", "disrupted": "supply_disrupted", "official": "official_actor", "accused": "accused_wrongdoing"}
RELAX = {"prices.consumer_up": "price & up", "energy.price_up": "energy & price & up", "energy.supply_cut": "energy & disrupted", "trust.wrongdoing": "official & accused"}
pm = StaticModel.from_pretrained("minishlab/potion-base-32M"); G = np.load(f"{D}/features/glance_full.npy")
SPLIT = re.compile(r"(?<=[.!?])\s+"); SENT, OWN = [], []
for k, r in enumerate(rows):
    for s in [r["title"]] + SPLIT.split(" ".join(r["text"].split()[:1200])):
        if len(s.split()) >= 3: SENT.append(r["title"] + ". " + s); OWN.append(k)
SV = pm.encode(SENT); OWN = np.array(OWN); print(f"{len(SENT)} sentences", flush=True)
have = np.array([i in SUP for i in ids]); tr_idx = np.where(V.TRN & have)[0]; te_idx = np.where(V.test)[0]; folds = list(KFold(5, shuffle=True, random_state=0).split(tr_idx))
def lab(src, i, key): a = src.get(i, {}); return a.get(f"{key}|a", 0) >= .5 and a.get(f"{key}|b", 0) >= .5
def cross(y, per_sentence):
    s = np.zeros(len(ids)); ss = np.zeros(len(SENT))
    for a, b in folds:
        m = LogisticRegression(C=4, class_weight="balanced", max_iter=5000).fit(G[tr_idx[a]], y[tr_idx[a]]); s[tr_idx[b]] = m.predict_proba(G[tr_idx[b]])[:, 1]; s[te_idx] += m.predict_proba(G[te_idx])[:, 1] / 5
        if per_sentence:
            pr = m.predict_proba(SV)[:, 1]; inb = np.isin(OWN, tr_idx[b]); ss[inb] = pr[inb]; ste = np.isin(OWN, te_idx); ss[ste] += pr[ste] / 5
    return s, ss
blocks, blocks_s = {}, {}
for sh, nm in SH.items():
    y = np.array([lab(SUP, i, NM[nm]) for i in ids]); blocks[sh], blocks_s[sh] = cross(y, True)
def rule(expr, v):
    toks = re.findall(r"\w+|[&|()]", expr); pos = [0]
    def at():
        t = toks[pos[0]]; pos[0] += 1
        if t == "(": r = orr(); pos[0] += 1; return r
        return v[t]
    def andd():
        r = at()
        while pos[0] < len(toks) and toks[pos[0]] == "&": pos[0] += 1; r = np.minimum(r, at())
        return r
    def orr():
        r = andd()
        while pos[0] < len(toks) and toks[pos[0]] == "|": pos[0] += 1; r = np.maximum(r, andd())
        return r
    return orr()
def best_sentence(score_s): b = np.zeros(len(ids)); np.maximum.at(b, OWN, score_s); return b
rng = np.random.default_rng(0); out = {}
for tgt, expr in B["rebuild"].items():
    y = np.array([lab(EV, i, tgt) for i in ids]); direct, _ = cross(y, False)
    sc = {"A direct": direct, "B story rule": rule(expr, blocks), "Bs sentence rule": best_sentence(rule(expr, blocks_s)), "Br sentence relaxed rule": best_sentence(rule(RELAX[tgt], blocks_s))}
    for ref in ("R1", "R2"):
        if ref == "R1": clear = np.array([(EV[i][f"{tgt}|a"] >= .5) == (EV[i][f"{tgt}|b"] >= .5) if i in EV else False for i in ids]); yy = y
        else:
            yw = np.array([lab(WIN, i, tgt) for i in ids]); cw = np.array([(WIN[i][f"{tgt}|a"] >= .5) == (WIN[i][f"{tgt}|b"] >= .5) if i in WIN else False for i in ids])
            c1 = np.array([(EV[i][f"{tgt}|a"] >= .5) == (EV[i][f"{tgt}|b"] >= .5) if i in EV else False for i in ids]); clear = c1 & cw & (y == yw); yy = y
        T = np.where(V.test & clear)[0]; npos = int(yy[T].sum()); res = {"positives": npos}
        if npos < 3: out[f"{tgt} {ref}"] = res; print(f"{tgt:20s} {ref}: only {npos} positives, not scored"); continue
        for k, s in sc.items():
            res[k] = round(float(average_precision_score(yy[T], s[T])), 3)
            if k != "A direct":
                d = []
                for _ in range(300):
                    r_ = rng.choice(T, len(T))
                    if yy[r_].sum() >= 2: d.append(average_precision_score(yy[r_], s[r_]) - average_precision_score(yy[r_], sc["A direct"][r_]))
                res[k + " minus A"] = [round(float(np.mean(d)), 3)] + [round(float(x), 3) for x in np.percentile(d, [2.5, 97.5])]
        out[f"{tgt} {ref}"] = res
        print(f"{tgt:20s} {ref} (positives {npos}): " + "  ".join(f"{k} {v}" for k, v in res.items() if k != "positives"), flush=True)
json.dump(out, open(f"{D}/proof/a4-results.json", "w"), indent=1)
