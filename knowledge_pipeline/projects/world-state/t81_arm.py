"""T81: one arm of the ontology-mapping matrix against MN-DS human IPTC level 2. MODEL = sentence-transformers id, TERM = def | tree. Writes <OUT>/t81_<model>_<term>.json with per-file (fresh, fresh2) in-vocabulary level-2 accuracy (top-1, top-3, top-5), constrained and unconstrained. Pre-registered at ledger L1566.
    MODEL=BAAI/bge-small-en-v1.5 TERM=def NP=<n> T73DIR=<folder> /workspace/models/embed-zs/.venv/bin/python -u t81_arm.py"""
import os, sys, json, random, collections
os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, torch
from sentence_transformers import SentenceTransformer
sys.path.insert(0, "."); from expert1_runtime import ExpertS
torch.set_num_threads(int(os.environ.get("THREADS", 12))); OUT = os.environ.get("T73DIR", "runs/pulse/t81"); NP = int(os.environ.get("NP", 0)); A = "/workspace/data/anchors/mn_ds/"; MODEL = os.environ["MODEL"]; TERM = os.environ.get("TERM", "def")
O = json.load(open("/workspace/data/ontologies/iptc_mediatopic/mediatopic.json"))["conceptSet"]; byq = {c["qcode"]: c for c in O}; parent = {}; kids = collections.defaultdict(list)
for c in O:
    for n in c.get("narrower", []) or []: parent[n] = c["qcode"]; kids[c["qcode"]].append(n)
lab = lambda c: (c["prefLabel"].get("en-GB") or next(iter(c["prefLabel"].values()))).lower(); dfn = lambda c: (c.get("definition") or {}).get("en-GB", "")
def chain(q):
    out = [q]; seen = {q}
    while out[-1] in parent and parent[out[-1]] not in seen: out.append(parent[out[-1]]); seen.add(out[-1])
    return out[::-1]
def at_depth(q, d): c = chain(q); return c[min(d, len(c) - 1)]
def descendants(q, levels):
    out = []; frontier = [q]
    for _ in range(levels):
        frontier = [k for f in frontier for k in kids.get(f, [])]; out += frontier
    return out
tq = [c["qcode"] for c in O]; d0 = [lab(byq[at_depth(q, 0)]) for q in tq]; d1 = [lab(byq[at_depth(q, 1)]) for q in tq]; D1 = sorted({lab(c) for c in O if len(chain(c["qcode"])) == 2})
text = lambda c: lab(c) + ". " + dfn(c) + ((" Includes: " + ", ".join(lab(byq[k]) for k in descendants(c["qcode"], 2)[:40]) + ".") if TERM == "tree" else "")
pre_q, pre_p = ("query: ", "passage: ") if "e5" in MODEL else ("", "")
G = {}; txt = {}; src = {}
for g, it, tag in (("gold_fresh.json", "items_fresh.jsonl", "fresh"), ("gold_fresh2.json", "items_fresh2.jsonl", "fresh2")):
    gg = json.load(open(A + g))
    for l in open(A + it):
        x = json.loads(l)
        if x["id"] in gg and x["id"] not in G: G[x["id"]] = gg[x["id"]]; txt[x["id"]] = x["text"]; src[x["id"]] = tag
ids = sorted(G); random.seed(7)
if NP: ids = random.sample(ids, min(NP, len(ids)))
m = SentenceTransformer(MODEL, device="cpu", trust_remote_code=False); m.max_seq_length = 128
T = m.encode([pre_p + text(c) for c in O], batch_size=32, normalize_embeddings=True, convert_to_numpy=True); X = m.encode([pre_q + txt[i] for i in ids], batch_size=32, normalize_embeddings=True, convert_to_numpy=True); sim = X @ T.T
from iptc_alias import AL
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); cats = []
for i in ids:
    r = e.read(txt[i])["topic_top2"]; cats.append({AL.get(c.lower(), c.lower()) for t in (r["answer"] or []) for c in M.get(t, [])} if r["answer"] else None)
anc_idx = collections.defaultdict(list)
for j in range(len(tq)): anc_idx[d1[j]].append(j)
names = sorted(anc_idx); AS = np.stack([sim[:, anc_idx[n]].max(1) for n in names], 1)  # ancestor score = best descendant term
top_of = {n: d0[anc_idx[n][0]] for n in names}
ASc = AS.copy()
for k in range(len(ids)):
    if cats[k]:
        for a, n in enumerate(names):
            if top_of[n] not in cats[k]: ASc[k, a] = -9
h2 = [G[i]["l2"].lower() for i in ids]; inv = np.array([x in set(D1) for x in h2]); tag = np.array([src[i] for i in ids])
def acc(S, mask):
    sel = np.where(mask & inv)[0]; rk = np.argsort(-S[sel], 1); out = {"items": int(len(sel))}
    for kk in (1, 3, 5): out[f"top{kk}"] = round(float(np.mean([h2[sel[r]] in {names[x] for x in rk[r, :kk]} for r in range(len(sel))])), 4)
    return out
res = {"model": MODEL, "term": TERM, "articles": len(ids), "in_vocabulary_share": round(float(inv.mean()), 4)}
for t in ("fresh", "fresh2"): mk = tag == t; res[t] = {"unconstrained": acc(AS, mk), "constrained": acc(ASc, mk)}
os.makedirs(OUT, exist_ok=True); fn = OUT + "/t81_" + MODEL.split("/")[-1] + "_" + TERM + ".json"; json.dump(res, open(fn, "w"), indent=1); print(json.dumps(res))
