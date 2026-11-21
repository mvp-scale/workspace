"""Funnel view (owner 2026-11-19): one file that walks a live-trace v2 run through the whole funnel, Read -> Extract -> Topic -> Graph -> World state -> Decide -> Learn,
as counts over every traced article plus two real articles walked step by step (one that passes, one that goes to Learn). Read-only on the trace; writes <trace>/funnel.json.
    /workspace/models/embed-zs/.venv/bin/python funnel_view.py /workspace/demo/mockups/structure-live/runs-v2/trace"""
import sys, os, json, glob, statistics, collections, time
import spacy
from structure_pack import Pack
import journal as JR
import ledger_split as LSP
import learn_queue as LQM
TR = sys.argv[1]; P = Pack(spacy.blank("en")); lab = lambda q: P.lab(q) if q in P.node else q
run = json.load(open(TR + "/run.json")); lines = [json.loads(json.loads(l)["line"]) for l in open(TR + "/chain.jsonl")]; lines = [l for l in lines if l.get("state") == "traced"]
def st(l, n): return next((s for s in l["stages"] if s["name"] == n), {})
WARN = []   # every degraded read is listed here, printed, written to funnel.json and appended to the Graph note
def dups(lines):
    """seq -> (kind, of_seq, publishers): the journal's own when EVERY line carries one; when none or only some do, recomputed read-only from the stored text with journal.replay (runs made before step 3, or a mixed run) and a warning says so. Second value: True when read from the journal."""
    nj = sum(1 for l in lines if (l.get("journal") or {}).get("dup"))
    if lines and nj == len(lines): return {l["seq"]: (l["journal"]["dup"]["kind"], l["journal"]["dup"]["of_seq"], l["journal"]["publishers"]) for l in lines}, True
    if nj: WARN.append("mixed run: %d of %d lines carry a journal, so every copy count is recomputed from the stored text, not read from the journal" % (nj, len(lines)))
    it = []
    for l in lines:
        d = json.load(open("%s/a/%d.json" % (TR, l["seq"]))); ti = l.get("title") or ""; it.append((l["seq"], ti, d["text"][len(ti) + 2:] if d["text"].startswith(ti + ". ") else "", l["source"]))
    return {x[0]: (r["kind"], r["of_seq"], r["publishers"]) for x, r in zip(it, JR.replay(it))}, False
def ids(l):
    """(topic ID found in the IPTC tree, place count, name count, journal-vs-stage topic mismatch): from the journal when the line has one, else from the stage outputs (same facts, same sources; each line without a journal is counted in NOJ and warned about). The topic check is a real join: the ID must be a node of the IPTC pack (P.node), and the journal's ID must equal the topic_landing stage's."""
    j = l.get("journal"); _to = st(l, "topic_landing").get("out") or {}; sb = (_to.get("rerank") or {}).get("node") or (_to.get("best") or {}).get("qcode")
    if j:
        jb = (j["ids"].get("topic") or {}).get("best"); jb = jb.get("qcode") if isinstance(jb, dict) else jb
        return bool(jb) and jb in P.node, len(j["ids"].get("places") or []), len(j["ids"].get("names") or []), bool(sb) and jb != sb
    return bool(sb) and sb in P.node, len((st(l, "place_linker").get("out") or {}).get("top_countries") or []), int(((st(l, "facts").get("out") or {}).get("kinds") or {}).get("name", 0)), False
