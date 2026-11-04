"""Area tag pilot (ledger L383): can open-vocabulary tags be proposed on the CPU and verified by local Clef, are they consistent, do they merge, and does reading the whole article add tags?
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python tag_pilot.py [--n N]      N small = smoke test. Local Clef (port 8018) answers typed yes/no questions; CPU for the rest; no hosted calls.
Publisher text stays local: article text is never printed or written to the results; only tag phrases and scores are."""
import os, sys, re, json, time, random, sqlite3, math, urllib.request, concurrent.futures as cf, collections, numpy as np
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"
import spacy
from sentence_transformers import SentenceTransformer
N = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 100
TECH = "--tech" in sys.argv   # capability pilot: full tech articles only
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
nlp = spacy.load("en_core_web_sm"); enc = SentenceTransformer("MongoDB/mdbr-leaf-mt", device="cpu"); enc.max_seq_length = 512
# ---- sample
pool = J("data/pool_train.jsonl"); pool = [r for r in pool if r["date"] and len(r["text"]) >= 120]; random.Random(5).shuffle(pool); shorts = [{"id": r["id"], "group": "short_pool", "text": re.sub(r"\s+", " ", r["text"])} for r in pool[:N]]
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); rows = db.execute("select id, title, body from items where length(coalesce(body,'')) > 3500 and length(body) < 14000" + (" and category = 'tech'" if TECH else "")).fetchall(); random.Random(6).shuffle(rows)
seen = set(); arts = []
for i, t, b in rows:
    k = re.sub(r"\W+", " ", (t or "").lower())[:60]
    if k in seen or not t: continue
    seen.add(k); b = re.sub(r"\s+", " ", b).strip(); arts.append((i, t.strip(), b))
    if len(arts) == N: break
items = [] if TECH else list(shorts)
for i, t, b in arts:
    if not TECH: items.append({"id": f"q:{i}", "group": "short_article", "pair": f"q:{i}", "text": t + ". " + b[:300]})
    items.append({"id": f"q:{i}", "group": "full_article", "pair": f"q:{i}", "text": t + ". " + b[:3500]})
print("items", len(items), collections.Counter(x["group"] for x in items), flush=True)
# ---- proposer (CPU)
BAD = {"DATE", "TIME", "CARDINAL", "ORDINAL", "PERCENT", "MONEY", "QUANTITY"}; DET = {"the", "a", "an", "this", "that", "these", "those", "his", "her", "its", "their", "our", "my", "your", "some", "any", "each", "every"}
def norm(s):
    w = [x for x in re.sub(r"[^\w\s\-&.']", " ", s.lower()).split() if x]
    while w and w[0] in DET: w = w[1:]
    s = " ".join(w).strip(" .-'"); return s
def propose(text, K):
    d = nlp(text); c = collections.Counter(); low = text.lower()
    for ch in d.noun_chunks:
        if ch.root.pos_ in ("PRON", "NUM") or ch.root.ent_type_ in BAD: continue
        s = norm(ch.text)
        if len(s) >= 3 and not s.isdigit() and not all(x in nlp.Defaults.stop_words for x in s.split()): c[s] += 1
    for e in d.ents:
        if e.label_ in BAD: continue
        s = norm(e.text)
        if len(s) >= 3 and not s.isdigit(): c[s] += 1
    cands = [s for s in c if len(s) <= 40]
    if not cands: return []
    E = enc.encode(cands + [text[:2000]], batch_size=64, normalize_embeddings=True, show_progress_bar=False); sims = E[:-1] @ E[-1]
    sc = [0.5 * float(sims[k]) + 0.5 * min(1.0, math.log1p(low.count(s)) / math.log(6)) for k, s in enumerate(cands)]
    return [cands[k] for k in np.argsort(sc)[::-1][:K]]
