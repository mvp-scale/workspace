"""learn_queue: the learn loop (build spec step 6, plan v2 step 6). Weak or disputed trace articles are queued once per story, a hosted teacher (Jev, through the registry in demo/backends.py) labels them in IPTC codes, a TF-IDF+SGD student (the T145 recipe) is trained on the labels and scored on MN-DS fresh2 by code.
Queue states (spec 2.5): queued -> sampled -> labelled | rejected -> trained | held_out. expired = the IPTC release changed (re-mapped by code). pilot = the first N MN-DS T28 items (scoring only, never queue items, never training).
Enqueued: a traced article with LANDING_WEAK or LANDING_SPLIT or a decider.topic_node abstain (harvest LABEL_QUEUE; spec 2.5); the legacy decider.topic abstain is recorded as the reason LEGACY_TOPIC_ABSTAIN beside a trigger and never queues an article by itself; one row per story key (journal.story_keys; a copy of a queued story is counted and skipped; no key = its own story).
Teacher: the question is a choice over the active IPTC level-1 codes plus "none fits"; then level 2 under the chosen level-1 code (same wiring and request shape as t135/t111: POST /v1/systemone, model and key from the registry entry "jev"). Cost = input tokens x 0.042 USD per million (output free), counted from the API's own usage field.
HARD CAP: every hosted call checks cap - already spent (runs/pulse/learn/spend.jsonl) before each chunk of 40 calls and stops before breaking it; --dry-run makes no hosted call.
MN-DS is scoring only: nothing in pilot rows or fresh2 enters a training file (train() reads queue rows only and asserts it).
    /workspace/models/embed-zs/.venv/bin/python learn_queue.py --enqueue <trace> | --pilot 500 [--dry-run] | --pilot-top2 500 [--dry-run] | --sample R | --teach R [--dry-run] | --train R | --score fresh2 [--round R] | --status | --selftest   (from projects/world-state)
Files (runs/pulse/learn/, or $LQ_OUT): learn_queue.jsonl (one row per story, versioned, with provenance), pilot_rows.jsonl, pilot.json, spend.jsonl, student_r<R>.pkl (saved, not wired), train_r<R>.json, score_<set>_r<R>.json"""
import os, sys, json, re, time, math, hashlib, pickle, argparse, collections, pathlib, threading, urllib.request, concurrent.futures as cf
HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE)); sys.path.insert(0, "/workspace/demo")
import journal as JR
from mnds_codes import gold_codes
OUT = pathlib.Path(os.environ.get("LQ_OUT", str(HERE / "runs/pulse/learn"))); QV = "learn_queue-v1"; PRICE = 0.042 / 1e6; CAP = 0.75; DIV = 3.5; CHUNK = 40; CONC = 8
MEDTOP = "/workspace/data/ontology_src/iptc/medtop.json"; MN = "/workspace/data/anchors/mn_ds"; BASE_FRESH2 = 0.562; BAR_PILOT = 0.561; STATES = ("queued", "sampled", "labelled", "rejected", "trained", "held_out", "expired")
INSTR1 = "Which one news topic is this text mainly about? Choose none if no topic fits."; NONE = {"none": "none fits: none of these topics fits the text"}
Q = lambda: OUT / "learn_queue.jsonl"; J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
def atomic(p, text): p = pathlib.Path(p); p.parent.mkdir(parents=True, exist_ok=True); t = p.with_suffix(p.suffix + ".tmp"); t.write_text(text); t.replace(p)
def rows(): return J(Q()) if Q().exists() else []
def save(R): atomic(Q(), "".join(json.dumps(r, sort_keys=True) + "\n" for r in R))
def wilson(k, n, z=1.96):
    if not n: return [0, 0]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [round(c - h, 3), round(c + h, 3)]
# ---- IPTC active set (by code)
def tree():
    d = json.load(open(MEDTOP)); C = {c["qcode"]: c for c in d["conceptSet"]}; L1 = sorted(q for q, c in C.items() if not c.get("broader") and not c.get("retired"))
    kids = {q: [k for k in C[q].get("narrower", []) if k in C and not C[k].get("retired")] for q in L1}; return d.get("dateReleased"), C, L1, kids
card = lambda c: c["prefLabel"]["en-GB"] + ": " + c.get("definition", {}).get("en-GB", "")
key = lambda q: "m" + q.split(":")[1]
def q_l1(T):
    _, C, L1, _ = T; return {"k": {"type": "choice", "instructions": INSTR1, "criteria": {**{key(q): card(C[q]) for q in L1}, **NONE}}}
def q_l2(T, l1):
    _, C, _, kids = T; return {"k": {"type": "choice", "instructions": "This text is mainly about %s. Which narrower topic fits best? Choose none if none fits." % C[l1]["prefLabel"]["en-GB"], "criteria": {**{key(q): card(C[q]) for q in kids[l1]}, **NONE}}}
state_of = lambda text: "News story:\n" + text
est_tok = lambda state, qs: math.ceil(len(json.dumps({"state": state, "questions": qs})) / DIV)
# ---- hosted wiring: registry entry "jev" (url, key, model), request shape as t135 call()/t111 ask(); the usage field gives the input tokens
LOCK = threading.Lock(); CALLS = [0]
def jev(state, qs):
    import backends; b = backends.BACKENDS["jev"]; body = {"state": state, "questions": qs, "model": b["model"]}
    req = urllib.request.Request(b["url"].rstrip("/") + "/v1/systemone", json.dumps(body).encode(), {"Content-Type": "application/json", "User-Agent": "kp-learn/0.1", "Authorization": "Bearer " + b["key"]}); last = None
    for a in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r: j = json.load(r)
            with LOCK: CALLS[0] += 1
            return j["answers"], (j.get("usage") or {}).get("input_tokens", 0), b["model"]
        except Exception as e: last = e; time.sleep(2 + 3 * a)
    raise last
def spent(): return sum(r["cost_usd"] for r in J(OUT / "spend.jsonl")) if (OUT / "spend.jsonl").exists() else 0.0
def log_spend(phase, calls, tok, **kw):
    with open(OUT / "spend.jsonl", "a") as f: f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "phase": phase, "calls": calls, "input_tokens": tok, "cost_usd": round(tok * PRICE, 6), **kw}) + "\n")
def run_calls(jobs, phase, cap):
    """jobs = [(id, state, qs)] -> ({id: (answers, tokens, model)}, info). Chunks of CHUNK; before each chunk spent + its estimate (scaled by the worst actual/estimate ratio seen) must stay under the cap, else stop (the unsent jobs are returned in info['unsent'])."""
    res = {}; ratio = 1.3; tok = est = 0; i = 0; OUT.mkdir(parents=True, exist_ok=True)   # 1.3 until the first chunk has measured the real ratio
    while i < len(jobs):
        ch = jobs[i:i + CHUNK]; e = sum(est_tok(s, q) for _, s, q in ch)
        if spent() + e * ratio * PRICE > cap: break
        with cf.ThreadPoolExecutor(CONC) as ex: out = list(ex.map(lambda j: (j[0], *jev(j[1], j[2])), ch))
        t = sum(o[2] for o in out); tok += t; est += e; ratio = max(1.0, tok / max(est, 1)); log_spend(phase, len(out), t, est_tokens=e)
        for k, a, u, m in out: res[k] = (a, u, m)
        i += len(ch)
    return res, {"sent": len(res), "unsent": [j[0] for j in jobs[i:]], "input_tokens": tok, "est_tokens": est, "actual_over_est": round(tok / max(est, 1), 3) if est else None, "cost_usd": round(tok * PRICE, 6)}
