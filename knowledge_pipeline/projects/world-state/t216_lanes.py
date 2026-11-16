"""T216 (plan T148-R): three lanes for Area and Capability on same-event article pairs from different publishers.
Lane A: the live reader's topic (seed list). Lane B: noun-chunk key phrases ranked by bge-small with MMR. Lane C: predicate+object phrases from the dependency triples.
Per lane: coverage (articles with a label), labels per article, agreement between two publishers of one event, the same measure on unrelated pairs (control), and the difference.
Text seen: headline plus teaser as stored in runs/queue/unsure_v1.jsonl (median 207 characters). Judge: none; this measures stability across publishers, not truth.
    NP=<pairs> OUT=<folder> /workspace/models/embed-zs/.venv/bin/python -u t216_lanes.py -> <OUT>/t216_lanes.json"""
import os, sys, json, random, re
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, spacy
from sentence_transformers import SentenceTransformer
sys.path.insert(0, "."); import spo_chains as S
from triple_support2 import ok as triple_ok
NP = int(os.environ.get("NP", 100)); OUT = os.environ.get("OUT", "runs/pulse/t216"); os.makedirs(OUT, exist_ok=True)
rows = [json.loads(l) for l in open("runs/queue/unsure_v1.jsonl")]; P = json.load(open("runs/pulse/pairs_cache.json"))
random.seed(11)
ok = [(a, b) for a, b in P if rows[a]["domain"] != rows[b]["domain"] and len(rows[a]["text"]) > 60 and len(rows[b]["text"]) > 60]
pairs = random.sample(ok, NP)
ctrl = [(pairs[i][0], pairs[(i + 1) % NP][1]) for i in range(NP)]
nlp = spacy.load("en_core_web_sm"); m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 128
enc = lambda xs: m.encode(list(xs), batch_size=64, normalize_embeddings=True, convert_to_numpy=True)
need = sorted({i for p in pairs + ctrl for i in p}); texts = {i: rows[i]["text"] for i in need}
docs = {i: nlp(texts[i]) for i in need}
def lane_a(i): return [rows[i]["topic"]] if rows[i].get("topic") else []
def lane_b(i, k=5, div=0.5):
    cand = []
    for c in docs[i].noun_chunks:
        t = " ".join(w.lemma_.lower() for w in c if w.pos_ in ("NOUN", "PROPN", "ADJ") and w.is_alpha)
        if t and len(t.split()) <= 4 and t not in cand: cand.append(t)
    if not cand: return []
    E = enc(cand); d = enc([texts[i]])[0]; sim = E @ d; chosen = []
    for _ in range(min(k, len(cand))):
        best, bs = None, -9
        for j in range(len(cand)):
            if j in chosen: continue
            s = (1 - div) * sim[j] - (div * max(E[j] @ E[c] for c in chosen) if chosen else 0)
            if s > bs: best, bs = j, s
        chosen.append(best)
    return [cand[j] for j in chosen]
def lane_c(i):
    out = []
    for t in S.extract(nlp, [s.text for s in docs[i].sents]):
        if not (t["s"] and t["o"]) or t["s_pronoun"] or t["o_pronoun"] or t["neg"] or t["modal"] or not triple_ok(t): continue
        p = (t["p_lemma"] + " " + t["o_key"]).strip()
        if p not in out: out.append(p)
    return out
L = {n: {i: f(i) for i in need} for n, f in (("A_seed_topic", lane_a), ("B_key_phrases", lane_b), ("C_triples", lane_c))}
allp = sorted({p for d in L.values() for v in d.values() for p in v}); V = dict(zip(allp, enc(allp))) if allp else {}
def agree(la, lb, tau, exact):
    if not la or not lb: return None
    if exact: return float(set(la) == set(lb))
    sa = [max(float(V[x] @ V[y]) for y in lb) >= tau for x in la]; sb = [max(float(V[x] @ V[y]) for y in la) >= tau for x in lb]
    return (sum(sa) / len(sa) + sum(sb) / len(sb)) / 2
res = {"pairs": NP, "text_seen": "headline plus teaser", "lanes": {}}
rng = np.random.default_rng(3)
for n, d in L.items():
    exact = n.startswith("A"); r = {"coverage": float(np.mean([bool(d[i]) for i in need])), "labels_per_article": float(np.mean([len(d[i]) for i in need]))}
    for tau in ([0.0] if exact else [0.70, 0.80, 0.90]):
        s = [agree(d[a], d[b], tau, exact) for a, b in pairs]; c = [agree(d[a], d[b], tau, exact) for a, b in ctrl]
        both = [(x, y) for x, y in zip(s, c) if x is not None and y is not None]
        if not both: r[f"tau{tau}"] = None; continue
        x = np.array([b[0] for b in both]); y = np.array([b[1] for b in both]); diff = x - y
        bs = [float(diff[rng.integers(0, len(diff), len(diff))].mean()) for _ in range(1000)]
        r[f"tau{tau}"] = {"pairs_scored": len(both), "same_event": float(x.mean()), "control": float(y.mean()), "diff": float(diff.mean()), "diff_ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}
    res["lanes"][n] = r
res["samples"] = [{"a": rows[a]["text"][:120], "b": rows[b]["text"][:120], **{n: [L[n][a][:4], L[n][b][:4]] for n in L}} for a, b in pairs[:6]]
json.dump(res, open(OUT + "/t216_lanes.json", "w"), indent=1); print(json.dumps({k: v for k, v in res.items() if k != "samples"}, indent=1))
