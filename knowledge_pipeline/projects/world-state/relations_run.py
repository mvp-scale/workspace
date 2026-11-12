"""Test 1: does meaning survive simplifying a sentence? Test 2: triples, chains and a relationship map per article. Nine articles of article_topics.json.
    CUDA_VISIBLE_DEVICES= /workspace/models/embed-zs/.venv/bin/python relations_run.py -> runs/harvest/relations/{simplify.json,relations.json,judge_items.json,judge_key.json}"""
import os, re, json, random, collections, warnings
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["CUDA_VISIBLE_DEVICES"] = ""; warnings.filterwarnings("ignore")
import numpy as np, spacy
from sentence_transformers import SentenceTransformer
import spo_chains as S, facts_lib as FL
OUT = "runs/harvest/relations"; A = json.load(open("runs/harvest/article_topics.json"))["articles"]
nlp = spacy.load("en_core_web_sm"); m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 256
enc = lambda xs: m.encode(xs, batch_size=64, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True).astype(np.float32)
NEG = {"not", "no", "n't", "never", "none", "nor", "neither", "nobody", "nothing", "cannot", "without"}
def variants(doc, triples):
    toks = [t for t in doc if not t.is_space]
    nostop = " ".join(t.text for t in toks if not t.is_stop and not t.is_punct)
    keepneg = " ".join(t.text for t in toks if (not t.is_stop or t.lower_ in NEG) and not t.is_punct)
    content = " ".join(t.text for t in toks if t.pos_ in ("NOUN", "PROPN", "VERB", "ADJ", "NUM"))
    core = "; ".join(" ".join(x for x in (tr["s"], tr["p"], tr["o"]) if x) for tr in triples)
    return {"original": doc.text, "no_noise_words": nostop, "no_noise_words_keep_negation": keepneg, "content_words": content, "core_triples": core}
simp = []; rel = []; all_orig = []; art_of = []
for ai, a in enumerate(A):
    sents = a["sentences"]; docs = list(nlp.pipe(sents)); T = S.extract(nlp, sents); alias = S.merge_aliases(T); ch = S.chains(T)
    by_sent = collections.defaultdict(list)
    for t in T: by_sent[t["sent"]].append(t)
    V = [variants(d, by_sent[i]) for i, d in enumerate(docs)]; simp.append((a, V)); all_orig += sents; art_of += [ai] * len(sents)
    tid = {t["id"]: t for t in T}
    # relationship map
    nodes = collections.defaultdict(lambda: {"mentions": collections.Counter(), "deg": 0}); edges = collections.defaultdict(lambda: {"ids": [], "verbs": collections.Counter()})
    for t in T:
        if t["s"] and t["o"] and not t["s_pronoun"] and not t["o_pronoun"]:
            for k, lab in ((t["s_key"], t["s"]), (t["o_key"], t["o"])): nodes[k]["mentions"][lab] += 1
            nodes[t["s_key"]]["deg"] += 1; nodes[t["o_key"]]["deg"] += 1; e = edges[(t["s_key"], t["o_key"])]; e["ids"].append(t["id"]); e["verbs"][("NOT " if t["neg"] else "") + t["p_lemma"] + ((" " + t["prep"]) if t["prep"] else "")] += 1
    node_list = sorted(({"key": k, "label": v["mentions"].most_common(1)[0][0], "mentions": sum(v["mentions"].values()), "degree": v["deg"]} for k, v in nodes.items()), key=lambda n: -n["degree"])
    edge_list = [{"from": k[0], "to": k[1], "verbs": dict(e["verbs"]), "count": len(e["ids"]), "ids": e["ids"]} for k, e in edges.items()]
    # existing Fact finder triples on the same sentences
    ff = FL.facts_for(" ".join(sents), "2026-01-01T00:00:00Z")[0]; fft = [f for f in ff if f["kind"] == "triple"]
    n = len(sents); with_t = len(by_sent); with_so = len({t["sent"] for t in T if t["s"] and t["o"] and not t["s_pronoun"]})
    rel.append({"idx": a["idx"], "title": a["title"], "domain": a["domain"], "sentences": sents, "triples": [{k: v for k, v in t.items() if k not in ("sent_text", "v_i")} for t in T], "chains": ch, "aliases": alias, "nodes": node_list, "edges": edge_list,
                "stats": {"sentences": n, "triples": len(T), "sentences_with_triple": with_t, "sentences_with_subject_and_object": with_so, "negated": sum(1 for t in T if t["neg"]), "modal": sum(1 for t in T if t["modal"]), "attributed": sum(1 for t in T if t["attrib"] or t["said_by"]), "passive": sum(1 for t in T if t["passive"]), "pronoun_subjects": sum(1 for t in T if t["s_pronoun"]), "chains": len(ch), "longest_chain": max([len(c) for c in ch], default=0), "chains_of_3_or_more": sum(1 for c in ch if len(c) >= 3),
                          "fact_finder_triples": len(fft), "fact_finder_stated": sum(1 for f in fft if f["status"] == "stated"), "fact_finder_unbound": sum(1 for f in fft if f["status"] == "unbound"), "fact_finder_invalid": sum(1 for f in fft if f["status"] == "invalid")},
                "fact_finder": [{"subject": f["value"][0], "verb": f["value"][1], "object": f["value"][2], "status": f["status"], "text": f["text"]} for f in fft]})
    st = rel[-1]["stats"]; print(f"{a['title'][:38]:38} sents {n:3} triples {st['triples']:3} (fact finder {st['fact_finder_triples']:3}) | sents with triple {with_t}/{n} | S+O {with_so} | longest chain {st['longest_chain']} | nodes {len(node_list)}", flush=True)
