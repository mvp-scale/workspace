"""Build a BitMob training-set file to docs/research/2026-10-19 BitMob training set spec.md (input filter D-0010, input D-0009).
Pool: CC-News (65 approved outlets) and the news reader's queue (title + teaser), filtered per D-0010; random sample, seed fixed.
Teacher (by registry name, default jev) reads exactly `input` = title + " — " + description[:250]:
  the engine's 328 questions, the 159 definition wordings (|2), the topic (one of 49) and the country (the engine's own two-step question).
Also: replicate reads (R17) and paired full-text labels (R18) on 2% each; tokens per record (R14). Progress to data/trainset/<name>.log.
Run from /workspace/probes/world-engine (kev venv):  WE_RULES=rules_v2 python -I /workspace/newsreader/bitmob/build_trainset.py <name> [N_ccnews] [N_feed] [teacher] [CONC]"""
import sys, os, re, json, time, glob, random, sqlite3, threading, unicodedata, urllib.request, concurrent.futures as cf
os.environ.setdefault("WE_RULES", "rules_v2"); sys.path.insert(0, "/workspace/probes/world-engine"); sys.path.insert(0, "/workspace/demo")
import pyarrow.parquet as pq, pyarrow as pa
import classify as C, backends
NAME = sys.argv[1]; NC = int(sys.argv[2]) if len(sys.argv) > 2 else 800; NF = int(sys.argv[3]) if len(sys.argv) > 3 else 200
TEACHER = sys.argv[4] if len(sys.argv) > 4 else "jev"; CONC = int(sys.argv[5]) if len(sys.argv) > 5 else 4
D = "/workspace/data/trainset"; os.makedirs(D, exist_ok=True); OUT = f"{D}/{NAME}.jsonl"; LOG = f"{D}/{NAME}.log"
PROMPT_VERSION = "engine328+def159+topic49 one call; country2step v2"
def log(m):
    line = f"{time.strftime('%F %T')}  {m}"; print(line, flush=True); open(LOG, "a").write(line + "\n")

# ---- teacher, with token counts (R14) ----
B = backends.BACKENDS[TEACHER]; tls = threading.local()
CHUNK = int(os.environ.get("CHUNK", "0"))      # >0: split the question set into calls of this many questions (local Clef cannot take 487 in one call)
def call(state, qs):
    if CHUNK and len(qs) > CHUNK:
        ks = list(qs); out = {}
        for i in range(0, len(ks), CHUNK): out.update(call1(state, {k: qs[k] for k in ks[i:i + CHUNK]}))
        return out
    return call1(state, qs)
def call1(state, qs):
    body = {"state": state, "questions": qs, **({"model": B["model"]} if B["model"] else {})}
    hdr = {"Content-Type": "application/json", "User-Agent": "jev-demo/0.1", **({"Authorization": f"Bearer {B['key']}"} if B["key"] else {})}
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(B["url"].rstrip("/") + "/v1/systemone", json.dumps(body).encode(), hdr), timeout=300) as r: d = json.load(r)
            tls.model = d.get("model") or tls.__dict__.get("model")      # the version that actually answered (jev-latest resolves server-side)
            u = d.get("usage") or {}; tls.tin = getattr(tls, "tin", 0) + u.get("input_tokens", 0); tls.tout = getattr(tls, "tout", 0) + u.get("output_tokens", 0); tls.calls = getattr(tls, "calls", 0) + 1
            return d["answers"]
        except Exception:
            if attempt == 2: raise
            time.sleep(2 * (attempt + 1))
C.O.call = call

# ---- input filter (D-0010, spec R2-R7) ----
src = open("/workspace/newsreader/bitmob/ccnews_headline_test.py").read()
OUTLETS = set(re.findall(r'"([a-z0-9.-]+\.[a-z]{2,})"', src.split("OUTLETS = [")[1].split("]")[0]))
AD = re.compile(r"(\d+% off|\bcoupons?\b|promo code|discount code|buy now|shop now|sale ends|\bbest [\w\s-]{0,30}\b(deals|to buy)\b|\bdeals (on|for)\b|\bon sale\b)", re.I)
ROUND = re.compile(r"(morning (everyone|briefing)|evening briefing|newsletter|what we know so far|live updates?|as it happened|in pictures|news in brief|top stories)", re.I)
COMMON = set("the a an of to in and for on is was are with that by as at from has have it be said will after its his her their were not this but".split())
norm = lambda t: re.sub(r"[^a-z0-9 ]", "", unicodedata.normalize("NFKD", (t or "").lower())).strip()
def english(s):
    L = [c for c in s if c.isalpha()]
    if not L or sum(not c.isascii() for c in L) / len(L) > 0.05: return False
    w = re.findall(r"[a-z']+", s.lower()); return len(w) >= 5 and sum(x in COMMON for x in w) / len(w) >= 0.05
