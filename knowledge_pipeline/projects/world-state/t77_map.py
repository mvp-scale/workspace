"""T77: map triples backed by 2+ independent publishers (T76) onto the IPTC Media Topics ontology (CC BY 4.0, 1,394 terms) by embedding similarity (bge-small-en-v1.5). Checks: coverage at a cosine threshold, consistency of the mapped top-level category with the live reader's topic for the same article, a shuffled-assignment control, and a first-draft Area table (terms with enough supported triples). No human naming; AI only maps. Unjudged against truth.
    T73DIR=<folder with t76_supported_triples.json> /workspace/models/embed-zs/.venv/bin/python -u t77_map.py -> <folder>/t77_map.json, t77_area_draft.json"""
import os, sys, json, random, collections
os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, torch
from sentence_transformers import SentenceTransformer
sys.path.insert(0, "."); from expert1_runtime import ExpertS
torch.set_num_threads(int(os.environ.get("THREADS", 8))); D = os.environ.get("T73DIR", "runs/pulse/t76"); NP = int(os.environ.get("NP", 0))
SUP = json.load(open(D + "/t76_supported_triples.json")); random.seed(7)
if NP: SUP = random.sample(SUP, min(NP, len(SUP)))
Q = [json.loads(l) for l in open(os.environ.get("QUEUE", "runs/queue/unsure_v1.jsonl"))]  # QUEUE: another article list (T92 uses the T91 pool); default unchanged
O = json.load(open("/workspace/data/ontologies/iptc_mediatopic/mediatopic.json"))["conceptSet"]
byq = {c["qcode"]: c for c in O}; parent = {}
for c in O:
    for n in c.get("narrower", []) or []: parent[n] = c["qcode"]
def top(q):
    seen = set()
    while q in parent and q not in seen: seen.add(q); q = parent[q]
    return q
lab = lambda c: c["prefLabel"].get("en-GB") or c["prefLabel"].get("en-US") or next(iter(c["prefLabel"].values()))
dfn = lambda c: (c.get("definition") or {}).get("en-GB", "")
def depth(q):
    n = 0; seen = set()
    while q in parent and q not in seen: seen.add(q); q = parent[q]; n += 1
    return n
DMAX = int(os.environ.get("DEPTH_MAX", 99)); SUF = os.environ.get("SUF", "")
terms = [c for c in O if depth(c["qcode"]) <= DMAX]; tq = [c["qcode"] for c in terms]; ttop = [lab(byq[top(q)]).lower() for q in tq]
m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 128
T = m.encode([lab(c) + ". " + dfn(c) for c in terms], batch_size=64, normalize_embeddings=True, convert_to_numpy=True)
def enc_unique(texts):  # syndicated copies repeat sentences and keys: embed each distinct text once
    us = sorted(set(texts)); ix = {t: i for i, t in enumerate(us)}; U = m.encode(us, batch_size=64, normalize_embeddings=True, convert_to_numpy=True); return U[[ix[t] for t in texts]]
X = enc_unique([s["sentence"] for s in SUP]); XK = enc_unique([" ".join(s["key"]) for s in SUP])
sim = X @ T.T; best = sim.argmax(1); bs = sim.max(1); simk = XK @ T.T; bk = simk.argmax(1); bsk = simk.max(1)
from iptc_alias import AL
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); cache = {}
def art_cats(a):
    if a not in cache:
        r = e.read(Q[a]["text"])["topic_top2"]; cache[a] = {AL.get(c.lower(), c.lower()) for t in (r["answer"] or []) for c in M.get(t, [])} if r["answer"] else None
    return cache[a]
res = {"depth_max": DMAX, "supported_triples": len(SUP), "unique_keys": len({tuple(s["key"]) for s in SUP}), "articles": len({s["article"] for s in SUP}), "ontology_terms": len(terms), "thresholds": {}}
rg = np.random.default_rng(7)
for th in (0.40, 0.45, 0.50, 0.55, 0.60):
    sel = [i for i in range(len(SUP)) if bs[i] >= th]; selk = [i for i in range(len(SUP)) if bsk[i] >= th]
    ok = [(ttop[best[i]] in art_cats(SUP[i]["article"])) for i in sel if art_cats(SUP[i]["article"]) is not None]
    rnd = [(ttop[int(rg.integers(0, len(terms)))] in art_cats(SUP[i]["article"])) for i in sel if art_cats(SUP[i]["article"]) is not None]
    cnt = collections.Counter(best[i] for i in sel)
    res["thresholds"][str(th)] = {"coverage_sentence": round(len(sel) / len(SUP), 4), "coverage_keys_only": round(len(selk) / len(SUP), 4), "consistency_with_article_topic": round(float(np.mean(ok)), 4) if ok else None, "consistency_random_term": round(float(np.mean(rnd)), 4) if rnd else None, "scored_items": len(ok),
                                  "terms_with_5plus": sum(1 for v in cnt.values() if v >= 5), "terms_with_10plus": sum(1 for v in cnt.values() if v >= 10), "top_level_categories_covered": len({ttop[i] for i in cnt})}
res["reader_abstained_share"] = round(sum(1 for a in cache.values() if a is None) / max(1, len(cache)), 4)
th = 0.50; cnt = collections.defaultdict(list)
for i in range(len(SUP)):
    if bs[i] >= th: cnt[int(best[i])].append(i)
draft = sorted(({"term": lab(terms[j]), "qcode": tq[j], "top_level": ttop[j], "supported_triples": len(v), "articles": len({SUP[i]["article"] for i in v}), "examples": [" ".join(SUP[i]["key"]) for i in v[:3]]} for j, v in cnt.items() if len(v) >= 5), key=lambda r: -r["supported_triples"])
res["area_draft_terms_at_0.50"] = len(draft); res["note"] = "Consistency = the mapped top-level IPTC category is among the categories of the live reader's top-two topics for the same article (lenient mapping topic_to_iptc_v1). Random control = a random ontology term's top-level category. Unjudged against truth; the reader's own error is in the number."
json.dump(res, open(D + "/t77_map" + SUF + ".json", "w"), indent=1); json.dump(draft, open(D + "/t77_area_draft" + SUF + ".json", "w"), indent=1); print(json.dumps(res, indent=1)); print([ (r["term"], r["supported_triples"]) for r in draft[:12]])
