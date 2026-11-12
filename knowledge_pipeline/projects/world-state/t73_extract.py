"""T66 (T65 split by syndication): do the same facts match across same-event articles under exact, entity-pair and embedding keys. Match rates only (unjudged).
    /workspace/models/embed-zs/.venv/bin/python -u triple_pairs.py -> runs/pulse/triple_pairs2.json"""
import os, sys, json, glob, datetime, random, re
os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, torch, spacy, pyarrow.parquet as pq, pyarrow as pa, pyarrow.compute as pc
from sentence_transformers import SentenceTransformer
import spo_chains as S
from triple_support2 import ok
torch.set_num_threads(18)
Q = [json.loads(l) for l in open("runs/queue/unsure_v1.jsonl")]
CACHE = "runs/pulse/pairs_cache.json"  # the shuffled list of all same-event pairs, computed once (saves about 8 minutes a run)
if os.path.exists(CACHE): pairs = [tuple(p) for p in json.load(open(CACHE))]; print("pairs from cache", len(pairs), flush=True)
else:
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
    random.seed(7); random.shuffle(pairs); json.dump([[int(a), int(b)] for a, b in pairs], open(CACHE, "w"))
pairs = pairs[int(os.environ.get("PAIR_START", 0)):int(os.environ.get("PAIR_END", 600))][:int(os.environ.get("NP", 600))]
need = {Q[i]["id"][3:] for p in pairs for i in p}; text = {}
for f in sorted(glob.glob("/workspace/data/ccnews/raw/plain_text/*.parquet")):
    t = pq.read_table(f, columns=["url", "text"]); mk = pc.is_in(t["url"], value_set=pa.array(list(need)))
    for u, x in zip(t["url"].filter(mk).to_pylist(), t["text"].filter(mk).to_pylist()): text[u] = x or ""
nlp = spacy.load("en_core_web_sm")
def trip(i):
    out = {}
    sents = [s.text for s in nlp(text.get(Q[i]["id"][3:], "")[:1500]).sents][:12]
    for t in S.extract(nlp, sents):
        if t["s"] and t["o"] and not t["s_pronoun"] and not t["o_pronoun"] and not t["neg"] and not t["modal"] and ok(t):
            out[(t["s_key"], t["p"].lower(), t["o_key"])] = {"s": t["s"], "s_key": t["s_key"], "p": t["p"].lower(), "p_lemma": t["p_lemma"], "o": t["o"], "o_key": t["o_key"], "sent_text": t["sent_text"]}
    return list(out.values())
def shing(t):
    w = re.findall(r"\w+", t.lower()); return {" ".join(w[i:i + 5]) for i in range(max(0, len(w) - 4))}
res = []
for a, b in pairs:
    A, B = trip(a), trip(b)
    if not A or not B: continue
    sa, sb = shing(text.get(Q[a]["id"][3:], "")[:1500]), shing(text.get(Q[b]["id"][3:], "")[:1500]); jac = len(sa & sb) / max(1, len(sa | sb))
    res.append({"a": int(a), "b": int(b), "group": "copy" if jac >= 0.30 else "independent", "A": A, "B": B})
json.dump(res, open(os.environ.get("T73DIR", "runs/pulse") + "/t73_triples.json", "w")); sents = sorted({t["sent_text"] for r in res for t in r["A"] + r["B"]})
json.dump(sents, open(os.environ.get("T73DIR", "runs/pulse") + "/t73_sentences.json", "w")); print("pairs with triples", len(res), "unique sentences", len(sents), "copy", sum(r["group"] == "copy" for r in res))