def parse(a, valid):
    """answer -> (code or None, confidence, reason): none, or a key outside the active set, is never a label."""
    c = (a or {}).get("choice"); conf = (a or {}).get("confidence")
    if c == "none": return None, conf, "none fits"
    for q in valid:
        if key(q) == c: return q, conf, None
    return None, conf, "code not in the active set: %r" % (c,)
# ---- enqueue
def story_ids(L, text):
    j = (L.get("journal") or {}).get("story_key"); ti = L.get("title") or ""
    k = j if j else JR.story_keys(ti, text[len(ti) + 2:] if text.startswith(ti + ". ") else "")   # journal when the line has one, else the same rule from the stored text
    return [x for x in (k.get("title"), k.get("prefix")) if x] or ["id:" + L["id"]]
def enqueue(tr):
    tr = pathlib.Path(tr).resolve(); run = json.load(open(tr / "run.json")); lv = run["label_version"]; R = rows(); idx = {k: r for r in R for k in r["keys"]}; c = collections.Counter(); now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for l in open(tr / "chain.jsonl"):
        L = json.loads(json.loads(l)["line"])
        if L.get("state") != "traced": continue
        c["traced"] += 1; g = set(L.get("gaps") or []); dd = L.get("decider") or {}; tn = (dd.get("topic_node") or {}); tp = (dd.get("topic") or {}).get("outcome", "")
        why = [x for x in ("LANDING_WEAK", "LANDING_SPLIT") if x in g] + (["TOPIC_NODE_ABSTAIN"] if tn.get("harvest") == "LABEL_QUEUE" or str(tn.get("outcome", "")).startswith("ABSTAIN") else [])   # triggers (spec 2.5): topic_node harvest LABEL_QUEUE, the landing gaps
        if not why: c["legacy_topic_abstain_only"] += tp.startswith("ABSTAIN"); continue   # the legacy decider.topic abstain is no trigger by itself; it is only recorded as a reason beside a real trigger
        if tp.startswith("ABSTAIN"): why.append("LEGACY_TOPIC_ABSTAIN")
        c["qualifying"] += 1; t = json.load(open(tr / "a" / ("%d.json" % L["seq"])))["text"]; ks = story_ids(L, t)
        hit = next((idx[k] for k in ks if k in idx), None)
        if hit:
            if hit["id"] == L["id"]: c["already_queued"] += 1   # the same article seen again (a second enqueue of the same trace)
            else: c["duplicate_story"] += 1; hit["copies"] = hit.get("copies", 0) + 1   # a copy of a queued story: counted on the root, never a second teacher read
            continue
        lo = next((s for s in L["stages"] if s["name"] == "topic_landing"), {}).get("out") or {}
        r = {"queue_version": QV, "state": "queued", "keys": ks, "id": L["id"], "trace": run["run_id"], "trace_dir": str(tr), "seq": L["seq"], "text_sha1": L["input"]["text_sha1"], "source": L["source"], "day": (L.get("published") or "")[:10], "why": why,
             "landing_l1_code": lo.get("l1_code"), "l1_source": "rerank-r1" if lo.get("rerank") else "landing", "landing_score": (lo.get("best") or {}).get("score"), "label_version": {"iptc_release": lv.get("iptc_release"), "cards": lv.get("cards")}, "enqueued_at": now, "copies": 0}
        R.append(r); [idx.__setitem__(k, r) for k in ks]; c["queued_new"] += 1
    save(R); return dict(c)
def text_of(r):
    d = json.load(open(pathlib.Path(r["trace_dir"]) / "a" / ("%d.json" % r["seq"]))); t = d["text"]; assert hashlib.sha1(t.encode()).hexdigest() == r["text_sha1"], "text changed since it was queued: " + r["id"]; return t
# ---- sample: seeded, split by source and day (train rows share no source and no day with held-out rows)
def held(salt, kind, val): return int(hashlib.sha1(("%d|%s|%s" % (salt, kind, val)).encode()).hexdigest(), 16) % 7 == 0   # 1 source in 7 and 1 day in 7 are held out
def pick_split(R, salt): return {r["id"]: ("held_out" if held(salt, "src", r["source"]) or held(salt, "day", r["day"]) else "train") for r in R}
def sample(rnd, n=None, seed=1):
    R = rows(); Qd = sorted([r for r in R if r["state"] == "queued"], key=lambda r: hashlib.sha1(("%d|%s" % (seed, r["id"])).encode()).hexdigest())
    if n: Qd = Qd[:n]
    if not Qd: return {"sampled": 0}
    salt = next((s for s in range(60) if 0.15 <= sum(v == "held_out" for v in pick_split(Qd, s).values()) / len(Qd) <= 0.30), 0); sp = pick_split(Qd, salt); ids = {r["id"] for r in Qd}   # first salt giving a 15-30% held-out share; chosen before any label exists
    for r in R:
        if r["id"] in ids: r.update(state="sampled", round=rnd, split=sp[r["id"]], split_salt=salt, seed=seed)
    save(R); return {"sampled": len(ids), "held_out": sum(v == "held_out" for v in sp.values()), "salt": salt}
# ---- pilot: first N MN-DS T28 items, scoring only
def pilot_items(n):
    G = json.load(open(MN + "/gold_T28_clean.json")); out = []
    for x in J(MN + "/items_T28.jsonl"):
        if x["id"] in G:
            c1, c2, st = gold_codes(G[x["id"]])
            if c1: out.append({"id": x["id"], "text": x["text"], "gold_l1": c1, "gold_l2": c2, "gold_l2_status": st})
        if len(out) == n: break
    return out