def ok(title, desc):      # judged on the stored text (description cut to 250), the same text the audit reads
    desc = (desc or "").strip()[:250]; t = f"{title} {desc}"
    return bool(title) and len((desc or "").strip()) >= 60 and english(t) and not AD.search(t) and not ROUND.search(t)

seen = set()
def fresh(title, desc):
    k1, k2 = "t:" + norm(title), "d:" + norm(desc)[:100]
    if k1 in seen or k2 in seen: return False
    seen.update((k1, k2)); return True
cc = pa.concat_tables([pq.read_table(f, columns=["url", "domain", "date", "title", "description", "text"]) for f in sorted(glob.glob("/workspace/data/ccnews/raw/plain_text/*.parquet"))]).to_pylist()
cc = [r for r in cc if r["domain"] in OUTLETS and ok(r["title"], r["description"])]
cc.sort(key=lambda r: r["url"]); random.Random(1).shuffle(cc); cc = [r for r in cc if fresh(r["title"], r["description"])]
db = sqlite3.connect("/workspace/data/newsreader/queue.sqlite")
fd = [dict(zip(("id", "url", "feed", "source", "title", "teaser", "body", "published"), r)) for r in db.execute("SELECT id, url, feed, source, title, teaser, body, published FROM items")]
fd = [r for r in fd if ok(r["title"], r["teaser"])]; fd.sort(key=lambda r: r["id"]); random.Random(1).shuffle(fd); fd = [r for r in fd if fresh(r["title"], r["teaser"])]
pool_c, pool_f = len(cc), len(fd)
items = [("ccnews", r) for r in cc[:NC]] + [("feed", r) for r in fd[:NF]]
SELECT = os.environ.get("SELECT_IDS")      # optional: label exactly these ids (one JSON {"id","selection"} per line), e.g. a targeted round (D-0013)
if SELECT:
    sel = {(x := json.loads(l))["id"]: x["selection"] for l in open(SELECT)}
    byid = {"cc:" + r["url"]: ("ccnews", r) for r in cc} | {"nr:" + r["id"]: ("feed", r) for r in fd}
    items = [byid[i] for i in sel if i in byid]
done = {json.loads(l)["id"] for l in open(OUT)} if os.path.exists(OUT) else set()
Q3 = {f"a|{d}|{dirn}|{i}|2": f"This story reports that {r['definition'].strip().rstrip('.')}." for (d, dirn), lst in C.ATTRS.items() for i, r in enumerate(lst)}
TOPIC_Q = {"type": "choice", "instructions": "Which topic is this news story mainly about?", "criteria": {d["id"]: f"{d['name']}: {(d.get('definition') or '').strip()[:140]}" for d in C.DOMAINS}}
assert len(TOPIC_Q["criteria"]) <= 64

def ask(state, qs):
    names, P = list(qs), {}
    for j in range(0, len(names), 20):
        a = C.O.call(state, {k: qs[k] for k in names[j:j + 20]}); P.update({k: a[k]["noul"] for k in a})
    return P
def target(P):      # majority of 3 wordings per attribute (>= 0.65), key = any attribute present (S-0002); conflicts kept apart
    keys, conflicts = set(), set()
    for (d, dirn), lst in C.ATTRS.items():
        for i, _ in enumerate(lst):
            votes = sum(P.get(f"a|{d}|{dirn}|{i}|{w}", 0) >= C.ATTR_MIN for w in (0, 1, 2))
            if votes >= 2: keys.add(f"{d}|{dirn}")
    for k in list(keys):
        d, dirn = k.split("|"); o = f"{d}|{'down' if dirn == 'up' else 'up'}"
        if o in keys: conflicts.update((k, o))
    return sorted(keys - conflicts), sorted(conflicts)
def near_cut(P):
    out = []
    for (d, dirn), lst in C.ATTRS.items():
        for i, r in enumerate(lst):
            m = (P[f"a|{d}|{dirn}|{i}|0"] + P[f"a|{d}|{dirn}|{i}|1"]) / 2
            if abs(m - C.ATTR_MIN) <= 0.05: out.append(f"{d}|{dirn}|{r['attribute']}")
    return out

