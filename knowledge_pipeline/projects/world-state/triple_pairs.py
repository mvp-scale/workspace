"""T65: do the same facts match across same-event articles under exact, entity-pair and embedding keys. Match rates only (unjudged).
    /workspace/models/embed-zs/.venv/bin/python -u triple_pairs.py -> runs/pulse/triple_pairs.json, triple_pairs_examples.json"""
import os, sys, json, glob, datetime, random
os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, torch, spacy, pyarrow.parquet as pq, pyarrow as pa, pyarrow.compute as pc
from sentence_transformers import SentenceTransformer
import spo_chains as S
from triple_support2 import ok
torch.set_num_threads(18)
Q = [json.loads(l) for l in open("runs/queue/unsure_v1.jsonl")]
m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 64
E = m.encode([q["text"] for q in Q], batch_size=128, normalize_embeddings=True, convert_to_numpy=True).astype(np.float32)
def _d(q):
    try: return datetime.date.fromisoformat(q["date"][:10]).toordinal()
    except Exception: return -99999
day = np.array([_d(q) for q in Q]); dom = np.array([q["domain"] for q in Q])
pairs = []; seen = set()
for s in range(0, len(Q), 2000):
    sim = E[s:s + 2000] @ E.T
    for i in range(sim.shape[0]):
        a = s + i; sim[i, a] = 0
        for b in np.where(sim[i] >= 0.85)[0]:
            if a < b and dom[a] != dom[b] and abs(day[a] - day[b]) <= 2 and (a, b) not in seen: seen.add((a, b)); pairs.append((a, b))
print("pairs", len(pairs), flush=True)
random.seed(7); random.shuffle(pairs); pairs = pairs[:600]
need = {Q[i]["id"][3:] for p in pairs for i in p}; text = {}
for f in sorted(glob.glob("/workspace/data/ccnews/raw/plain_text/*.parquet")):
    t = pq.read_table(f, columns=["url", "text"]); mk = pc.is_in(t["url"], value_set=pa.array(list(need)))
    for u, x in zip(t["url"].filter(mk).to_pylist(), t["text"].filter(mk).to_pylist()): text[u] = x or ""
nlp = spacy.load("en_core_web_sm")
def trip(i):
    sents = [s.text for s in nlp(text.get(Q[i]["id"][3:], "")[:1500]).sents][:12]; out = set()
    for t in S.extract(nlp, sents):
        if t["s"] and t["o"] and not t["s_pronoun"] and not t["o_pronoun"] and not t["neg"] and not t["modal"] and ok(t): out.add((t["s_key"], t["p"].lower(), t["o_key"]))
    return sorted(out)
tot = ex = ent = emb = 0; examples = []; npairs = 0
for a, b in pairs:
    A, B = trip(a), trip(b)
    if not A or not B: continue
    npairs += 1; sB = {" ".join(t) for t in B}; eB = {(t[0], t[2]) for t in B}
    ea = m.encode([" ".join(t) for t in A], normalize_embeddings=True, convert_to_numpy=True); eb = m.encode([" ".join(t) for t in B], normalize_embeddings=True, convert_to_numpy=True)
    sim = ea @ eb.T
    for i, t in enumerate(A):
        tot += 1; x = " ".join(t) in sB; y = (t[0], t[2]) in eB; z = sim[i].max() >= 0.90
        ex += x; ent += y; emb += z
        if z and not x and len(examples) < 25: examples.append({"a": list(t), "b": list(B[int(sim[i].argmax())]), "cos": round(float(sim[i].max()), 3)})
res = {"same_event_pairs_found": len(seen), "pairs_used_with_triples_both": npairs, "triples_in_A": tot, "exact_rate": round(ex / tot, 4), "entity_pair_rate": round(ent / tot, 4), "embedding_rate_cos090": round(emb / tot, 4)}
json.dump(res, open("runs/pulse/triple_pairs.json", "w"), indent=1); json.dump(examples, open("runs/pulse/triple_pairs_examples.json", "w"), indent=1); print(res)
