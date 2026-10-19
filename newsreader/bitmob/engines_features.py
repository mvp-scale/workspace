"""Compute every engine's features for every labelled story once, and each engine's CPU cost per story (one thread, one story at a time).
Engines (docs/cpu-reader-plan.md):
  Glance   potion-base-32M static vectors for three views: full story, lead (title + first 80 words), title
  Scholar  e5-small frozen, mean-pooled, for full story (512 tokens) and lead; bulk vectors on the GPU to save time, cost measured on CPU
  Sieve    our own word lists and patterns, counted per part (title, lead, rest): numbers, %, money, dates, quotes, attribution, hedges, future,
           negation, question headline, superlatives, up and down change words, plus per-atom lexicon hits (content words of the atom's own
           questions, prefix-matched): no learning, nothing taken from the labels
  Grammar  spaCy en_core_web_sm tags and dependencies per part: past / present / modal / "will" verbs, negations, passives, first person, sentences
  Locate   spaCy entities per part (GPE, NORP, ORG, PERSON, LOC, MONEY, PERCENT, DATE, EVENT, LAW), countries from our 100-country list,
           actor types from organisation names (government, police/court, military, bank, company, union, international body)
  Echo     novelty: highest cosine (Glance full) to any earlier story in the previous 7 days, and how many earlier stories are above 0.8 / 0.9
Writes data/mm3-train/features/<engine>.npy (+ ids.json, names.json, cost.json). Run: models/embed-zs/.venv/bin/python -I newsreader/bitmob/engines_features.py"""
import json, glob, re, time, os, csv, email.utils, numpy as np, torch
D = "/workspace/data/mm3-train"; F = f"{D}/features"; os.makedirs(F, exist_ok=True)
Q = {"first": {r["id"]: r for r in map(json.loads, open(f"{D}/queue.jsonl"))}}; ATOMQ = {}
for f in sorted(glob.glob("/workspace/newsreader/bitmob/batteries/evidence-v*.json")):
    B = json.load(open(f)); Q[B["name"]] = {r["id"]: r for r in map(json.loads, open(f"{D}/queue-{B['name']}.jsonl"))}
    for c in B["concerns"]: ATOMQ[c["atom"]] = c["probes"]["a"] + " " + c["probes"]["b"]
FIRSTQ = {"civil_unrest|up": "protests riots civil unrest gathering marching striking against government employer", "war_terror|up": "armed conflict terrorism attack battle strike threat escalation armed groups states",
          "crime|up": "crime criminal act arrest charge police investigation", "cyber_insecurity|up": "cyber digital security risk hack data breach flaw online scam"}
ATOMQ.update(FIRSTQ)
ids = sorted(set.intersection(*[set(q) for q in Q.values()])); rows = [Q["first"][i] for i in ids]; json.dump(ids, open(f"{F}/ids.json", "w"))
words = lambda r: r["text"].split()
parts = [(r["title"], " ".join(words(r)[:80]), " ".join(words(r)[80:1200])) for r in rows]
cost = {}; torch.set_num_threads(1)
def timed(name, fn, sample):
    t = time.perf_counter(); [fn(x) for x in sample]; cost[name] = round((time.perf_counter() - t) * 1000 / len(sample), 3)
