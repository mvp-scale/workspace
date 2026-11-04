"""B3 (ledger T17, prediction L411): do small CPU cross-encoder NLI calls agree with local Clef on real sentence pairs from different articles that share an accepted tag? Local only; sentence text is never written, only numbers and tag names.
    HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python claim_test.py [cross-encoder/nli-deberta-v3-xsmall]"""
import os, sys, re, json, time, random, sqlite3, collections, urllib.request, concurrent.futures as cf, numpy as np, torch
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"
import spacy
from transformers import AutoTokenizer, AutoModelForSequenceClassification
MODEL = next((a for a in sys.argv[1:] if "/" in a), "cross-encoder/nli-deberta-v3-xsmall"); torch.set_num_threads(1); R = random.Random(21)
L = [json.loads(l) for l in open("runs/tag_head/labels.jsonl")]; db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True)
nlp = spacy.load("en_core_web_sm", disable=["ner", "lemmatizer"]); tags = collections.defaultdict(list); text = {}
for r in L:
    row = db.execute("select title, body from items where id = ?", (r["id"][2:],)).fetchone()
    if not row or not row[0] or not row[1]: continue
    text[r["id"]] = row[0].strip() + ". " + re.sub(r"\s+", " ", row[1]).strip()[:3500]
    for c, a in zip(r["cands"], r["ans"]):
        if sum(x >= 0.5 for x in a) >= 2 and len(c) >= 4: tags[c].append(r["id"])
multi = {t: v for t, v in tags.items() if len(v) >= 2}; print("articles", len(text), "tags in 2+ articles", len(multi), flush=True)
sents = {}
def S(i):
    if i not in sents: sents[i] = [s.text.strip() for s in nlp(text[i]).sents if 40 <= len(s.text.strip()) <= 250]
    return sents[i]
def pick(i, tag):
    c = [s for s in S(i) if re.search(r"(?<!\w)" + re.escape(tag) + r"(?!\w)", s.lower())]; return R.choice(c) if c else None
pairs = []; tl = list(multi); R.shuffle(tl)
for t in tl:
    ids = multi[t][:]; R.shuffle(ids); n = 0
    for k in range(len(ids) - 1):
        a, b = ids[k], ids[k + 1]
        if a == b: continue
        sa, sb = pick(a, t), pick(b, t)
        if sa and sb and sa != sb: pairs.append({"kind": "tagged", "tag": t, "a": sa, "b": sb}); n += 1
        if n == 3: break
    if len(pairs) >= 300: break
pairs = pairs[:300]; ids = list(text); tagset = {i: {t for t, v in tags.items() if i in v} for i in ids}
while sum(p["kind"] == "control" for p in pairs) < 100:
    a, b = R.sample(ids, 2)
    if tagset[a] & tagset[b]: continue
    sa, sb = R.choice(S(a) or [None]), R.choice(S(b) or [None])
    if sa and sb: pairs.append({"kind": "control", "tag": "", "a": sa, "b": sb})
print("pairs", collections.Counter(p["kind"] for p in pairs), flush=True)
tok = AutoTokenizer.from_pretrained(MODEL); mdl = AutoModelForSequenceClassification.from_pretrained(MODEL, dtype=torch.float32).eval(); lab = [mdl.config.id2label[i].lower() for i in range(3)]; print("labels", lab, flush=True)
lat = []
for p in pairs:
    e = tok(p["a"], p["b"], return_tensors="pt", truncation=True, max_length=256); t0 = time.time()
    with torch.no_grad(): lg = mdl(**e).logits[0]
    lat.append((time.time() - t0) * 1000); p["nli"] = lab[int(lg.argmax())]
Q = {"same": "Does statement B say the same thing as statement A?", "opp": "Does statement B say the opposite of statement A?"}
def ask(p):
    body = {"state": f"Statement A: {p['a']}\nStatement B: {p['b']}", "questions": {k: {"type": "noul", "instructions": v} for k, v in Q.items()}, "model": "clef-flash-q4km"}
    for _ in range(3):
        try: a = json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8018/v1/systemone", json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=600))["answers"]; return {k: float(v["noul"]) for k, v in a.items()}
        except Exception: time.sleep(2)
    return None
t0 = time.time()
with cf.ThreadPoolExecutor(6) as ex: A = list(ex.map(ask, pairs))
print(f"clef {time.time() - t0:.0f}s", flush=True); err = sum(a is None for a in A)
for p, a in zip(pairs, A):
    if a is None: p["clef"] = None; continue
    p["clef"] = "contradiction" if a["opp"] >= 0.5 else ("entailment" if a["same"] >= 0.5 else "neutral")
ok = [p for p in pairs if p["clef"]]; res = {"model": MODEL, "labels": lab, "clef_errors": err, "ms_per_pair": {"p50": round(float(np.percentile(lat, 50)), 1), "p95": round(float(np.percentile(lat, 95)), 1)}, "threads": 1}
for kind in ("tagged", "control"):
    s = [p for p in ok if p["kind"] == kind]
    res[kind] = {"n": len(s), "clef": dict(collections.Counter(p["clef"] for p in s)), "nli": dict(collections.Counter(p["nli"] for p in s)), "agreement_3class": round(float(np.mean([p["clef"] == p["nli"] for p in s])), 3)}
s = [p for p in ok if p["kind"] == "tagged"]; nn = [p for p in s if p["nli"] != "neutral"]; cn = [p for p in s if p["clef"] != "neutral"]
res["precision_nonneutral"] = round(float(np.mean([p["clef"] == p["nli"] for p in nn])), 3) if nn else None; res["recall_clef_nonneutral"] = round(float(np.mean([p["clef"] == p["nli"] for p in cn])), 3) if cn else None
res["n_nli_nonneutral"] = len(nn); res["n_clef_nonneutral"] = len(cn); res["n_clef_contradiction"] = sum(p["clef"] == "contradiction" for p in s)
res["confusion_tagged"] = {f"clef_{c}": {n: sum(p["clef"] == c and p["nli"] == n for p in s) for n in lab} for c in lab}
res["example_tags"] = [p["tag"] for p in s if p["clef"] != "neutral"][:10]
os.makedirs("runs/snapshots", exist_ok=True); json.dump(res, open("runs/snapshots/claim_test_" + MODEL.split("/")[-1] + ".json", "w"), indent=1); print(json.dumps(res, indent=1))
