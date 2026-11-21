"""T157: does choosing a word's sense by the article topic put placed words on the right IPTC subtopic?
Same lean pack and 300 MN-DS articles as T156 (IPTC Media Topics, WordNet 3.0). A word's candidate IPTC nodes (exact, synonym, one hop up) are kept only if their top-level topic equals a topic prior: none, predicted (bge-small nearest IPTC top-level label), or oracle (the MN-DS label: an upper bound, not a result).
Article top-label accuracy is circular under a filter and is not used. Metric: among placed words whose node has a level-2 ancestor, the share whose level-2 node equals the article's MN-DS level-2 node (gold_T28_clean.json), reported with the share of words placed.
    N=300 SENSES=3 OUT=runs/pulse/t157 /workspace/models/embed-zs/.venv/bin/python -u t157_sense_by_topic.py -> <OUT>/sense_by_topic.json"""
import os, re, json, random, time, collections
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, spacy
N = int(os.environ.get("N", 300)); SENSES = int(os.environ.get("SENSES", 3)); OUT = os.environ.get("OUT", "runs/pulse/t157"); os.makedirs(OUT, exist_ok=True)
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

from sentence_transformers import SentenceTransformer
m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 128
names = list(L1); LE = m.encode([f"{n}: {node[L1[n]]['definition']['en-GB']}" for n in names], normalize_embeddings=True, convert_to_numpy=True)
AE = m.encode([items[i] for i in ids], batch_size=64, normalize_embeddings=True, convert_to_numpy=True)
pred = {i: L1[names[int(k)]] for i, k in zip(ids, (AE @ LE.T).argmax(1))}
l2q = {}
for q in node:
    c = chain(q)
    if len(c) == 2: l2q[(lab(c[0]), lab(c[1]))] = q
gl2 = {i: l2q.get((gold[i]["l1"], gold[i]["l2"])) for i in ids}
PRI = {"exact": 0, "side": 1, "up": 2}
def run(prior):
    nt = placed = deep = agree = 0; rows = []
    for i in ids:
        nt += len(terms[i])
        for t in terms[i]:
            c = cache[t]
            if prior == "pred": c = [x for x in c if chain(x[1])[0] == pred[i]]
            elif prior == "oracle": c = [x for x in c if chain(x[1])[0] == L1[gold[i]["l1"]]]
            if not c: continue
            x = sorted(c, key=lambda y: PRI[y[0]])[0]; placed += 1; ch = chain(x[1])
            if len(ch) >= 2 and gl2[i]:
                deep += 1; ok = ch[1] == gl2[i]; agree += int(ok)
                rows.append({"article": i, "term": t, "hop": x[0], "via": x[2], "path": " > ".join(lab(q) for q in ch), "gold": f"{gold[i]['l1']} > {gold[i]['l2']}", "l2_agrees": ok})
    return {"terms": nt, "placed": placed, "share_placed": placed / nt, "placed_with_level2_and_gold": deep, "level2_agreement": agree / max(1, deep)}, rows
out = {"articles": len(ids), "articles_with_gold_l2_node": sum(1 for i in ids if gl2[i]), "predicted_topic_accuracy": sum(pred[i] == L1[gold[i]["l1"]] for i in ids) / len(ids)}; rr = {}
for p in ("none", "pred", "oracle"): out[p], rr[p] = run(p)
rnd = random.Random(3); sample = rr["pred"][:]; rnd.shuffle(sample); out["paths_40_predicted_filter"] = sample[:40]
json.dump(out, open(OUT + "/sense_by_topic.json", "w"), indent=1); print(json.dumps({k: v for k, v in out.items() if k != "paths_40_predicted_filter"}, indent=1))
# worked examples for the plan page: short articles with the most agreeing placed words under the predicted filter
ex = []
for i in ids:
    if len(items[i]) > 480: continue
    ws = []
    for t in terms[i]:
        c = cache[t]
        if not c: continue
        a = sorted(c, key=lambda y: PRI[y[0]])[0]; f = [x for x in c if chain(x[1])[0] == pred[i]]; b = sorted(f, key=lambda y: PRI[y[0]])[0] if f else None
        ws.append({"term": t, "no_filter": {"hop": a[0], "via": a[2], "path": " > ".join(lab(q) for q in chain(a[1]))}, "filtered": None if not b else {"hop": b[0], "via": b[2], "path": " > ".join(lab(q) for q in chain(b[1]))}})
    ex.append({"id": i, "text": items[i], "gold": f"{gold[i]['l1']} > {gold[i]['l2']}", "predicted_topic": lab(pred[i]), "words": ws, "n_filtered": sum(1 for w in ws if w["filtered"]), "n_ok": sum(1 for w in ws if w["filtered"] and gl2[i] and chain(next(q for q in node if " > ".join(lab(z) for z in chain(q)) == w["filtered"]["path"]))[1:2] == [gl2[i]])})
ex.sort(key=lambda e: (-e["n_ok"], -e["n_filtered"])); json.dump(ex[:6], open(OUT + "/examples.json", "w"), indent=1)
