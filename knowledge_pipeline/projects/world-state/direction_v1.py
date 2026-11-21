"""direction v1 (T173, owner yes L2870): up/down read from a claim of claims v1. Rules only, no training, no SENTiVENT in any fit (its LICENCE.txt: internal scoring only, T96 L1727); it is the holdout.
Rule per claim (claims-v1.py extract output, read-only):
  1 verb class  the predicate's words are matched against the direction_gate.py lexicon (UP 62 / DOWN 55 words, L951, parsed from that file read-only), a nominal change word in the object phrase ('a 3.1 % rise in traffic') is the second source
  2 negated     a negated claim abstains (direction unknown, reason negated): 'did not fall 5 %' says nothing about up
  3 attributed  attributed_to / said_by is kept, never flipped: 'X said sales fell' still reads down, flagged attributed
  4 amount      the first number, percent or money in the object phrase or its attributes; has_amount is reported, not required
  5 mixed       both classes in one claim = unknown
Links (read-only): the claim subject and object text is matched to a condition name of specs/iptc_condition_v0.json (every word stem of the name present) and to a resource name of resources.csv; effect = up_means for up, the opposite for down.
Wire (integrator): direction_v1.read_claims(claims) -> [{"i","direction","evidence","amount","negated","attributed_to","conditions","resources","provisional"}]; direction_v1.read_text(text, nlp) runs claims-v1 first; direction_v1.story_direction(rows) -> 'up'|'down'|'unknown'. Every row carries provisional=PROVISIONAL until runs/pulse/t173-direction/t173_direction.json says the bar (accuracy >= 0.80 on the SENTiVENT holdout) is met.
    /workspace/models/embed-zs/.venv/bin/python direction_v1.py [sentivent|runs-v7|all]   (from projects/world-state)"""
import ast, csv, importlib.util, json, pathlib, re, sys
H0 = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(H0))
BAR = 0.80; PROVISIONAL = True   # set False by the integrator only after the score file shows the bar met
def _lex():
    t = ast.parse((H0 / "direction_gate.py").read_text(encoding="utf-8")); d = {}
    for n in t.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id in ("UP", "DOWN"): d[n.targets[0].id] = ast.literal_eval(n.value)
    return re.compile(d["UP"], re.I), re.compile(d["DOWN"], re.I)
UP, DOWN = _lex()
_AMT = re.compile(r"(?:[$€£]\s?)?\d[\d,.]*\s?(?:%|percent|per cent|billion|million|thousand|bn|m\b)?|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|hundred|dozens?)\s+(?:percent|million|billion|thousand)\b", re.I)
_V1 = None
def v1():
    global _V1
    if _V1 is None:
        sp = importlib.util.spec_from_file_location("claims_v1", str(H0 / "claims-v1.py")); _V1 = importlib.util.module_from_spec(sp); sp.loader.exec_module(_V1)
    return _V1
def _stem(w): return w[:5]
def _links():
    cs = json.load(open(H0 / "specs/iptc_condition_v0.json", encoding="utf-8"))["rows"]
    rs = list(csv.DictReader(open("/workspace/probes/persona/rules_v2/resources.csv", encoding="utf-8")))
    ST = {"and", "the", "of", "in", "for", "from"}
    cond = [(r["condition"], {_stem(w) for w in re.findall(r"[a-z]+", r["name"].lower()) if w not in ST}, r["resource"], r["up_means"]) for r in cs]
    res = [(r["id"], {_stem(w) for w in re.findall(r"[a-z]+", r["name"].lower()) if w not in ST}) for r in rs]
    return cond, res
COND, RES = _links()
OPP = {"strain": "relief", "build": "erode"}
def _words(t): return {_stem(w) for w in re.findall(r"[a-z]+", (t or "").lower())}
def link(claim):
    ws = _words((claim.get("s") or "") + " " + (claim.get("o") or ""))
    return [c for c in COND if c[1] and c[1] <= ws], [r[0] for r in RES if r[1] and r[1] <= ws]
def _cls(text):
    text = IDIOM.sub(" ", text or "")
    u = len(UP.findall(text or "")); d = len(DOWN.findall(text or "")); return ("up" if u > d else "down" if d > u else None) if (u or d) else None, (u, d)