# test 1 embeddings
names = ["no_noise_words", "no_noise_words_keep_negation", "content_words", "core_triples"]
allE = enc(all_orig); pos = 0; agg = {k: {"cos": [], "top1": [], "top3": [], "same_article": [], "empty": 0} for k in names}; rnd = []; examples = []; neg_lost = collections.Counter(); neg_total = 0
rng = random.Random(7)
for ai, (a, V) in enumerate(simp):
    n = len(V); O = allE[pos:pos + n]
    for k in names:
        idx = [i for i in range(n) if V[i][k].strip()]; agg[k]["empty"] += n - len(idx)
        if not idx: continue
        VE = enc([V[i][k] for i in idx]); sim_in = VE @ O.T; sim_all = VE @ allE.T
        for r, i in enumerate(idx):
            agg[k]["cos"].append(float(VE[r] @ O[i])); order = np.argsort(-sim_in[r]); agg[k]["top1"].append(int(order[0] == i)); agg[k]["top3"].append(int(i in order[:3]))
            sa = sim_all[r].copy(); sa[pos + i] = -1; best = int(np.argmax(sa)); agg[k]["same_article"].append(int(art_of[best] == ai))  # the sentence's own original is excluded
    for _ in range(n): i, j = rng.randrange(n), rng.randrange(n); rnd.append(float(O[i] @ O[j])) if i != j else None
    for i in range(n):
        has_neg = any(w.lower_ in NEG for w in nlp(V[i]["original"]) if True)
        if has_neg:
            neg_total += 1
            for k in ("no_noise_words", "no_noise_words_keep_negation"):
                if not any(w in V[i][k].lower().split() for w in NEG): neg_lost[k] += 1
    pos += n
summary = {k: {"mean_cosine_to_original": round(float(np.mean(v["cos"])), 3), "own_sentence_first": round(float(np.mean(v["top1"])), 3), "own_sentence_in_top_3": round(float(np.mean(v["top3"])), 3), "nearest_sentence_is_from_same_article": round(float(np.mean(v["same_article"])), 3), "sentences_with_empty_variant": v["empty"], "sentences_scored": len(v["cos"])} for k, v in agg.items()}
# the same-article rate for the ORIGINAL sentence as a reference
O_sim = allE @ allE.T; np.fill_diagonal(O_sim, -1); ref_same = float(np.mean([art_of[int(np.argmax(O_sim[i]))] == art_of[i] for i in range(len(allE))]))
json.dump({"v": "simplify-v0", "model": "BAAI/bge-small-en-v1.5 (CPU)", "sentences": len(all_orig), "random_pair_cosine": round(float(np.mean(rnd)), 3), "original_nearest_other_sentence_same_article": round(ref_same, 3), "variants": summary, "negation": {"sentences_with_negation": neg_total, "negation_lost_no_noise_words": neg_lost["no_noise_words"], "negation_lost_keep_negation": neg_lost["no_noise_words_keep_negation"]},
           "per_article": [{"idx": a["idx"], "title": a["title"], "rows": [{"i": i + 1, **v} for i, v in enumerate(V)]} for a, V in simp]}, open(f"{OUT}/simplify.json", "w"), indent=1)
json.dump({"v": "relations-v0", "parser": "spaCy en_core_web_sm", "articles": rel}, open(f"{OUT}/relations.json", "w"), indent=1)
# blind judge sample: 30 own triples + 30 Fact finder triples (subject and object both present)
rng = random.Random(20261108); mine = []; theirs = []
for r in rel:
    for t in r["triples"]:
        if t["s"] and t["o"] and not t["s_pronoun"]: mine.append((r["title"], t))
    for f, tt in zip([x for x in r["fact_finder"] if x["subject"] and x["object"]], [None] * 999): theirs.append((r["title"], f))
rng.shuffle(mine); rng.shuffle(theirs); items = []; key = []
for src, lst, kind in (("mine", mine[:30], "own"), ("theirs", theirs[:30], "fact_finder")):
    for ttl, t in lst:
        if kind == "own": sent = next(x["sent_text"] if "sent_text" in x else None for x in [t]) if False else None
        items.append({"title": ttl, "kind": kind, "triple": t})
# attach the sentence text for each item
sentmap = {r["title"]: r["sentences"] for r in rel}; final = []
for it in items:
    t = it["triple"]
    if it["kind"] == "own": sent = sentmap[it["title"]][t["sent"]]; txt = {"subject": t["s"], "relation": t["p"] + (" [negated]" if t["neg"] else "") + (" [modal: " + ",".join(t["modal"]) + "]" if t["modal"] else ""), "object": t["o"]}
    else:
        sent = next((s for s in sentmap[it["title"]] if t["subject"] and t["subject"] in s and t["object"] and t["object"] in s), None) or next((s for s in sentmap[it["title"]] if t["text"] in s), ""); txt = {"subject": t["subject"], "relation": t["verb"], "object": t["object"]}
    final.append({"kind": it["kind"], "sentence": sent, **txt})
rng.shuffle(final)
for n_, f in enumerate(final): f["id"] = f"t{n_+1}"
json.dump([{k: v for k, v in f.items() if k != "kind"} for f in final], open(f"{OUT}/judge_items.json", "w"), indent=1); json.dump([{"id": f["id"], "kind": f["kind"]} for f in final], open(f"{OUT}/judge_key.json", "w"), indent=1)
print("\nSIMPLIFY (", len(all_orig), "sentences; random pair cosine", round(float(np.mean(rnd)), 3), "; original nearest-other same article", round(ref_same, 3), ")"); [print(" ", k, v) for k, v in summary.items()]; print("negation:", neg_total, "sentences;", dict(neg_lost))
print("judge items:", len(final), collections.Counter(f["kind"] for f in final))