N = len(lines); C = collections.Counter(); l1 = collections.Counter(); l2 = collections.Counter(); dec = collections.defaultdict(collections.Counter); chars = []
for l in lines:
    g = set(l.get("gaps") or []); chars.append(l["input"]["chars"]); C["body"] += l["input"]["has_body"]
    f = st(l, "facts").get("out") or {}; k = f.get("kinds", {})
    C["facts_any"] += bool(f.get("stated")); C["names"] += bool(k.get("name")); C["dates"] += bool(f.get("stated_date")); C["amounts"] += bool(f.get("stated_amount")); C["triples"] += bool(k.get("triple"))
    C["place"] += bool((st(l, "place_linker").get("out") or {}).get("linked"))
    t = st(l, "topic_landing")
    if t.get("state") in ("ran", "abstain"):   # abstain = the stage ran and the calibrated p was under the line (spec 2.1)
        o = t["out"]; C["landed"] += 1; C["abstain"] += t["state"] == "abstain"; C["v1"] += o.get("p") is not None; C["answer_l1"] += o.get("decision") == "ANSWER_L1"; C["damped"] += bool(o.get("damped")); C["voted"] += bool(o.get("voted")); C["rerank"] += "rerank" in o; C["rr_differs"] += bool(o.get("landing_l1_code")) and o["landing_l1_code"] != o["l1_code"]; C["agree3"] += o["l1_agree3"] == 3; C["weak"] += "LANDING_WEAK" in g; C["split"] += "LANDING_SPLIT" in g
        C["learn"] += ("LANDING_WEAK" in g) or ("LANDING_SPLIT" in g); l1[o["l1_code"]] += 1
        _nd = (o.get("rerank") or {}).get("node") or o["best"]["qcode"]; ch = P.chain(_nd) if _nd in P.node else []; l2[ch[1] if len(ch) > 1 else ch[0] if ch else None] += 1
    for fld, v in (l.get("decider") or {}).items() if isinstance(l.get("decider"), dict) else []: dec[fld]["answered" if v["outcome"].startswith("ANSWER") else "abstained"] += 1
pct = lambda a: round(100 * a / N, 1) if N else 0
DUP, FROM_J = dups(lines); KC = collections.Counter(v[0] for v in DUP.values()); INDEP = KC["first"] + KC["generic_title"] + KC["no_key"]; MULTI = len({v[1] for v in DUP.values() if v[0] == "copy"}); MAXP = max([v[2] for v in DUP.values()] or [1]); ID = [ids(l) for l in lines]; NOJ = [sum(1 for l in lines if not l.get("journal"))]; MISM = sum(x[3] for x in ID)
if NOJ[0] and NOJ[0] < N: WARN.append("%d of %d lines have no journal: their topic, place and name IDs are read from the stage outputs" % (NOJ[0], N))
if MISM: WARN.append("%d records: the journal's topic ID differs from the topic_landing stage's" % MISM)
try: CAL = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "specs/landing_calibration_v1.json")))
except Exception: CAL = None
LQP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs/pulse/learn"); IDS = {l["id"] for l in lines}; LQ = [r for r in (json.loads(l) for l in open(LQP + "/learn_queue.jsonl")) if r["id"] in IDS] if os.path.exists(LQP + "/learn_queue.jsonl") else []; LC = collections.Counter(r["state"] for r in LQ)   # queue rows whose article is in this run (an article first queued by an earlier run still counts: the same article, its real queue state)   # step 6 queue: this run's articles
def _lj(f):
    try: return json.load(open(os.path.join(LQP, f)))
    except Exception: return None
