"""T135: the whole one-pass read, every head on (owner D38, D39), on 100 stories: 40 engine stories (Clef readings stored), 30 label-store stories (teacher story_type and topic), 30 MN-DS fresh2 stories (outside truth for Domain, scoring only). Hosted Jev, one request for everything up front, one for the dials that fired plus place, and the engine's original 328 questions in one request for the engine contract. Every raw answer and the exact requests are saved.
    OUT=<folder> ROWS=<jsonl> /workspace/kev/.venv/bin/python -I t135_full_read.py (run from /workspace/probes/world-engine) -> <OUT>/t135_full_read.json"""
import os, sys, json, re, time, random, hashlib, pathlib, sqlite3, urllib.request, concurrent.futures as cf, collections, threading
os.environ.setdefault("WE_RULES", "rules_v2"); sys.path.insert(0, "/workspace/probes/world-engine")
import classify as C
NE, NL, NM, CONC = [int(os.environ.get(k, d)) for k, d in (("NE", 40), ("NL", 30), ("NM", 30), ("CONC", 5))]; NREP = int(os.environ.get("NREP", 10))
OUT = pathlib.Path(os.environ.get("OUT", "/workspace/knowledge_pipeline/projects/world-state/runs/pulse/t135")); OUT.mkdir(parents=True, exist_ok=True); ROWS = os.environ.get("ROWS", "/workspace/data/newsreader/labels/full-read-100.jsonl")
KEY = ""
for l in open("/workspace/secrets/vault.env"):
    if l.startswith("TYPESAFE_API_KEY="): KEY = l.split("=", 1)[1].strip().strip(chr(34)).strip(chr(39))
URL = "https://api.typesafe.ai/v1/systemone"; lock = threading.Lock(); TOK = collections.Counter(); NCALL = collections.Counter(); FIRST = {}
def call(kind, state, qs, tag=None):
    body = {"state": state, "questions": qs, "model": "jev-1.14.0"}
    if tag is not None and kind not in FIRST:
        with lock: FIRST.setdefault(kind, {"story": tag, "request": body})
    req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json", "User-Agent": "kp-t135/0.1", "Authorization": "Bearer " + KEY}); last = None
    for a in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as r: j = json.load(r)
            u = (j.get("usage") or {}).get("input_tokens", 0)
            with lock: TOK[kind] += u; NCALL[kind] += 1
            return j["answers"], u
        except Exception as e: last = e; time.sleep(2 + 3 * a)
    raise last