def read_claim(c, i=0):
    ev = None; dr = None
    d, (u, dn) = _cls(c.get("p"))
    if d: dr, ev = d, "predicate"
    elif u == dn and u:   # tie inside the predicate
        dr, ev = None, "mixed"
    if dr is None and ev is None:
        d, (u, dn) = _cls(c.get("o"))
        if d: dr, ev = d, "object"
    text_o = (c.get("o") or "") + " " + " ".join(a.get("text", "") for a in c.get("attrs", []))
    m = _AMT.search(text_o); amount = m.group(0).strip() if m else None
    if amount is not None and YEAR.fullmatch(amount): amount = None   # a year is not an amount (T158 DIRECTION)
    if amount is not None and not re.search(r"\d|one|two|three|four|five|six|seven|eight|nine|ten|hundred|dozen", amount, re.I): amount = None
    neg = bool(c.get("neg")); att = c.get("attrib") or c.get("said_by")
    if neg and dr: dr, ev = None, "negated"
    cond, res = link(c)
    return {"i": i, "direction": dr or "unknown", "evidence": ev, "amount": amount, "negated": neg, "attributed_to": att, "claim": {"s": c.get("s"), "p": c.get("p"), "o": c.get("o")},
            "conditions": [{"condition": k, "resource": r, "effect": (um if dr == "up" else OPP[um]) if dr else None} for k, _, r, um in cond], "resources": res, "provisional": "PROVISIONAL" if PROVISIONAL else "met"}
def read_claims(claims): return [read_claim(c, i) for i, c in enumerate(claims)]
def read_text(text, nlp): return read_claims(v1().extract(text, nlp))
def story_direction(rows):
    u = sum(1 for r in rows if r["direction"] == "up"); d = sum(1 for r in rows if r["direction"] == "down")
    return "up" if u > d else "down" if d > u else "unknown"

