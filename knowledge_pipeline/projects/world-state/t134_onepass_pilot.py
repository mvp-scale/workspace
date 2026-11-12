"""T134: pilot of the one-pass multi-head read on hosted Jev (decision D37). Call 1 asks everything up front in ONE request (content-function choice, 49-topic domain choice, domain companion noul, 39 condition nouls with true/false criteria); call 2 asks, for the dials that fired (noul >= 0.7), direction (choice), strength (score), evidence existence (noul) and the evidence sentence (choice over sentence ids). P1 sends the engine's original 328 questions in ONE request on 20 stories and compares presence with the chunked T130 readings.
    N=<stories for calls 1 and 2> NP1=<stories for P1> OUT=<folder> ROWS=<jsonl> /workspace/kev/.venv/bin/python t134_onepass_pilot.py -> <OUT>/t134_pilot.json"""
import os, sys, json, re, time, random, hashlib, pathlib, urllib.request, concurrent.futures as cf, collections, threading
sys.path.insert(0, "/workspace/probes/world-engine"); os.environ.setdefault("WE_RULES", "rules_v2")
N = int(os.environ.get("N", 40)); NP1 = int(os.environ.get("NP1", 20)); CONC = int(os.environ.get("CONC", 4))
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t134")); OUT.mkdir(parents=True, exist_ok=True); ROWS = os.environ.get("ROWS", "/workspace/data/newsreader/labels/onepass-pilot.jsonl")
KEY = ""
for l in open("/workspace/secrets/vault.env"):
    if l.startswith("TYPESAFE_API_KEY="): KEY = l.split("=", 1)[1].strip().strip(chr(34)).strip(chr(39))
URL = "https://api.typesafe.ai/v1/systemone"; lock = threading.Lock(); TOK = collections.Counter(); NCALL = collections.Counter()
def call(kind, state, qs):
    body = {"state": state, "questions": qs, "model": "jev-1.14.0"}; req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json", "User-Agent": "kp-t134/0.1", "Authorization": "Bearer " + KEY})
    last = None
    for a in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as r: j = json.load(r)
            with lock: TOK[kind] += (j.get("usage") or {}).get("input_tokens", 0); NCALL[kind] += 1
            return j["answers"], (j.get("usage") or {}).get("input_tokens", 0)
        except Exception as e: last = e; time.sleep(2 + 3 * a)
    raise last
o = json.load(open("/workspace/exports/world-engine-ontology-rules_v2.json")); topics = {t["id"]: f"{t['name']}: {t['definition']}" for t in o["topics"]}
def q_call1():
    Q = {"content_function": {"type": "choice", "instructions": "What does this story mainly do?", "criteria": {
        "fact": "Reports something that happened or was measured, with sources. Not opinion or prediction.", "opinion": "Argues a view or comments; the author or a named person judges rather than reports.",
        "forecast": "Mainly says what will or might happen later (a prediction, projection or warning).", "unclear": "Cannot be told from the text, or a mix with no main function."}},
         "domain_main": {"type": "choice", "instructions": "Which topic is this story mainly about?", "criteria": topics},
         "domain_fits_a_listed_topic": {"type": "noul", "instructions": "Does the story fit at least one of the listed topics?", "criteria": {"true": "The main subject of the story is covered by one of the listed topics.", "false": "The main subject is not covered by any listed topic (a new or unlisted subject)."}}}
    for c in o["conditions"]:
        n = c["name"].lower(); Q[f"cond_{c['id']}"] = {"type": "noul", "instructions": f"Does the story report a change in {n}?", "criteria": {
            "true": f"The story reports that {n} is changing, has changed or is being acted on in a specific place or group: a new event, measurement, decision or order. Meaning of the dial: {c['definition']}",
            "false": f"The story only mentions {n} as background, a general statement, an opinion or a possibility, or does not mention it."}}
    return Q
Q1 = q_call1(); QS_HASH = hashlib.sha256(json.dumps(Q1, sort_keys=True).encode()).hexdigest()[:12]; COND = {f"cond_{c['id']}": c for c in o["conditions"]}
def build_state(r):
    body = re.sub(r"^# .*?\n", "", r["text"]).strip(); body = re.sub(r"^# [^\n]*? - Published\s*", "", body)
    sents = [s for s in re.split(r"(?<=[.!?\"])\s+(?=[A-Z\"#])", body) if s.strip()]
    return {"title": r["title"], "sentences": {f"s{i + 1}": s for i, s in enumerate(sents)}}
def q_call2(state, fired):
    Q = {}
    opts = {k: " ".join(v.split()[:14]) for k, v in state["sentences"].items()}
    for k in fired:
        c = COND[k]; n = c["name"].lower(); d = c["id"]
        Q[f"{d}__direction"] = {"type": "choice", "instructions": f"In this story, is {n} going up or down?", "criteria": {"up": c["up_means"], "down": "the opposite: less of it", "mixed": "both happen in the story", "neither": "the story reports no movement"}}
        Q[f"{d}__strength"] = {"type": "score", "instructions": f"How large is the reported change in {n}?", "criteria": ["slight: a small or local change", "clear: a clear change affecting many", "severe: a major change, crisis or record"]}
        Q[f"{d}__evidence_exists"] = {"type": "noul", "instructions": f"Does any sentence report the change in {n}?", "criteria": {"true": "At least one sentence states the change.", "false": "No sentence states it; it is only implied."}}
        Q[f"{d}__evidence_sentence"] = {"type": "choice", "instructions": f"Which sentence most directly reports the change in {n}?", "criteria": opts}
    return Q