O = json.load(open("/workspace/exports/world-engine-ontology-rules_v2.json")); IPT = json.load(open("/workspace/data/diag/flow/iptc_top_level.json"))["top_level"]
SPEC_IPTC = json.load(open("/workspace/knowledge_pipeline/projects/world-state/specs/topic_to_iptc_v1.json"))["iptc"]; ALIAS = {"politics": "politics and government", "religion and belief": "religion"}
slug = lambda s: re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
BOUND = lambda what: {"true": f"The story is mainly or substantially about {what}.", "false": f"{what[:1].upper() + what[1:]} is not a subject of the story, or is only mentioned in passing."}
def build_q1():
    Q = {}
    for k, (ins, t, f) in {"function_report": ("Does the story report something that happened or was measured?", "States what happened, who did it or what was measured, as reporting.", "Mainly argues a view, predicts, asks for something or announces a decision."),
        "function_opinion": ("Is the story mainly the author's or a named person's opinion or commentary?", "The text argues or judges: it says what should be, who is to blame or what the author thinks.", "The text mainly reports events or facts without arguing a view."),
        "function_prediction": ("Does the story mainly say what will or might happen later?", "A forecast, projection or warning about the future is the main content.", "Mainly about the past or present; a future remark is in passing."),
        "function_request": ("Does the story ask someone to do something or ask for help?", "An appeal, petition, call to action or request is the main content.", "No request is made, or only in passing."),
        "function_decision": ("Does the story announce or describe a decision made by an official body, court or company?", "A ruling, vote, order, policy or business decision is the main content.", "No decision is announced.")}.items():
        Q[k] = {"type": "noul", "instructions": ins, "criteria": {"true": t, "false": f}}
    for q, v in IPT.items(): Q["domain_" + slug(v["label"])] = {"type": "noul", "instructions": f"Is the story about {v['label']}? IPTC definition: {v['definition']}", "criteria": BOUND("this IPTC subject")}
    topics = {t["id"]: f"{t['name']}: {t['definition']}" for t in O["topics"]}
    Q["area_main"] = {"type": "choice", "instructions": "Which area is this story mainly about?", "criteria": topics}
    Q["area_fits_a_listed_area"] = {"type": "noul", "instructions": "Does the story fit at least one of the listed areas?", "criteria": {"true": "The main subject is covered by one of the listed areas.", "false": "The main subject is not covered by any listed area (a new or unlisted subject)."}}
    for t in O["topics"]: Q["area_" + t["id"]] = {"type": "noul", "instructions": f"Is the story about {t['name']}? Meaning: {t['definition']}", "criteria": BOUND(t["name"].lower())}
    for c in O["conditions"]:
        n = c["name"].lower(); Q["cond_" + c["id"]] = {"type": "noul", "instructions": f"Does the story report a change in {n}? Meaning: {c['definition']}", "criteria": {"true": "A change is reported or ordered: a new event, measurement or decision in a specific place or group.", "false": "Only background, a general statement, an opinion or a possibility, or not mentioned."}}
    rows = C._country_rows(); regions = sorted({r["region"] for r in rows}); crit = {g: C.region_text(g, rows) for g in regions}; crit["GLOBAL"] = "The whole world, or no single part of it"
    Q["place_region"] = {"type": "choice", "instructions": "Which part of the world is this story mainly about?", "criteria": crit}
    Q["time_recent"] = {"type": "noul", "instructions": "Does the story report something that happened or was announced in the last few days?", "criteria": {"true": "The reported events are recent: today, this week or just announced.", "false": "The events are older, ongoing background or undated."}}
    for r in O["resources"]: Q["capcand_" + r["id"]] = {"type": "noul", "instructions": f"Does the story show people, places or services using, lacking or losing {r['name'].lower()}? Meaning: {r['definition']}", "criteria": {"true": f"The story shows use, shortage or loss of {r['name'].lower()}.", "false": "Not mentioned, or only in passing."}}
    Q["novelty_choice"] = {"type": "choice", "instructions": "How well do the listed areas cover this story's subject?", "criteria": {"known": "The subject is clearly covered by a listed area.", "emerging": "The subject is partly covered but shows something new: a pattern, event type or actor the list does not name.", "unsupported": "The story makes claims it does not support, or no listed area applies."}}
    Q["uncertain_claims"] = {"type": "noul", "instructions": "Does the story say that something is uncertain, disputed or denied?", "criteria": {"true": "A claim is described as unconfirmed, contested or denied.", "false": "No claim is described as unconfirmed, contested or denied."}}
    Q["conflicting_claims"] = {"type": "noul", "instructions": "Does the story contain claims that contradict each other?", "criteria": {"true": "Two parties or sources give accounts that cannot both be true.", "false": "The accounts in the story are consistent, or there is only one."}}
    return Q
SIZE = ["minor: a local or narrow change, real but barely noticeable", "notable: a clear change that many people in the place would notice, for example a nationwide price rise or the closure of a major service", "major: daily life changing for many people, wide disruption or crisis-scale effects", "severe: a crisis across the place (draft wording, no source found)", "extreme: the most extreme: catastrophe or collapse (draft wording, no source found)"]
FACT = {"asserted": "The story states it as fact in its own voice.", "reported": "The story says someone said or claimed it.", "planned": "The story says it is planned or scheduled.", "predicted": "The story says it is expected or forecast.", "denied": "The story says it did not happen or is false.", "unknown": "The story does not make clear whether it happened."}
COND = {"cond_" + c["id"]: c for c in O["conditions"]}; Q1 = build_q1()
def build_q2(state, fired, region):
    Q = {}; ids = {k: f"the sentence keyed {k}" for k in state["sentences"]}
    for k in fired:
        c = COND[k]; n = c["name"].lower(); d = c["id"]
        Q[f"{d}__direction"] = {"type": "choice", "instructions": f"In this story, is {n} going up or down?", "criteria": {"up": c["up_means"], "down": "the opposite: less of it", "mixed": "both happen in the story", "neither": "the story reports no movement"}}
        Q[f"{d}__form"] = {"type": "choice", "instructions": f"Is the change in {n} delayed, disrupted or expanded?", "criteria": {"delayed": "Held up, postponed or slowed.", "disrupted": "Interrupted or broken for a time.", "expanded": "Widened, extended or scaled up.", "none_of_these": "None of delayed, disrupted or expanded fits."}}
        Q[f"{d}__size"] = {"type": "score", "instructions": f"How large is the reported change in {n}? Judge by how many people are affected and how directly, as the story states it, not by dramatic wording.", "criteria": SIZE}
        Q[f"{d}__factuality"] = {"type": "choice", "instructions": f"How does the story present the change in {n}?", "criteria": FACT}
        Q[f"{d}__evidence_exists"] = {"type": "noul", "instructions": f"Does any sentence report the change in {n}?", "criteria": {"true": "At least one sentence states the change.", "false": "No sentence states it; it is only implied."}}
        Q[f"{d}__evidence_sentence"] = {"type": "choice", "instructions": f"Which sentence most directly reports the change in {n}?", "criteria": ids}
    if region and region != "GLOBAL":
        rows = [r for r in C._country_rows() if r.get("region") == region]; inr = {r["id"]: r["name"] for r in rows}; inr["other_here"] = "A different country in this part of the world, or no single country"
        Q["place_country"] = {"type": "choice", "instructions": "Which country is this story mainly about?", "criteria": inr}
    return Q