_pj, _sj = _lj("pilot.json"), _lj("score_fresh2_r1.json"); _t2, _s2, _p2 = _lj("teach_r2_top2.json"), _lj("score_fresh2_r2.json"), _lj("pilot_top2_v1.json")
LEARN_NOTE = ("Queue built (plan step 6): one row per story, %d copies skipped. " % sum(r.get("copies", 0) for r in LQ) if LQ else "Queue built (plan step 6) but empty for this run: run learn_queue.py --enqueue <trace>. ") + ("Teacher pilot on 500 MN-DS items: level-1 %.3f, level-2 %.3f, cost %.3f USD. " % (_pj["l1_accuracy"], _pj["l2_accuracy_on_current"], _pj["cost_usd"]) if _pj else "No teacher pilot yet. ") + ("Student round 1 on MN-DS fresh2: level-1 %.3f against the 0.592 bar (%s); saved, not registered." % (_sj["l1_top1"], "passes" if _sj["passes_bar"] else "fails") if _sj else "No student scored yet.") + (" Round 2 (owner yes L2746): %d stories relabelled with two IPTC codes each (%d with both) for %.3f USD (cap 0.40; shrunk from %d queue stories to fit); student trained on both labels (first weight 1.0, second 0.5), saved, not registered. On MN-DS fresh2: top-1 %.3f against the 0.59 bar (%s), correct code in its top 2 %.3f against 0.80 (%s). When it agrees with the landing (%.1f%% of items) it is right %.1f%% (landing alone %.1f%%). Agreement with the teacher on held-back queue rows: %.1f%%." % (_t2["label_rows"], _t2["two_labels"], _t2["cost_usd"], _t2["stories_in_queue"], _s2["l1_top1"], "PASS" if _s2["pass_top1"] else "FAIL", _s2["gold_in_top2"], "PASS" if _s2["pass_top2"] else "FAIL", 100 * _s2["agreement_view"]["coverage"], 100 * _s2["agreement_view"]["accuracy"], 100 * _s2["landing_v1_top1_same_items"], 100 * _s2["heldout_agreement_top1_with_teacher_first"][2]) if _t2 and _s2 else "")
LGP = TR + "/ledger.json"; LG = json.load(open(LGP)) if os.path.exists(LGP) else None   # step 5 output: ledger_split.py <trace> --write
if LG and (LG.get("as_of") or {}).get("run_id") != run.get("run_id"): WARN.append("ledger.json is from run %s, not this run: step 5 shown as not built" % (LG.get("as_of") or {}).get("run_id")); LG = None
LSPEC = json.load(open(LSP.SPEC)); RNAME = {r["id"]: r["name"] for r in LSPEC["resources"]}; LED = LSP.Ledger(LSPEC); EV = {l["seq"]: LED.add(l) for l in lines}   # per-article ledger events, same code as the page and ledger.json
def ledger_stage():
    if not LG: return {"step": "5. World state", "built": False, "plain": "Each topic becomes a tracked resource: how much it is talked about, which direction, which names are attached.", "rows": [[lab(k), v, pct(v)] for k, v in l2.most_common(8) if k], "note": "Ledger output missing for this run: python ledger_split.py <trace> --write. Shown: the level-2 topics this run's articles landed in."}
    R = LG["rows"]; sh = LG.get("split_half") or {}; touched = [r for r in R if r["items"]]; stc = collections.Counter(r["state"] for r in R); a = LG["as_of"]
    return {"step": "5. World state", "built": True, "plain": "Each topic becomes a tracked resource: how much it is talked about, which direction, which names are attached.", "rows": [["Resources with a mention (of %d)" % len(R), len(touched), round(100 * len(touched) / max(1, len(R)), 1)]] + [["%s (%s, value %.2f)" % (r["name"], r["state"], r["value"]), r["items"], pct(r["items"])] for r in touched[:8]],
            "note": "Built (plan step 5, resource ledger v0; panel wording is a draft, owner to confirm R7). %d stories counted once, as of article #%s; a condition with a direction on %d of them. States: %s. Counts are stories that reached the resource; every link from topic to resource is the world engine's own guess. Split-half over two publisher groups (pre-written prediction M4, %d of %d checks FAILED: %s): overall mix agrees (%s) but so does a random publisher split (%s), so it reflects a stable topic mix; change between windows does not agree (%s), so trends are not shown. Two size and timing rules are our readings of spec 2.4 (ledger.json \"readings\"), owner to confirm. Panel: sim page, #s_ledger." % (LG["independent"], a["seq"], LG["direction_items"], ", ".join("%s %d" % kv for kv in sorted(stc.items())), sh.get("m4_failed", "?"), len(sh.get("m4_checks") or []), "; ".join("%s predicted %s, measured %s" % (x["check"], x["predicted"], x["measured"]) for x in sh.get("m4_checks") or [] if x["result"] == "FAIL"), sh.get("whole_stream"), (sh.get("whole_random_publisher_split_mean_p95") or ["?"])[0], sh.get("change_median"))}