t0 = time.time()
for x in items: x["cands"] = propose(x["text"], 8 if x["group"] != "full_article" else 12)
print("proposed", sum(len(x["cands"]) for x in items), f"{time.time() - t0:.0f}s", flush=True)
# ---- Clef verifier: five narrow questions per candidate (<=160 chars, one polarity)
Q = {"s1": "Is '{c}' one of the main subjects of this article, not just a passing mention?", "s2": "Would a person searching for information about '{c}' find this article relevant?", "s3": "Does the article say something specific about '{c}', beyond just naming it?",
     "t1": "Is '{c}' a technology, skill, method or process, something that can be done or used?", "t2": "Is '{c}' the name of a specific organisation, person or place?"}
assert all(len(v.format(c="x" * 40)) <= 160 for v in Q.values())
def ask(x):
    qs = {f"{j}|{k}": {"type": "noul", "instructions": Q[k].format(c=c)} for j, c in enumerate(x["cands"]) for k in Q}
    body = {"state": "News article:\n" + x["text"], "questions": qs, "model": "clef-flash-q4km"}
    for attempt in range(3):
        try:
            a = json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8018/v1/systemone", json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=900))["answers"]
            return {key: float(v["noul"]) for key, v in a.items()}
        except Exception as e: err = str(e)[:120]; time.sleep(2)
    return {"error": err}
t0 = time.time()
with cf.ThreadPoolExecutor(6) as ex: R = list(ex.map(ask, items))
print(f"clef {time.time() - t0:.0f}s for {len(items)} calls", flush=True)
errs = sum(1 for r in R if "error" in r)
for x, r in zip(items, R): x["ans"] = r
json.dump([{k: v for k, v in x.items() if k != "text"} for x in items], open(("runs/tag_pilot/raw_tech.json" if TECH else "runs/tag_pilot/raw.json") if N >= 50 else "runs/tag_pilot/smoke.json", "w"))
print("errors", errs, flush=True)
# ---- analysis
def kappa(a, b):
    a, b = np.array(a), np.array(b); po = float((a == b).mean()); pe = float(a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean())); return (po - pe) / (1 - pe) if pe < 1 else 1.0
cand_rows = []
for x in items:
    if "error" in x["ans"]: continue
    for j, c in enumerate(x["cands"]):
        a = {k: x["ans"].get(f"{j}|{k}", 0.0) for k in Q}; cand_rows.append({"grp": x["group"], "id": x["id"], "c": c, **a, "accepted": sum(a[k] >= 0.5 for k in ("s1", "s2", "s3")) >= 2})
res = {"n_items": len(items), "clef_errors": errs, "candidates": len(cand_rows), "accepted": sum(r["accepted"] for r in cand_rows)}
b = {k: [r[k] >= 0.5 for r in cand_rows] for k in Q}
res["kappa"] = {"s1_s2": round(kappa(b["s1"], b["s2"]), 3), "s1_s3": round(kappa(b["s1"], b["s3"]), 3), "s2_s3": round(kappa(b["s2"], b["s3"]), 3)}; res["yes_rate"] = {k: round(float(np.mean(v)), 3) for k, v in b.items()}
per = collections.defaultdict(list)
for x in items:
    if "error" not in x["ans"]: per[x["group"]].append(sum(r["accepted"] for r in cand_rows if r["id"] == x["id"] and r["grp"] == x["group"]))