def build_state(title, body, published):
    body = body.strip()
    if body.startswith("#"):
        m = re.match(r"#+ .*? - Published\s*", body); body = body[m.end():] if m else re.sub(r"^#+ [^\n]*\n?", "", body)
    body = body.replace("**", ""); sents = [s.strip() for s in re.split(r"(?<=[.!?\"])\s+(?=[A-Z\"])", body) if s.strip()]; off = {}; pos = 0
    for i, s in enumerate(sents): j = body.find(s, pos); off[f"s{i + 1}"] = [j, j + len(s)]; pos = max(pos, j + len(s))
    return {"title": title.strip(), "published": published or "unknown", "sentences": {f"s{i + 1}": s for i, s in enumerate(sents)}}, off
qh = lambda q: hashlib.sha256(json.dumps(q, sort_keys=True).encode()).hexdigest()[:10]; QSET = hashlib.sha256(json.dumps(Q1, sort_keys=True).encode()).hexdigest()[:12]
ONTV = hashlib.sha256((open("/workspace/exports/world-engine-ontology-rules_v2.json").read() + open("/workspace/knowledge_pipeline/projects/world-state/specs/topic_to_iptc_v1.json").read() + open("/workspace/data/diag/flow/iptc_top_level.json").read()).encode()).hexdigest()[:12]
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True)
def queue_row(i):
    r = db.execute("select title, body, published from items where id=? and body is not null", (i,)).fetchone(); return r
def sample():
    rng = random.Random(135); S = []
    eng = [json.loads(l) for l in open("/workspace/data/newsreader/labels/clef-q4km.jsonl")]; rng.shuffle(eng)
    for r in eng[:NE]:
        q = queue_row(r["id"]); S.append({"set": "engine", "id": r["id"], "title": r["title"], "body": r["text"], "published": (q[2] if q else None), "clef_reading": bool(r.get("readings"))})
    seen = set(); L = []
    for l in open("/workspace/knowledge_pipeline/projects/world-state/runs/label_store/labels.jsonl"):
        x = json.loads(l)
        if x.get("family") == "sonnet" and x["item_id"] not in seen: seen.add(x["item_id"]); L.append(x)
    rng.shuffle(L); n = 0
    for x in L:
        q = queue_row(x["item_id"].replace("nr:", ""))
        if q and len(q[1].split()) >= 80 and n < NL: S.append({"set": "label_store", "id": x["item_id"], "title": q[0], "body": " ".join(q[1].split()[:1200]), "published": q[2], "ls_story_type": x["story_type"], "ls_topic": x["topic"]}); n += 1
    gold = json.load(open("/workspace/data/anchors/mn_ds/gold_fresh2.json")); items = {}
    for l in open("/workspace/data/anchors/mn_ds/items_fresh2.jsonl"): r = json.loads(l); items[r["id"]] = r
    by = collections.defaultdict(list)
    for i, v in gold.items():
        if i in items: by[v["l1"]].append(i)
    cats = sorted(by); pick = []
    for a in range(NM): c = cats[a % len(cats)]; pick.append(rng.choice(by[c]))
    for i in pick:
        t = items[i]["text"]; title = re.split(r"(?<=[.!?])\s", t, 1)[0][:200]; S.append({"set": "mnds", "id": i, "title": title, "body": " ".join(t.split()[:1200]), "published": None, "mn_l1": ALIAS.get(gold[i]["l1"], gold[i]["l1"])})
    return S