# ---- T158 DIRECTION widening (add-only): non-change senses, extra words, particle up/down, comparators, from->to pair
IDIOM = re.compile(r"\b(?:fall(?:s|ing)?\s+(?:under|into|within|outside|short|behind|apart|victim|prey|asleep|in love|back on|out)|rais(?:e|es|ed|ing)\s+(?:questions?|concerns?|eyebrows?|awareness|doubts?|alarm|issues?|the question|the possibility)|rise\s+to\s+the\s+occasion|(?:the|this|last|next)\s+fall\b|in\s+the\s+fall\b|cut\s+(?:off|out|across)|cut\s+and\s+dried|lower\s+(?:house|court|chamber|level)s?|rising\s+star|growth\s+(?:stock|fund|investor)s?)", re.I)
YEAR = re.compile(r"(?:19|20)\d\d")
WN_UP = r"grown|doubl(?:e|ed|es|ing)|adding\s+(?:\$\s?)?\d[\d,.]*\s+(?:points?|cents?|%)|escalation|expansion|intensification|upswing|upturn|rall(?:y|ies|ied|ying)|rocket(?:s|ed|ing)?|skyrocket(?:s|ed|ing)?|advanc(?:e|ed|es|ing)|flown|flew|ran up|run up|ahead of"
WN_DOWN = r"shrinkage|declination|downturn|downswing|shed(?:s|ding)?|slip(?:s|ped|ping)?|crumbl(?:e|ed|es|ing)|sold off|sell-?off|retreat(?:s|ed|ing)?|dip(?:s|ped|ping)?|sag(?:s|ged|ging)?|eroded?|erodes|erasing|erased|lost|loses|losing|loss(?:es)?|pared?|weaker|weakness|ceded|below"
_X_UP = re.compile(r"\b(?:" + WN_UP + r")\b", re.I); _X_DN = re.compile(r"\b(?:" + WN_DOWN + r")\b", re.I)
_NUM = r"(?:[$\u20ac\u00a3]\s?)?\d[\d,]*(?:\.\d+)?"
_QUAL = r"(?:about|nearly|almost|approximately|roughly|more than|less than|as much as|as little as|over|around|just|some|only|a)\s+"
_PART = re.compile(r"\b(up|down|off|higher|lower)\s+(?:" + _QUAL + r")?(?:" + _NUM + r")\s?(?:%|percent|per cent|points?|cents?|basis points|bps|billion|million|thousand|bn|pts)", re.I)
_PART2 = re.compile(r"\b(?:closed|ended|finished|trading|traded|trades|stock is|stock was|shares? (?:are|were|is|was)|is|are|was|were|still|now|again|been|being|\bwas)\s+(?:still\s+)?(up|down)\b(?!\s+(?:to|for|on|in|with|and\s+running|the\s+(?:road|line|street|drain|hall)))", re.I)
_PART3 = re.compile(r"\b(up|down)\s+(?:year[- ]to[- ]date|year[- ]over[- ]year|y-o-y|year over year|so far|this year|for the year|on the (?:day|year|week)|ytd|YTD)", re.I)
_FROM = re.compile(r"\b(up|down|rose|fell|climbed|dropped|slipped)\s+from\b", re.I)
_PAIR = re.compile(r"\bfrom\s+(?:" + _QUAL + r")?(" + _NUM + r")\s?(%|percent|billion|million|thousand|bn)?\s+(?:to|at)\s+(?:" + _QUAL + r")?(" + _NUM + r")\s?(%|percent|billion|million|thousand|bn)?(?!\s?[ap]\.?m)", re.I)
_PAIR2 = re.compile(r"\bto\s+(" + _NUM + r")\s?(%|percent|billion|million|thousand|bn)?\s*,?\s+from\s+(" + _NUM + r")", re.I)
_ABV = re.compile(r"\b(above|below)\s+(?:the\s+|its\s+|a\s+)?(?:[\w.\-$']+\s+){0,3}?(?:record|high|low|close|level|\d)", re.I)
def _f(x): return float(re.sub(r"[^\d.]", "", x) or "nan")
def ext_cls(text):
    """sentence-level fallback after the claim rules: returns (direction|None, evidence list). Counts votes, ties abstain."""
    t = IDIOM.sub(" ", re.sub(r"\s+", " ", text or "")); v = {"up": 0, "down": 0}; ev = []
    v["up"] += len(UP.findall(t)); v["down"] += len(DOWN.findall(t))
    for m in _X_UP.finditer(t): v["up"] += 1; ev.append(("word", m.group(0)))
    for m in _X_DN.finditer(t):
        if m.group(0).lower() == "below" and _ABV.search(t): continue
        v["down"] += 1; ev.append(("word", m.group(0)))
    for rx in (_PART,):
        for m in rx.finditer(t): d = "up" if m.group(1).lower() in ("up", "higher") else "down"; v[d] += 1; ev.append(("particle", m.group(0)))
    for rx in (_PART2, _PART3):
        for m in rx.finditer(t): d = "up" if m.group(1).lower() == "up" else "down"; v[d] += 1; ev.append(("particle", m.group(0)))
    for m in _ABV.finditer(t): d = "up" if m.group(1).lower() == "above" else "down"; v[d] += 1; ev.append(("comparative", m.group(0)))
    for m in _PAIR.finditer(t):
        a, b = _f(m.group(1)), _f(m.group(3))
        if a == a and b == b and a != b: v["up" if b > a else "down"] += 1; ev.append(("from_to", m.group(0)))
    for m in _PAIR2.finditer(t):
        b, a = _f(m.group(1)), _f(m.group(3))
        if a == a and b == b and a != b: v["up" if b > a else "down"] += 1; ev.append(("to_from", m.group(0)))
    d = "up" if v["up"] > v["down"] else "down" if v["down"] > v["up"] else None
    return d, ev
def read_story(text, claims_rows):
    """claim rows first (unchanged v1); if the story is still unknown, the sentence-level extension decides. Returns (direction, evidence)."""
    d = story_direction(claims_rows)
    if d != "unknown": return d, "claims"
    if any(r.get("evidence") == "negated" for r in claims_rows): return "unknown", "negated"
    d2, ev = ext_cls(text)
    return (d2 or "unknown"), ("sentence_ext" if d2 else None)

# ---- scoring (SENTiVENT holdout, runs-v7 fire rate)
def _nlp():
    import spacy; return spacy.load("en_core_web_lg", exclude=["ner"])