if C["v1"] and CAL: fc = CAL["fresh2_check"]; TOPIC_NOTE = "Landing-v1 (hub damping on %d articles, sentence vote on %d (%s), calibrated confidence p). Measured on MN-DS human labels, by IPTC code: top-level topic right %.1f%% on fresh ones (%.1f%% before damping; bar 60%%, so still provisional). The answer line is p %.3f, where running accuracy held 80%% on MN-DS T28; on fresh ones it covers %.1f%% at %.1f%% right. Confidence quality on fresh ones: AUROC %.2f. This run: %d of %d answered, the rest abstain and go to Learn." % (C["damped"], C["voted"], "the articles where the 3 best cards disagree" if CAL.get("gate") else "every article with a sentence of 40 or more characters", 100 * CAL["L1_top1"]["fresh2"], 100 * 0.562, CAL["line_permille"] / 1000, 100 * fc["at_the_line"]["coverage"], 100 * fc["at_the_line"]["accuracy"], fc["AUROC"], C["answer_l1"], N)
_RC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "specs/rerank_calibration_v1.json"); _R1 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs/pulse/topic_loop/r1/results.json")
if C["rerank"] and os.path.exists(_RC) and os.path.exists(_R1):   # live-trace-v3: the answer is the round-1 re-ranker's; numbers read from its files
    _rc = json.load(open(_RC)); _r1 = json.load(open(_R1))["confirm"]["P1"]
    TOPIC_NOTE = "Topic re-ranker (self-improvement loop round 1, ledger L2751; wired L2756) answers the top-level topic from the landing's 1,059 card scores. Measured on clean MN-DS items from publishers never trained on, by IPTC code: top-level topic right %.1f%% (the landing alone %.1f%%; bar 60%%, so the topic field stays provisional until the owner moves its marker). The answer line is p %.3f (fitted on out-of-fold predictions of MN-DS train publishers); on the dev half it covers %.1f%% at %.1f%% right. This run: %d of %d answered, the rest abstain and go to Learn; the re-ranker names a different top-level topic than the landing alone on %d articles (information only)." % (100 * _r1["top1"]["option"], 100 * _r1["top1"]["landing"], _rc["line_permille"] / 1000, 100 * _rc["dev_select"]["at_line"]["coverage"], 100 * _rc["dev_select"]["at_line"]["accuracy"], C["answer_l1"], C["landed"], C["rr_differs"])