def one(r):
    st, off = build_state(r["title"], r["body"], r["published"]); t0 = time.time()
    try:
        a1, t1 = call("call1", st, Q1, r["id"]); p = {k: a1[k]["noul"] for k in a1 if k.startswith("cond_")}; fired = sorted([k for k in p if p[k] >= 0.7], key=lambda k: -p[k])[:6]
        region = a1["place_region"]["choice"]; a2, t2 = call("call2", st, build_q2(st, fired, region), r["id"]) if (fired or region != "GLOBAL") else ({}, 0)
        state328 = f"News item (published {r['published'] or time.strftime('%Y-%m-%d')}; today is {time.strftime('%Y-%m-%d')}):\n{r['title']}. {r['body']}"; a3, t3 = call("p328", state328, {k: {"type": "noul", "instructions": C.QS[k]} for k in C.QS}, r["id"]); P = {k: a3[k]["noul"] for k in a3}; rd = C.read(P)["readings"]
        return {**{k: r[k] for k in r if k not in ("body",)}, "model": "jev-1.14.0", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "qset": QSET, "ontology_version": ONTV, "sentence_offsets": off, "state_sha": hashlib.sha256(json.dumps(st, sort_keys=True).encode()).hexdigest()[:12],
                "tokens": {"call1": t1, "call2": t2, "p328": t3}, "fired": fired, "answers_call1": a1, "answers_call2": a2, "answers_p328": P, "readings_p328": rd, "seconds": round(time.time() - t0, 1)}
    except Exception as e: return {"set": r["set"], "id": r["id"], "error": repr(e)[:200]}
S = sample(); T0 = time.time()
with cf.ThreadPoolExecutor(CONC) as ex: rows = list(ex.map(one, S))
ok = [x for x in rows if "error" not in x]
# repeat stability on a few stories, call 1 only
def rep(x):
    r = next(s for s in S if s["id"] == x["id"]); st, _ = build_state(r["title"], r["body"], r["published"]); a, _ = call("repeat", st, Q1); return max(abs(a[k]["noul"] - x["answers_call1"][k]["noul"]) for k in a if "noul" in a[k]), sum(abs(a[k]["noul"] - x["answers_call1"][k]["noul"]) for k in a if "noul" in a[k]) / sum(1 for k in a if "noul" in a[k])
with cf.ThreadPoolExecutor(CONC) as ex: reps = list(ex.map(rep, ok[:NREP]))
def noul_keys(prefix): return [k for k in Q1 if k.startswith(prefix) and Q1[k]["type"] == "noul"]
unsure = {}
for nm, pre in (("function", "function_"), ("domain", "domain_"), ("area", "area_"), ("conditions", "cond_"), ("capability_candidates", "capcand_")):
    ks = [k for k in noul_keys(pre) if k != "area_fits_a_listed_area"]; vals = [x["answers_call1"][k]["noul"] for x in ok for k in ks]; unsure[nm] = round(sum(0.3 < v < 0.7 for v in vals) / max(len(vals), 1), 4)