def sentivent():
    A = pathlib.Path("/workspace/data/anchors/sentivent/data/sentivent_unified_sentence"); out = []
    for sp in ("train", "validation", "test"):
        for l in open(A / f"{sp}.jsonl"):
            r = json.loads(l); dirs = set(); items = []
            for a in r["annotations"]:
                if a.get("kind") != "event": continue
                for x in a["participants"] + a["fillers"]:
                    ro = x["role"]
                    if ro.startswith("IncreaseAmount") or ro.startswith("DecreaseAmount"):
                        dirs.add("up" if ro.startswith("Inc") else "down"); items.append({"trig": a["span"]["chars"][0], "amount": x["text"], "ach": x["span"]["chars"][0], "neg": a.get("negated"), "mod": a.get("modality"), "realis": a.get("realis"), "dir": "up" if ro.startswith("Inc") else "down"})
            if items: out.append({"id": r["id"], "split": sp, "text": r["text"], "items": items, "mixed": len(dirs) > 1, "dir": next(iter(dirs)) if len(dirs) == 1 else None})
    return out
def gate_read(t, lead=1):
    """direction_gate.py read() reproduced (that file runs its scoring on import): change words in the first 600 characters, one side must lead"""
    t = re.sub(r"\s+", " ", t)[:600]; u = len(UP.findall(t)); d = len(DOWN.findall(t)); return "up" if u - d >= lead else "down" if d - u >= lead else "unknown"
def prf(rows, key_t, key_p):
    res = {}
    for c in ("up", "down"):
        tp = sum(1 for r in rows if r[key_t] == c and r[key_p] == c); pp = sum(1 for r in rows if r[key_p] == c); rl = sum(1 for r in rows if r[key_t] == c)
        res[c] = {"real": rl, "predicted": pp, "precision": round(tp / pp, 3) if pp else None, "recall": round(tp / rl, 3) if rl else None}
    return res
def score(rows, key_p):
    ans = [r for r in rows if r[key_p] != "unknown"]; ok = sum(1 for r in ans if r[key_p] == r["truth"])
    return {"items": len(rows), "answered": len(ans), "coverage": round(len(ans) / len(rows), 3), "accuracy_over_answered": round(ok / max(len(ans), 1), 3), "accuracy_over_all_abstain_is_miss": round(ok / len(rows), 3), "per_class": prf(rows, "truth", key_p)}
def run_sentivent(out, subset=None):
    """subset None = all 263 as in T173; 'select' / 'confirm' = the T158 by-document halves (runs/pulse/t173-direction/t158_split.json)"""
    nlp = _nlp()
    S = sentivent(); rows = []; mixed = 0
    if subset:
        sp = json.load(open(out / "t158_split.json")); keep = set(sp[subset + "_docs"]); S = [x for x in S if x["id"].split("_s")[0] in keep]
    for s in S:
        if s["mixed"]: mixed += 1; continue
        claims = v1().extract(s["text"], nlp); rr = read_claims(claims)
        blind = story_direction(rr)
        # located: claim whose verb span is within 12 chars of a gold trigger, else whose object holds the gold amount
        loc = "unknown"
        for it in s["items"]:
            lo, hi = it["trig"]; cand = [x for x, c in zip(rr, claims) if c.get("v_span") and c["v_span"][0] <= hi + 12 and c["v_span"][1] >= lo - 12]
            cand = cand or [x for x, c in zip(rr, claims) if it["amount"] and it["amount"].lower() in (c.get("o") or "").lower()]
            d = story_direction(cand)
            if d != "unknown": loc = d; break
        gate = gate_read(s["text"], 1); ext, ext_ev = read_story(s["text"], rr)
        rows.append({"ext": ext, "ext_evidence": ext_ev, "id": s["id"], "split": s["split"], "text": s["text"], "truth": s["dir"], "blind": blind, "located": loc, "gate": gate, "n_claims": len(claims), "negated_any": any(r["negated"] for r in rr), "attributed_any": any(r["attributed_to"] for r in rr)})
    res = {"holdout": "SENTiVENT all splits, sentences with IncreaseAmount*/DecreaseAmount* roles, single-direction sentences; never trained on", "sentences_total_with_role": len(S), "mixed_direction_sentences_excluded": mixed, "items": len(rows), "share_up": round(sum(1 for r in rows if r["truth"] == "up") / len(rows), 3),
           "direction_v1_blind_sentence_level": score(rows, "blind"), "direction_v1_located_by_gold_trigger_or_amount": score(rows, "located"), "direction_gate_py_same_items_lead1": score(rows, "gate"), "direction_v1_ext_T158": score(rows, "ext"),
           "always_up_baseline_accuracy": round(sum(1 for r in rows if r["truth"] == "up") / len(rows), 3)}
    b = res["direction_v1_ext_T158"] if subset else res["direction_v1_blind_sentence_level"]; res["bar"] = {"accuracy_over_answered_min": BAR, "met": b["accuracy_over_answered"] >= BAR, "met_over_all_items": b["accuracy_over_all_abstain_is_miss"] >= BAR}
    res["status"] = "PROVISIONAL" if not res["bar"]["met"] else "bar met on answered items only; accuracy over all items (abstain = miss) is " + str(b["accuracy_over_all_abstain_is_miss"]) + " against always-up " + str(res["always_up_baseline_accuracy"]) + ", so PROVISIONAL stays on until the integrator decides"
    with open(out / ("t158_%s_items.jsonl" % subset if subset else "t173_sentivent_items.jsonl"), "w") as f:
        for r in rows: f.write(json.dumps(r) + "\n")
    return res