else: TOPIC_NOTE = "Measured elsewhere: the top-level topic is right 56% of the time against human labels (bar 60%). This run has no calibrated confidence (landing-v0)."
stages = [
 {"step": "1. Read", "built": True, "plain": "The article arrives: headline, teaser, and the body when the reader has it.", "rows": [["Articles read", N, 100], ["With body text", C["body"], pct(C["body"])], ["Headline and teaser only", N - C["body"], pct(N - C["body"])]], "note": "Median length %d characters." % (statistics.median(chars) if chars else 0)},
 {"step": "2. Extract", "built": True, "plain": "Tools pull out the facts, each tied to the exact words in the text.", "rows": [["Any stated fact", C["facts_any"], pct(C["facts_any"])], ["Names", C["names"], pct(C["names"])], ["Places linked to a country", C["place"], pct(C["place"])], ["Dates", C["dates"], pct(C["dates"])], ["Amounts", C["amounts"], pct(C["amounts"])], ["Who-did-what statements", C["triples"], pct(C["triples"])]], "note": "Share of articles where each kind was found."},
 {"step": "3. Topic", "built": True, "plain": "The article lands on the IPTC news-topic tree (1,059 topics, 6 levels), by code, with its path up and its neighbours.", "rows": [["Landed", C["landed"], pct(C["landed"])], ["Top 3 candidates agree on the top-level topic", C["agree3"], pct(C["agree3"])]] + ([["Confident (calibrated p at or above the line): answers", C["answer_l1"], pct(C["answer_l1"])]] if C["v1"] else []) + [["Abstained (p below the line)" if C["v1"] else "Weak landing (low score)", C["weak"], pct(C["weak"])], ["Sentences disagree with the article", C["split"], pct(C["split"])]], "note": TOPIC_NOTE},
 {"step": "4. Graph", "built": True, "plain": "Facts, names and topics are joined by ID into one record per article; copies from other publishers are counted once.", "rows": [["Records (one per article)", N, 100], ["Stories, each counted once", INDEP, pct(INDEP)], ["Copies from another publisher", KC["copy"], pct(KC["copy"])], ["Republished by the same publisher", KC["republished"], pct(KC["republished"])], ["Stories carried by 2 or more publishers", MULTI, pct(MULTI)], ["Records whose topic ID is a node of the IPTC tree", sum(x[0] for x in ID), pct(sum(x[0] for x in ID))], ["Records with a place ID (country code)", sum(1 for x in ID if x[1]), pct(sum(1 for x in ID if x[1]))], ["Records with names (as text until Wikidata IDs exist)", sum(1 for x in ID if x[2]), pct(sum(1 for x in ID if x[2]))]],
  "note": ("Copies read from the journal each article carries. " if FROM_J else "Copies recomputed from the stored text with the journal rule (the run has no journal on some or all lines). ") + ("IDs read from the journal on %d of %d lines, from the stage outputs on %d. " % (N - NOJ[0], N, NOJ[0])) + "Topic row = the ID is a node of the IPTC tree and equals the landing stage's (%d mismatches). Most publishers on one story: %d. Titles too short or a column name (matched by body start only): %d. No story key: %d. Counted per run." % (MISM, MAXP, KC["generic_title"], KC["no_key"]) + ("".join(" WARNING: " + w + "." for w in WARN))},
 ledger_stage(),
 {"step": "6. Decide", "built": True, "plain": "For each field the decider answers only when the evidence passes its admission rule; otherwise it abstains.", "rows": [[f, v["answered"], pct(v["answered"])] for f, v in sorted(dec.items())], "note": "Answered share per field (rules verified in Lean)." + (" topic_node = the landing's top-level topic: provisional answer when p reaches the line, otherwise abstain and queue for Learn; the legacy topic field is unchanged." if "topic_node" in dec else "")},
 {"step": "7. Learn", "built": True, "plain": "Weak or disputed articles go to the teacher (Jev), which labels them in IPTC codes; the labels retrain the BitMob models.", "rows": [["Would go to the teacher", C["learn"], pct(C["learn"])], ["In the learn queue (one per story, with topic abstains)", len(LQ), pct(len(LQ))], ["Labelled by the teacher", LC["labelled"] + LC["trained"] + LC["held_out"], pct(LC["labelled"] + LC["trained"] + LC["held_out"])], ["Teacher said none fits", LC["rejected"], pct(LC["rejected"])], ["Used to train the student", LC["trained"], pct(LC["trained"])], ["Held back to score the student", LC["held_out"], pct(LC["held_out"])], ["Still waiting", LC["queued"] + LC["sampled"], pct(LC["queued"] + LC["sampled"])]] + ([["Round 2: relabelled with two codes each (labels, not queue states)", _t2["label_rows"], pct(_t2["label_rows"])]] if _t2 and _s2 else []), "note": LEARN_NOTE}]
