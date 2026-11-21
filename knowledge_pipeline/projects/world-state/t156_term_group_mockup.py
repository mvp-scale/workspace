"""T156 mock-up: place a word our ontology does not know by going sideways (a WordNet synonym) or one hop up (a WordNet parent) to a known IPTC Media Topics node; the IPTC tree then supplies the rest of the path.
Data: MN-DS articles with their IPTC top-level label (items_T28.jsonl + gold_T28_clean.json); IPTC Media Topics (CC BY 4.0) and Princeton WordNet 3.0, both copied to /workspace/data/ontology_src. CPU only, no download, no hosted call.
Terms: noun lemmas and noun-chunk phrases from spaCy (names are left to an entity linker). WordNet senses used: the first SENSES senses of a lemma (frequency order).
Modes per term: exact (IPTC label equals the term), side (a synonym of the term equals an IPTC label), up (a direct parent of the term equals an IPTC label), both (exact, else side, else up). Article top-level label = most votes from distinct placed terms; no votes = abstain.
Baseline: bge-small nearest IPTC top-level label (label plus definition). Scored against the MN-DS label: a proxy for correctness on the topic layer only (owner Q1, ledger L2608).
    N=300 SENSES=3 OUT=runs/pulse/t156 /workspace/models/embed-zs/.venv/bin/python -u t156_term_group_mockup.py -> <OUT>/mockup.json"""
import os, re, json, random, time, collections
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, spacy
N = int(os.environ.get("N", 300)); SENSES = int(os.environ.get("SENSES", 3)); OUT = os.environ.get("OUT", "runs/pulse/t156"); os.makedirs(OUT, exist_ok=True)
SRC = "/workspace/data/ontology_src"; MN = "/workspace/data/anchors/mn_ds"
nlp = spacy.load("en_core_web_sm", disable=["ner"])
norm = lambda s: " ".join(t.lemma_.lower() for t in nlp(s) if t.is_alpha)
# IPTC tree
cs = json.load(open(SRC + "/iptc/medtop.json"))["conceptSet"]
node = {c["qcode"]: c for c in cs}; u2q = {c["uri"]: c["qcode"] for c in cs}
par = {c["qcode"]: ((lambda b: b if b in node else u2q.get(b))((c.get("broader") or [None])[0]) if c.get("broader") else None) for c in cs}
lab = lambda q: node[q]["prefLabel"]["en-GB"].lower()
def chain(q):
    out = []
    while q: out.append(q); q = par.get(q)
    return out[::-1]
L1 = {lab(q): q for q in node if not par.get(q)}
idx = collections.defaultdict(set)     # normalised label (and comma/and parts) -> IPTC nodes
for q in node:
    full = lab(q); idx[norm(full)].add(q)
    parts = [p.strip() for p in re.split(r",| and ", full) if p.strip()]
    if len(parts) > 1:
        for p in parts: idx[norm(p)].add(q)
# WordNet nouns
wn_dir = SRC + "/wordnet/wordnet/"; syn = {}; lem = collections.defaultdict(list)
for l in open(wn_dir + "data.noun"):
    if l.startswith(" "): continue
    h, _ = l.split("|", 1); f = h.split(); off = f[0]; wc = int(f[3], 16); words = [f[4 + 2 * i].lower().replace("_", " ") for i in range(wc)]
    pc = int(f[4 + 2 * wc]); ptr = f[5 + 2 * wc:]; hy = [ptr[4 * i + 1] for i in range(pc) if ptr[4 * i] in ("@", "@i")]
    syn[off] = (words, hy)
for l in open(wn_dir + "index.noun"):
    if l.startswith(" "): continue
    f = l.split(); pcnt = int(f[3]); lem[f[0].replace("_", " ")] = f[6 + pcnt:]
def place(term):
    """-> list of (hop, iptc node, via text); one entry per distinct (hop,node)."""
    r = []
    for q in sorted(idx.get(term, ())): r.append(("exact", q, term))
    offs = lem.get(term, [])[:SENSES]
    for o in offs:
        words, hy = syn[o]
        for w in words:
            if w != term:
                for q in sorted(idx.get(norm(w), ())): r.append(("side", q, f"{term} = {w}"))
        for h in hy:
            for w in syn[h][0]:
                for q in sorted(idx.get(norm(w), ())): r.append(("up", q, f"{term} -> {w}"))
    seen = set(); out = []
    for x in r:
        if x[:2] not in seen: seen.add(x[:2]); out.append(x)
    return out
