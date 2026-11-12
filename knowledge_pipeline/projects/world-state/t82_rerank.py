"""T82: rerank the five nearest ontology terms (depth-1 ancestors) with a CPU zero-shot classifier. Candidate step = T81's code (bge-small, label+definition, constrained to the live reader's Domain). Reranker = MoritzLaurer/deberta-v3-base-zeroshot-v2.0, hypothesis 'This text is about <label>.'. Scores: embedding top-1, zero-shot rerank, fixed fusion (equal weight z-scores). Pre-registered at ledger L1575.
    NP=<n> T73DIR=<folder> /workspace/models/embed-zs/.venv/bin/python -u t82_rerank.py -> <folder>/t82_rerank.json"""
import os, sys, json, time
os.environ.setdefault("MODEL", "BAAI/bge-small-en-v1.5"); os.environ.setdefault("TERM", "def")
exec(open("t81_arm.py").read().split("h2 = [G")[0])   # ASc (article x ancestor scores, constrained), names, ids, txt, src, G, inv, h2 setup comes next
from transformers import AutoTokenizer, AutoModelForSequenceClassification
h2 = [G[i]["l2"].lower() for i in ids]; inv = np.array([x in set(D1) for x in h2]); tag = np.array([src[i] for i in ids])
ZM = "MoritzLaurer/deberta-v3-base-zeroshot-v2.0"; ztok = AutoTokenizer.from_pretrained(ZM); zm = AutoModelForSequenceClassification.from_pretrained(ZM).eval()
ent = [k for k, v in zm.config.id2label.items() if v.lower().startswith("entail")][0]
FILES = os.environ.get("FILES", "fresh,fresh2").split(","); sel = np.array([k for k in np.where(inv)[0] if tag[k] in FILES]); K = 5; cand = {k: list(np.argsort(-ASc[k])[:K]) for k in sel}; pairs = [(k, c) for k in sel for c in cand[k]]; Z = {}; t0 = time.time()
with torch.no_grad():
    for b in range(0, len(pairs), 16):
        chunk = pairs[b:b + 16]; enc = ztok([txt[ids[k]] for k, c in chunk], ["This text is about " + names[c] + "." for k, c in chunk], truncation="only_first", max_length=192, padding=True, return_tensors="pt")
        lo = zm(**enc).logits; lg = (lo[:, ent] - torch.logsumexp(torch.stack([lo[:, j] for j in range(lo.shape[1]) if j != ent], 1), 1)).numpy()   # entailment log-odds
        for (k, c), v in zip(chunk, lg): Z[(k, c)] = float(v)
        if (b // 16) % 50 == 0: print("pairs", b, len(pairs), f"{time.time() - t0:.0f}s", flush=True)
def zs(x): x = np.array(x); return (x - x.mean()) / (x.std() + 1e-9)
out = {"model": ZM, "term_text": TERM, "embedder": MODEL, "pairs_scored": len(pairs), "seconds": round(time.time() - t0, 1)}
for t in FILES:
    ks = [k for k in sel if tag[k] == t]; r = {"emb": 0, "zs": 0, "fusion": 0, "top5": 0}; per = []   # per-item hits, for a paired interval
    for k in ks:
        cs = cand[k]; e = [ASc[k, c] for c in cs]; z = [Z[(k, c)] for c in cs]; f = zs(e) + zs(z); gold = h2[k]
        r["emb"] += names[cs[int(np.argmax(e))]] == gold; r["zs"] += names[cs[int(np.argmax(z))]] == gold; r["fusion"] += names[cs[int(np.argmax(f))]] == gold; r["top5"] += gold in {names[c] for c in cs}; per.append([int(names[cs[int(np.argmax(e))]] == gold), int(names[cs[int(np.argmax(f))]] == gold)])
    out[t] = {"items": len(ks), **{k_: round(v / len(ks), 4) for k_, v in r.items()}, "per_item_emb_fusion": per}
os.makedirs(OUT, exist_ok=True); json.dump(out, open(OUT + "/t82_rerank.json", "w"), indent=1); print(json.dumps(out, indent=1))