SAMPLE = list(range(0, len(rows), max(1, len(rows) // 60)))[:60]
# ---- Glance
from model2vec import StaticModel
pm = StaticModel.from_pretrained("minishlab/potion-base-32M")
views = {"full": [r["title"] + ". " + r["text"] for r in rows], "lead": [p[0] + ". " + p[1] for p in parts], "title": [p[0] for p in parts]}
for v, txt in views.items():
    np.save(f"{F}/glance_{v}.npy", pm.encode(txt)); timed(f"glance_{v}", lambda i: pm.encode([txt[i]]), SAMPLE)
print("glance done", {k: v for k, v in cost.items()}, flush=True)
# ---- Scholar
from transformers import AutoTokenizer, AutoModel
tok = AutoTokenizer.from_pretrained("intfloat/e5-small-v2"); g = AutoModel.from_pretrained("intfloat/e5-small-v2").cuda().eval(); c1 = AutoModel.from_pretrained("intfloat/e5-small-v2").eval()
def e5(model, txt, dev, bs=32):
    out = []
    with torch.no_grad():
        for i in range(0, len(txt), bs):
            b = tok(["query: " + x for x in txt[i:i + bs]], truncation=True, max_length=512, padding=True, return_tensors="pt").to(dev)
            h = model(**b).last_hidden_state; m = b["attention_mask"].unsqueeze(-1); out.append(((h * m).sum(1) / m.sum(1)).cpu().numpy())
    return np.concatenate(out)
for v in ("full", "lead"):
    np.save(f"{F}/scholar_{v}.npy", e5(g, views[v], "cuda")); timed(f"scholar_{v}", lambda i: e5(c1, [views[v][i]], "cpu", 1), SAMPLE[:30])
print("scholar done", {k: v for k, v in cost.items() if k.startswith("scholar")}, flush=True)
# ---- Sieve (our code)
W = lambda *xs: re.compile(r"\b(" + "|".join(xs) + r")\b", re.I)
PAT = {"number": re.compile(r"\b\d[\d,.]*\b"), "percent": re.compile(r"\d\s?(%|per ?cent\b)", re.I), "money": re.compile(r"[$€£¥₹]\s?\d|\b\d[\d,.]*\s?(dollars|euros|pounds|yen|rupees|million|billion|bn|m)\b", re.I),
       "date": W("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", r"(19|20)\d\d"),
       "quote": re.compile(r"[\"“”]"), "attribution": W("said", "says", "told", "according to", "announced", "confirmed", "stated"),
       "hedge": W("could", "may", "might", "would", "possibly", "likely", "expected to", "warn", "warns", "warned", "feared", "fears", "risk", "risks", "concern", "concerns"),
       "future": W("will", "plans to", "set to", "to be", "next year", "next week", "next month"), "negation": W("not", "no", "never", r"\w+n't", "without", "denied", "denies"),
       "superlative": W(r"\w+est", "most", "record", "biggest", "worst", "highest", "lowest", "unprecedented"),
       "up": W("rise", "rises", "rose", "risen", "rising", "jump", "jumped", "jumps", "soar", "soared", "surge", "surged", "climb", "climbed", "increase", "increased", "increases", "hike", "hikes", "hiked", "grow", "grew", "growing", "spike", "spiked", "double", "doubled", "higher", "up"),
       "down": W("fall", "falls", "fell", "fallen", "falling", "drop", "dropped", "drops", "plunge", "plunged", "slump", "slumped", "decline", "declined", "cut", "cuts", "lower", "lowered", "ease", "eased", "eases", "shrink", "shrank", "halve", "halved", "down")}
STOP = set("does the story in file report describe say that people a an of or to for by with is are be being been their them this from as at on into than more less some such going getting become becoming something any its it who what when where which have has had".split())
LEX = {a: sorted({w[:5] for w in re.findall(r"[a-z]+", q.lower()) if w not in STOP and len(w) > 3}) for a, q in ATOMQ.items()}
LEXRE = {a: re.compile(r"\b(" + "|".join(map(re.escape, ws)) + r")\w*", re.I) for a, ws in LEX.items()}
ATOMS = sorted(ATOMQ); json.dump({"atoms": ATOMS, "lexicon": LEX, "patterns": list(PAT)}, open(f"{F}/sieve_names.json", "w"), indent=1)
def sieve(p):
    t, l, b = p; v = []
    for part in (t, l, b):
        n = max(1, len(part.split())); v += [np.log1p(len(x.findall(part))) for x in PAT.values()] + [len(part.split()) and np.log1p(len(x.findall(part)) / n * 100) for x in (PAT["up"], PAT["down"], PAT["hedge"])]
    v.append(float(t.strip().endswith("?")))
    for a in ATOMS:
        v += [np.log1p(len(LEXRE[a].findall(part))) for part in (t, l, b)]
    return v
np.save(f"{F}/sieve.npy", np.array([sieve(p) for p in parts], np.float32)); timed("sieve", lambda i: sieve(parts[i]), SAMPLE)
print("sieve done", cost["sieve"], flush=True)
# ---- Grammar + Locate (spaCy, one pass)
import spacy
nlp = spacy.load("en_core_web_sm", disable=["lemmatizer"]); nlp.max_length = 2_000_000
cn = [r for r in csv.DictReader(open("/workspace/probes/world-engine/data/countries_world100.csv"))]
CRE = re.compile(r"\b(" + "|".join(sorted({re.escape(c["name"]) for c in cn} | {"US", "USA", "U.S.", "UK", "Britain", "EU"}, key=len, reverse=True)) + r")\b")
ACT = {"government": W("government", "ministry", "minister", "parliament", "president", "senate", "congress", "council", "white house", "cabinet", "department"),
       "justice": W("police", "court", "judge", "prosecutor", "fbi", "justice"), "military": W("army", "military", "forces", "navy", "air force", "defence", "defense", "idf", "hamas", "hezbollah", "nato"),
       "bank": W("bank", "central bank", "federal reserve", "fed", "imf", "treasury"), "company": W("inc", "ltd", "corp", "group", "company", "plc", "llc", "airlines", "motors"),
       "union": W("union", "unions"), "intl": W("un", "united nations", "eu", "european union", "who", "world bank", "g20", "g7")}
ENTS = ["GPE", "NORP", "ORG", "PERSON", "LOC", "MONEY", "PERCENT", "DATE", "EVENT", "LAW"]
def gram_loc(p):
    G, L = [], []
    for part in p:
        d = nlp(part); n = max(1, sum(1 for t in d if t.is_alpha))
        tags = [t.tag_ for t in d]; G += [tags.count("VBD") / n * 100, (tags.count("VBZ") + tags.count("VBP")) / n * 100, tags.count("MD") / n * 100, sum(t.lower_ == "will" for t in d) / n * 100,
                                          sum(t.dep_ == "neg" for t in d) / n * 100, sum(t.dep_ in ("nsubjpass", "auxpass") for t in d) / n * 100,
                                          sum(t.lower_ in ("i", "we", "my", "our") for t in d) / n * 100, np.log1p(sum(1 for _ in d.sents))]
        lab = [e.label_ for e in d.ents]; orgs = " ".join(e.text for e in d.ents if e.label_ == "ORG")
        L += [np.log1p(lab.count(x)) for x in ENTS] + [np.log1p(len(set(CRE.findall(part))))] + [np.log1p(len(r.findall(orgs + " " + part))) for r in ACT.values()]
    return G, L
GL = [gram_loc(p) for p in parts]; np.save(f"{F}/grammar.npy", np.array([g for g, _ in GL], np.float32)); np.save(f"{F}/locate.npy", np.array([l for _, l in GL], np.float32))
timed("grammar+locate (spaCy, one pass)", lambda i: gram_loc(parts[i]), SAMPLE[:30])
t = time.perf_counter(); [CRE.findall(" ".join(parts[i])) for i in SAMPLE]; cost["locate_countries_only (our regex)"] = round((time.perf_counter() - t) * 1000 / len(SAMPLE), 3)
print("spacy done", cost["grammar+locate (spaCy, one pass)"], flush=True)
# ---- Echo
X = np.load(f"{F}/glance_full.npy"); X = X / np.linalg.norm(X, axis=1, keepdims=True)
def when(r):
    try: return email.utils.parsedate_to_datetime(r["published"]).timestamp()
    except Exception:
        try: return time.mktime(time.strptime(r["published"][:19], "%Y-%m-%dT%H:%M:%S"))
        except Exception: return float(r.get("batch", 0))
ts = np.array([when(r) for r in rows]); E = np.zeros((len(rows), 3), np.float32)
t0 = time.perf_counter()
for i in range(len(rows)):
    m = (ts < ts[i]) & (ts >= ts[i] - 7 * 86400)
    if m.any(): s = X[m] @ X[i]; E[i] = [s.max(), (s > .8).sum(), (s > .9).sum()]
cost["echo (vs a 7-day index, numpy)"] = round((time.perf_counter() - t0) * 1000 / len(rows), 3); np.save(f"{F}/echo.npy", E); np.save(f"{F}/published_ts.npy", ts)
json.dump(cost, open(f"{F}/cost.json", "w"), indent=1); print(json.dumps(cost, indent=1))