def one(idx, kind, r):
    tls.tin = tls.tout = tls.calls = 0
    if kind == "ccnews":
        rid, title, desc, day, outlet, feed, full = "cc:" + r["url"], r["title"], r["description"], (r["date"] or "")[:10], r["domain"], None, r["text"] or ""
    else:
        rid, title, desc, day, outlet, feed, full = "nr:" + r["id"], r["title"], r["teaser"], (r["published"] or "")[:10], None, r["feed"], r["body"] or ""
    if rid in done: return None
    day = day or time.strftime("%F"); d250 = desc.strip()[:250]; inp = f"{title} — {d250}"
    ev = {"published_at": day, "title": title, "description": d250}; state = f"News item (published {day}; today is {day}):\n{title}. {d250}"
    allq = {k: {"type": "noul", "instructions": q} for k, q in C.QS.items()}; allq.update({k: {"type": "noul", "instructions": q} for k, q in Q3.items()}); allq["topic"] = TOPIC_Q
    ans = C.O.call(state, allq)      # one call per story: every yes/no question + topic (Jev answers do not depend on grouping, F-0041)
    P = {k: v["noul"] for k, v in ans.items() if k != "topic"}; tp = ans["topic"]
    rd = C.read(P)
    country, cprob, _ = C.ask_country_detailed(ev, today=day)
    keys, conflicts = target(P)
    rec = {"id": rid, "source": kind, "ccnews": kind == "ccnews", "outlet": outlet, "feed": feed, "date": day, "title": title, "description": d250,
           "input": inp, "label_input": inp, "P": P, "gate": rd["gate"], "gate_ok": rd["gate_ok"], "engine_readings": rd["readings"],
           "target_rule": "mv3>=0.65 any-attribute (S-0002)", "target_keys": keys, "conflicts": conflicts, "near_cut": near_cut(P),
           "topic": tp["choice"], "topic_p": {k: round(float(v), 3) for k, v in tp["probabilities"].items()}, "topic_source": "reader",
           "country": country, "country_p": cprob, "country_source": "reader",
           "teacher": TEACHER, "teacher_model": getattr(tls, "model", None) or B["model"], "rules": os.environ["WE_RULES"], "prompt_version": PROMPT_VERSION, "labelled_at": time.strftime("%FT%T"),
           "inclusion_prob": None if SELECT else round((NC / pool_c) if kind == "ccnews" else (NF / pool_f), 6), "split": "train",
           "selection": sel.get(rid) if SELECT else "random"}
    if idx % 50 == 0:      # R17: replicate read of the engine questions
        rec["replicate"] = True; R = C.ask(ev, today=day); rec["P_rep"] = R
        rec["rep_flips"] = sorted({f"{x['dial']}|{x['direction']}" for x in rd["readings"]} ^ {f"{x['dial']}|{x['direction']}" for x in C.read(R)["readings"]})
    if idx % 50 in (25, 26, 27) and len(full.split()) >= 80 and not paired_in.get(idx // 50):      # R18: one paired full-text record per 50; falls through to the next when a story has no body
        paired_in[idx // 50] = True
        fev = {"published_at": day, "title": title, "description": " ".join(full.split()[:1200])}; rec["P_fulltext"] = C.ask(fev, today=day)
    rec["tokens"] = {"input": tls.tin, "output": tls.tout, "calls": tls.calls}
    return rec

log(f"start {NAME}: teacher {TEACHER} ({B['model']}), pools ccnews {pool_c} / feed {pool_f} after filter, sample {NC} + {NF}, {len(done)} already done, {CONC} at a time")
lock, t0, n, toks = threading.Lock(), time.time(), [0], [0, 0]
paired_in = {}
def run(args):
    rec = one(*args)
    if rec is None: return
    with lock:
        open(OUT, "a").write(json.dumps(rec) + "\n"); n[0] += 1; toks[0] += rec["tokens"]["input"]; toks[1] += rec["tokens"]["output"]
        if n[0] % 25 == 0 or n[0] == len(items):
            el = time.time() - t0; rate = n[0] / el * 60
            log(f"{n[0]}/{len(items)} labelled, {rate:.1f}/min, {el / 60:.1f} min, ETA {(len(items) - n[0]) / rate:.0f} min, tokens in {toks[0]:,} out {toks[1]:,} ({toks[0] // n[0]:,}/{toks[1] // n[0]:,} per record)")
with cf.ThreadPoolExecutor(CONC) as ex:
    for f in cf.as_completed([ex.submit(run, (i, k, r)) for i, (k, r) in enumerate(items)]):
        if f.exception(): log(f"error: {repr(f.exception())[:200]}")
log(f"DONE {n[0]} records in {(time.time() - t0) / 60:.1f} min; tokens in {toks[0]:,} out {toks[1]:,}")
