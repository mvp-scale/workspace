"""live_gaps: per-article gap codes and the run.json aggregates for the live trace (schema live_trace_schema.json, T160).
Pure functions over article_line dicts (parsed). No accuracy column anywhere: a gap is a place where the chain did not produce, or two tools disagree, never a score.
Thresholds below are ours (first guesses), printed on the page next to each code; they can be changed only with a new schema version."""
import math
GAP_CODES = ["TEASER_ONLY", "WINDOW_CUT", "FACTS_ZERO", "UNBOUND_HIGH", "QUARANTINED", "INDEPENDENT_LOW", "BUNDLE_NO_SIZE", "CHANGE_NO_CONDITION", "TOPIC_DISAGREE", "LANDING_SPLIT", "LANDING_WEAK", "RERANK_DISAGREE", "SYNDICATED", "PLACE_DISAGREE", "UNPLACED_HIGH", "DECIDER_ABSTAIN", "OVER_BUDGET", "STAGE_ERROR", "NOT_ATTACHED"]
RULES = {"TEASER_ONLY": "no extracted body: the chain read title + teaser",
         "WINDOW_CUT": "the v6b encoder saw less than 100% of the body (window cap)",
         "FACTS_ZERO": "the fact finder produced no fact",
         "UNBOUND_HIGH": "at least 8 facts and more than half are unbound or invalid",
         "QUARANTINED": "a fact or span failed the span-matches-text check and was held back",
         "INDEPENDENT_LOW": "the independent counter sees at least 3 amount or date runs and the facts found less than half of them as stated",
         "BUNDLE_NO_SIZE": "change bundles exist but none carries a stated size",
         "CHANGE_NO_CONDITION": "change-lexicon bundles exist but the condition head does not say a condition is present",
         "TOPIC_DISAGREE": "reference: the topic landing's IPTC level-1 code differs from the Domain roll-up top (the roll-up is the legacy 49-to-17 map); v1 traces: the pack's level-1 guess vs the roll-up",
         "LANDING_SPLIT": "the article's landing level-1 code differs from the sentence vote's top level-1 code (the vote has at least 3 sentences)",
         "LANDING_WEAK": "v0: the landing's best cosine is under 0.58 (bottom quarter of scores in run A); v1: the landing's decision is ABSTAIN; v3: the re-ranker's calibrated p is under its line (the decision is the re-ranker's)",
         "RERANK_DISAGREE": "informational (live-trace-v3): the topic re-ranker's level-1 code differs from the landing's own level-1 code (the re-ranker's is the answer; the landing's stays as evidence)",
         "SYNDICATED": "the journal says this story key (title or first 300 characters) was already traced in this run: from another publisher (copy) or the same one again (republished)",
         "PLACE_DISAGREE": "Place student (answered, not GLOBAL) maps to a different region than the place linker's top country",
         "UNPLACED_HIGH": "the pack placed under half of at least 10 noun terms",
         "DECIDER_ABSTAIN": "the decider abstained on story_type or topic",
         "OVER_BUDGET": "total_ms above the p90 budget",
         "STAGE_ERROR": "a stage ended in error or timeout",
         "NOT_ATTACHED": "four stages have no model (function_sentence, novelty, time, factuality_story); live-trace-v4 stages that are off by their flag do not count"}
def _st(line): return {s["name"]: s for s in line.get("stages", [])}
def _o(s): return (s.get("out") if s and isinstance(s.get("out"), dict) else {}) or {}
def per_article_gaps(line):
    if line.get("state") != "traced": return []
    g = []; S = _st(line); inp = line.get("input", {})
    if not inp.get("has_body"): g.append("TEASER_ONLY")
    pr = (inp.get("pct_read_per_model") or {}).get("v6b_windows")
    if pr is not None and pr < 100: g.append("WINDOW_CUT")
    f = S.get("facts"); fo = _o(f)
    if f and f["state"] in ("ran", "empty"):
        n = f.get("n") or 0
        if n == 0: g.append("FACTS_ZERO")
        elif n >= 8 and (fo.get("unbound", 0) + fo.get("invalid", 0)) * 2 > n: g.append("UNBOUND_HIGH")
    if any(_o(s).get("quarantined", 0) for s in S.values() if s["name"] in ("facts", "span_rules")): g.append("QUARANTINED")
    i = S.get("independent_counter"); io = _o(i)
    if i and i["state"] in ("ran", "empty"):
        ind = io.get("amount", 0) + io.get("date", 0); st = fo.get("stated_amount", 0) + fo.get("stated_date", 0)
        if ind >= 3 and st * 2 < ind: g.append("INDEPENDENT_LOW")
    b = S.get("tags_bundles"); bo = _o(b)
    if b and b["state"] == "ran" and bo.get("bundles", 0) > 0:
        if bo.get("with_size", 0) == 0: g.append("BUNDLE_NO_SIZE")
        c = S.get("condition")
        if c and c["state"] in ("ran", "abstain") and _o(c).get("present") is not True: g.append("CHANGE_NO_CONDITION")
    p = S.get("structure_pack"); d = S.get("domain_rollup"); L = S.get("topic_landing")
    if L:   # live-trace-v2 lines; v1 lines (no landing stage) keep the old pack-guess rule below
        if L["state"] in ("ran", "abstain"):
            lo = _o(L); vt = lo.get("vote") or []
            if lo.get("agrees_rollup") is False: g.append("TOPIC_DISAGREE")
            if (lo.get("n_sent") or 0) >= 3 and vt and vt[0][0] != lo.get("l1_code"): g.append("LANDING_SPLIT")
            if lo.get("landing_l1_code") and lo["landing_l1_code"] != lo.get("l1_code"): g.append("RERANK_DISAGREE")
            if lo.get("decision") in ("ANSWER_L1", "ABSTAIN"):
                if lo["decision"] == "ABSTAIN": g.append("LANDING_WEAK")
            elif ((lo.get("best") or {}).get("score") or 1) < 0.58: g.append("LANDING_WEAK")
    elif p and d and p["state"] == "ran" and d["state"] == "ran":
        gl = _o(p).get("l1_guess"); dt = (_o(d).get("top") or [[None]])[0][0]
        if gl and dt and gl != dt: g.append("TOPIC_DISAGREE")
    if ((line.get("journal") or {}).get("dup") or {}).get("kind") in ("copy", "republished"): g.append("SYNDICATED")   # journal.py; v2 lines without a journal never fire it
    ps = S.get("place_student"); pl = S.get("place_linker")
    if ps and pl and ps["state"] == "ran" and pl["state"] == "ran":
        a = _o(ps).get("top1"); r = _o(pl).get("region")
        if a and r and a != "GLOBAL" and a != r: g.append("PLACE_DISAGREE")
    if p and p["state"] == "ran":
        o = _o(p)
        if o.get("n_terms", 0) >= 10 and o.get("n_placed", 0) * 2 < o["n_terms"]: g.append("UNPLACED_HIGH")
    dec = line.get("decider") or {}
    if isinstance(dec, dict) and any(str((dec.get(k) or {}).get("outcome", "")).startswith("ABSTAIN") for k in ("story_type", "topic")): g.append("DECIDER_ABSTAIN")
    if line.get("over_budget"): g.append("OVER_BUDGET")
    if any(s["state"] in ("error", "timeout") for s in line.get("stages", [])): g.append("STAGE_ERROR")
    if any(s["state"] == "not_attached" and s["name"] not in V4_STAGES for s in line.get("stages", [])): g.append("NOT_ATTACHED")   # live-trace-v4: a v4 stage that is off by its flag is a choice, not a gap
    return g
