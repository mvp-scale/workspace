"""T219 (plan T148-R4; copy of t218 plus: number and generic objects dropped from lane C, verb-level capability candidates, per-topic concentrated key-phrase clusters).
T218 (plan T148-R3; copy of t217 with filters): generic phrases (weekday, month, number words, seen in more than GEN of articles) and light-verb predicates are dropped; per cluster the top-topic share (catch-all topics culture_leisure and other ignored) separates Area-like (concentrated) from Capability-like (spans 3 or more topics).
T217 (plan T148-R2): do key-phrase (B) and triple (C) labels recur across DIFFERENT events and publishers?
A phrase is canonicalised by greedy leader clustering on bge-small vectors (cosine at or above TAU). An event is a connected component of the same-event pair list (runs/pulse/pairs_cache.json); an article in no pair is its own event.
A cluster is reusable when it appears in at least MIN_EV events and at least MIN_DOM publishers. It spans Areas when its articles carry at least 3 different live-reader topics.
Text seen: headline plus teaser (runs/queue/unsure_v1.jsonl). No outside judge: this measures recurrence, not that a cluster is a true Area or Capability; clusters are printed for reading.
    NA=<articles> TAU=0.85 MIN_EV=5 MIN_DOM=3 OUT=<folder> /workspace/models/embed-zs/.venv/bin/python -u t219_frames.py -> <OUT>/t219_frames.json"""
import os, sys, json, random, collections
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, spacy
from sentence_transformers import SentenceTransformer
sys.path.insert(0, "."); import spo_chains as S
from triple_support2 import ok as triple_ok
NA = int(os.environ.get("NA", 8000)); TAU = float(os.environ.get("TAU", 0.85)); MIN_EV = int(os.environ.get("MIN_EV", 5)); MIN_DOM = int(os.environ.get("MIN_DOM", 3))
GEN = float(os.environ.get("GEN", 0.03)); CATCH = {"culture_leisure", "other", None}
LIGHT = {"take", "have", "make", "get", "go", "find", "add", "give", "put", "come", "see", "use", "let", "keep", "do", "be", "say", "tell", "want", "need"}
TIME = {"monday","tuesday","wednesday","thursday","friday","saturday","sunday","weekend","today","yesterday","tomorrow","year","month","week","day","time","hour","night","morning","afternoon","evening","thousand","million","hundred","billion","people","man","woman","news","life","part","way","thing","ap","information"}
OUT = os.environ.get("OUT", "runs/pulse/t219"); os.makedirs(OUT, exist_ok=True)
rows = [json.loads(l) for l in open("runs/queue/unsure_v1.jsonl")]; P = json.load(open("runs/pulse/pairs_cache.json"))
par = list(range(len(rows)))
def find(x):
    while par[x] != x: par[x] = par[par[x]]; x = par[x]
    return x
for a, b in P: par[find(a)] = find(b)
random.seed(5); ids = sorted(random.sample(range(len(rows)), NA))
nlp = spacy.load("en_core_web_sm"); m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 64
enc = lambda xs: m.encode(list(xs), batch_size=128, normalize_embeddings=True, convert_to_numpy=True)
def phrases(doc):
    b, c = [], []
    for ch in doc.noun_chunks:
        t = " ".join(w.lemma_.lower() for w in ch if w.pos_ in ("NOUN", "PROPN", "ADJ") and w.is_alpha)
        if t and len(t.split()) <= 4 and t not in b and not (set(t.split()) <= TIME): b.append(t)
    for t in S.extract(nlp, [s.text for s in doc.sents]):
        if not (t["s"] and t["o"]) or t["s_pronoun"] or t["o_pronoun"] or t["neg"] or t["modal"] or not triple_ok(t): continue
        if t["p_lemma"] in LIGHT or set(t["o_key"].split()) <= TIME: continue
        p = (t["p_lemma"] + " " + t["o_key"]).strip()
        if p not in c: c.append(p)
    return b, c