# articles
items = {}
for l in open(MN + "/items_T28.jsonl"): d = json.loads(l); items[d["id"]] = d["text"]
gold = json.load(open(MN + "/gold_T28_clean.json")); ids = sorted(i for i in items if i in gold and gold[i]["l1"] in L1); random.Random(1).shuffle(ids); ids = ids[:N]
print("articles", len(ids), "iptc nodes", len(node), "top", len(L1), "wordnet noun lemmas", len(lem), flush=True)
t0 = time.perf_counter(); terms = {}
for i, doc in zip(ids, nlp.pipe([items[i] for i in ids], batch_size=32)):
    s = {t.lemma_.lower() for t in doc if t.pos_ == "NOUN" and t.is_alpha and len(t.lemma_) > 2}
    for ch in doc.noun_chunks:
        w = [t for t in ch if t.pos_ in ("NOUN", "PROPN", "ADJ") and t.is_alpha]
        if 2 <= len(w) <= 3: s.add(" ".join(t.lemma_.lower() for t in w))
    terms[i] = sorted(s)
parse_s = time.perf_counter() - t0
cache = {}
t0 = time.perf_counter()
for i in ids:
    for t in terms[i]: cache.setdefault(t, place(t))
compile_s = time.perf_counter() - t0
t0 = time.perf_counter(); res = {m: {} for m in ("exact", "side", "up", "both")}
for i in ids:
    for t in terms[i]:
        p = cache[t]; by = {h: [x for x in p if x[0] == h] for h in ("exact", "side", "up")}
        for m in ("exact", "side", "up"):
            if by[m]: res[m].setdefault(i, {})[t] = by[m]
        for h in ("exact", "side", "up"):
            if by[h]: res["both"].setdefault(i, {})[t] = by[h]; break
lookup_ms = (time.perf_counter() - t0) / len(ids) * 1000
def vote(placed):
    c = collections.Counter()
    for t, xs in placed.items():
        for q in {chain(x[1])[0] for x in xs}: c[q] += 1.0 / len({chain(x[1])[0] for x in xs})
    return c
summ = {}
for m in res:
    ans = 0; ok = 0; nt = 0; nplaced = 0; agree = 0; deep = 0; nn = 0
    for i in ids:
        nt += len(terms[i]); pl = res[m].get(i, {}); nplaced += len(pl)
        for t, xs in pl.items():
            tops = {chain(x[1])[0] for x in xs}; agree += int(L1[gold[i]["l1"]] in tops); nn += 1; deep += int(any(len(chain(x[1])) >= 3 for x in xs))
        if pl:
            c = vote(pl); ans += 1; ok += int(max(c.items(), key=lambda kv: (kv[1], kv[0]))[0] == L1[gold[i]["l1"]])
    summ[m] = {"terms": nt, "placed_terms": nplaced, "share_terms_placed": nplaced / nt, "articles_answered": ans, "answered_share": ans / len(ids), "top_label_accuracy_on_answered": ok / max(1, ans), "placed_term_agrees_with_article_label": agree / max(1, nn), "share_placed_at_depth_2_or_more": deep / max(1, nn)}
# embedding baseline
from sentence_transformers import SentenceTransformer
m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 128
names = list(L1); LE = m.encode([f"{n}: {node[L1[n]]['definition']['en-GB']}" for n in names], normalize_embeddings=True, convert_to_numpy=True)
t0 = time.perf_counter(); AE = m.encode([items[i] for i in ids], batch_size=64, normalize_embeddings=True, convert_to_numpy=True); emb_ms = (time.perf_counter() - t0) / len(ids) * 1000
pred = [names[int(k)] for k in (AE @ LE.T).argmax(1)]; emb_ok = [int(p == gold[i]["l1"]) for p, i in zip(pred, ids)]
both_ans = [i for i in ids if i in res["both"]]
summ["embedding_nearest_label"] = {"top_label_accuracy_all": float(np.mean(emb_ok)), "top_label_accuracy_on_articles_both_answered": float(np.mean([emb_ok[ids.index(i)] for i in both_ans])) if both_ans else None, "ms_per_article": emb_ms}
summ["chance_majority_share"] = collections.Counter(gold[i]["l1"] for i in ids).most_common(1)[0][1] / len(ids)
# 40 paths to read
paths = []; rnd = random.Random(2)
for i in ids:
    for t, xs in res["both"].get(i, {}).items():
        x = xs[0]; paths.append({"article": i, "article_label": gold[i]["l1"], "term": t, "hop": x[0], "via": x[2], "iptc_path": " > ".join(lab(q) for q in chain(x[1])), "agrees": L1[gold[i]["l1"]] == chain(x[1])[0]})
rnd.shuffle(paths)
out = {"articles": len(ids), "senses": SENSES, "iptc_nodes": len(node), "unique_terms": len(cache), "parse_s_total": parse_s, "compile_s_total": compile_s, "lookup_ms_per_article": lookup_ms, "summary": summ, "paths_40": paths[:40]}
json.dump(out, open(OUT + "/mockup.json", "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "paths_40"}, indent=1))