def run_v7(out):
    nlp = _nlp(); d = pathlib.Path("/workspace/demo/mockups/structure-live/runs-v7/trace/a"); fires = amt = both = lk = 0; n = 0; byd = {"up": 0, "down": 0}; ex = []; fx = 0; ext_ev = {}; exx = []
    for f in sorted(d.glob("*.json"), key=lambda p: int(p.stem)):
        t = json.load(open(f))["text"]; n += 1; rr = read_text(t, nlp); fired = [r for r in rr if r["direction"] != "unknown"]
        dx, evx = read_story(t, rr)
        if dx != "unknown": fx += 1; ext_ev[evx] = ext_ev.get(evx, 0) + 1
        if dx != "unknown" and evx == "sentence_ext" and len(exx) < 12: exx.append({"file": f.name, "direction": dx, "evidence": ext_cls(t)[1][:3]})
        if fired: fires += 1; byd[story_direction(fired)] = byd.get(story_direction(fired), 0) + 1
        if any(r["amount"] for r in fired): amt += 1
        if any(r["conditions"] for r in fired): lk += 1
        if fired and len(ex) < 12: ex.append({"file": f.name, **{k: fired[0][k] for k in ("direction", "evidence", "amount", "claim", "attributed_to")}})
    return {"articles": n, "fires_any_direction": fires, "fire_rate": round(fires / n, 4), "fires_with_ext_T158_any_evidence": fx, "fire_rate_with_ext_T158": round(fx / n, 4), "ext_evidence_counts": ext_ev, "ext_only_examples": exx, "fires_with_amount": amt, "fire_rate_with_amount": round(amt / n, 4), "fires_and_linked_to_condition": lk, "story_direction_counts": byd, "condition_head_reference": "108/3600 = 0.03 (task text, not re-measured here)", "examples": ex}
if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"; out = H0 / "runs/pulse/t173-direction"; out.mkdir(parents=True, exist_ok=True); res = {"script": "direction_v1.py", "provisional": PROVISIONAL}
    if what in ("select", "confirm"):
        res["subset"] = what; res["sentivent"] = run_sentivent(out, what); json.dump(res, open(out / ("t158_direction_%s.json" % what), "w"), indent=1); print(json.dumps(res["sentivent"]["direction_v1_ext_T158"], indent=1)); print(json.dumps(res["sentivent"]["direction_v1_blind_sentence_level"])[:300]); sys.exit(0)
    if what in ("sentivent", "all"): res["sentivent"] = run_sentivent(out)
    if what in ("runs-v7", "all"): res["runs_v7"] = run_v7(out)
    json.dump(res, open(out / "t173_direction.json", "w"), indent=1); print(json.dumps({k: v for k, v in res.items()}, indent=1)[:4000])
