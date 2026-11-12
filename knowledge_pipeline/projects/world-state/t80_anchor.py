"""T80: the ontology mapping against MN-DS human IPTC labels (level 1 and level 2). Articles, not triples. Variants: unconstrained and constrained to the live reader's Domain. Pre-registered at ledger L1558.
    NP=<n items> T73DIR=<folder> /workspace/models/embed-zs/.venv/bin/python -u t80_anchor.py -> <folder>/t80_anchor.json"""
import os, sys, json, random, collections
os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, torch
from sentence_transformers import SentenceTransformer
sys.path.insert(0, "."); from expert1_runtime import ExpertS
torch.set_num_threads(8); OUT = os.environ.get("T73DIR", "runs/pulse/t76b"); NP = int(os.environ.get("NP", 0)); A = "/workspace/data/anchors/mn_ds/"
O = json.load(open("/workspace/data/ontologies/iptc_mediatopic/mediatopic.json"))["conceptSet"]; byq = {c["qcode"]: c for c in O}; parent = {}
for c in O:
    for n in c.get("narrower", []) or []: parent[n] = c["qcode"]
lab = lambda c: (c["prefLabel"].get("en-GB") or next(iter(c["prefLabel"].values()))).lower(); dfn = lambda c: (c.get("definition") or {}).get("en-GB", "")
def chain(q):
    out = [q]; seen = {q}
    while out[-1] in parent and parent[out[-1]] not in seen: out.append(parent[out[-1]]); seen.add(out[-1])
    return out[::-1]  # top ... term
def at_depth(q, d): c = chain(q); return c[min(d, len(c) - 1)]
tq = [c["qcode"] for c in O]; d0 = [lab(byq[at_depth(q, 0)]) for q in tq]; d1 = [lab(byq[at_depth(q, 1)]) for q in tq]; D1 = {lab(c) for c in O if len(chain(c["qcode"])) == 2}
G = {}; txt = {}
for g, it in (("gold_fresh.json", "items_fresh.jsonl"), ("gold_fresh2.json", "items_fresh2.jsonl")):
    gg = json.load(open(A + g))
    for l in open(A + it):
        x = json.loads(l)
        if x["id"] in gg and x["id"] not in G: G[x["id"]] = gg[x["id"]]; txt[x["id"]] = x["text"]
ids = sorted(G); random.seed(7)
if NP: ids = random.sample(ids, min(NP, len(ids)))
m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 128
T = m.encode([lab(c) + ". " + dfn(c) for c in O], batch_size=64, normalize_embeddings=True, convert_to_numpy=True); X = m.encode([txt[i] for i in ids], batch_size=64, normalize_embeddings=True, convert_to_numpy=True); sim = X @ T.T
from iptc_alias import AL  # AL also maps the MN-DS level-1 names politics and religion and belief to the IPTC names (ledger T93)
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); cats = []
for i in ids:
    r = e.read(txt[i])["topic_top2"]; cats.append({AL.get(c.lower(), c.lower()) for t in (r["answer"] or []) for c in M.get(t, [])} if r["answer"] else None)
un = sim.argmax(1); co = un.copy()
for k in range(len(ids)):
    if cats[k]: co[k] = int(np.where(np.array([d0[j] in cats[k] for j in range(len(tq))]), sim[k], -9).argmax())
h1 = [AL.get(G[i]["l1"].lower(), G[i]["l1"].lower()) for i in ids]; h2 = [G[i]["l2"].lower() for i in ids]; inv = np.array([x in D1 for x in h2])
def acc(assign, inv_only):
    sel = np.where(inv)[0] if inv_only else np.arange(len(ids)); rg = np.random.default_rng(0)
    a1 = np.array([d0[assign[k]] == h1[k] for k in sel]); a2 = np.array([d1[assign[k]] == h2[k] for k in sel]); bs = [a2[rg.integers(0, len(sel), len(sel))].mean() for _ in range(300)]
    return {"items": int(len(sel)), "level1_accuracy": round(float(a1.mean()), 4), "level2_accuracy": round(float(a2.mean()), 4), "level2_ci95": [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)]}
maj = collections.Counter(h2[k] for k in np.where(inv)[0]).most_common(1)[0]; rg = np.random.default_rng(1); d1list = sorted(D1)
res = {"items_total": len(ids), "in_vocabulary_share": round(float(inv.mean()), 4), "unconstrained_in_vocab": acc(un, True), "constrained_in_vocab": acc(co, True), "unconstrained_all_items": acc(un, False), "constrained_all_items": acc(co, False),
       "baseline_most_common_level2": {"label": maj[0], "accuracy": round(maj[1] / int(inv.sum()), 4)}, "baseline_random_depth1_term": round(float(np.mean([d1list[int(rg.integers(0, len(d1list)))] == h2[k] for k in np.where(inv)[0] for _ in range(20)])), 4),
       "reader_domain_available_share": round(sum(1 for c in cats if c) / len(cats), 4), "note": "Level 1 / level 2 = MN-DS human IPTC labels. Mapped depth-1 ancestor compared with the human level 2 (exact label); top-level compared with the human level 1. In-vocabulary = the human level 2 is an ontology depth-1 term. Outside truth, strict labels."}
json.dump(res, open(OUT + "/t80_anchor.json", "w"), indent=1); print(json.dumps(res, indent=1))