art = {}
for i, doc in zip(ids, nlp.pipe([rows[i]["text"] for i in ids], batch_size=64, n_process=1)): art[i] = phrases(doc)
res = {"articles": NA, "tau": TAU, "min_events": MIN_EV, "min_publishers": MIN_DOM, "text_seen": "headline plus teaser", "lanes": {}}
for lane, li in (("B_key_phrases", 0), ("C_triples", 1)):
    cnt = collections.Counter(p for i in ids for p in art[i][li]); uniq = [p for p, _ in cnt.most_common()]
    if not uniq: continue
    E = enc(uniq); lead = []; LM = np.zeros((len(uniq), E.shape[1]), dtype=np.float32); lab = {}
    for k, p in enumerate(uniq):
        if lead:
            s = LM[:len(lead)] @ E[k]; j = int(s.argmax())
            if s[j] >= TAU: lab[p] = lead[j]; continue
        LM[len(lead)] = E[k]; lead.append(p); lab[p] = p
    cl = collections.defaultdict(lambda: {"ev": set(), "dom": set(), "top": collections.Counter(), "arts": set(), "forms": collections.Counter()})
    for i in ids:
        for p in set(lab[x] for x in art[i][li]):
            c = cl[p]; c["ev"].add(find(i)); c["dom"].add(rows[i]["domain"]); c["top"][rows[i].get("topic")] += 1; c["arts"].add(i)
        for x in art[i][li]: cl[lab[x]]["forms"][x] += 1
    reuse = {p for p, c in cl.items() if len(c["ev"]) >= MIN_EV and len(c["dom"]) >= MIN_DOM and len(c["arts"]) <= GEN * NA}
    tot = sum(len(set(lab[x] for x in art[i][li])) for i in ids); inr = sum(len(set(lab[x] for x in art[i][li]) & reuse) for i in ids)
    wl = [i for i in ids if art[i][li]]; wr = [i for i in wl if set(lab[x] for x in art[i][li]) & reuse]
    tp = lambda p: {t: n for t, n in cl[p]["top"].items() if t not in CATCH}
    multi = [p for p in reuse if sum(1 for t, n in tp(p).items() if n >= 2) >= 3]
    conc = [p for p in reuse if tp(p) and max(tp(p).values()) / sum(tp(p).values()) >= 0.5 and sum(tp(p).values()) >= 5]
    top = sorted(reuse, key=lambda p: -len(cl[p]["ev"]))[:40]
    res["lanes"][lane] = {"unique_phrases": len(uniq), "clusters": len(cl), "reusable_clusters": len(reuse), "reusable_spanning_3plus_topics": len(multi), "reusable_topic_concentrated_top_share_0.5": len(conc),
        "share_of_article_labels_in_reusable": inr / max(1, tot), "articles_with_label": len(wl), "share_of_labelled_articles_with_a_reusable_label": len(wr) / max(1, len(wl)),
        "top_reusable": [{"cluster": p, "forms": [f for f, _ in cl[p]["forms"].most_common(3)], "events": len(cl[p]["ev"]), "publishers": len(cl[p]["dom"]), "topics": [t for t, _ in cl[p]["top"].most_common(4) if t not in CATCH][:3]} for p in top]}
    if lane == "C_triples":
        pv = collections.defaultdict(lambda: {"ev": set(), "dom": set(), "obj": collections.Counter(), "top": collections.Counter()})
        for i in ids:
            for ph in set(art[i][1]):
                v = ph.split()[0]; q = pv[v]; q["ev"].add(find(i)); q["dom"].add(rows[i]["domain"]); q["obj"][lab[ph]] += 1; q["top"][rows[i].get("topic")] += 1
        keep = {v: q for v, q in pv.items() if len(q["ev"]) >= MIN_EV and len(q["dom"]) >= MIN_DOM and len(q["obj"]) >= 3}
        res["lanes"][lane]["verb_capabilities"] = len(keep)
        res["lanes"][lane]["verb_capabilities_top"] = [{"verb": v, "events": len(q["ev"]), "publishers": len(q["dom"]), "object_clusters": len(q["obj"]), "topics": [t for t, _ in q["top"].most_common(4) if t not in CATCH][:3], "sample_objects": [o for o, _ in q["obj"].most_common(4)]} for v, q in sorted(keep.items(), key=lambda kv: -len(kv[1]["ev"]))[:60]]
    if lane == "B_key_phrases":
        bt = collections.defaultdict(list)
        for p in conc:
            t = tp(p); top = max(t, key=t.get); bt[top].append((len(cl[p]["ev"]), p, max(t.values()) / sum(t.values())))
        res["lanes"][lane]["per_topic_concentrated"] = {t: [{"cluster": p, "events": e, "top_share": round(sh, 2), "forms": [f for f, _ in cl[p]["forms"].most_common(2)]} for e, p, sh in sorted(v, reverse=True)[:8]] for t, v in sorted(bt.items(), key=lambda kv: -len(kv[1]))}
        res["lanes"][lane]["topics_with_3plus_concentrated"] = sum(1 for v in bt.values() if len(v) >= 3)
json.dump(res, open(OUT + "/t219_frames.json", "w"), indent=1)
for n, r in res["lanes"].items(): print(n, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items() if k != "top_reusable"})
