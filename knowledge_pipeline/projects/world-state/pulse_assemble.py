"""Assemble the pulse answers for the mock-up articles directly from gate evidence, by explicit rules, showing the arithmetic and the evidence spans (pre-registered L962). No trained model is used for the answers; the trained G3 answer is shown only as a cross-check.
    python3 pulse_assemble.py   (from projects/world-state)"""
import json, re, collections
DATA = "/workspace/demo/mockups/gates/data.json"; D = json.load(open(DATA)); V = json.load(open("runs/pulse/wide_vocab.json")); DOMNAME = {d["id"]: d["name"] for d in V["domains"]}
UP = r"\b(?:ris(?:e|es|ing|en)|rose|rais(?:e|ed|es|ing)|increas(?:e|ed|es|ing)|surg(?:e|ed|es|ing)|soar(?:s|ed|ing)?|jump(?:s|ed|ing)?|climb(?:s|ed|ing)?|spik(?:e|ed|es|ing)|grow(?:s|ing)?|grew|growth|higher|hik(?:e|ed|es|ing)|worsen(?:s|ed|ing)?|escalat(?:e|ed|es|ing)|highest|gain(?:s|ed|ing)?|mount(?:s|ed|ing)|intensif(?:y|ied|ies|ying))\b"
DOWN = r"\b(?:fall(?:s|ing|en)?|fell|drop(?:s|ped|ping)?|declin(?:e|ed|es|ing)|decreas(?:e|ed|es|ing)|plung(?:e|ed|es|ing)|slump(?:s|ed|ing)?|slid(?:e|es|ing)?|sink(?:s|ing)?|sank|cuts?|cutting|slash(?:es|ed|ing)?|reduc(?:e|ed|es|ing|tion)|lower|lowest|eas(?:e|ed|es|ing)|shrink(?:s|ing)?|shrank|dwindl(?:e|ed|es|ing)|tumbl(?:e|ed|es|ing))\b"
DELAY = r"\b(?:delay\w*|postpon\w+|defer\w*|put off|stall\w*|halt\w*)\b"; DISR = r"\b(?:disrupt\w*|outage\w*|blackout\w*|shut(?:s|ting)? ?down|cancel\w*|strike\w*|block\w*|closure\w*|suspend\w*|sack(?:ed|s|ing)?|dismiss\w*|collaps\w+|crash\w*)\b"; EXPAND = r"\b(?:expand\w*|launch\w*|extend\w*|widen\w*|boost\w*)\b"
CAS = r"\b(?:killed|dead|deaths?|died|injured|wounded|casualt\w+|fatalit\w+)\b"; SHORT = r"\b(?:shortages?|outages?|blackouts?|ran out|run out|scarcity|rationing)\b"; PRICE = r"\b(?:prices?|costs?|inflation|fuel|rent|bills?)\b"
MONTHS = set("january february march april may june july august september october november december jan feb mar apr jun jul aug sep sept oct nov dec monday tuesday wednesday thursday friday saturday sunday".split()); PRON = {"it", "they", "he", "she", "we", "i", "you", "that", "this", "who", "which", "there"}
def fv(f, path):
    d = json.load(open("runs/pulse/" + f))
    for k in path.split("."): d = d[int(k)] if k.isdigit() else d[k]
    return d
