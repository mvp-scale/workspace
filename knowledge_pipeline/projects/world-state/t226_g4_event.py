"""T226 (plan T148 step 30, G4 alignment inside one event): within each same-event article group (connected groups of runs/pulse/pairs_cache.json over runs/queue/unsure_v1.jsonl), align the full-article triples across publishers.
Baseline: exact (subject key, predicate lemma, object key). Matcher: same predicate lemma, and subject key and object key each equal or at least TAU cosine apart (bge-small on the key phrases).
A group's independent sources = distinct article clusters after merging copies (5-word shingle Jaccard at or above 0.30 over the first 1,500 body characters). Also counts how many exact-key groups merged ACROSS events when keys are pooled over the whole corpus (the T225 problem).
Text seen: first 1,500 characters of the article body (runs from /workspace/data/ccnews). No outside judge: 40 matcher-only merges are written out for reading.
    TAU=0.85 OUT=runs/pulse/t226 /workspace/models/embed-zs/.venv/bin/python -u t226_g4_event.py -> <OUT>/t226_g4_event.json"""
import os, sys, json, re, glob, random, collections
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, spacy, pyarrow as pa, pyarrow.parquet as pq, pyarrow.compute as pc
from multiprocessing import Pool
sys.path.insert(0, "."); import spo_chains as S
from triple_support2 import ok as triple_ok
TAU = float(os.environ.get("TAU", 0.85)); OUT = os.environ.get("OUT", "runs/pulse/t226"); os.makedirs(OUT, exist_ok=True)
rows = [json.loads(l) for l in open("runs/queue/unsure_v1.jsonl")]; P = json.load(open("runs/pulse/pairs_cache.json"))
par = list(range(len(rows)))
def find(x):
    while par[x] != x: par[x] = par[par[x]]; x = par[x]
    return x
for a, b in P: par[find(a)] = find(b)
ev = collections.defaultdict(set)
for a, b in P: ev[find(a)] |= {a, b}
events = [sorted(v) for v in ev.values()][:int(os.environ.get("LIMIT", 10**9))]; ids = sorted({i for e in events for i in e})
urls = {rows[i]["id"][3:] for i in ids}; text = {}
for f in sorted(glob.glob("/workspace/data/ccnews/raw/plain_text/*.parquet")):
    t = pq.read_table(f, columns=["url", "text"]); mk = pc.is_in(t["url"], value_set=pa.array(list(urls)))
    for u, x in zip(t["url"].filter(mk).to_pylist(), t["text"].filter(mk).to_pylist()): text[u] = x or ""
body = {i: text.get(rows[i]["id"][3:], "")[:1500] for i in ids}
nlp = None
def init():
    global nlp; nlp = spacy.load("en_core_web_sm")
def trip(i):
    b = body[i]
    if len(b.strip()) < 3: return i, []
    sents = [s.text for s in nlp(b).sents][:12]; sents = [x for x in sents if len(re.findall(r"\w", x)) >= 2]; out = []
    for t in S.extract(nlp, sents):
        if t["s"] and t["o"] and not t["s_pronoun"] and not t["o_pronoun"] and not t["neg"] and not t["modal"] and triple_ok(t): out.append((t["s_key"], t["p_lemma"], t["o_key"], t["sent_text"]))
    return i, out