def _pct(v, q):
    if not v: return None
    s = sorted(v); return round(s[min(len(s) - 1, int(math.ceil(q * len(s))) - 1)], 2)
STATES = ("ran", "empty", "abstain", "error", "timeout", "not_attached")
V4_STAGES = ("journal_durable", "ner_fewnerd", "claims_v1", "identity_g4", "contradictions")   # live_trace_v4.STAGE; NOT_ATTACHED ignores them (a flag that is off is not a gap)
def journal_block(tr, lab=None):
    """run.json journal block from the lines alone (None when no line carries a journal). A story = a root item (first, generic_title, no_key) plus the copies and republished items that point at it; independent items = stories; publishers = distinct sources over a story's items."""
    js = [(l, l["journal"]) for l in tr if ((l.get("journal") or {}).get("dup") or {}).get("kind")]
    if not js: return None
    kc = {k: 0 for k in ("first", "copy", "republished", "generic_title", "no_key")}; st = {}
    for l, j in js:
        k = j["dup"]["kind"]; kc[k] = kc.get(k, 0) + 1; o = j["dup"].get("of_seq")
        root = o if k in ("copy", "republished") and o is not None else l["seq"]; e = st.setdefault(root, {"src": set(), "l2": None}); e["src"].add(l["source"])
        if root == l["seq"]: e["l2"] = ((j.get("ids") or {}).get("topic") or {}).get("l2")
    nd = {}
    for e in st.values():
        if e["l2"]: n = nd.setdefault(e["l2"], {"items": 0, "src": set()}); n["items"] += 1; n["src"] |= e["src"]
    rows = sorted(({"code": c, "label": lab(c) if lab else c, "items": n["items"], "publishers": len(n["src"])} for c, n in nd.items()), key=lambda r: (-r["items"], r["code"]))[:50]
    return {"records": len(js), **kc, "independent_items": len(st), "multi_publisher_stories": sum(1 for e in st.values() if len(e["src"]) > 1), "max_publishers": max(len(e["src"]) for e in st.values()), "no_l2_items": sum(1 for e in st.values() if not e["l2"]), "l2_nodes": rows}
def aggregate(lines, lab=None):
    """lines: parsed article_lines (traced and skipped). Returns the run.json parts: stages, decider, gaps, total p50/p90, journal (None before step 3 lines). lab: code -> label for the journal's level-2 rows."""
    tr = [l for l in lines if l.get("state") == "traced"]; stages = {}; ms = {}; dec = {}; gc = {}; ex = {}
    for l in tr:
        for s in l["stages"]:
            r = stages.setdefault(s["name"], {k: 0 for k in STATES}); r[s["state"]] = r.get(s["state"], 0) + 1
            if s["state"] != "not_attached": ms.setdefault(s["name"], []).append(s["ms"])
        for k, v in (l.get("decider") or {}).items():
            if isinstance(v, dict): dec.setdefault(k, {}); dec[k][v["outcome"]] = dec[k].get(v["outcome"], 0) + 1
        for c in l.get("gaps", []):
            gc[c] = gc.get(c, 0) + 1; e = ex.setdefault(c, [])
            if len(e) < 5: e.append(l["seq"])
    for n, r in stages.items(): r["p50_ms"] = _pct(ms.get(n, []), .5); r["p90_ms"] = _pct(ms.get(n, []), .9)
    N = len(tr); gaps = sorted(({"code": c, "count": n, "rate": round(n / N, 4), "examples": ex[c]} for c, n in gc.items()), key=lambda x: (-x["rate"], x["code"]))
    tot = [l["total_ms"] for l in tr]
    return {"stages": stages, "decider": dec, "gaps": gaps, "total_p50_ms": _pct(tot, .5), "total_p90_ms": _pct(tot, .9), "over_budget_n": sum(1 for l in tr if l.get("over_budget")), "journal": journal_block(tr, lab)}