ch_conf = {k: round(sum(x["answers_call1"][k]["confidence"] for x in ok) / max(len(ok), 1), 3) for k in ("area_main", "place_region", "novelty_choice")}
eng = [x for x in ok if x["set"] == "engine"]; any_v3 = lambda x: any(x["answers_call1"][k]["noul"] >= 0.7 for k in x["answers_call1"] if k.startswith("cond_")); has328 = lambda x: bool(x["readings_p328"])
ls = [x for x in ok if x["set"] == "label_store"]; mn = [x for x in ok if x["set"] == "mnds"]
def derived_type(x): a = x["answers_call1"]; return "opinion" if a["function_opinion"]["noul"] >= 0.5 else "forecast" if a["function_prediction"]["noul"] >= 0.5 else "fact"
dom_keys = {slug(v["label"]): v["label"] for v in IPT.values()}
def top_domain(x): a = x["answers_call1"]; k = max((k for k in a if k.startswith("domain_")), key=lambda k: a[k]["noul"]); return dom_keys[k[7:]]
onto = {t["id"] for t in O["topics"]}; ls_in = [x for x in ls if x["ls_topic"] in onto]
fired_n = sum(len(x["fired"]) for x in ok); ev = sum(1 for x in ok for k in x["fired"] if x["answers_call2"].get(f"{k[5:]}__evidence_exists", {}).get("noul", 0) >= 0.5)
res = {"stories": len(S), "stories_ok": len(ok), "errors": len(rows) - len(ok), "sets": dict(collections.Counter(x["set"] for x in ok)), "question_set_hash": QSET, "ontology_version": ONTV, "questions_in_call1": len(Q1),
       "P0_all_typed": bool(ok), "tokens_per_story": {k: round(sum(x["tokens"][k] for x in ok) / max(len(ok), 1)) for k in ("call1", "call2", "p328")}, "tokens_per_story_total": round(sum(sum(x["tokens"].values()) for x in ok) / max(len(ok), 1)),
       "P1_presence_v3_vs_328_read_agreement": round(sum(any_v3(x) == has328(x) for x in ok) / max(len(ok), 1), 4), "P1_n": len(ok),
       "engine_presence_v3_vs_clef_stored": round(sum(any_v3(x) == x["clef_reading"] for x in eng) / max(len(eng), 1), 4), "engine_presence_328read_vs_clef_stored": round(sum(has328(x) == x["clef_reading"] for x in eng) / max(len(eng), 1), 4), "engine_n": len(eng),
       "P3_evidence_exists_share_of_fired": round(ev / max(fired_n, 1), 4), "fired_dials": fired_n,
       "P4_domain_top1_vs_mnds_l1": round(sum(top_domain(x) == x["mn_l1"] for x in mn) / max(len(mn), 1), 4), "P4_n": len(mn), "P4_majority_chance": round(1 / 17, 4),
       "P5_function_derived_vs_label_store_story_type": round(sum(derived_type(x) == x["ls_story_type"] for x in ls) / max(len(ls), 1), 4), "P5_n": len(ls), "P5_label_store_fact_share": round(sum(x["ls_story_type"] == "fact" for x in ls) / max(len(ls), 1), 4),
       "area_main_vs_label_store_topic_exact": round(sum(x["answers_call1"]["area_main"]["choice"] == x["ls_topic"] for x in ls_in) / max(len(ls_in), 1), 4), "area_overlap_n": len(ls_in),
       "P6_unsure_share_by_head": unsure, "choice_mean_confidence": ch_conf, "P7_repeat_mean_abs_diff": round(sum(r[1] for r in reps) / max(len(reps), 1), 4), "P7_repeat_max_abs_diff": round(max((r[0] for r in reps), default=0), 4), "P7_n": len(reps),
       "novelty_choice_counts": dict(collections.Counter(x["answers_call1"]["novelty_choice"]["choice"] for x in ok)), "region_counts": dict(collections.Counter(x["answers_call1"]["place_region"]["choice"] for x in ok).most_common(8)),
       "recent_share": round(sum(x["answers_call1"]["time_recent"]["noul"] >= 0.7 for x in ok) / max(len(ok), 1), 4), "uncertain_share": round(sum(x["answers_call1"]["uncertain_claims"]["noul"] >= 0.7 for x in ok) / max(len(ok), 1), 4), "conflict_share": round(sum(x["answers_call1"]["conflicting_claims"]["noul"] >= 0.7 for x in ok) / max(len(ok), 1), 4),
       "factuality_counts": dict(collections.Counter(x["answers_call2"][f"{k[5:]}__factuality"]["choice"] for x in ok for k in x["fired"] if f"{k[5:]}__factuality" in x["answers_call2"])), "size_mean_score_fired": round(sum(x["answers_call2"][f"{k[5:]}__size"]["score"] for x in ok for k in x["fired"] if f"{k[5:]}__size" in x["answers_call2"]) / max(fired_n, 1), 3),
       "capability_candidates_fired_per_story": round(sum(sum(x["answers_call1"][k]["noul"] >= 0.7 for k in noul_keys("capcand_")) for x in ok) / max(len(ok), 1), 2),
       "input_tokens_total": sum(TOK.values()), "cost_usd_at_0_042_per_million": round(sum(TOK.values()) * 0.042 / 1e6, 3), "calls": dict(NCALL), "seconds": round(time.time() - T0),
       "note": "Every head ON. Domain is scored against MN-DS (outside truth, scoring only); function and area against the label store (a teacher label, not outside truth); presence against Clef's stored reading and the 328-question read (agreement, not accuracy). Size wording for severe and extreme is draft; capability questions are draft candidates (resources)."}
json.dump(res, open(OUT / "t135_full_read.json", "w"), indent=1); open(ROWS, "w").write("\n".join(json.dumps(x) for x in rows))
json.dump({k: v for k, v in FIRST.items()}, open(os.environ.get("REQ_OUT", "/workspace/data/diag/flow/exact_requests_first_story.json"), "w"), indent=1); print(json.dumps(res, indent=1))