stored = [json.loads(l) for l in open("/workspace/data/newsreader/labels/clef-q4km.jsonl")]; random.Random(134).shuffle(stored); S = stored[:N]
chunked = {}
for l in open("/workspace/data/newsreader/labels/jev-engine-stored.jsonl"):
    r = json.loads(l); chunked[r["id"]] = r
def one(r):
    st = build_state(r); t0 = time.time()
    try:
        a1, t1 = call("call1", st, Q1)
        p = {k: a1[k]["noul"] for k in a1 if k.startswith("cond_")}; fired = sorted([k for k in p if p[k] >= 0.7], key=lambda k: -p[k])[:6]; unsure = [k for k in p if 0.3 < p[k] < 0.7]
        a2, t2 = ({}, 0)
        if fired: a2, t2 = call("call2", st, q_call2(st, fired))
        return {"id": r["id"], "title": r["title"], "sentences": len(st["sentences"]), "qs_hash": QS_HASH, "model": "jev-1.14.0", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "call1_tokens": t1, "call2_tokens": t2, "all_typed": all(("noul" in a1[k] or "choice" in a1[k]) for k in a1) and len(a1) == len(Q1),
                "fired": fired, "unsure_n": len(unsure), "cond_n": len(p), "answers_call1": a1, "answers_call2": a2, "clef_has_reading": bool(r.get("readings")), "chunked_jev_has_reading": bool((chunked.get(r["id"]) or {}).get("jev_readings")), "seconds": round(time.time() - t0, 1)}
    except Exception as e: return {"id": r["id"], "error": repr(e)[:200]}
T0 = time.time()
with cf.ThreadPoolExecutor(CONC) as ex: rows = list(ex.map(one, S))
ok = [x for x in rows if "error" not in x]
# P1: the original 328 engine questions in ONE request, compared with the chunked T130 readings on NP1 stories
import classify as C
def p1(r):
    state = f"News item (published {time.strftime('%Y-%m-%d')}; today is {time.strftime('%Y-%m-%d')}):\n{r['title']}. {r['text']}"
    a, t = call("p1", state, {k: {"type": "noul", "instructions": C.QS[k]} for k in C.QS}); P = {k: a[k]["noul"] for k in a}; return {"id": r["id"], "has_reading": bool(C.read(P)["readings"]), "tok": t, "n": len(a)}
try:
    with cf.ThreadPoolExecutor(CONC) as ex: p1rows = list(ex.map(p1, [r for r in S if r["id"] in chunked][:NP1]))
    p1ok = True
except Exception as e: p1rows = []; p1ok = False; p1err = repr(e)[:200]
agree = sum(x["has_reading"] == bool(chunked[x["id"]].get("jev_readings")) for x in p1rows) / max(len(p1rows), 1)
fired_n = sum(len(x["fired"]) for x in ok); ev = sum(1 for x in ok for k in x["fired"] if x["answers_call2"].get(f"{k[5:]}__evidence_exists", {}).get("noul", 0) >= 0.5)
unsure_rate = sum(x["unsure_n"] for x in ok) / max(sum(x["cond_n"] for x in ok), 1); tps = (TOK["call1"] + TOK["call2"]) / max(len(ok), 1)
res = {"stories": len(S), "stories_ok": len(ok), "errors": len(rows) - len(ok), "P0_call1_accepted_all_typed": bool(ok) and all(x["all_typed"] for x in ok), "P0_p1_328_in_one_request_accepted": p1ok and all(x["n"] == 328 for x in p1rows), "P0_questions_in_call1": len(Q1),
       "P1_stories": len(p1rows), "P1_presence_agreement_with_chunked": round(agree, 4), "P2_tokens_per_story_mean": round(tps), "P2_call1_tokens_mean": round(TOK["call1"] / max(len(ok), 1)), "P2_call2_tokens_mean": round(TOK["call2"] / max(len(ok), 1)), "P2_p1_one_request_328_tokens_mean": round(TOK["p1"] / max(len(p1rows), 1)),
       "P3_fired_dials": fired_n, "P3_evidence_exists_share": round(ev / max(fired_n, 1), 4), "P5_unsure_share_0.3_to_0.7": round(unsure_rate, 4), "dials_fired_per_story_mean": round(fired_n / max(len(ok), 1), 2),
       "fired_story_share": round(sum(1 for x in ok if x["fired"]) / max(len(ok), 1), 4), "clef_reading_share": round(sum(x["clef_has_reading"] for x in ok) / max(len(ok), 1), 4),
       "cost_usd_at_0_042_per_million": round(sum(TOK.values()) * 0.042 / 1e6, 3), "input_tokens_total": sum(TOK.values()), "calls": dict(NCALL), "seconds": round(time.time() - T0), "question_set_hash": QS_HASH, "P4_domain_outside_reference": "not run in this pilot",
       "note": "Plumbing and cost pilot on a small sample; no accuracy verdicts. Reference for presence is Clef's stored reading, agreement not accuracy."}
json.dump(res, open(OUT / "t134_pilot.json", "w"), indent=1); open(ROWS, "w").write("\n".join(json.dumps(x) for x in rows)); print(json.dumps(res, indent=1))
