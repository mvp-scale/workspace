"""T97 (T91 on the whole-pool pairs of T95; pairs are row numbers in runs/pulse/t95/pairs_idx.npy with pool_meta.jsonl; at most CAP partners per article are kept (seeded), so the largest same-event clusters do not dominate the cost). Earlier: T91 (T76 on the T90 pool; pairs are url ids from runs/pulse/t90/pairs_ids.json, not queue indexes). Original T76: how many independent publishers back a triple. For each article with at least 2 same-event partners (from the cached pair list), count how many independent partners (different domain by construction, shingle Jaccard under 0.30) have a triple that agrees on at least two of subject key, predicate lemma, object key. Text keys only (T73 and T75 showed entity keys add nothing). Control: the same count against random articles. Match rates only, unjudged.
    PAIRS=<pairs_ids.json> NP=<n core articles> T73DIR=<folder> PROCS=<n> /workspace/models/embed-zs/.venv/bin/python -u t97_support.py -> <folder>/t97_support.json, t97_supported_triples.json (article = url)"""
import os, sys, json, glob, re, random, collections, pathlib
os.environ["CUDA_VISIBLE_DEVICES"] = ""
sys.path.insert(0, "/workspace/knowledge_pipeline/kit/live")
import pyarrow.parquet as pq, pyarrow as pa, pyarrow.compute as pc, spacy
from multiprocessing import Pool
sys.path.insert(0, "."); import spo_chains as S
from triple_support2 import ok
OUT = os.environ.get("T73DIR", "runs/pulse/t97"); NP = int(os.environ.get("NP", 0)); os.makedirs(OUT, exist_ok=True)
# smoke runs say SMOKE=1; NP alone is a real run on a sample
import heartbeat as hb; JOB = "t97-support" if not os.environ.get("SMOKE") else "t97-support-smoke"; CAP = int(os.environ.get("CAP", 30)); import numpy as np
PD = pathlib.Path(os.environ.get("PAIRDIR", "runs/pulse/t95")); PI = np.load(PD / "pairs_idx.npy"); META = [json.loads(l) for l in open(PD / "pool_meta.jsonl")]; nb = collections.defaultdict(set)
for a, b in PI.tolist(): nb[a].add(b); nb[b].add(a)
core = sorted(a for a, v in nb.items() if len(v) >= 2); random.seed(7)
if NP: core = random.sample(core, min(NP, len(core)))
nbc = {a: (sorted(nb[a]) if len(nb[a]) <= CAP else random.Random(a).sample(sorted(nb[a]), CAP)) for a in core}  # kept partners
need = set(core)
for a in core: need |= set(nbc[a])
need = sorted(need); urls = {META[i]["url"] for i in need}; text = {}; print("core", len(core), "to parse", len(need), flush=True)
for f in sorted(glob.glob("/workspace/data/ccnews/raw/plain_text/*.parquet")):
    t = pq.read_table(f, columns=["url", "text"]); mk = pc.is_in(t["url"], value_set=pa.array(list(urls)))
    for u, x in zip(t["url"].filter(mk).to_pylist(), t["text"].filter(mk).to_pylist()): text[u] = x or ""
body = lambda i: text.get(META[i]["url"], "")[:1500]
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
    hb.beat(JOB, state="running", where="[CPU]", alive_pid=os.getpid(), every_s=180, why="Parse the whole-pool core articles and count triples backed by 2 or more independent publishers (T97)", success="t91_support.json written", progress=f"parsing {len(need)} articles")
    with Pool(int(os.environ.get("PROCS", 6)), initializer=init) as pool: TR = dict(pool.map(trip, need, chunksize=20))
    def shing(t):
        w = re.findall(r"\w+", t.lower()); return {hash(" ".join(w[i:i + 5])) for i in range(max(0, len(w) - 4))}  # hashed to keep 150000 articles in memory
    SH = {i: shing(body(i)) for i in need}; jac = lambda a, b: len(SH[a] & SH[b]) / max(1, len(SH[a] | SH[b]))
    def agree2(t, u): t, u = t[0], u[0]; return (t[0] == u[0]) + (t[1] == u[1]) + (t[2] == u[2]) >= 2
    def support(t, partners):  # number of partners with at least one triple agreeing on two of three
        return sum(any(agree2(t, u) for u in TR[b]) for b in partners)
    pool_ids = [i for i in need if TR[i]]; SUP = []; B = {"1": [0, 0, 0, 0], "2": [0, 0, 0, 0], "3-5": [0, 0, 0, 0], "6+": [0, 0, 0, 0]}; C = {k: [0, 0, 0, 0] for k in B}
    for a in core:
        ip = [b for b in nbc[a] if TR[b] and jac(a, b) < 0.30]
        if not TR[a] or not ip: continue
        k = len(ip); bk = "1" if k == 1 else "2" if k == 2 else "3-5" if k <= 5 else "6+"
        rnd = [x for x in random.sample(pool_ids, min(k + 40, len(pool_ids))) if x != a and x not in nb[a]][:k]  # control: random articles, not partners
        for t in TR[a]:
            for D, partners in ((B, ip), (C, rnd)):
                s = support(t, partners)
                if D is B and s >= 2: SUP.append({"article": META[a]["url"], "key": list(t[0]), "sentence": t[1], "support": int(s), "independent_partners": int(k)})
                D[bk][0] += 1; D[bk][1] += s >= 1; D[bk][2] += s >= 2; D[bk][3] += s >= 3
    rate = lambda D: {k: {"triples": v[0], "support_ge1": round(v[1] / max(1, v[0]), 4), "support_ge2": round(v[2] / max(1, v[0]), 4), "support_ge3": round(v[3] / max(1, v[0]), 4), "n_support_ge2": v[2]} for k, v in D.items()}
    res = {"n_supported_triples_ge2": len(SUP), "articles_with_supported_triples": len({x["article"] for x in SUP}), "core_articles": len(core), "articles_parsed": len(need), "articles_with_triples": len(pool_ids), "independent_partners_bucket": rate(B), "control_random_partners": rate(C), "note": "Share of an article's triples backed by at least 1, 2, 3 independent same-event partner articles on two of three elements (text keys, predicate lemma). Bucket = how many independent partners the article has. Control: the same number of random articles. Unjudged."}
    json.dump(res, open(OUT + "/t97_support.json", "w"), indent=1); json.dump(SUP, open(OUT + "/t97_supported_triples.json", "w")); print(json.dumps(res, indent=1))
    (hb.drop(JOB) if JOB.endswith("smoke") else hb.finish(JOB, "done", progress=f"{len(SUP)} supported triples", last="finished"))
