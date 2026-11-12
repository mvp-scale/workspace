"""T79: Domain from the live reader, term from the ontology. Reproducibility of the assignment for the same fact stated in different articles. Reuses the T77 loading, embeddings and similarity (first part of t77_map.py).
    T73DIR=<folder with t76_supported_triples.json> /workspace/models/embed-zs/.venv/bin/python -u t79_constrain.py -> <folder>/t79_constrain.json, t79_area_draft.json"""
import os, sys, json, random, collections
src = open("t77_map.py").read().split('res = {"depth_max"')[0]; exec(src)
anc = {}
def chain(q):
    out = [q]; seen = {q}
    while out[-1] in parent and parent[out[-1]] not in seen: out.append(parent[out[-1]]); seen.add(out[-1])
    return out  # term, parent, ..., top
def at_depth(q, d):  # ancestor at depth d (0 = top); the term itself if it is shallower
    c = chain(q)[::-1]; return c[min(d, len(c) - 1)]
tqi = {q: j for j, q in enumerate(tq)}; cats = [art_cats(s["article"]) for s in SUP]
un = best.copy(); co = best.copy(); marg = np.zeros(len(SUP))
for i in range(len(SUP)):
    if cats[i]:
        mask = np.array([ttop[j] in cats[i] for j in range(len(tq))]); s_ = np.where(mask, sim[i], -9); co[i] = int(s_.argmax())
groups = collections.defaultdict(list)
for i, s_ in enumerate(SUP): groups[tuple(s_["key"])].append(i)
rnd = random.Random(7); pairs = []
for k, v in groups.items():
    ps = [(a, b) for x, a in enumerate(v) for b in v[x + 1:] if SUP[a]["article"] != SUP[b]["article"]]
    rnd.shuffle(ps); pairs += ps[:10]
keys_multi = [k for k, v in groups.items() if len({SUP[i]["article"] for i in v}) >= 2]
allidx = list(range(len(SUP))); base = [(rnd.choice(allidx), rnd.choice(allidx)) for _ in range(len(pairs))]
base = [(a, b) for a, b in base if tuple(SUP[a]["key"]) != tuple(SUP[b]["key"]) and SUP[a]["article"] != SUP[b]["article"]]
def agree(assign, P):
    if not P: return None
    t = [assign[a] == assign[b] for a, b in P]; d1 = [at_depth(tq[assign[a]], 1) == at_depth(tq[assign[b]], 1) for a, b in P]; d0 = [ttop[assign[a]] == ttop[assign[b]] for a, b in P]
    return {"pairs": len(P), "same_term": round(float(np.mean(t)), 4), "same_depth1_ancestor": round(float(np.mean(d1)), 4), "same_top_level": round(float(np.mean(d0)), 4)}
res = {"supported_triples": len(SUP), "unique_keys": len(groups), "keys_in_2plus_articles": len(keys_multi), "pairs_same_key": len(pairs), "unconstrained": agree(un, pairs), "constrained_to_reader_domain": agree(co, pairs), "baseline_random_pairs_unconstrained": agree(un, base), "baseline_random_pairs_constrained": agree(co, base),
       "reader_domain_available_share": round(sum(1 for c in cats if c) / len(cats), 4), "note": "Pairs of rows with the same triple key from different articles. Same-term etc. = both rows were assigned the same ontology term / depth-1 ancestor / top-level category. Constrained = candidates limited to the descendants of the top-level categories of the live reader's top-two topics for the row's article. Measures reproducibility of the assignment, not truth."}
cnt = collections.defaultdict(list)
for i in range(len(SUP)):
    if bs[i] >= 0.0: cnt[int(co[i])].append(i)
draft = sorted(({"term": lab(terms[j]), "qcode": tq[j], "top_level": ttop[j], "depth1_ancestor": lab(byq[at_depth(tq[j], 1)]), "supported_triples": len(v), "articles": len({SUP[i]["article"] for i in v}), "examples": [" ".join(SUP[i]["key"]) for i in v[:3]]} for j, v in cnt.items() if len(v) >= 5), key=lambda r: -r["supported_triples"])
res["constrained_terms_with_5plus"] = len(draft); res["constrained_terms_with_10plus"] = sum(1 for r in draft if r["supported_triples"] >= 10)
if os.environ.get("DUMP"):
    json.dump({"rows": len(SUP), "term_qcode": tq, "term_label": [lab(t) for t in terms], "depth1_label": [lab(byq[at_depth(q, 1)]) for q in tq], "top_label": ttop, "assign_constrained": [int(x) for x in co], "assign_unconstrained": [int(x) for x in un]}, open(D + "/t79_assign.json", "w"))
json.dump(res, open(D + "/t79_constrain.json", "w"), indent=1); json.dump(draft, open(D + "/t79_area_draft.json", "w"), indent=1); print(json.dumps(res, indent=1)); print([(r["term"], r["supported_triples"]) for r in draft[:10]])
