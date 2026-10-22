import json, re, math, collections, sys, os
import numpy as np
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D + "/pylib")
STOP = set("the and for that with from this have has was were are said says will would been their they its his her who which about after into more than also not but over new one two year years could other some what when there people state told percent per be do get make go".split())
W = re.compile(r"[a-z]{3,}")
CHANGE = set("rise rose rising raise surge soar jump climb increase grow growth gain high higher record hike spike double triple fall drop plunge slump decline decrease cut slash reduce shrink lose loss low lower shortage scarcity short ban halt suspend delay disrupt strain squeeze worsen hit crisis spiral shock".split())
def load_jsonl(p): return [json.loads(l) for l in open(p)]
def lemset(n): return set(w for w in n["lem"] if W.fullmatch(w) and w not in STOP)
def mine(docs, dial_sets, topk=20, minpos=3):
    """docs: list of sets; dial_sets: list of sets of dials. returns {dial:[words]}"""
    N = len(docs); df = collections.Counter(w for t in docs for w in t); KW = {}
    for d in sorted({d for ds in dial_sets for d in ds}):
        pos = [t for t, ds in zip(docs, dial_sets) if d in ds]; npos = len(pos)
        if npos < minpos: continue
        c = collections.Counter(w for t in pos for w in t); sc = []
        for w, k in c.items():
            if k < 3: continue
            rest = df[w] - k
            lo = math.log((k + .5) / (npos - k + .5)) - math.log((rest + .5) / (N - npos - rest + .5)); sc.append((lo * math.sqrt(k), w))
        KW[d] = [w for _, w in sorted(sc, reverse=True)[:topk]]
    return KW
def kw_score(docs, KW):
    out = np.zeros((len(docs), 2))
    for i, t in enumerate(docs):
        h = [len(t & set(ws)) for ws in KW.values()]
        out[i] = (max(h), sum(h))
    return out[:, 0] + out[:, 1] / 100.0
_wn = None
def wn_expand(KW, docs, dial_sets, maxsyn=3):
    """add WordNet synonyms of each keyword, keep those with lift>=2 and >=2 positive docs on the given (train) docs"""
    global _wn
    if _wn is None:
        import nltk; nltk.data.path.insert(0, D + "/data/nltk")
        from nltk.corpus import wordnet as wn; _wn = wn
    N = len(docs); df = collections.Counter(w for t in docs for w in t); out = {}
    for d, ws in KW.items():
        npos = sum(1 for ds in dial_sets if d in ds); prior = npos / N
        cands = set()
        for w in ws:
            for s in _wn.synsets(w)[:maxsyn]:
                for l in s.lemma_names():
                    l = l.lower()
                    if W.fullmatch(l) and l not in STOP and l not in ws: cands.add(l)
        keep = []
        for c in cands:
            if df[c] < 3: continue
            k = sum(1 for t, ds in zip(docs, dial_sets) if c in t and d in ds)
            if k >= 2 and k / df[c] >= 2 * prior: keep.append(c)
        out[d] = list(ws) + keep
    return out
def conc_table():
    T = {}
    for l in open(D + "/data/concreteness.txt").read().split("\n")[1:]:
        p = l.split("\t")
        if len(p) > 3 and p[1] == "0": 
            try: T[p[0]] = float(p[2])
            except: pass
    return T
def change_feats(n, ctab):
    lem = [w for w in n["lem"] if W.fullmatch(w)]; L = max(len(lem), 1)
    cv = sum(1 for w in lem if w in CHANGE)
    c = [ctab[w] for w in lem if w in ctab]
    return [n["n_num"] / L * 100, n["n_pct"] / L * 100, n["n_money"] / L * 100, cv / L * 100, cv, n["n_pct"] + n["n_money"] > 0]
def conc_feats(n, ctab):
    c = [ctab[w] for w in n["lem"] if w in ctab]
    return [np.mean(c) if c else 3, np.mean([x >= 4 for x in c]) if c else .3]
def ner_feats(n):
    L = max(len(n["lem"]), 1); e = n["ents"]; tot = sum(e.values())
    return [tot / L * 100, e.get("PERSON", 0) / L * 100, (e.get("GPE", 0) + e.get("LOC", 0)) / L * 100, e.get("ORG", 0) / L * 100,
            (e.get("MONEY", 0) + e.get("PERCENT", 0) + e.get("CARDINAL", 0)) / L * 100, math.log(L)]
