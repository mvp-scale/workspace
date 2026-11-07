"""G1 and G2 feature tokens for every labelled story (L942 step 2): G1 spot-class counts and G2 fragment tokens (predicate lemma, factuality, subject head lemma, object head lemma) from a dependency parse of the first 600 characters.
    /workspace/models/embed-zs/.venv/bin/python g2_tokens.py   (from projects/world-state)"""
import json, re, time, pickle, numpy as np, spacy
import scan_gate as G
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
S = {}
for r in J("runs/label_store/labels.jsonl"):
    if r["family"] == "sonnet" and r["version"] == "ws-v2-frozen": S[r["item_id"]] = 1
pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}
for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r["text"]
ids = sorted(i for i in S if i in pool); T = [re.sub(r"\s+", " ", pool[i])[:600] for i in ids]
nlp = spacy.load("en_core_web_sm", disable=["ner"]); SPEECH = {"say", "tell", "report", "claim", "announce", "warn", "state", "add", "note", "according"}; PLAN = {"plan", "expect", "intend", "vow", "set", "aim", "seek", "threaten", "promise"}
CLASSES = ["quote", "money", "percent", "quantity", "date", "attribution", "negation", "modal", "change", "event", "entity"]
def toks(doc):
    out = []
    for t in doc:
        if t.pos_ != "VERB" or t.lemma_ in SPEECH or t.lemma_ in ("be", "have", "do"): continue
        subj = next((c for c in t.children if c.dep_ in ("nsubj", "nsubjpass")), None); obj = next((c for c in t.children if c.dep_ in ("dobj", "attr", "oprd")), None)
        if obj is None:
            pp = next((c for c in t.children if c.dep_ == "prep"), None); obj = next((c for c in pp.children if c.dep_ == "pobj"), None) if pp else None
        if subj is None and obj is None: continue
        neg = any(c.dep_ == "neg" for c in t.children); aux = [c.lemma_ for c in t.children if c.dep_ == "aux"]
        fact = "denied" if neg else "reported" if (t.dep_ in ("ccomp", "parataxis") and t.head.lemma_ in SPEECH) else "planned" if (any(a in ("will", "would", "shall") for a in aux) or (t.dep_ == "xcomp" and t.head.lemma_ in PLAN)) else "predicted" if any(a in ("could", "may", "might", "can", "should") for a in aux) else "asserted"
        out += ["P_" + t.lemma_.lower(), "F_" + fact] + (["S_" + subj.lemma_.lower()] if subj else []) + (["O_" + obj.lemma_.lower()] if obj else [])
    return out
TOK, CNT = [], np.zeros((len(T), len(CLASSES)), np.float32); t0 = time.time()
for n, doc in enumerate(nlp.pipe(T, batch_size=64)):
    TOK.append(" ".join(toks(doc)))
    c = {}
    for sp in G.scan(T[n], "2026-01-01T00:00:00Z")[0]: c[sp[2]] = c.get(sp[2], 0) + 1
    CNT[n] = [c.get(k, 0) for k in CLASSES]
    if n % 3000 == 0: print("g2", n, round(time.time() - t0), "s", flush=True)
pickle.dump({"ids": ids, "tokens": TOK, "counts": CNT, "classes": CLASSES}, open("runs/pulse/g2_tokens.pkl", "wb")); print("saved", len(TOK), flush=True)