def pilot(n=500, dry=False, cap=CAP):
    T = tree(); items = pilot_items(n); q1 = q_l1(T); q2 = max((q_l2(T, l1) for l1 in T[2]), key=lambda q: len(json.dumps(q)))   # level-2 estimate uses the largest criteria set (worst case: the level-1 answer is not known yet)
    e1 = [est_tok(state_of(x["text"]), q1) for x in items]; e2 = [est_tok(state_of(x["text"]), q2) for x in items]
    cur = [x["gold_l2_status"] == "current" for x in items]; room = cap - spent(); n_fit = 0; tot = 0
    for a, b, c in zip(e1, e2, cur):
        if (tot + a + (b if c else 0)) * PRICE > room: break
        tot += a + (b if c else 0); n_fit += 1
    est = {"items": len(items), "level1_calls": len(items), "level2_calls_if_level1_ok": sum(cur), "est_input_tokens_level1": sum(e1), "est_input_tokens_level2_worst_case": sum(b for b, c in zip(e2, cur) if c),
           "est_input_tokens_total": sum(e1) + sum(b for b, c in zip(e2, cur) if c), "est_cost_usd": round((sum(e1) + sum(b for b, c in zip(e2, cur) if c)) * PRICE, 4), "cap_usd": cap, "already_spent_usd": round(spent(), 4), "items_that_fit_the_cap": n_fit, "token_estimate": "serialised request characters / %.1f; price %.3f USD per million input tokens" % (DIV, PRICE * 1e6)}
    if dry or n_fit == 0: print(json.dumps(est, indent=1)); return est
    if n_fit < len(items): print("SHRINK: %d items would break the %.2f USD cap; using the first %d" % (len(items), cap, n_fit)); items = items[:n_fit]
    r1, i1 = run_calls([(x["id"], state_of(x["text"]), q1) for x in items], "pilot_l1", cap); P = {}
    for x in items:
        if x["id"] in r1: a, u, m = r1[x["id"]]; c, conf, why = parse(a.get("k"), T[2]); P[x["id"]] = {**x, "model": m, "l1": c, "l1_conf": conf, "l1_why": why, "tokens": u}
    jobs = [(x["id"], state_of(x["text"]), q_l2(T, P[x["id"]]["l1"])) for x in items if x["id"] in P and P[x["id"]]["l1"] and x["gold_l2_status"] == "current"]; r2, i2 = run_calls(jobs, "pilot_l2", cap)
    for k, (a, u, m) in r2.items(): c, conf, why = parse(a.get("k"), T[3][P[k]["l1"]]); P[k].update(l2=c, l2_conf=conf, l2_why=why, tokens=P[k]["tokens"] + u)
    atomic(OUT / "pilot_rows.jsonl", "".join(json.dumps({**v, "state": "pilot", "scoring_only": True}) + "\n" for v in P.values()))
    sc = list(P.values()); k1 = sum(v["l1"] == v["gold_l1"] for v in sc); n1 = len(sc); l2s = [v for v in sc if v["gold_l2_status"] == "current"]   # level 2 is asked, and scored, only where the gold level-2 code is a current IPTC node
    k2 = sum(v.get("l2") == v["gold_l2"] for v in l2s); l1ok = [v for v in l2s if v["l1"] == v["gold_l1"] and "l2" in v]
    tok = i1["input_tokens"] + i2["input_tokens"]; none1 = sum(v["l1_why"] == "none fits" for v in sc); none2 = sum(v.get("l2_why") == "none fits" for v in sc)
    res = {"version": "pilot-v1", "teacher": "jev (registry entry)", "model": next(iter(P.values()))["model"] if P else None, "judge": "MN-DS T28 gold by IPTC code (mnds_codes.gold_codes), first %d items with a level-1 code; scoring only" % len(items), "items_scored": n1, "iptc_release": T[0],
           "l1_accuracy": round(k1 / n1, 3) if n1 else None, "l1_ci95": wilson(k1, n1), "l1_none_fits_share": round(none1 / n1, 3) if n1 else None, "l1_wrong_code_share": round(sum(v["l1"] not in (None, v["gold_l1"]) for v in sc) / n1, 3) if n1 else None,
           "l2_items_scored_current": len(l2s), "l2_accuracy_on_current": round(k2 / len(l2s), 3) if l2s else None, "l2_ci95": wilson(k2, len(l2s)), "l2_accuracy_given_l1_right": round(sum(v.get("l2") == v["gold_l2"] for v in l1ok) / len(l1ok), 3) if l1ok else None, "l2_none_fits_share_of_asked": round(none2 / max(len(r2), 1), 3),
           "unsent_by_cap": len(i1["unsent"]) + len(i2["unsent"]), "input_tokens": tok, "est_input_tokens": i1["est_tokens"] + i2["est_tokens"], "actual_over_est": round(tok / max(i1["est_tokens"] + i2["est_tokens"], 1), 3), "cost_usd": round(tok * PRICE, 4), "hosted_calls": len(r1) + len(r2),
           "stop_rule": "teacher L1 <= %.3f means do not run round 1" % BAR_PILOT, "round1_allowed": bool(n1 and k1 / n1 > BAR_PILOT), "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    atomic(OUT / "pilot.json", json.dumps(res, indent=1)); print(json.dumps(res, indent=1)); return res
# ---- pilot top-2 (owner yes L2744, scoring only): the same first 500 MN-DS T28 items, the teacher names its two most likely level-1 codes and a level-2 code under each. HARD CAP: 0.10 USD of NEW spend (phases pilot_top2_*), checked before every chunk of calls
TOP2_CAP = 0.10; TOP2_V = "pilot-top2-v1"; INSTR_B = "A first reader judged that this text is mainly about %s. Which other news topic is the next most likely main topic of this text? Choose none if no other topic fits."
def q_l1_excl(T, first):
    _, C, L1, _ = T; return {"k": {"type": "choice", "instructions": INSTR_B % C[first]["prefLabel"]["en-GB"], "criteria": {**{key(q): card(C[q]) for q in L1 if q != first}, **NONE}}}
def q_l2_pair(T, a, b): return {"a": q_l2(T, a)["k"], "b": q_l2(T, b)["k"]}
def spent_phase(pre): return sum(r["cost_usd"] for r in J(OUT / "spend.jsonl") if r["phase"].startswith(pre)) if (OUT / "spend.jsonl").exists() else 0.0
def pilot_top2(n=500, dry=False, cap=TOP2_CAP):
    T = tree(); items = pilot_items(n); old = {json.loads(l)["id"] for l in open(OUT / "pilot_rows.jsonl")} if (OUT / "pilot_rows.jsonl").exists() else None; same = (old == {x["id"] for x in items}) if old else None
    q1 = q_l1(T); L1 = T[2]; avg_excl = sum(est_tok("News story:\n", q_l1_excl(T, c)) for c in L1) / len(L1); l2_sizes = [est_tok("News story:\n", q_l2_pair(T, a, a)) for a in L1]; avg_l2 = sum(l2_sizes) / len(l2_sizes)
    txt = [est_tok(state_of(x["text"]), {}) for x in items]; ea = [est_tok(state_of(x["text"]), q1) for x in items]; eb = [t + avg_excl for t in txt]; ec = [t + avg_l2 for t, x in zip(txt, items) if x["gold_l2_status"] == "current"]
    tot = sum(ea) + sum(eb) + sum(ec); ratio = 1.35; est = {"version": TOP2_V, "items": len(items), "same_items_as_pilot_v1": same, "calls_round_a": len(ea), "calls_round_b_if_a_answered": len(eb), "calls_round_c_level2_pairs": len(ec), "est_input_tokens": tot, "est_input_tokens_x_measured_ratio_1.35": round(tot * ratio), "est_cost_usd": round(tot * PRICE, 4), "est_cost_usd_x_ratio": round(tot * ratio * PRICE, 4), "cap_usd": cap, "new_spend_so_far_usd": round(spent_phase("pilot_top2"), 4),
           "level2_estimate": "mean case: the pair of level-2 question sets averaged over the %d level-1 codes (the real chunks are gated on the real request sizes)" % len(L1), "token_estimate": "serialised request characters / %.1f; price %.3f USD per million input tokens; ratio 1.35 = the earlier pilot's actual/estimate (1.33) rounded up" % (DIV, PRICE * 1e6)}
    if dry or tot * ratio * PRICE > cap: print(json.dumps(est, indent=1)); print("DRY RUN" if dry else "ABORT: estimate over the cap"); return est
    base = spent(); capx = base + cap   # run_calls compares total spend with its cap; this makes the new-spend cap 0.10 USD
    ra, ia = run_calls([(x["id"], state_of(x["text"]), q1) for x in items], "pilot_top2_a", capx); P = {}
    for x in items:
        if x["id"] in ra: a, u, m = ra[x["id"]]; c, conf, why = parse(a.get("k"), L1); P[x["id"]] = {**x, "model": m, "version": TOP2_V, "l1a": c, "l1a_conf": conf, "l1a_why": why, "tokens": u}
    rb, ib = run_calls([(k, state_of(P[k]["text"]), q_l1_excl(T, P[k]["l1a"])) for k in P if P[k]["l1a"]], "pilot_top2_b", capx)
    for k, (a, u, m) in rb.items(): c, conf, why = parse(a.get("k"), [q for q in L1 if q != P[k]["l1a"]]); P[k].update(l1b=c, l1b_conf=conf, l1b_why=why, tokens=P[k]["tokens"] + u)
    jobs = [(k, state_of(v["text"]), q_l2_pair(T, v["l1a"], v["l1b"])) for k, v in P.items() if v["gold_l2_status"] == "current" and v["l1a"] and v.get("l1b")]; rc, ic = run_calls(jobs, "pilot_top2_c", capx)
    for k, (a, u, m) in rc.items():
        for w, l1k in (("a", "l1a"), ("b", "l1b")): c, conf, why = parse(a.get(w), T[3][P[k][l1k]]); P[k].update({"l2" + w: c, "l2%s_conf" % w: conf, "l2%s_why" % w: why})
        P[k]["tokens"] += u
    atomic(OUT / "pilot_rows_top2_v1.jsonl", "".join(json.dumps({**v, "state": "pilot", "scoring_only": True}) + "\n" for v in P.values())); sc = list(P.values()); n1 = len(sc)
    top1 = sum(v["l1a"] == v["gold_l1"] for v in sc); top2 = sum(v["gold_l1"] in (v["l1a"], v.get("l1b")) for v in sc); l2s = [v for v in sc if v["gold_l2_status"] == "current"]; l2any = sum(v["gold_l2"] in (v.get("l2a"), v.get("l2b")) for v in l2s)
    tok = ia["input_tokens"] + ib["input_tokens"] + ic["input_tokens"]
    res = {"version": TOP2_V, "teacher": "jev (registry entry)", "model": next(iter(P.values()))["model"] if P else None, "judge": "MN-DS T28 gold by IPTC code, the same first %d items as pilot-v1 (same ids: %s); scoring only, never trained" % (len(items), same), "items_scored": n1, "iptc_release": T[0],
           "l1_top1": round(top1 / n1, 3), "l1_top1_ci95": wilson(top1, n1), "gold_l1_in_top2": round(top2 / n1, 3), "gold_l1_in_top2_ci95": wilson(top2, n1), "none_fits_first": round(sum(v["l1a_why"] == "none fits" for v in sc) / n1, 3), "none_fits_second_of_asked": round(sum(v.get("l1b_why") == "none fits" for v in sc) / max(len(rb), 1), 3), "second_equals_first_or_invalid": sum(bool(v.get("l1b_why")) and v.get("l1b_why") != "none fits" for v in sc),
           "l2_items_scored_current": len(l2s), "gold_l2_in_either_l2_answer": round(l2any / len(l2s), 3) if l2s else None, "gold_l2_in_either_ci95": wilson(l2any, len(l2s)), "unsent_by_cap": len(ia["unsent"]) + len(ib["unsent"]) + len(ic["unsent"]), "hosted_calls": len(ra) + len(rb) + len(rc), "input_tokens": tok, "est_input_tokens": ia["est_tokens"] + ib["est_tokens"] + ic["est_tokens"], "cost_usd": round(tok * PRICE, 4), "cap_usd": cap, "pilot_v1_for_comparison": {"l1_top1": 0.564, "l2_on_current": 0.34}, "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    atomic(OUT / "pilot_top2_v1.json", json.dumps(res, indent=1)); print(json.dumps(res, indent=1)); return res
# ---- teach: teacher labels for the sampled rows of a round; refuses to run when the pilot did not pass
def teach(rnd, dry=False, cap=CAP, l2=True):
    pj = OUT / "pilot.json"
    if not pj.exists() or not json.load(open(pj)).get("round1_allowed"): print("REFUSED: the pilot is missing or did not pass its stop rule (teacher L1 > %.3f)" % BAR_PILOT); return {"refused": True}
    T = tree(); R = rows(); S = [r for r in R if r["state"] == "sampled" and r.get("round") == rnd]; q1 = q_l1(T)
    def exp(r):
        t = text_of(r)[:2000]; return est_tok(state_of(t), q1), est_tok(state_of(t), max((q_l2(T, x) for x in T[2]), key=lambda q: len(json.dumps(q))))
    E = [exp(r) for r in S]; room = cap - spent()
    for use2 in ((True, False) if l2 else (False,)):   # level 2 only when level 1 + level 2 for every sampled row fits the cap; else level 1 only
        need = sum(a + (b if use2 else 0) for a, b in E) * PRICE
        if need <= room: break
    n_fit = 0; tot = 0
    for a, b in E:
        if (tot + a + (b if use2 else 0)) * PRICE > room: break
        tot += a + (b if use2 else 0); n_fit += 1
    est = {"round": rnd, "sampled_rows": len(S), "level2": use2, "est_input_tokens": sum(a + (b if use2 else 0) for a, b in E), "est_cost_usd": round(sum(a + (b if use2 else 0) for a, b in E) * PRICE, 4), "rows_that_fit_the_cap": n_fit, "cap_usd": cap, "already_spent_usd": round(spent(), 4)}
    if dry: print(json.dumps(est, indent=1)); return est
    S = S[:n_fit]; r1, i1 = run_calls([(r["id"], state_of(text_of(r)[:2000]), q1) for r in S], "teach_l1_r%d" % rnd, cap); by = {r["id"]: r for r in S}; lab = {}
    for k, (a, u, m) in r1.items(): c, conf, why = parse(a.get("k"), T[2]); lab[k] = {"model": m, "l1": c, "l1_conf": conf, "why": why, "tokens": u}
    r2 = {}; i2 = {"input_tokens": 0, "unsent": []}
    if use2: r2, i2 = run_calls([(k, state_of(text_of(by[k])[:2000]), q_l2(T, v["l1"])) for k, v in lab.items() if v["l1"]], "teach_l2_r%d" % rnd, cap)
    for k, (a, u, m) in r2.items(): c, conf, why = parse(a.get("k"), T[3][lab[k]["l1"]]); lab[k].update(l2=c, l2_conf=conf, l2_why=why, tokens=lab[k]["tokens"] + u)
    for r in S:
        v = lab.get(r["id"])
        if not v: continue
        base = {"teacher": "jev", "model_version": v["model"], "label_version": {"iptc_release": T[0], "cards": r["label_version"].get("cards")}, "cost_usd": round(v["tokens"] * PRICE, 6), "labelled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "teacher_question": "l1 choice over %d active codes + none; l2 under the chosen code" % len(T[2]) if use2 else "l1 choice over %d active codes + none" % len(T[2])}
        if v["l1"]: r.update(state="labelled", l1_code=v["l1"], l1_conf=v["l1_conf"], l2_code=v.get("l2"), l2_conf=v.get("l2_conf"), l2_why=v.get("l2_why"), **base)
        else: r.update(state="rejected", reject_reason=v["why"], **base)
    save(R); res = {**est, "labelled": sum(r["state"] == "labelled" for r in S), "rejected": sum(r["state"] == "rejected" for r in S), "unsent_by_cap": len(i1["unsent"]) + len(i2["unsent"]), "input_tokens": i1["input_tokens"] + i2["input_tokens"], "cost_usd": round((i1["input_tokens"] + i2["input_tokens"]) * PRICE, 4), "hosted_calls": len(r1) + len(r2)}
    atomic(OUT / ("teach_r%d.json" % rnd), json.dumps(res, indent=1)); print(json.dumps(res, indent=1)); return res
# ---- expire: a new IPTC release re-maps labels by code; a retired code becomes rejected
def expire():
    T = tree(); R = rows(); n = 0
    for r in R:
        if r["state"] in ("labelled", "trained", "held_out") and r["label_version"]["iptc_release"] != T[0]:
            n += 1
            if r["l1_code"] not in T[2]: r.update(state="rejected", reject_reason="retired in " + str(T[0]))
            else: r["label_version"] = {**r["label_version"], "iptc_release": T[0], "remapped_by_code": True}
    save(R); return n
# ---- train: the T145 recipe (TF-IDF 1-2 grams, SGD log loss alpha 2e-6, 12 epochs; min_df 2 under 2000 texts as t144) on level-1 codes of teacher-labelled train-split queue rows
def fit(y, texts):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import SGDClassifier
    v = TfidfVectorizer(ngram_range=(1, 2), min_df=3 if len(texts) > 2000 else 2, max_features=150000, sublinear_tf=True); A = v.fit_transform(texts)
    return v, SGDClassifier(loss="log_loss", alpha=2e-6, max_iter=12, tol=None, n_jobs=6, random_state=7).fit(A, y)
def train(rnd):
    R = rows(); use = [r for r in R if r["state"] == "labelled" and r.get("split") == "train" and r.get("round", 0) <= rnd]
    assert not any(r["id"].startswith(("mn:", "mn4:", "mn2:")) for r in use), "MN-DS item in the training set"
    X = [text_of(r)[:6000] for r in use]; y = [r["l1_code"] for r in use]; v, m = fit(y, X); sid = hashlib.sha1("\n".join(sorted(r["id"] for r in use)).encode()).hexdigest()[:16]
    meta = {"round": rnd, "student": "tfidf-1-2gram + SGD log_loss (T145 recipe)", "trained_on": "teacher IPTC level-1 codes, queue rows only, split=train", "rows": len(use), "classes": dict(collections.Counter(y)), "train_ids_sha": sid, "iptc_release": tree()[0], "teacher_models": sorted({r["model_version"] for r in use}), "registered": False, "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    OUT.mkdir(parents=True, exist_ok=True); pickle.dump({"vectorizer": v, "model": m, "meta": meta}, open(OUT / ("student_r%d.pkl" % rnd), "wb")); ids = {r["id"] for r in use}
    for r in R:
        if r["id"] in ids: r.update(state="trained", student_round=rnd)
        elif r["state"] == "labelled" and r.get("split") == "held_out" and r.get("round", 0) <= rnd: r["state"] = "held_out"
    save(R); atomic(OUT / ("train_r%d.json" % rnd), json.dumps(meta, indent=1)); print(json.dumps(meta, indent=1)); return meta
# ---- score: on MN-DS fresh2 by code (scoring only), plus agreement with the teacher on the held-out queue rows
def score(rnd, sset="fresh2"):
    import numpy as np
    S = pickle.load(open(OUT / ("student_r%d.pkl" % rnd), "rb")); v, m = S["vectorizer"], S["model"]; G = json.load(open(MN + "/gold_%s.json" % sset)); it = {x["id"]: x["text"] for x in J(MN + "/items_%s.jsonl" % sset)}; ids = [i for i in it if i in G]
    gc = [gold_codes(G[i]) for i in ids]; keep = [k for k, g in enumerate(gc) if g[0]]; y = np.array([gc[k][0] for k in keep]); P = m.predict_proba(v.transform([it[ids[k]][:6000] for k in keep])); cls = np.array(m.classes_); top = cls[P.argmax(1)]
    k1 = int((top == y).sum()); n = len(keep); o3 = np.argsort(-P, 1)[:, :3]; k3 = int(sum(y[j] in set(cls[o3[j]]) for j in range(n))); maj = collections.Counter(y.tolist()).most_common(1)[0][1] / n
    pol = y == "medtop:11000000"; rel = y == "medtop:12000000"; hold = [r for r in rows() if r["state"] == "held_out" and r.get("round", 0) <= rnd]; ag = None
    if hold: Ph = m.predict(v.transform([text_of(r)[:6000] for r in hold])); ag = [int(sum(a == r["l1_code"] for a, r in zip(Ph, hold))), len(hold)]
    res = {"set": sset, "round": rnd, "judge": "MN-DS %s gold by IPTC code, level 1, top-1; scoring only" % sset, "items_scored": n, "l1_top1": round(k1 / n, 3), "l1_ci95": wilson(k1, n), "l1_in_top3": round(k3 / n, 3), "majority_class_share": round(maj, 3),
           "baseline_landing_l1_top1": BASE_FRESH2, "bar": round(BASE_FRESH2 + 0.03, 3), "delta_vs_baseline_points": round(100 * (k1 / n - BASE_FRESH2), 1), "passes_bar": bool(k1 / n >= BASE_FRESH2 + 0.03), "l1_top1_politics": [int(pol.sum()), round(float((top[pol] == y[pol]).mean()), 3)], "l1_top1_religion": [int(rel.sum()), round(float((top[rel] == y[rel]).mean()), 3)],
           "l1_top1_without_politics_religion": round(float((top[~(pol | rel)] == y[~(pol | rel)]).mean()), 3), "student_classes": len(cls), "train_rows": S["meta"]["rows"], "heldout_queue_agreement_with_teacher": (ag + [round(ag[0] / ag[1], 3), wilson(*ag)]) if ag else None, "student_registered": False}
    atomic(OUT / ("score_%s_r%d.json" % (sset, rnd)), json.dumps(res, indent=1)); print(json.dumps(res, indent=1)); return res
# ---- round 2 (owner yes L2746): the teacher names its two most likely level-1 codes (second call excludes the first, as pilot_top2) and a level-2 code under each, for the queue stories. Versioned rows in labels_learn-r2-top2.jsonl beside round 1 (queue rows and round-1 files are never touched). HARD CAP 0.40 USD of NEW spend (phases r2_*).
R2_V = "learn-r2-top2"; R2_CAP = 0.40; R2_TARGET = 0.38; R2_RATIO = 1.35; R2_TEXT = 2000; R2_W2 = 0.5; R2_LAB = lambda: OUT / "labels_learn-r2-top2.jsonl"; LANDING_F2 = lambda: OUT / "landing_v1_fresh2_l1.json"
def r2_rows():
    """The stories to relabel, one row per story key (the queue is already deduplicated): the round-1 rows first (trained, held_out; their split kept), then queued rows in seeded order, with the split rule of round 1 (same salt: 1 source in 7 and 1 day in 7 held out)."""
    R = rows(); salt = {r["split_salt"] for r in R if r.get("split_salt") is not None}; assert len(salt) == 1, salt; salt = salt.pop(); seen = set(); out = []
    first = sorted([r for r in R if r["state"] in ("trained", "held_out")], key=lambda r: r["id"]); rest = sorted([r for r in R if r["state"] == "queued"], key=lambda r: hashlib.sha1(("1|%s" % r["id"]).encode()).hexdigest())
    for r in first + rest:
        if any(k in seen for k in r["keys"]): continue
        seen.update(r["keys"]); out.append((r, r["split"] if r.get("split") else ("held_out" if held(salt, "src", r["source"]) or held(salt, "day", r["day"]) else "train")))
    return out, salt
def teach_top2(dry=False, cap=R2_CAP, target=R2_TARGET):
    T = tree(); L1 = T[2]; q1 = q_l1(T); RS, salt = r2_rows(); avg_excl = sum(est_tok("News story:\n", q_l1_excl(T, c)) for c in L1) / len(L1); avg_l2 = sum(est_tok("News story:\n", q_l2_pair(T, a, a)) for a in L1) / len(L1); per = []
    for r, sp in RS: t = est_tok(state_of(text_of(r)[:R2_TEXT]), {}); per.append(est_tok(state_of(text_of(r)[:R2_TEXT]), q1) + (t + avg_excl) + (t + avg_l2))
    cum = 0; n_fit = 0
    for e in per:
        if (cum + e) * R2_RATIO * PRICE > target: break
        cum += e; n_fit += 1
    tot = sum(per); est = {"version": R2_V, "stories_in_queue": len(RS), "round1_rows_first": sum(r["state"] in ("trained", "held_out") for r, _ in RS), "est_input_tokens_all": tot, "est_cost_usd_all_x1.35": round(tot * R2_RATIO * PRICE, 4), "stories_that_fit": n_fit, "est_input_tokens_fit": cum, "est_cost_usd_fit": round(cum * PRICE, 4), "est_cost_usd_fit_x1.35": round(cum * R2_RATIO * PRICE, 4), "cap_usd": cap, "target_usd": target, "text": "title+body as the trace read it, first %d characters (as round 1)" % R2_TEXT, "split_salt": salt,
           "ratio": "1.35 = pilot-top2 measured actual/estimate (1.27) and round 1 (1.01) rounded up; the tokens are estimated as request characters / %.1f" % DIV, "calls": "a: level 1; b: next level 1 excluding a; c: level 2 under a and b (one call)"}
    if dry: print(json.dumps(est, indent=1)); return est
    if n_fit < len(RS): print("SHRINK: %d stories would break the %.2f USD target; using the first %d" % (len(RS), target, n_fit))
    RS = RS[:n_fit]; capx = spent() + cap; txt = {r["id"]: state_of(text_of(r)[:R2_TEXT]) for r, _ in RS}
    ra, ia = run_calls([(r["id"], txt[r["id"]], q1) for r, _ in RS], "r2_a", capx); P = {}
    for r, sp in RS:
        if r["id"] in ra: a, u, m = ra[r["id"]]; c, conf, why = parse(a.get("k"), L1); P[r["id"]] = {"id": r["id"], "keys": r["keys"], "label_version": R2_V, "teacher": "jev", "model_version": m, "iptc_release": T[0], "source": r["source"], "day": r["day"], "split": sp, "split_salt": salt, "queue_state_at_run": r["state"], "round1_l1_code": r.get("l1_code"), "l1a": c, "l1a_conf": conf, "l1a_why": why, "tokens": u}
    rb, ib = run_calls([(k, txt[k], q_l1_excl(T, v["l1a"])) for k, v in P.items() if v["l1a"]], "r2_b", capx)
    for k, (a, u, m) in rb.items(): c, conf, why = parse(a.get("k"), [q for q in L1 if q != P[k]["l1a"]]); P[k].update(l1b=c, l1b_conf=conf, l1b_why=why, tokens=P[k]["tokens"] + u)
    jobs = [(k, txt[k], q_l2_pair(T, v["l1a"], v["l1b"]) if v.get("l1b") else {"a": q_l2(T, v["l1a"])["k"]}) for k, v in P.items() if v["l1a"] and "l1b" in v]; rc, ic = run_calls(jobs, "r2_c", capx)
    for k, (a, u, m) in rc.items():
        for w, l1k in (("a", "l1a"), ("b", "l1b")):
            if w in a and P[k].get(l1k): c, conf, why = parse(a.get(w), T[3][P[k][l1k]]); P[k].update({"l2" + w: c, "l2%s_conf" % w: conf, "l2%s_why" % w: why})
        P[k]["tokens"] += u
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()); atomic(R2_LAB(), "".join(json.dumps({**v, "cost_usd": round(v["tokens"] * PRICE, 6), "labelled_at": now}, sort_keys=True) + "\n" for v in P.values())); V = list(P.values())
    tok = ia["input_tokens"] + ib["input_tokens"] + ic["input_tokens"]; est_t = ia["est_tokens"] + ib["est_tokens"] + ic["est_tokens"]
    res = {**est, "stories_sent": len(RS), "label_rows": len(V), "a_none_or_invalid": sum(v["l1a"] is None for v in V), "b_none_fits": sum(v.get("l1b_why") == "none fits" for v in V), "two_labels": sum(bool(v["l1a"] and v.get("l1b")) for v in V), "with_l2a": sum(bool(v.get("l2a")) for v in V), "with_l2b": sum(bool(v.get("l2b")) for v in V), "split_counts": dict(collections.Counter(v["split"] for v in V)), "state_counts_at_run": dict(collections.Counter(v["queue_state_at_run"] for v in V)),
           "unsent_by_cap": len(ia["unsent"]) + len(ib["unsent"]) + len(ic["unsent"]), "hosted_calls": len(ra) + len(rb) + len(rc), "input_tokens": tok, "est_input_tokens_run": est_t, "actual_over_est": round(tok / max(est_t, 1), 3), "cost_usd": round(tok * PRICE, 4), "when": now}
    atomic(OUT / "teach_r2_top2.json", json.dumps(res, indent=1)); print(json.dumps(res, indent=1)); return res
def fit_w(y, texts, w):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import SGDClassifier
    v = TfidfVectorizer(ngram_range=(1, 2), min_df=3 if len(texts) > 2000 else 2, max_features=150000, sublinear_tf=True); A = v.fit_transform(texts)   # the T145 recipe as fit(), with a sample weight per row
    return v, SGDClassifier(loss="log_loss", alpha=2e-6, max_iter=12, tol=None, n_jobs=6, random_state=7).fit(A, y, sample_weight=w)
def train_top2():
    """Student choice (stated before the run): one TF-IDF+SGD one-vs-rest student on IPTC level-1 codes; each split=train story contributes its first teacher label with weight 1.0 and, when the teacher gave a second code, a second row of the same text with that code at weight 0.5."""
    L = J(R2_LAB()); Q = {r["id"]: r for r in rows()}; use = [x for x in L if x["split"] == "train" and x["l1a"]]
    assert not any(x["id"].startswith(("mn:", "mn4:", "mn2:")) for x in use), "MN-DS item in the training set"; salt = L[0]["split_salt"]; bad = sum(held(salt, "src", x["source"]) or held(salt, "day", x["day"]) for x in use); assert bad == 0, "train rows on a held-out source or day: %d" % bad
    X = []; y = []; w = []
    for x in use:
        t = text_of(Q[x["id"]])[:6000]; X.append(t); y.append(x["l1a"]); w.append(1.0)
        if x.get("l1b"): X.append(t); y.append(x["l1b"]); w.append(R2_W2)
    v, m = fit_w(y, X, w); meta = {"round": 2, "label_version": R2_V, "student": "tfidf-1-2gram + SGD log_loss one-vs-rest (T145 recipe), sample-weighted", "weights": "first label 1.0, second label %.1f (second row of the same text)" % R2_W2, "stories": len(use), "training_rows": len(X), "second_labels": sum(1 for x in use if x.get("l1b")), "classes_first": dict(collections.Counter(x["l1a"] for x in use)), "iptc_release": tree()[0], "split": "round-1 source-and-day split (same salt); no MN-DS item in training (asserted)",
            "train_rows_on_a_held_out_source_or_day": bad, "registered": False, "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    pickle.dump({"vectorizer": v, "model": m, "meta": meta}, open(OUT / "student_r2.pkl", "wb")); atomic(OUT / "train_r2.json", json.dumps(meta, indent=1)); print(json.dumps(meta, indent=1)); return meta
def score_top2(sset="fresh2"):
    import numpy as np
    S = pickle.load(open(OUT / "student_r2.pkl", "rb")); v, m = S["vectorizer"], S["model"]; G = json.load(open(MN + "/gold_%s.json" % sset)); it = {x["id"]: x["text"] for x in J(MN + "/items_%s.jsonl" % sset)}; ids = [i for i in it if i in G]
    gc = [gold_codes(G[i]) for i in ids]; keep = [k for k, g in enumerate(gc) if g[0]]; y = np.array([gc[k][0] for k in keep]); kid = [ids[k] for k in keep]; P = m.predict_proba(v.transform([it[i][:6000] for i in kid])); cls = np.array(m.classes_); o = np.argsort(-P, 1); top = cls[o[:, 0]]; n = len(keep)
    k1 = int((top == y).sum()); k2 = int(sum(y[j] in set(cls[o[j, :2]]) for j in range(n))); LD = json.load(open(LANDING_F2())); land = np.array([LD["l1"].get(i) for i in kid]); lk = int((land == y).sum()); ag = top == land; na = int(ag.sum())
    L = J(R2_LAB()); hold = [x for x in L if x["split"] == "held_out" and x["l1a"]]; Q = {r["id"]: r for r in rows()}; Ph = m.predict_proba(v.transform([text_of(Q[x["id"]])[:6000] for x in hold])); th = cls[Ph.argmax(1)]; t2 = [set(cls[np.argsort(-Ph[j])[:2]]) for j in range(len(hold))]
    a1 = int(sum(a == x["l1a"] for a, x in zip(th, hold))); a2 = int(sum(x["l1a"] in t2[j] for j, x in enumerate(hold))); a3 = int(sum(bool(x.get("l1b")) and x["l1b"] in t2[j] for j, x in enumerate(hold) if x.get("l1b")))
    res = {"set": sset, "round": 2, "label_version": R2_V, "judge": "MN-DS %s gold by IPTC code, level 1; scoring only" % sset, "items_scored": n, "l1_top1": round(k1 / n, 3), "l1_top1_ci95": wilson(k1, n), "bar_top1": 0.59, "pass_top1": bool(k1 / n >= 0.59), "gold_in_top2": round(k2 / n, 3), "gold_in_top2_ci95": wilson(k2, n), "bar_top2": 0.80, "pass_top2": bool(k2 / n >= 0.80),
           "landing_v1_top1_same_items": round(lk / n, 3), "round1_student_top1": 0.362, "agreement_view": {"rule": "student top-1 equals the landing-v1 level-1 code", "coverage": round(na / n, 3), "n": na, "accuracy": round(float((top[ag] == y[ag]).mean()), 3) if na else None, "accuracy_ci95": wilson(int((top[ag] == y[ag]).sum()), na), "landing_alone_accuracy": round(lk / n, 3)},
           "heldout_queue_rows": len(hold), "heldout_agreement_top1_with_teacher_first": [a1, len(hold), round(a1 / len(hold), 3), wilson(a1, len(hold))], "heldout_teacher_first_in_student_top2": [a2, len(hold), round(a2 / len(hold), 3)], "heldout_teacher_second_in_student_top2": [a3, sum(bool(x.get("l1b")) for x in hold), round(a3 / max(1, sum(bool(x.get("l1b")) for x in hold)), 3)], "train_stories": S["meta"]["stories"], "student_registered": False}
    atomic(OUT / ("score_%s_r2.json" % sset), json.dumps(res, indent=1)); print(json.dumps(res, indent=1)); return res
def status(tr=None):
    R = [r for r in rows() if not tr or r["trace"] == tr]; c = collections.Counter(r["state"] for r in R); return {"rows": len(R), "by_state": dict(c), "copies_skipped": sum(r.get("copies", 0) for r in R), "spent_usd": round(spent(), 4)}
# ---- selftest: offline, no hosted call, in a temp folder
def selftest():
    import tempfile, shutil; global OUT, jev; OUT = pathlib.Path(tempfile.mkdtemp(prefix="lq_")); ok = []; chk = lambda name, cond, got: (ok.append((name, bool(cond), got)), print("PASS" if cond else "FAIL", name, got))
    tr = OUT / "trace"; (tr / "a").mkdir(parents=True); lines = []
    mk = lambda seq, ti, body, gaps, out="ANSWER_PROVISIONAL", src="S1", day="2026-11-05": (seq, ti, body, gaps, out, src, day)
    spec = [mk(0, "Mayor opens the new bridge over the river after a long delay", "x" * 150, ["LANDING_WEAK"]), mk(1, "Mayor opens the new bridge over the river after a long delay", "x" * 150, ["LANDING_WEAK"], src="S2"), mk(2, "A strong landing story about the harvest in the north", "y" * 150, []),
            mk(3, "Short story one", "w" * 120, ["LANDING_SPLIT"]), mk(4, "Short story two", "w" * 120, ["LANDING_SPLIT"], day="2026-11-06"), mk(5, "Council votes on a new housing plan for the east side", "z" * 150, [], out="ABSTAIN_NOT_ADMITTED"), mk(6, "Skipped line", "q", ["LANDING_WEAK"]), mk(7, "Only the old topic field abstains on this one story today", "v" * 150, [], out="ABSTAIN_NOT_ADMITTED")]
    for seq, ti, body, gaps, out, src, day in spec:
        text = ti + ". " + body; L = {"state": "skipped" if seq == 6 else "traced", "gaps": gaps, "id": "id%d" % seq, "seq": seq, "title": ti, "source": src, "published": day + "T10:00:00Z", "input": {"text_sha1": hashlib.sha1(text.encode()).hexdigest()}, "decider": {"topic": {"outcome": out}, "topic_node": {"outcome": "ABSTAIN_LOW_CONFIDENCE" if seq == 5 else "ANSWER_PROVISIONAL", "harvest": "LABEL_QUEUE" if seq == 5 else "DISCARD"}}, "stages": [{"name": "topic_landing", "out": {"l1_code": "medtop:11000000", "best": {"score": 0.5}}}]}
        (tr / "a" / ("%d.json" % seq)).write_text(json.dumps({"text": text})); lines.append(json.dumps({"seq": seq, "line": json.dumps(L)}))
    (tr / "chain.jsonl").write_text("\n".join(lines)); (tr / "run.json").write_text(json.dumps({"run_id": "run-test", "label_version": {"iptc_release": tree()[0], "cards": "abc"}}))
    c = enqueue(tr); chk("U-enqueue counts", c["traced"] == 7 and c["qualifying"] == 5 and c["legacy_topic_abstain_only"] == 1 and c["queued_new"] == 3 + 0 and c["duplicate_story"] == 2, c)   # ids 0 (copy 1 skipped), 3 (copy 4 skipped), 5
    c2 = enqueue(tr); chk("U-enqueue idempotent", c2.get("queued_new", 0) == 0 and len(rows()) == 3, c2)
    chk("U-no strong landing / skipped queued", {r["id"] for r in rows()} == {"id0", "id3", "id5"}, sorted(r["id"] for r in rows()))
    chk("U-reasons: topic_node trigger, legacy abstain labelled beside it, legacy alone queues nothing", {r["id"]: r["why"] for r in rows()}["id5"] == ["TOPIC_NODE_ABSTAIN", "LEGACY_TOPIC_ABSTAIN"] and "id7" not in {r["id"] for r in rows()}, {r["id"]: r["why"] for r in rows()})
    # more rows so a split and a fit exist: synthetic queued rows with real-looking text via the same trace folder
    R = rows(); T = tree()
    for i in range(60):
        ti = "Synthetic story number %d about topic words %s" % (i, "alpha beta gamma delta"[i % 4 * 6:i % 4 * 6 + 5]); body = ("code %d " % i) * 40; text = ti + ". " + body
        (tr / "a" / ("%d.json" % (100 + i))).write_text(json.dumps({"text": text})); R.append({**R[0], "id": "syn%d" % i, "seq": 100 + i, "keys": ["k%d" % i], "text_sha1": hashlib.sha1(text.encode()).hexdigest(), "source": "S%d" % (i % 9), "day": "2026-11-%02d" % (1 + i % 11), "state": "queued"})
    save(R); s = sample(1, seed=3); chk("U-sample split", s["sampled"] == 63 and 0.10 <= s["held_out"] / 63 <= 0.40, s)
    S = rows(); sl = S[0]["split_salt"]; bad_tr = [r["id"] for r in S if r["split"] == "train" and (held(sl, "src", r["source"]) or held(sl, "day", r["day"]))]; bad_ho = [r["id"] for r in S if r["split"] == "held_out" and not (held(sl, "src", r["source"]) or held(sl, "day", r["day"]))]
    chk("U-split: train rows have no held-out source or day", not bad_tr and not bad_ho and any(r["split"] == "train" for r in S), [len(bad_tr), len(bad_ho)])
    chk("U-teach refused without pilot", teach(1).get("refused"), "no pilot.json")
    (OUT / "pilot.json").write_text(json.dumps({"round1_allowed": True})); n_calls = [0]
    def stub(state, qs):   # a fake teacher: answers by the number in the state; every 9th row none fits
        n_calls[0] += 1; k = list(qs["k"]["criteria"]); h = int(hashlib.sha1(state.encode()).hexdigest(), 16)
        return {"k": {"choice": "none" if h % 9 == 0 else k[h % (len(k) - 1)], "confidence": 0.9}}, 700, "stub-model"
    jev = lambda state, qs: (lambda a, u, m: (a, u, m))(*stub(state, qs))
    d = teach(1, dry=True); chk("U-dry-run makes no call", n_calls[0] == 0 and d["rows_that_fit_the_cap"] == 63, d["rows_that_fit_the_cap"])
    d = teach(1, cap=0.00001); rc, ri = run_calls([("j%d" % i, "s" * 800, {"k": {}}) for i in range(40)], "t", 1e-9)
    chk("U-cap stops before any call it cannot pay", n_calls[0] == 0 and d["labelled"] == 0 and d["rejected"] == 0 and not rc and len(ri["unsent"]) == 40, n_calls[0])
    d = teach(1, cap=0.75); R = rows(); chk("U-teach states", d["labelled"] + d["rejected"] == 63 and all(r["state"] in ("labelled", "rejected") for r in R) and d["rejected"] > 0 and all(r["reject_reason"] == "none fits" for r in R if r["state"] == "rejected"), {k: d[k] for k in ("labelled", "rejected", "hosted_calls")})
    sp0 = spent(); chk("U-spend recorded from usage", abs(sp0 - 700 * d["hosted_calls"] * PRICE) < 1e-5, round(sp0, 6))
    n0 = n_calls[0]; chk("U-no relabel", teach(1)["rows_that_fit_the_cap"] == 0 and n_calls[0] == n0, n_calls[0] - n0)
    # the student: trains on queue rows only, never on pilot ids; held-out rows are never trained
    p = {"id": "mn:1", "text": "x"}; (OUT / "pilot_rows.jsonl").write_text(json.dumps(p) + "\n"); m = train(1); R = rows()
    chk("U-train uses train split only", m["rows"] == sum(r["state"] == "trained" for r in R) and not any(r["state"] == "trained" and r["split"] == "held_out" for r in R) and not any(r["id"] == "mn:1" for r in R), m["rows"])
    chk("U-held_out kept apart", all(r["state"] == "held_out" for r in R if r.get("split") == "held_out" and r.get("l1_code")), collections.Counter(r["state"] for r in R))
    chk("U-expire remaps by code", expire() == 0, "same release"); shutil.rmtree(OUT, ignore_errors=True)
    print("selftest: %d of %d pass" % (sum(o[1] for o in ok), len(ok))); return all(o[1] for o in ok)
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--enqueue"); ap.add_argument("--pilot", type=int); ap.add_argument("--pilot-top2", type=int); ap.add_argument("--sample", type=int); ap.add_argument("--n", type=int); ap.add_argument("--teach", type=int); ap.add_argument("--train", type=int); ap.add_argument("--score"); ap.add_argument("--round", type=int, default=1)
    ap.add_argument("--teach-top2", action="store_true"); ap.add_argument("--train-top2", action="store_true"); ap.add_argument("--score-top2", action="store_true"); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--cap", type=float, default=CAP); ap.add_argument("--status", action="store_true"); ap.add_argument("--selftest", action="store_true"); ap.add_argument("--expire", action="store_true"); a = ap.parse_args()
    if a.selftest: sys.exit(0 if selftest() else 1)
    if a.enqueue: print(json.dumps(enqueue(a.enqueue))); print(json.dumps(status()))
    if a.pilot: pilot(a.pilot, a.dry_run, a.cap)
    if a.pilot_top2: pilot_top2(a.pilot_top2, a.dry_run, TOP2_CAP if a.cap == CAP else a.cap)
    if a.sample: print(json.dumps(sample(a.sample, a.n)))
    if a.teach: teach(a.teach, a.dry_run, a.cap)
    if a.train: train(a.train)
    if a.score: score(a.round if not a.train else a.train, a.score)
    if a.teach_top2: teach_top2(a.dry_run, R2_CAP if a.cap == CAP else a.cap)
    if a.train_top2: train_top2()
    if a.score_top2: score_top2()
    if a.expire: print(expire())
    if a.status: print(json.dumps(status()))