res["accepted_per_item"] = {g: {"mean": round(float(np.mean(v)), 2), "median": float(np.median(v)), "zero": int(sum(1 for t in v if t == 0))} for g, v in per.items()}
acc = [r for r in cand_rows if r["accepted"]]; res["type_share"] = {"capability(t1)": round(float(np.mean([r["t1"] >= 0.5 for r in acc])), 3) if acc else None, "entity(t2)": round(float(np.mean([r["t2"] >= 0.5 for r in acc])), 3) if acc else None, "neither": round(float(np.mean([(r["t1"] < 0.5) and (r["t2"] < 0.5) for r in acc])), 3) if acc else None}
occ = collections.defaultdict(set)
for r in acc: occ[r["c"]].add((r["id"], r["grp"]))
tags = sorted(occ); res["distinct_tags"] = len(tags); res["singleton_share_before_merge"] = round(float(np.mean([len(occ[t]) == 1 for t in tags])), 3) if tags else None
if len(tags) > 5:
    from sklearn.cluster import AgglomerativeClustering
    TE = enc.encode(tags, batch_size=64, normalize_embeddings=True, show_progress_bar=False); cl = AgglomerativeClustering(n_clusters=None, distance_threshold=0.2, metric="cosine", linkage="average").fit(TE).labels_
    cocc = collections.defaultdict(set); members = collections.defaultdict(list)
    for t, c in zip(tags, cl): cocc[c] |= occ[t]; members[c].append(t)
    res["clusters_at_cos_0.80"] = len(cocc); res["reduction_by_merge"] = round(1 - len(cocc) / len(tags), 3); res["singleton_share_after_merge"] = round(float(np.mean([len(v) == 1 for v in cocc.values()])), 3)
    # information gain of the whole article: cluster ids accepted under FULL vs SHORT for the same article
    tc = {t: c for t, c in zip(tags, cl)}; gain = []; lost = []
    for i, t0_, b0 in arts:
        qid = f"q:{i}"; f = {tc[r["c"]] for r in acc if r["id"] == qid and r["grp"] == "full_article"}; s = {tc[r["c"]] for r in acc if r["id"] == qid and r["grp"] == "short_article"}
        if f: gain.append(len(f - s) / len(f))
        if s: lost.append(len(s - f) / len(s))
    res["full_tags_absent_from_short_share"] = round(float(np.mean(gain)), 3) if gain else None; res["short_tags_absent_from_full_share"] = round(float(np.mean(lost)), 3) if lost else None
    res["top_tags"] = [(t, len(occ[t])) for t in sorted(tags, key=lambda t: -len(occ[t]))[:20]]; res["merged_examples"] = [v[:6] for v in sorted(members.values(), key=lambda v: -len(v))[:12] if len(v) > 1]
cap = [r for r in acc if r["t1"] >= 0.5]; res["capability_accepted"] = len(cap); res["capability_share_of_accepted"] = round(len(cap) / max(1, len(acc)), 3); ct = collections.Counter(r["c"] for r in cap); res["capability_distinct"] = len(ct)
t1yes = [r for r in cand_rows if r["t1"] >= 0.5]; res["capability_question_yes_candidates"] = len(t1yes); res["capability_yes_that_are_accepted"] = round(float(np.mean([r["accepted"] for r in t1yes])), 3) if t1yes else None
if len(ct) > 5:
    from sklearn.cluster import AgglomerativeClustering
    ctags = sorted(ct); CE = enc.encode(ctags, batch_size=64, normalize_embeddings=True, show_progress_bar=False); ccl = AgglomerativeClustering(n_clusters=None, distance_threshold=0.2, metric="cosine", linkage="average").fit(CE).labels_; res["capability_clusters_at_cos_0.80"] = len(set(ccl)); res["capability_reduction_by_merge"] = round(1 - len(set(ccl)) / len(ctags), 3)
    mem = collections.defaultdict(list)
    for t, c in zip(ctags, ccl): mem[c].append(t)
    res["capability_merged_examples"] = [v[:5] for v in sorted(mem.values(), key=lambda v: -len(v))[:10] if len(v) > 1]
res["capability_top"] = ct.most_common(25)
json.dump(res, open(("runs/snapshots/tag_pilot_tech.json" if TECH else "runs/snapshots/tag_pilot.json") if N >= 50 else "runs/tag_pilot/smoke_result.json", "w"), indent=1); print(json.dumps({k: v for k, v in res.items() if k not in ("top_tags", "merged_examples", "capability_top", "capability_merged_examples")}, indent=1)); print("CAP TOP", res.get("capability_top")); print("CAP MERGED", res.get("capability_merged_examples")); print("TOP", res.get("top_tags")); print("MERGED", res.get("merged_examples"))
