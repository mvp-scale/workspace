"""T76: how many independent publishers back a triple. For each article with at least 2 same-event partners (from the cached pair list), count how many independent partners (different domain by construction, shingle Jaccard under 0.30) have a triple that agrees on at least two of subject key, predicate lemma, object key. Text keys only (T73 and T75 showed entity keys add nothing). Control: the same count against random articles. Match rates only, unjudged.
    NP=<n core articles> T73DIR=<folder> /workspace/models/embed-zs/.venv/bin/python -u t76_support.py -> <folder>/t76_support.json"""
import os, sys, json, glob, re, random, collections
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import pyarrow.parquet as pq, pyarrow as pa, pyarrow.compute as pc, spacy
from multiprocessing import Pool
sys.path.insert(0, "."); import spo_chains as S
from triple_support2 import ok
OUT = os.environ.get("T73DIR", "runs/pulse"); NP = int(os.environ.get("NP", 0))
Q = [json.loads(l) for l in open("runs/queue/unsure_v1.jsonl")]; P = json.load(open("runs/pulse/pairs_cache.json")); nb = collections.defaultdict(set)
for a, b in P: nb[a].add(b); nb[b].add(a)
core = sorted(a for a, v in nb.items() if len(v) >= 2); random.seed(7)
if NP: core = random.sample(core, min(NP, len(core)))
need = set(core)
for a in core: need |= nb[a]
need = sorted(need); urls = {Q[i]["id"][3:] for i in need}; text = {}
for f in sorted(glob.glob("/workspace/data/ccnews/raw/plain_text/*.parquet")):
    t = pq.read_table(f, columns=["url", "text"]); mk = pc.is_in(t["url"], value_set=pa.array(list(urls)))
    for u, x in zip(t["url"].filter(mk).to_pylist(), t["text"].filter(mk).to_pylist()): text[u] = x or ""
body = lambda i: text.get(Q[i]["id"][3:], "")[:1500]
nlp = None
def init():
    global nlp; nlp = spacy.load("en_core_web_sm")
def trip(i):
    b = body(i)
    if len(b.strip()) < 3: return i, []
    sents = [s.text for s in nlp(b).sents][:12]; sents = [x for x in sents if len(re.findall(r"\w", x)) >= 2]; out = {}
    for t in S.extract(nlp, sents):
        if t["s"] and t["o"] and not t["s_pronoun"] and not t["o_pronoun"] and not t["neg"] and not t["modal"] and ok(t): out[(t["s_key"], t["p_lemma"], t["o_key"])] = t["sent_text"]
    return i, [(k, v) for k, v in out.items()]
if __name__ == "__main__":
    with Pool(int(os.environ.get("PROCS", 6)), initializer=init) as pool: TR = dict(pool.map(trip, need, chunksize=20))
    def shing(t):
        w = re.findall(r"\w+", t.lower()); return {" ".join(w[i:i + 5]) for i in range(max(0, len(w) - 4))}
    SH = {i: shing(body(i)) for i in need}; jac = lambda a, b: len(SH[a] & SH[b]) / max(1, len(SH[a] | SH[b]))
    def agree2(t, u): t, u = t[0], u[0]; return (t[0] == u[0]) + (t[1] == u[1]) + (t[2] == u[2]) >= 2
    def support(t, partners):  # number of partners with at least one triple agreeing on two of three
        return sum(any(agree2(t, u) for u in TR[b]) for b in partners)
    pool_ids = [i for i in need if TR[i]]; SUP = []; B = {"1": [0, 0, 0, 0], "2": [0, 0, 0, 0], "3-5": [0, 0, 0, 0], "6+": [0, 0, 0, 0]}; C = {k: [0, 0, 0, 0] for k in B}
    for a in core:
        ip = [b for b in nb[a] if TR[b] and jac(a, b) < 0.30]
        if not TR[a] or not ip: continue
        k = len(ip); bk = "1" if k == 1 else "2" if k == 2 else "3-5" if k <= 5 else "6+"
        rnd = random.sample([x for x in pool_ids if x != a and x not in nb[a]], min(k, len(pool_ids) - 1))
        for t in TR[a]:
            for D, partners in ((B, ip), (C, rnd)):
                s = support(t, partners)
                if D is B and s >= 2: SUP.append({"article": int(a), "key": list(t[0]), "sentence": t[1], "support": int(s), "independent_partners": int(k)})
                D[bk][0] += 1; D[bk][1] += s >= 1; D[bk][2] += s >= 2; D[bk][3] += s >= 3
    rate = lambda D: {k: {"triples": v[0], "support_ge1": round(v[1] / max(1, v[0]), 4), "support_ge2": round(v[2] / max(1, v[0]), 4), "support_ge3": round(v[3] / max(1, v[0]), 4), "n_support_ge2": v[2]} for k, v in D.items()}
    res = {"core_articles": len(core), "articles_parsed": len(need), "articles_with_triples": len(pool_ids), "independent_partners_bucket": rate(B), "control_random_partners": rate(C), "note": "Share of an article's triples backed by at least 1, 2, 3 independent same-event partner articles on two of three elements (text keys, predicate lemma). Bucket = how many independent partners the article has. Control: the same number of random articles. Unjudged."}
    json.dump(res, open(OUT + "/t76_support.json", "w"), indent=1); json.dump(SUP, open(OUT + "/t76_supported_triples.json", "w")); print(json.dumps(res, indent=1))