QALL = LQM.rows(); QID = {r["id"]: r for r in QALL}; QKEY = {k: r for r in QALL for k in r["keys"]}   # the real queue (all runs): by article id, and by story key for copies
def qstate(l):
    """(state, row, why) from the learn queue itself: queued, sampled, labelled, rejected, trained, held_out, expired; or 'not queued' with the reason read from the line (no learn trigger, or a trigger the queue has not seen yet)"""
    r = QID.get(l["id"])
    if r: return r["state"], r, None
    d = json.load(open("%s/a/%d.json" % (TR, l["seq"])))["text"]; r = next((QKEY[k] for k in LQM.story_ids(l, d) if k in QKEY), None)
    if r: return "copy of a queued story", r, None
    g = set(l.get("gaps") or []); tp = ((l.get("decider") or {}).get("topic_node") or {}).get("outcome", "")
    if {"LANDING_WEAK", "LANDING_SPLIT"} & g or tp.startswith("ABSTAIN"): return "not queued", None, "it has a learn trigger but is not in the queue (run learn_queue.py --enqueue <trace>)"
    return "not queued", None, "no learn trigger: the landing was strong and the sentences agree"
SRC = {l["seq"]: l["source"] for l in lines}; plur = lambda n, w: "%d %s%s" % (n, w, "" if n == 1 else "s")
def graph_line(l, best):
    k, o, n = DUP[l["seq"]]; t, p, nm, _ = ids(l); story = "the first item of its story in this run" if o is None else "%s of #%d (%s)" % ("a copy" if k == "copy" else "a republish", o, SRC.get(o, "?"))
    return "One record under article #%d: topic %s, %s, %s (as text). Story: %s, carried by %s so far." % (l["seq"], best, plur(p, "place code"), plur(nm, "name"), story, plur(n, "publisher"))
def ledger_walk(seq, l2n):
    ev = EV.get(seq)
    if ev is None: return "A copy of a story already counted: adds nothing to the ledger."
    if not ev: return "Reaches no resource through the engine's topic links (level-2 topic: %s)." % l2n
    return "Counted once. Adds to %d resource%s: %s. (Resource ledger v0, draft; links are the engine's guess.)" % (len(ev), "" if len(ev) == 1 else "s", "; ".join("%s %+.2f%s" % (RNAME[r], tk + sg, " (a condition with a direction)" if sg else " (talked about)") for r, tk, sg in ev[:4]) + (" and %d more" % (len(ev) - 4) if len(ev) > 4 else ""))
def learn_walk(l, why):
    s, r, nq = qstate(l); trig = " and ".join(why) or "a topic abstain"
    if s == "not queued": return "Queue state: not queued (%s)." % nq
    if s == "copy of a queued story": return "Queue state: not queued itself; a copy of a story already queued (article #%d, state %s). Counted on the root, never a second teacher read." % (r["seq"], r["state"])
    x = {"queued": "waiting for a teacher round (trigger: %s)" % trig, "sampled": "picked for round %s, split %s, not yet labelled" % (r.get("round"), r.get("split")), "labelled": "labelled by the teacher with %s (level 2 %s), not yet used to train" % (r.get("l1_code"), r.get("l2_code") or "none"),
         "rejected": "the teacher gave no usable label (%s), stays out of training" % r.get("reject_reason"), "trained": "labelled by the teacher with %s and used to train the student (round %s)" % (r.get("l1_code"), r.get("student_round")), "held_out": "labelled by the teacher, held back to score the student, never trained", "expired": "expired: the IPTC release changed"}.get(s, s)
    return "Queue state: %s, %s." % (s, x)