pc = lambda x: f"{100*x:.1f}%"
TAUB = D["wide_net_suite"]["tau_broad_z"]; ST_FORECAST, ST_FACT = 0.20, 0.75
def spans_of(rx, body): return [[m.start(), m.end()] for m in re.finditer(rx, body, re.I)]
for a in D["articles"]:
    c = a["contract"]; body = c["body"]; sents = a["sentences"]; sims = a["lens"]["sentence_sims"]; fr = a["solver"]["fragments"]; w = a["wide_net"]; facts = a["stated_facts"]["facts"]; spots = a["scan"]["spots"]
    sent_of = lambda pos: next((i for i, s in enumerate(sents) if s["start"] is not None and s["start"] <= pos < s["end"]), None)
    P = {}
    # ---- story type
    cnt = collections.Counter(f["factuality"] for f in fr); N = max(len(fr), 1); sh = lambda *k: sum(cnt[x] for x in k) / N
    if sh("planned", "predicted") >= ST_FORECAST: st, why = "forecast", f"planned + predicted = {cnt['planned']} + {cnt['predicted']} of {N} = {sh('planned','predicted'):.0%}, at or over the 20% line"
    elif sh("asserted", "reported") >= ST_FACT: st, why = "fact", f"asserted + reported = {cnt['asserted']} + {cnt['reported']} of {N} = {sh('asserted','reported'):.0%}, at or over 75%; planned + predicted only {sh('planned','predicted'):.0%}"
    else: st, why = "unclear", f"asserted + reported {sh('asserted','reported'):.0%} is under 75% and planned + predicted {sh('planned','predicted'):.0%} is under 20%"
    cue = collections.Counter(s[2] for s in spots); ev = []
    for f in fr:
        if (st == "forecast" and f["factuality"] in ("planned", "predicted")) or (st == "fact" and f["factuality"] in ("asserted", "reported") and len(ev) < 6): ev.append({"s": f["predicate"][0], "e": f["predicate"][1], "label": f["factuality"]})
    P["story_type"] = {"answer": st, "math": why + f"; cues: {cue['attribution']} who-said-it, {cue['modal']} could/will, {cue['quote']} quotes, {cue['negation']} negations", "evidence": ev[:12], "caveat": f"the gate cues cannot tell fact from opinion: against CheckThat human labels the best single cue scores {fv('judge_gates.json','j3.best_cue_auc')} and the sum of four cues {fv('judge_gates.json','j3.auc_sum_of_modal_negation_attribution_quote')}, where 0.5 is chance. Rule lines: planned + predicted at least {ST_FORECAST:.0%} gives forecast, asserted + reported at least {ST_FACT:.0%} gives fact", "also": a["observation"]["content_function"]["answer"] + " " + str(a["observation"]["content_function"]["confidence"])}
    # ---- topic
    votes = collections.defaultdict(float); parts = collections.defaultdict(list); evd = collections.defaultdict(list)
    for o in w["items"]:
        for b in o["best"]:
            if b["kind"] == "domain" and b["z"] >= TAUB:
                votes[b["name"]] += b["z"]; parts[b["name"]].append(f"{o['phrase']} {b['z']}")
                for s_, e_ in spans_of(r"\b" + re.escape(o["phrase"]).replace(r"\ ", r"\s+") + r"\b", body)[:3]: evd[b["name"]].append({"s": s_, "e": e_, "label": b["name"]})
    for t in w["themes"]:
        for m in t["maps"]:
            if m["kind"] == "domain" and m["z"] >= TAUB:
                votes[m["name"]] += m["z"] * t["sentences"]; parts[m["name"]].append(f"theme of {t['sentences']} sentences {m['z']}x{t['sentences']}"); r_ = sents[t["representative"]]
                if r_["start"] is not None: evd[m["name"]].append({"s": r_["start"], "e": r_["end"], "label": m["name"]})
    tot = sum(votes.values()); rank = sorted(votes.items(), key=lambda kv: -kv[1])[:3]
    if rank: top, tv = rank[0]; P["topic"] = {"answer": f"{top} ({tv/tot:.0%})", "math": "; ".join(f"{n}: " + " + ".join(parts[n][:4]) + f" = {v:.1f} of {tot:.1f}" for n, v in rank[:2]), "evidence": evd[top][:12], "caveat": f"match scores are similarity estimates (a match counts at {TAUB} or more). Against people-labelled MN-DS articles this method is right within two guesses {pc(fv('topic_gate_mnds.json','primary_pulse_assemble_method.top2_lenient_rate'))}; the trained head {pc(fv('topic_gate_mnds.json','trained_head_for_comparison.top2_lenient_rate'))}", "also": DOMNAME.get(a["observation"]["domains"]["answer"], a["observation"]["domains"]["answer"]) + " " + str(a["observation"]["domains"]["confidence"]) + " (" + a["observation"]["domains"]["status"] + ")"}
    else: P["topic"] = {"answer": "none above the threshold", "math": f"no open phrase or theme matched a topic at {TAUB} or more", "evidence": [], "caveat": "similarity estimates", "also": ""}
    # ---- change type and direction
    hits = {k: spans_of(rx, body) for k, rx in (("rising", UP), ("falling", DOWN), ("delayed", DELAY), ("disrupted", DISR), ("expanded", EXPAND))}; n = {k: len(v) for k, v in hits.items()}
    lead = n["rising"] - n["falling"]; direction = "up" if lead >= 1 else "down" if lead <= -1 else "unknown"; top_type = max(n, key=n.get) if any(n.values()) else "none found"
    ev = [{"s": s_, "e": e_, "label": k} for k, v in hits.items() for s_, e_ in v][:14]
    P["change"] = {"answer": f"{top_type}" + (f", direction {direction}" if top_type in ("rising", "falling") or direction != "unknown" else ""), "math": " | ".join(f"{k} {v}" for k, v in n.items()) + f" ; rising minus falling = {lead} gives direction {direction}", "evidence": ev, "caveat": f"counting these words alone is no better than guessing for direction ({pc(fv('direction_cls.json','heads.lexicon_counts_only.accuracy'))} against {pc(fv('direction_cls.json','always_up_accuracy'))} for always up); the trained head reaches {pc(fv('direction_cls.json','heads.embedding.accuracy'))}, scored against Sonnet. The five change types are an untested set", "also": ""}
    # ---- size: stated amounts
    am = []
    for f in facts:
        if f["kind"] != "amount" or f["status"] != "stated": continue
        nm = (f.get("noun") or "").lower(); t_ = f["text"].strip()
        if nm in MONTHS or re.search(r"\b(?:" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\b", body[f["e"]:f["e"] + 12], re.I) and not f["unit"]: continue
        i = sent_of(f["s"]); am.append((sims[i] if i is not None else 0, f, t_))
    am.sort(key=lambda x: -x[0]); sel = am[:6]
    P["size"] = {"answer": f"{len(am)} amounts stated" + (": " + "; ".join(f"{t_} {('(' + (f['noun'] or f['verb'] or '?') + ')')}" for _, f, t_ in sel[:4]) if sel else ""), "math": f"{len(am)} stated amounts (checked against the text; day numbers excluded); ordered by how close their sentence is to the title", "evidence": [{"s": f["s"], "e": f["e"], "label": "amount"} for _, f, _ in sel], "caveat": f"stated, not true. {pc(fv('stated_facts.json','per_kind.amount.validity'))} of amounts pass the four text checks; that an amount is the condition's own was checked by one reader on 100 amounts: {pc(fv('size_quantity_judged.json','precision_conditions_own_amount'))}", "also": ""}
    # ---- traits (atomic candidates from stated facts)
    tr = []; ams = [(f["s"], f["e"], f) for _, f, _ in am]
    def amt_in(i): return [x for x in ams if sent_of(x[0]) == i]
    for name, rx, extra in (("deaths or injuries", CAS, None), ("shortage or outage", SHORT, None), ("price rising", PRICE, UP)):
        for s_, e_ in spans_of(rx, body):
            i = sent_of(s_)
            if i is None or not amt_in(i): continue
            if extra and not re.search(extra, body[sents[i]["start"]:sents[i]["end"]], re.I): continue
            tr.append({"s": s_, "e": e_, "label": name}); break
    P["traits"] = {"answer": ", ".join(sorted({t['label'] for t in tr})) or "none fired", "math": "deaths or injuries = casualty word with a stated amount in the same sentence; shortage or outage = shortage word with a stated amount; price rising = price word and a rising word and a stated amount in one sentence", "evidence": tr, "caveat": "atomic rules, not scored against trait labels", "also": ""}
    # ---- what changed: most salient who-did-what fragments
    cand = []
    for f in fr:
        if not f["subject"] or not f["object"]: continue
        i = sent_of(f["predicate"][0]); st_ = body[f["subject"][0]:f["subject"][1]].strip()
        if i is None or st_.lower() in PRON: continue
        na = len(amt_in(i)); nd = sum(1 for s in spots if s[2] == "date" and sents[i]["start"] <= s[0] < sents[i]["end"])
        sal = sims[i] + 0.15 * min(na, 2) + 0.1 * min(nd, 1) + 0.1; cand.append((sal, i, f, na, nd))
    cand.sort(key=lambda x: -x[0]); seen = set(); pick = []
    for x in cand:
        if x[1] in seen: continue
        seen.add(x[1]); pick.append(x)
        if len(pick) == 3: break
    txt = lambda r: re.sub(r"\s+", " ", body[r[0]:r[1]]).strip()[:70]
    P["what_changed"] = {"answer": " || ".join(f"{txt(f['subject'])} - {body[f['predicate'][0]:f['predicate'][1]]} - {txt(f['object'])}" for _, _, f, _, _ in pick) or "no complete who-did-what link found", "math": "salience = closeness of the sentence to the title + 0.15 per stated amount (max 2) + 0.1 if it has a date + 0.1 for a complete subject and object; top three sentences: " + ", ".join(f"sentence {i+1}: {sal:.2f}" for sal, i, _, _, _ in pick), "evidence": [{"s": min(f['subject'][0], f['predicate'][0]), "e": max(f['object'][1], f['predicate'][1]), "label": f['factuality']} for _, _, f, _, _ in pick], "caveat": f"read by a parser; against MAVEN-FACT human labels its verbs cover {pc(fv('judge_gates.json','covered_by_g2_fragment'))} of real events and its did-it-happen call is right {pc(fv('judge_gates.json','j2.happened_call_accuracy'))}", "also": ""}
    ai = D["articles"].index(a); da = f"demo/mockups/gates/data.json#articles.{ai}"; R = "runs/pulse/"
    P["story_type"]["src"] = [f"{da}.solver.factuality", f"{da}.scan.counts", R + "judge_gates.json#j3.best_cue_auc", "thresholds ST_FORECAST and ST_FACT in pulse_assemble.py"]; P["story_type"]["ledger"] = "L957 L962"
    P["topic"]["src"] = [f"{da}.wide_net.items", f"{da}.wide_net.themes", "demo/mockups/gates/data.json#wide_net_suite.tau_broad_z", R + "topic_gate_mnds.json#primary_pulse_assemble_method.top2_lenient_rate", R + "topic_gate_mnds.json#trained_head_for_comparison.top2_lenient_rate"]; P["topic"]["ledger"] = "L946 L973"
    P["change"]["src"] = ["word lists UP, DOWN, DELAY, DISR, EXPAND in pulse_assemble.py applied to " + da + ".contract.body", R + "direction_cls.json#heads.lexicon_counts_only.accuracy", R + "direction_cls.json#heads.embedding.accuracy"]; P["change"]["ledger"] = "L954 L962"
    P["size"]["src"] = [f"{da}.stated_facts.facts", R + "stated_facts.json#per_kind.amount.validity", R + "size_quantity_judged.json#precision_conditions_own_amount"]; P["size"]["ledger"] = "L932 L959"
    P["traits"]["src"] = [f"{da}.stated_facts.facts", "rules CAS, SHORT, PRICE in pulse_assemble.py"]; P["traits"]["ledger"] = "L959 L962"
    P["what_changed"]["src"] = [f"{da}.solver.fragments", f"{da}.lens.sentence_sims", R + "judge_gates.json#covered_by_g2_fragment", R + "judge_gates.json#j2.happened_call_accuracy"]; P["what_changed"]["ledger"] = "L957 L962"
    a["pulse"] = P; print(a["id"], {k: (v["answer"][:90]) for k, v in P.items()})
json.dump(D, open(DATA, "w")); print("saved")