if __name__ == "__main__":
    with Pool(int(os.environ.get("PROCS", 8)), initializer=init) as pool: TR = dict(pool.map(trip, ids, chunksize=20))
    shing = lambda t: {" ".join(w[k:k + 5]) for w in [re.findall(r"\w+", t.lower())] for k in range(max(0, len(w) - 4))}
    SH = {i: shing(body[i]) for i in ids}; jac = lambda a, b: len(SH[a] & SH[b]) / max(1, len(SH[a] | SH[b]))
    keys = sorted({k for i in ids for t in TR[i] for k in (t[0], t[2])})
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 32
    E = m.encode(keys, batch_size=256, normalize_embeddings=True, convert_to_numpy=True); ix = {k: j for j, k in enumerate(keys)}
    def uf(n):
        p = list(range(n))
        def f(x):
            while p[x] != x: p[x] = p[p[x]]; x = p[x]
            return x
        return p, f
    per_event = []; edges = []; samples = []; rnd = random.Random(4)
    for e in events:
        src_p, src_f = uf(len(e))
        for a in range(len(e)):
            for b in range(a + 1, len(e)):
                if jac(e[a], e[b]) >= 0.30: src_p[src_f(a)] = src_f(b)
        T = [(src_f(a), e[a], *t) for a, art in enumerate(e) for t in TR[art]]   # (source cluster, article, s, p, o, sentence)
        n = len(T); res = {}
        for name in ("exact", "matcher"):
            p, f = uf(n)
            byp = collections.defaultdict(list)
            for j, t in enumerate(T): byp[t[3]].append(j)
            for pl, js in byp.items():
                for x in range(len(js)):
                    for y in range(x + 1, len(js)):
                        i, j = js[x], js[y]
                        if T[i][0] == T[j][0]: continue
                        if name == "exact": hit = T[i][2] == T[j][2] and T[i][4] == T[j][4]
                        else:
                            hit = (T[i][2] == T[j][2] or float(E[ix[T[i][2]]] @ E[ix[T[j][2]]]) >= TAU) and (T[i][4] == T[j][4] or float(E[ix[T[i][4]]] @ E[ix[T[j][4]]]) >= TAU)
                            if hit and not (T[i][2] == T[j][2] and T[i][4] == T[j][4]) and len(samples) < 4000: samples.append({"a": [T[i][2], T[i][3], T[i][4], T[i][5].strip()[:160]], "b": [T[j][2], T[j][3], T[j][4], T[j][5].strip()[:160]]})
                        if hit: p[f(i)] = f(j)
            g = collections.defaultdict(set)
            for j in range(n): g[f(j)].add(T[j][0])
            sizes = collections.Counter(f(j) for j in range(n))
            if name == "exact":
                gi = collections.defaultdict(list)
                for j in range(n): gi[f(j)].append(j)
                for r, js in gi.items():
                    if len({T[j][0] for j in js}) >= 2: edges.append({"event": len(per_event), "subject": T[js[0]][2], "predicate": T[js[0]][3], "object": T[js[0]][4], "triples": len(js), "independent_sources": len({T[j][0] for j in js}), "articles": sorted({T[j][1] for j in js}), "publishers": sorted({rows[T[j][1]]["domain"] for j in js}), "sentences": [T[j][5].strip()[:200] for j in js[:3]], "provenance": "exact-key alignment inside one same-event group; no outside truth"})
            res[name] = {"triples": n, "in_2plus": sum(sizes[r] for r, s in g.items() if len(s) >= 2), "groups_2plus": sum(1 for s in g.values() if len(s) >= 2), "groups_3plus": sum(1 for s in g.values() if len(s) >= 3)}
        per_event.append(res)
    agg = lambda nm, k: sum(r[nm][k] for r in per_event)
    ratios = []; rng = np.random.default_rng(9); idx = np.arange(len(per_event))
    ex = np.array([r["exact"]["in_2plus"] for r in per_event]); ma = np.array([r["matcher"]["in_2plus"] for r in per_event]); g3e = np.array([r["exact"]["groups_3plus"] for r in per_event]); g3m = np.array([r["matcher"]["groups_3plus"] for r in per_event])
    for _ in range(1000):
        s = rng.choice(idx, len(idx)); ratios.append(ma[s].sum() / max(1, ex[s].sum()))
    gk = collections.defaultdict(lambda: {"ev": set(), "art": set()})
    for ei, e in enumerate(events):
        for a in e:
            for t in TR[a]: k = (t[0], t[1], t[2]); gk[k]["ev"].add(ei); gk[k]["art"].add(a)
    multi = [v for v in gk.values() if len(v["art"]) >= 2]
    random.Random(5).shuffle(samples)
    out = {"events": len(events), "articles": len(ids), "articles_with_body": sum(1 for i in ids if body[i]), "triples": sum(len(TR[i]) for i in ids), "tau": TAU,
           "exact": {k: agg("exact", k) for k in ("triples", "in_2plus", "groups_2plus", "groups_3plus")}, "matcher": {k: agg("matcher", k) for k in ("triples", "in_2plus", "groups_2plus", "groups_3plus")},
           "ratio_in_2plus_matcher_over_exact": float(ma.sum() / max(1, ex.sum())), "ratio_ci95": [float(np.percentile(ratios, 2.5)), float(np.percentile(ratios, 97.5))], "events_with_a_3plus_group": {"exact": int((g3e > 0).sum()), "matcher": int((g3m > 0).sum())},
           "global_exact_keys_in_2plus_articles": len(multi), "share_of_those_spanning_2plus_events": sum(1 for v in multi if len(v["ev"]) >= 2) / max(1, len(multi)),
           "matcher_only_merges_total": len(samples), "reading_sample_40": samples[:40]}
    open(OUT + "/g4_edges_exact.jsonl", "w").write("".join(json.dumps(x) + "\n" for x in edges))
    json.dump(out, open(OUT + "/t226_g4_event.json", "w"), indent=1); print(json.dumps({k: v for k, v in out.items() if k != "reading_sample_40"}, indent=1))