def walk(l):
    d = json.load(open("%s/a/%d.json" % (TR, l["seq"]))); sf = d["stages_full"]; o = st(l, "topic_landing")["out"]; g = set(l["gaps"])
    fi = (sf.get("facts") or {}).get("items") or []; names = [x["text"] for x in fi if x["kind"] == "name" and x["status"] == "stated"][:6]
    trip = [" ".join(map(str, x["value"])) for x in fi if x["kind"] == "triple" and isinstance(x.get("value"), list)][:2]
    pl = [x["text"] + " → " + x["country"] for x in (sf.get("place_linker") or {}).get("items", []) if x.get("country")][:4]
    best = (o.get("rerank") or {}).get("node") or o["best"]["qcode"]; path = " › ".join(lab(q) for q in P.chain(best)); top3 = ", ".join(lab(q) for q, _ in o["top3"])
    vote = ", ".join("%s (%d)" % (lab(q), n) for q, n in o["vote"]) or ("not run (the 3 best cards agree)" if o.get("voted") is False and o.get("n_sent") else "none (short text)"); learn = ("LANDING_WEAK" in g) or ("LANDING_SPLIT" in g)
    why = [w for w, k in (("weak landing", "LANDING_WEAK"), ("sentences disagree", "LANDING_SPLIT")) if k in g]
    decs = "; ".join("%s: %s" % (k, v["outcome"].replace("_", " ").lower()) for k, v in l["decider"].items())
    ch = P.chain(best); l2n = lab(ch[1]) if len(ch) > 1 else lab(ch[0])
    return {"seq": l["seq"], "title": l.get("title") or "", "source": l["source"], "excerpt": d["text"][:420], "steps": [
        ["1. Read", "%d characters%s." % (l["input"]["chars"], ", with body" if l["input"]["has_body"] else ", headline and teaser only")],
        ["2. Extract", "Names: %s. Places: %s. Statements: %s." % (", ".join(names) or "none", ", ".join(pl) or "none", "; ".join(trip) or "none")],
        ["3. Topic", "%s on %s (%s). Landing candidates: %s. Sentence vote: %s. %s%s" % ("Re-ranker answers (p %s; landing alone said %s)" % (o.get("p"), lab(o.get("landing_l1_code"))) if o.get("rerank") else "Lands", path, best, top3, vote, "All 3 candidates agree on the top level." if o["l1_agree3"] == 3 else "Candidates disagree on the top level.", "")],
        ["4. Graph", graph_line(l, "%s (%s)" % (lab(best), best))],
        ["5. World state", ledger_walk(l["seq"], l2n)],
        ["6. Decide", decs + "."],
        ["7. Learn", learn_walk(l, why)]]}
def pick(ok):
    c = [l for l in lines if ok(l)]; c.sort(key=lambda l: abs(l["input"]["chars"] - 1200)); return c[0] if c else None
clean = pick(lambda l: l["input"]["has_body"] and st(l, "topic_landing").get("out", {}).get("l1_agree3") == 3 and not ({"LANDING_WEAK", "LANDING_SPLIT"} & set(l["gaps"])) and (st(l, "place_linker").get("out") or {}).get("linked") and (st(l, "facts").get("out") or {}).get("stated", 0) >= 3)
learn = pick(lambda l: l["input"]["has_body"] and {"LANDING_WEAK", "LANDING_SPLIT"} <= set(l["gaps"]))
out = {"as_of": {"run_id": run.get("run_id"), "state": run.get("state"), "traced": N, "label_version": run.get("label_version"), "built_at": time.strftime("%Y-%m-%d %H:%M:%S")},
       "warnings": WARN, "stages": stages, "top_level": [[lab(k), v, pct(v)] for k, v in l1.most_common()], "examples": [walk(x) for x in (clean, learn) if x]}
json.dump(out, open(TR + "/funnel.json", "w"), indent=1); import scoreboard as SB; json.dump({"built_at": out["as_of"]["built_at"], "run_id": run.get("run_id"), "rows": SB.build(TR)}, open(TR + "/scoreboard.json", "w"), indent=1); [print("WARNING:", w, file=sys.stderr) for w in WARN]; print(N, "articles;", [s["step"] for s in stages], "examples", [e["seq"] for e in out["examples"]])
