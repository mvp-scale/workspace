"""Builds demo/mockups/solver/index.html: the six steps an article passes through, in one table. Numbers are read from runs/pulse/*.json at build time.
    python3 solver_shape_page.py   (from projects/world-state)"""
import json, html
R = "runs/pulse/"; L = lambda f: json.load(open(R + f))
sel = L("sparse_selective_flat.json"); rust = L("rust_decider_flat.json"); tm = L("timing_analyze2.json"); ft = L("fulltext_topic_flat.json"); sp = L("sparse_topic_human.json")
TR = json.load(open(R + "trace_articles.json"))["articles"]
import re as _re
for _a in TR: _a["shift"] = len(_re.sub(r"\s+", " ", _a["title"])) + 2
pct = lambda x: f"{x*100:.1f}%"
M = '<span class="chip m">trained model</span>'; RU = '<span class="chip r">rules</span>'
rows = [
 ("1", "Clean", "the article", "clean text", RU, ""),
 ("2", "Windows", "clean text", "slices the reader can take in", RU, ""),
 ("3", "BitMob Domain (v6b)", "the slices", "topic and story type, each with a confidence", M + " BitMob Domain (v6b, 22.6M)", f"{tm['t8_reader_median']:.0f} ms"),
 ("4", "Extract facts (toolchain tools 5 to 10)", "clean text", "facts: amounts, dates, names, who did what", RU + " + " + M + " spaCy parser (not ours)", f"{tm['t8_solver_median']:.0f} ms"),
 ("5", "Check facts (toolchain tool 11, Validator)", "the facts", "each fact marked stated, unbound or invalid", RU, ""),
 ("6", "Decider", "answers, confidences, facts", "answer, or abstain and say why", RU + " proved in Lean, run in Rust", f"{rust['ns_per_call']} ns"),
]
tr = "".join(f"<tr><td>{a}</td><td><b>{b}</b></td><td>{c}</td><td>{d}</td><td>{e}</td><td>{f}</td></tr>" for a, b, c, d, e, f in rows)
nlab = sum(1 for _ in open("runs/label_store/labels.jsonl"))


import os as _os, re
def _deps(m, seen=None):
    seen = seen if seen is not None else set()
    if m in seen or not _os.path.exists(m + ".py"): return seen
    seen.add(m)
    for _l in open(m + ".py"):
        _m = re.match(r"\s*(?:import|from)\s+([\w, as]+)", _l)
        if _m:
            for _n in re.split(r"[,\s]+", _m.group(1)):
                if _n and _n != "as": _deps(_n, seen)
    return seen
LIVE = _deps("analyze2"); HARV = _deps("harvest") | _deps("extract")
R1 = json.load(open("runs/pulse/round1_cascade.json"))
RP = "runs/pulse/"; RH = "runs/harvest/"
_j = lambda f: json.load(open(f))
SF_ = _j(RP + "stated_facts.json")["per_kind"]; RAo = _j(RH + "recall_audit_old.json")["recall_vs_ner"]; RAu = _j(RH + "recall_audit_union.json")["recall_vs_ner"]
TA = _j(RH + "relations/trackA_happened.json"); CB = _j(RH + "relations/carb_score.json")["results"][0]; MT = _j(RH + "relations/maven_trigger.json"); J2 = _j(RH + "relations/judged_v2.json"); TG_ = _j(RH + "teacher_gist/result.json"); PR = _j(RH + "place_reach.json"); LR = _j(RH + "link_reach.json"); WC = _j(RP + "wiring_check.json"); R2 = _j(RP + "round2_story_cascade.json"); PS = _j(RP + "parity_span.json"); BPM = _j(RH + "toolchain_measure/bp_measure.json"); TM = _j(RH + "toolchain_measure/toolchain_measure.json"); FM = _j(RH + "toolchain_measure/factuality_maven.json"); FV = _j(RH + "toolchain_measure/factuality_v2.json")
pc1 = lambda x: f"{100*x:.1f}%"
# groups: (title, what the group is for, [ (number, name, module, plain what it does, value class, value sentence, action, source) ])
GROUPS = [
 ("Prepare the text", "Get one clean text with fixed positions, so every other tool points at the same words.", [
  ("1", "Source and link capture", "extract", "Keeps who published the page, its section and every link inside it.", "unmeasured", f"Runs in the harvest script. Only counted: {LR['cc_with_link']} of {LR['cc_articles']} stored articles still carry a link. Effect on any answer not measured.", "Measure: does a cited link or source help topic or trust? If not, drop the idea.", RH + "link_reach.json"),
  ("2", "Boilerplate strip", "extract", "Removes lines a publisher repeats on every page (menus, sign-ups).", "unmeasured", f"On/off test: the topic score is {pc1(BPM['V0']['top2'])} with and without it, because it changed {BPM['train_strip']['changed']} of {BPM['train_items']:,} training texts and {BPM['test_strip']['changed']} of {BPM['test_strip']['n']:,} test texts. It matches whole lines and our labelled texts have no line breaks, so it has no reach there. No value shown for headline-and-teaser items; not tested on full articles.", "Test it on full articles with line breaks before deciding. Until then it stays harvest only.", RH + "toolchain_measure/bp_measure.json#V0, #train_strip"),
  ("3", "Clean", "analyze2", "Collapses white space into one text with stable positions.", "unmeasured", "Every tool needs it; no separate test.", "Keep. Merge 2, 3 and 7 into one Prepare step.", "analyze2.py"),
  ("7", "Sentence splitter", "scan_gate", "Cuts the text into sentences, because a fact must sit inside one.", "unmeasured", "No separate test. The scan and the parser each split sentences their own way (to check).", "Merge into Prepare and share one splitter across tools.", "scan_gate.py, facts_lib.py"),
 ]),
 ("Spot things in the text", "One cheap pass that marks dates, amounts, quotes and cue words with exact positions.", [
  ("5", "Scan", "scan_gate", "Marks quotes, money, percents, dates and cue words with their positions.", "weak", f"On 400 articles it found {pc1(RAo['date'])} of the dates the name finder found and {pc1(RAo['amount'])} of the amounts, before span rules.", "Merge 5, 6 and span rules into one spotter.", RH + "recall_audit_old.json#recall_vs_ner"),
  ("6", "Date resolver", "scan_gate", "Turns Friday or last month into a calendar date.", "weak", f"Dates pass our own four checks {pc1(SF_['date']['validity'])} of the time; not tested against outside truth. The 13 June form is missed.", "Fold into the spotter and fix the day-before-month form.", RP + "stated_facts.json#per_kind.date.validity"),
  ("+", "Span rules", "analyze2", "Catches dates, years, durations and ages the scan missed.", "adds", f"Date overlap with the name finder went from {pc1(RAo['date'])} to {pc1(RAu['date'])}; amounts {pc1(RAo['amount'])} to {pc1(RAu['amount'])}.", "Wired into the live chain as evidence ("+f"{PS['identical']} of {PS['articles']} articles identical to the harvest path, {PS['span_rules_ms_median']} ms median"+"). Next: merge with the scan so its dates become stated facts.", RH + "recall_audit_union.json#recall_vs_ner"),
 ]),
 ("Name things", "Say who and where.", [
  ("+", "spaCy name finder", "extract", "Marks people, organisations, places, dates and money.", "unmeasured", "Used only as an audit to find what we miss. Never tested as a source of names.", "Test as a second source for names. Names pass our checks only 40.7% today.", RH + "recall_audit_union.json"),
  ("15", "Place linker", "extract", "Ties a place name to a country.", "weak", f"{PR['with_country']} of {PR['articles']} articles get a country; {PR['city_links_ambiguous']} of {PR['city_links']} city links are ambiguous. Accuracy not measured; U.S., US and UK are the commonest misses.", "Fix the aliases, then measure accuracy.", RH + "place_reach.json"),
 ]),
 ("Build and check facts", "Turn spots into facts that can be checked against the text, and hold back what fails.", [
  ("8", "Parse (spaCy)", "facts_lib", "Gives each sentence a grammar tree so a number can be tied to what it counts.", "unmeasured", "Borrowed tool. Judged only through the facts built on it.", "Keep.", "facts_lib.py"),
  ("9", "Fact extractors", "facts_lib", "Pulls amounts, dates, names and who-did-what out as checkable facts.", "weak", f"Pass our four checks: amounts {pc1(SF_['amount']['validity'])}, dates {pc1(SF_['date']['validity'])}, names {pc1(SF_['name']['validity'])}, who-did-what {pc1(SF_['triple']['validity'])}.", "Keep amounts and dates. Rebuild names and who-did-what.", RP + "stated_facts.json#per_kind"),
  ("10", "Binder", "facts_lib", "Says what an amount counts and which verb governs it.", "weak", f"Left unbound: amounts {pc1(SF_['amount']['unbound_share'])}, dates {pc1(SF_['date']['unbound_share'])}, names {pc1(SF_['name']['unbound_share'])}.", "Merge into the extractors as one step; compare with the rule binder.", RP + "stated_facts.json#per_kind.*.unbound_share"),
  ("11", "Validator", "facts_lib", "Marks each fact stated, unbound or invalid, so a guess never passes as a fact.", "weak", f"{pc1(SF_['overall']['validity'])} of {SF_['overall']['captured']:,} captured facts pass all four checks. Our own checks, not outside truth.", "Keep as the gate. Add a test against an outside answer.", RP + "stated_facts.json#per_kind.overall"),
  ("12", "Independent counter", "facts_lib", "A second simple count to check the extractors miss little.", "unmeasured", "Used inside the coverage check; no separate score.", "Fold into the Validator's coverage report.", "facts_lib.py"),
 ]),
 ("Read the meaning", "Say what happened, to whom, and whether it really happened.", [
  ("+", "Who-did-what triples", "spo_chains", "Writes each sentence as subject, verb, object, with negation, and links them into chains.", "adds", f"Against the same {TM['event_mentions']:,} marked events, these find the event word in {pc1(TM['B_spo_chains_triples']['trigger_recall_verb_or_argument_head'])} against {pc1(TM['A_facts_lib_triples']['trigger_recall_verb_or_argument_head'])} for the extractors' who-did-what (gap +{100*TM['recall_difference_B_minus_A']['verb_or_argument_head']['diff']:.1f} points, range {100*TM['recall_difference_B_minus_A']['verb_or_argument_head']['ci95'][0]:.1f} to {100*TM['recall_difference_B_minus_A']['verb_or_argument_head']['ci95'][1]:.1f}). Cost: {TM['B_spo_chains_triples']['median_ms_per_article']} ms per article against {TM['A_facts_lib_triples']['median_ms_per_article']}, and a lower precision proxy ({pc1(TM['B_spo_chains_triples']['precision_proxy_verb_is_trigger'])} against {pc1(TM['A_facts_lib_triples']['precision_proxy_verb_is_trigger'])}).", "Keep both: these for finding events, the extractors for the cheaper, more precise fact line. Wire into the live path where events matter.", RH + "toolchain_measure/toolchain_measure.json"),
  ("13", "Factuality tagger", "extract", "Tells asserted from reported, denied or planned.", "weak", f"Against human labels on {FM['mentions_scored']:,} marked events: balanced accuracy {FM['metrics']['bal3']} against {FM['best_constant']['bal3']:.3f} for a constant guess, but plain accuracy {FM['metrics']['acc3']} against {FM['best_constant']['acc']} for always saying certain; it caught {FV['full']['V1']['neg_recall']} of {FM['gold_counts']['negated']} negated events. Taking the certain, negated or possible call from the triples instead lifts balanced accuracy to {FV['full']['V2']['bal3']} (paired range +{FV['paired95']['V2']['bal3_minus_V1'][0]} to +{FV['paired95']['V2']['bal3_minus_V1'][1]}) and negated events caught to {FV['full']['V2']['neg_recall']}, still below always-certain on plain accuracy.", "Take negation from the triples in the live path when the event-meaning step is built; merge the two. Not a new task now.", RH + "toolchain_measure/factuality_v2.json#full, #paired95"),
  ("14", "Change lexicon", "extract", "Says rising, falling, delayed, disrupted or expanded.", "unmeasured", "The word list is doubtful (T42 note). Not wired.", "Measure, fix the list, then wire. Candidate to merge with the tagger.", "dir_lexicon.py"),
 ]),
 ("Choose what the models read", "Decide which text a model or the teacher sees.", [
  ("4", "Windows", "analyze2", "Cuts the article into slices of 64 word pieces, headline first, so the model sees the whole article.", "adds", f"On did-it-happen the head scores {TA['embedding_head_alone']} without window features and {TA['head_with_window_features_reproduced']} with them.", "Keep.", RH + "relations/trackA_happened.json"),
  ("+", "Gist", "gist", "Picks the few sentences that cover the article, for the teacher to read.", "adds", f"A teacher reading the gist agrees with its own full-article labels {TG_['agree_full_gist']} on topic, with about 4 times fewer tokens.", "Wire into the teacher path (Track C) and test for condition.", RH + "teacher_gist/result.json#agree_full_gist"),
 ]),
 ("Answer", "The models and the rule that decides whether to answer.", [
  ("+", "Sparse topic and story heads", "analyze2", "Answer easy articles from word counts in under 1 ms, so the encoder is skipped.", "adds", f"Round 1 (topic, human labels): half the articles answered keeps the score at {pc1(R1['cascade_at_share50']['top2'])} against {pc1(R1['v6b_alone']['top2'])}. Round 2 (story type, agreement with Sonnet): {pc1(R2['story_lines']['0.5']['rate'])} against {pc1(R2['v6b_alone_story']['rate'])}. Wired in with both confident: the encoder is skipped for {pc1(WC['encoder_skipped_share'])} of 200 full articles and the median time falls from {WC['median_ms_heads_off']} to {WC['median_ms_heads_on']} ms. Weak on forecast and opinion (recall {R2['per_class_recall']['forecast']['sparse_recall']} and {R2['per_class_recall']['opinion']['sparse_recall']}); v6b still carries those.", "Wired behind a switch, off by default. Turn on by default after a score on the whole chain.", RP + "wiring_check.json; round2_story_cascade.json; round1_cascade.json"),
  ("M", "BitMob Domain v6b", "expert1_runtime", "The trained model that answers topic, story type and condition.", "adds", "Scores per head are on the Reading gates page.", "Keep.", "demo/mockups/gates"),
  ("M", "Decider", "decider", "Decides answer, provisional or withheld, and gives the reason.", "adds", "160 cases made from the Lean rules; the Rust build fails if any differs.", "Keep.", "rust_decider/vectors.txt"),
 ]),
]
TOOLS = [(t[0], t[1], t[2], t[3], t[4], t[5], t[7], t[6]) for g in GROUPS for t in g[2]]  # (n, name, module, plain, class, value, source, action)
def _stat(mod):
    live = mod in LIVE or mod == "expert1_runtime"; harv = mod in HARV
    return live, harv
_nl = sum(1 for t in TOOLS if _stat(t[2])[0]); _nh = sum(1 for t in TOOLS if not _stat(t[2])[0] and _stat(t[2])[1])
VL = {"adds": ("built", "adds value"), "weak": ("partial", "weak or mixed"), "unmeasured": ("missing", "not measured")}
WHYNOT = {"Source and link capture": "Runs in the harvest script only. No recorded reason. Few stored articles carry a link.", "Boilerplate strip": "Runs in the harvest script only. No recorded reason.", "Span rules": "Wired into analyze2.py 2026-11-08 as evidence only.", "spaCy name finder": "Switched off in the live chain on purpose (facts_lib.py disables it), presumably for speed.", "Place linker": "Runs in the harvest script only. No recorded reason.", "Change lexicon": "Runs in the harvest script (extract.py, the conditions it records); analyze2.py returns not run for change. The word list is doubtful.", "Factuality tagger": "Built for harvesting labels, not wired into analyze2.py. No recorded reason.", "Who-did-what triples": "Tested 2026-11-08; the small parser gets about 40% fully correct.", "Gist": "Meant for the teacher path (Track C), which waits for the owner's yes.", "Sparse topic and story heads": "Wired 2026-11-08 behind a switch (sparse= argument), off by default."}
def _where(mod):
    l, h = _stat(mod)
    return ('<span class="tag built">live</span> ' if l else '') + ('<span class="tag partial">harvest</span>' if h else '') + ('' if (l or h) else '<span class="tag missing">neither</span>')
audit = "<table><tr><th>Tool and what it does</th><th>Where it runs</th><th>Does it add value?</th><th>What I would do</th></tr>"
for _title, _purpose, _items in GROUPS:
    audit += f'<tr class="grp"><td colspan="4"><b>{_title}</b> <span class="z-un">{_purpose}</span></td></tr>'
    for _n, _name, _mod, _plain, _vc, _vt, _act, _src in _items:
        audit += f'<tr><td><b>{_name}</b> <span class="z-un">(tool {_n})</span><br>{_plain}</td><td>{_where(_mod)}' + (f'<div class="src">Not live: {WHYNOT[_name]}</div>' if (_name in WHYNOT) else '') + f'</td><td><span class="tag {VL[_vc][0]}">{VL[_vc][1]}</span><br>{_vt}<div class="src">{_src}</div></td><td>{_act}</td></tr>'
audit += "</table>"
_nv = {k: sum(1 for t in TOOLS if t[4] == k) for k in VL}

r1tab = "<table><tr><th>Sparse head answers</th><th>Chain topic score (two guesses)</th><th>Sparse right on its share</th><th>v6b right on the same share</th></tr>"
for _q, _r in R1["lines"].items():
    r1tab += f'<tr><td><b>{100*_r["sparse_share"]:.0f}%</b> of articles</td><td><b>{100*_r["top2"]:.1f}%</b> [{100*_r["ci95"][0]:.1f} to {100*_r["ci95"][1]:.1f}]</td><td>{100*_r["sparse_right_when_answering"]:.1f}%</td><td>{100*_r["v6b_right_on_those"]:.1f}%</td></tr>'
r1tab += f'<tr><td>0% (v6b alone)</td><td><b>{100*R1["v6b_alone"]["top2"]:.1f}%</b> [{100*R1["v6b_alone"]["ci95"][0]:.1f} to {100*R1["v6b_alone"]["ci95"][1]:.1f}]</td><td></td><td></td></tr></table>'

TODO = [
 ("1. Wire the toolchain into the live path", [
  ("DONE Put the sparse topic and story heads in front of v6b (behind a switch)", f"Round 1: half the articles skip the slow model at the same topic score ({pc1(R1['cascade_at_share50']['top2'])} against {pc1(R1['v6b_alone']['top2'])})", "CPU, free", False),
  ("DONE Wire span rules into analyze2 (evidence; merge with the scan next)", f"Date overlap {pc1(RAo['date'])} to {pc1(RAu['date'])}", "CPU, free", False),
  ("Fill the change field from the change lexicon (fix the word list first)", "analyze2.py returns not run for change today", "CPU, free", False),
  ("DONE Run the same articles through the live and harvest paths (span rules: 199 of 200 identical; the one difference is the 12,000-character cut)", "MM3-0002: the two paths could differ (0.91)", "CPU, free", False),
 ]),
 ("2. Measure the nine tools nobody has measured", [
  ("Test each unmeasured tool against an outside answer or against itself switched off, starting with the name finder, the factuality tagger and boilerplate strip", "A tool without a measure is the same as not running (owner)", "CPU, free", False),
 ]),
 ("3. Fix the weak tools", [
  ("Head-to-head: triples against the extractors' who-did-what, then replace the loser", f"Who-did-what passes only {pc1(SF_['triple']['validity'])} of our checks; names {pc1(SF_['name']['validity'])}", "CPU, free", False),
  ("Test the name finder as a second source for names", "Names are the weakest fact kind", "CPU, free", False),
 ]),
 ("4. Learn across all the models", [
  ("Run the toolchain over the live feed and the historical feeds; store each label with its strength (proved, rule, weak)", "Playbook 15 rule 5; cheap labels for every head", "CPU, in chunks under one hour", False),
  ("Teacher labels for the cases the toolchain and the models leave open, reading the gist (Track C)", "Gist matches the full-article teacher at lower token cost", "Hosted spend is near its cap (67.7 of 70 USD) or session tokens", True),
  ("Retrain the heads on the pooled labels (Track D)", "Retrain at every 10,000 articles (playbook 15 rule 6)", "Kaggle", True),
  ("Define Condition for full articles; define Area, Capability and Novelty before training them", "No outside truth yet for these", "Owner decision", True),
 ]),
 ("5. Let Opus drive the rounds", [
  ("Three supervised rounds with an Opus picker, using the permissions list and the round runner", "The loop has no decision step today", "Opus tokens; I confirm before launching", True),
 ]),
 ("6. Report it in one place", [
  ("Four numbers per head and the round list on the Reading gates page; then merge the pages", "Owner: one place that says how good it is; stop growing pages", "CPU, free", False),
 ]),
]
todohtml = ""
for _ph, _ts in TODO:
    todohtml += f'<div class="beat"><h3>{_ph}</h3><div class="cards">'
    for _t, _w, _c, _y in _ts:
        _dn = _t.startswith("DONE "); _t = _t[5:] if _dn else _t
        _st = "built" if _dn else ("missing" if _y else "partial")
        todohtml += f'<div class="card {_st}"><div><h4>{_t}</h4><span class="tag {_st}">{"done" if _dn else ("needs your yes" if _y else "I can do now")}</span><p><b>Why:</b> {_w}</p><p><b>Cost:</b> {_c}</p></div></div>'
    todohtml += '</div></div>'
LOOP = [
 ("Read and answer", "Every article goes through the tools first. The models only see what the tools could not settle.", [
  ("1", "Tools read", "built", "built", "Rules and tools make one evidence record per article. Code analyze2.py (ledger L1022)."),
  ("2", "Router picks who answers", "partial", "defined, not a service", "Order and rules are written (playbook/15-bitmob-stack.md rules 1 to 4) and the order is proved (lean/BitMobFlow.lean). No running Router."),
  ("3", "BitMob models answer", "partial", "built, 1 of 6 heads", "BitMob Domain v6b answers topic, story type and condition. Area, Capability and Novelty are names only (ledger L1057)."),
 ]),
 ("Learn", "What the models were not sure of gets labelled, and the models are trained again.", [
  ("4", "Teacher labels the rest", "built", "built", f"The label store holds {nlab:,} labels (projects/world-state/runs/label_store/labels.jsonl, counted when this page was built). The gist test says the teacher can read the gist instead of the full article (runs/harvest/teacher_gist/result.json)."),
  ("5", "Retrain", "partial", "by hand", "Rule: retrain every 10,000 articles (playbook 15 rule 6). Today a person starts each training run. Kaggle upload (Track D) is waiting for the owner's yes."),
 ]),
 ("Judge and decide", "The score comes from outside answers. Then something has to choose the next change. That is the missing piece.", [
  ("6", "Score on outside anchors", "built", "built", "The Reading gates page scores each field against MN-DS, MAVEN-FACT and CheckThat. The four numbers per head (settled by tools, tool accuracy, routed, abstained) are not built yet."),
  ("7", "Opus picks the next change", "missing", "not built", "Today a person (or this session) reads the scoreboard and picks. It would read the scoreboard, the ledger and the permissions list, and write one round card."),
  ("8", "Sonnet or Haiku run it", "partial", "pattern exists, not wired", "kit/live/run_round.py runs one card: prediction in the ledger, command with a time cap, score from the result file. The captain pattern (.claude/skills/captain) launches crew. Neither is wired to step 7."),
 ]),
]
_n = {"built": 0, "partial": 0, "missing": 0}
for _b in LOOP:
    for _x in _b[2]: _n[_x[2]] += 1

HC = json.load(open("runs/pulse/head_coverage.json"))
def _v(x, pct=True):
    if x.get("value") is None: return f'<span class="z-un">{x["why"]}</span>'
    return f'<b>{100*x["value"]:.1f}%</b>'
hctab = "<table><tr><th>Head</th><th>Tools alone settle</th><th>Model answers</th><th>Model right</th><th>Left for the teacher</th><th>Judged against</th></tr>"
for _h, _d in HC.items():
    _acc = _v(_d["model_accuracy"]) + (f' <span class="z-un">({_d["model_accuracy"]["note"]})</span>' if _d["model_accuracy"].get("note") else "")
    hctab += f'<tr><td><b>{_h}</b></td><td>{_v(_d["tools_settled"])}</td><td>{_v(_d["model_answered"])}</td><td>{_acc}</td><td>{_v(_d["left_for_teacher"])}</td><td>{_d["judge"]}</td></tr>'
hctab += "</table>"
loophtml = '<div class="strip">' + "".join(f'<span class="seg {x[2]}"><b>{x[0]}</b> {x[1]}</span>' for b in LOOP for x in b[2]) + '</div>'
loophtml += f'<p class="tally"><span class="dot built"></span>{_n["built"]} built <span class="dot partial"></span>{_n["partial"]} partly <span class="dot missing"></span>{_n["missing"]} not built</p>'
for i, (bt, point, items) in enumerate(LOOP, 1):
    loophtml += f'<div class="beat"><div class="kick">Beat {i}</div><h3>{bt}</h3><p class="point">{point}</p><div class="cards">'
    for num, name, st, label, body in items:
        loophtml += f'<div class="card {st}"><div class="num">{num}</div><div><h4>{name}</h4><span class="tag {st}">{label}</span><p>{body}</p></div></div>'
    loophtml += '</div></div>'
page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>The BitMob Solver</title><link rel="stylesheet" href="../mock.css">
<style>
main{{max-width:1500px;width:94%;margin:0 auto;padding:24px 16px 80px}} h1{{margin:0 0 6px;font-size:24px}} h2{{margin:26px 0 6px;font-size:18px}}
p{{line-height:1.6;font-size:16px;margin:8px 0}} .src{{font:12px ui-monospace,monospace;color:var(--ink-2)}}
table{{border-collapse:collapse;width:100%;font-size:15px}} th,td{{text-align:left;vertical-align:top;padding:11px 12px;border-bottom:1px solid var(--line,#8884)}} th{{font-size:12px;color:var(--ink-2);font-weight:600}}
.chip{{font:700 11px ui-monospace,monospace;padding:2px 7px;border-radius:10px;border:1px solid var(--line,#8884)}} .chip.m{{background:var(--accent);color:#fff}} .chip.r{{background:var(--surface-2)}}
.z-old{{background:#2e8b5744}} .z-read{{background:#3b7dd844}} .z-un{{color:var(--ink-2);opacity:.6}} .fact{{text-decoration:underline;text-decoration-thickness:2px}} .txt{{white-space:pre-wrap;line-height:1.5;font-size:13px;max-height:none;padding:8px;border:1px solid var(--line,#8884);border-radius:8px;margin:8px 0}}
.step{{margin:12px 0;padding:8px 10px;border-left:3px solid var(--accent)}} .step h3{{margin:0 0 4px;font-size:15px}} .io{{display:grid;grid-template-columns:40px 1fr;gap:2px 10px;font-size:14px}} .io p{{margin:2px 0}} .bar{{position:relative;height:18px;background:var(--surface-2);border:1px solid var(--line,#8884);border-radius:4px;margin:6px 0}} .wbar{{position:absolute;top:2px;bottom:2px;background:#3b7dd8;opacity:.6;border-right:1px solid #fff}} .obar{{position:absolute;top:0;height:5px;background:#2e8b57}}
.flow{{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:12px 0}} .flow span{{padding:6px 10px;border:1px solid var(--line,#8884);border-radius:8px;background:var(--surface-2);font-size:13px}} .flow i{{font-style:normal;color:var(--ink-2)}}
dl{{display:grid;grid-template-columns:120px 1fr;gap:6px 12px;font-size:14px}} dt{{font-weight:700}} dd{{margin:0}}
.lead{{font-size:21px;line-height:1.5;margin:10px 0 4px}} .lead b{{color:var(--accent)}}
.act{{margin:56px 0 16px;padding:24px 28px;border-radius:12px;background:var(--surface-2);border-left:6px solid var(--accent)}} .act .kick{{font:700 12px ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--accent)}} .act h2{{margin:6px 0 6px;font-size:30px}} .act p{{margin:2px 0;font-size:17px}}
.strip{{display:flex;flex-wrap:wrap;gap:4px;margin:12px 0 4px}} .seg{{flex:1 1 150px;padding:12px 12px;border-radius:6px;font-size:12px;line-height:1.3;color:#fff}} .seg b{{display:block;font-size:16px}} .built{{--c:#2e8b57}} .partial{{--c:#c98a12}} .missing{{--c:#c0463c}} .seg.built,.seg.partial,.seg.missing{{background:var(--c)}}
.tally{{font-size:13px;color:var(--ink-2)}} .dot{{display:inline-block;width:10px;height:10px;border-radius:50%;margin:0 4px 0 12px;background:var(--c)}} .dot:first-child{{margin-left:0}}
.beat{{margin:26px 0 0}} .beat .kick{{font:700 12px ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-2)}} .beat h3{{margin:2px 0;font-size:20px}} .point{{font-size:15px;color:var(--ink-2)}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px;margin-top:12px}} .card{{display:flex;gap:14px;padding:18px;border:1px solid var(--line,#8884);border-top:5px solid var(--c);border-radius:8px}} .card .num{{font-size:28px;font-weight:800;color:var(--c);line-height:1}} .card h4{{margin:0 0 6px;font-size:18px}} .card p{{font-size:15px;line-height:1.55;margin:10px 0 0}} .grp td{{background:var(--surface-2);padding-top:14px}} .tag{{font:700 11px ui-monospace,monospace;padding:2px 8px;border-radius:10px;background:var(--c);color:#fff}}
@media (max-width:620px){{table,tbody,tr,td,th{{display:block}} th{{display:none}} tr{{padding:6px 0;border-bottom:1px solid var(--line,#8884)}} td{{border:0;padding:2px 0}} dl{{grid-template-columns:1fr}}}}
</style></head><body><main>
<h1>The BitMob Solver: how an article becomes a Pulse answer</h1>
<p class="lead">An article comes in. <b>Tools</b> read what the text proves. A <b>small model</b> answers what is left. The <b>teacher</b> labels the rest, and that trains the next model. <b>Built:</b> the tools, one model, the teacher and the scoring. <b>Missing:</b> the step that decides what to improve next.</p>
<div class="act"><div class="kick">Act 1</div><h2>The route</h2><p>Six steps. Each hands a checked result to the next, and the last one gives the answer with its working.</p></div>
<p>The <b>BitMob Solver</b> is the whole chain: fixed-rule tools and BitMob models working together. An article passes through six steps. Each step hands a checked result to the next. The rules decide when a model is worth calling. The chain is defined in the playbook (sections 1, 2, 4) and built as <code>analyze2.py</code>.</p>
<div class="flow"><span>Article</span><i>→</i><span>1 Clean</span><i>→</i><span>2 Windows</span><i>→</i><span>3 BitMob Domain (v6b)</span><i>→</i><span>4 Extract facts</span><i>→</i><span>5 Check facts</span><i>→</i><span>6 Decider</span><i>→</i><span>Answer with working</span></div>
<table><tr><th>#</th><th>Step</th><th>Takes</th><th>Gives</th><th>Uses</th><th>Time</th></tr>{tr}</table>
<p class="src">Sources: analyze2.py; facts_lib.py; runs/pulse/timing_analyze2.json#t8_reader_median, #t8_solver_median (median, 8 threads); runs/pulse/rust_decider_flat.json#ns_per_call. Times not shown are not measured.</p>
<p>Step 6 is tested by the 160 cases in <code>vectors.txt</code>, made from the Lean rules. The Rust build fails if any case differs. Steps 1 to 5 are still Python.</p>
<h3 style="margin-top:28px">The BitMob toolchain: what each tool does, and whether it earns its place</h3><p>The six steps above are groups. This is the actual list, grouped by job. Three words used in the table:</p>
<dl><dt>Live</dt><dd>The tool runs when we ask the Solver to answer one article (the path in <code>analyze2.py</code>). If a tool is not live, it does not affect any answer we give today.</dd>
<dt>Harvest</dt><dd>The tool runs in the batch job that reads thousands of articles to collect evidence and training labels (<code>harvest.py</code>, <code>extract.py</code>). It feeds training, not answers.</dd>
<dt>Neither</dt><dd>Built and tested, but not part of either path yet.</dd></dl>
<p>Rule: a tool stays in the toolchain only with a stated point and a measured answer to "does it add value". <b>{_nv["adds"]}</b> add value, <b>{_nv["weak"]}</b> are weak or mixed, <b>{_nv["unmeasured"]}</b> are not measured yet. "Adds value" means a measured gain against an outside answer or against the same step switched off. Passing our own checks is not truth, so those are marked weak. Where a tool is not live, the table says why, or says that no reason is recorded. Of {len(TOOLS)} tools, <b>{_nl}</b> are live and {_nh} more are harvest only. The last column is my reading, to merge or wire in; it is not a measured result.</p>{audit}<p class="src">Sources: playbook/15-bitmob-stack.md (tools 1 to 15); import check of analyze2.py, harvest.py and extract.py; analyze2.py line "change: not run, no extractor wired yet"</p>



<div class="act"><div class="kick">Act 2</div><h2>The cast</h2><p>Who does the work. Three are in use, three are only names.</p></div>

<table><tr><th>Name</th><th>What it is</th><th>Status</th></tr>
<tr><td><b>BitMob Solver</b></td><td>The whole chain: the tools first, then the BitMob models</td><td>built (analyze2.py)</td></tr>
<tr><td><b>BitMob Domain</b></td><td>Decides the broad sector (topic). Two versions: v6b (the 22.6M network, step 3, registry code PULSEB, formerly Pulse reader and BitMob Reader) and sparse (keyword model, formerly BitMob Keys)</td><td>v6b in use; sparse tested alone, not wired in</td></tr>
<tr><td><b>BitMob Function</b></td><td>Decides report, opinion, forecast and similar (story type); same v6b network today</td><td>in use</td></tr>
<tr><td><b>BitMob Condition</b></td><td>Decides rising, falling and similar, with direction; same v6b network today</td><td>in use for 4 kinds</td></tr>
<tr><td><b>BitMob Area</b></td><td>Decides the specific Area</td><td>name only; nothing trained</td></tr>
<tr><td><b>BitMob Capability</b></td><td>Decides which Capability</td><td>name only; nothing trained</td></tr>
<tr><td><b>BitMob Novelty</b></td><td>Decides known, emerging or unsupported</td><td>name only; nothing trained</td></tr>
<tr><td><b>BitMob toolchain</b></td><td>All the rule-based tools that find and check things in the text (22 listed in Act 1, each with its point and a measured test of value). Replaces the name "Fact finder"</td><td>12 live, see Act 1</td></tr>
</table>
<p class="src">Sources: demo/models.json (pulse-reader name, code PULSEB, aliases); playbook/00-knowledge-pipeline-v1.md sections 1, 2, 4; ledger L1022, L1055, L1056, and the owner's confirmation of the six names.</p>
<div class="act"><div class="kick">Act 3</div><h2>One real article</h2><p>Pick an article and see what each step took in and gave out.</p></div>

<p>Pick a real article. Below it you see what each step took in and gave out. In the text, <span class="z-old">green</span> is what the old reader saw (first 64 word pieces), <span class="z-read">blue</span> is what the current reader reads (up to 12 windows), and <span class="z-un">grey</span> is text the reader never sees. Amounts and dates the solver found are underlined.</p>
<p><select id="pick"></select></p>
<div id="watch"></div>
<p class="src">Source: runs/pulse/trace_articles.json, made by trace_articles.py from runs/pulse/golden/articles.jsonl (8 of the 200 reference articles, picked by length).</p>
<script>
const DATA = {json.dumps(TR).replace("</","<\\/")};
const el = (t, c, x) => {{ const e = document.createElement(t); if (c) e.className = c; if (x !== undefined) e.textContent = x; return e; }};
const sel = document.getElementById("pick"), box = document.getElementById("watch");
DATA.forEach((a, i) => {{ const o = el("option", "", a.title.slice(0, 70) + " (" + a.body_chars.toLocaleString() + " characters)"); o.value = i; sel.appendChild(o); }});
function step(n, name, inp, out) {{ const d = el("div", "step"); d.appendChild(el("h3", "", n + " " + name)); const l = el("div", "io"); [["In", inp], ["Out", out]].forEach(([k, v]) => {{ l.appendChild(el("b", "", k)); const s = el("div", "", ""); (Array.isArray(v) ? v : [v]).forEach(x => {{ if (x instanceof Node) s.appendChild(x); else s.appendChild(el("p", "", x)); }}); l.appendChild(s); }}); d.appendChild(l); return d; }}
function textView(a) {{
  const t = a.clean, rs = a.shift + a.windows_cover_body_chars, os = a.shift + a.old_reading.body_chars_seen; const pts = new Set([0, t.length, os, rs]);
  a.facts.forEach(f => {{ pts.add(f.s); pts.add(f.e); }}); const P = [...pts].filter(x => x >= 0 && x <= t.length).sort((x, y) => x - y); const wrap = el("div", "txt");
  for (let i = 0; i < P.length - 1; i++) {{ const s = P[i], e = P[i + 1]; if (e <= s) continue; const sp = el("span", s < a.shift ? "z-old" : s < os ? "z-old" : s < rs ? "z-read" : "z-un", t.slice(s, e)); const f = a.facts.find(f => f.s <= s && e <= f.e); if (f) {{ sp.classList.add("fact"); sp.title = f.kind + ": " + f.text.trim() + " (" + f.status + ")"; }} wrap.appendChild(sp); }}
  return wrap;
}}
function render(a) {{
  box.textContent = ""; const T = a.ms;
  box.appendChild(el("h3", "", a.title)); box.appendChild(el("p", "src", "Reader reads " + Math.round(a.windows_cover_share * 100) + "% of the body; the old reader read " + Math.round(a.old_reading.body_share_seen * 100) + "%. The solver reads up to 12,000 characters."));
  box.appendChild(textView(a));
  box.appendChild(step("1", "Clean", a.raw_chars.toLocaleString() + " characters of headline and body", a.clean_chars.toLocaleString() + " characters of clean text (cut at 12,000)"));
  const bar = el("div", "bar"); a.windows.forEach((w, i) => {{ const s = el("span", "wbar"); s.style.left = (w.start / a.body_chars * 100) + "%"; s.style.width = Math.max((w.end - w.start) / a.body_chars * 100, .4) + "%"; s.title = "window " + (i + 1); bar.appendChild(s); }});
  const ob = el("span", "obar"); ob.style.left = "0"; ob.style.width = Math.max(a.old_reading.body_chars_seen / a.body_chars * 100, .4) + "%"; bar.appendChild(ob);
  box.appendChild(step("2", "Windows", "the clean text", [a.windows.length + " windows of up to " + a.max_pieces + " word pieces, headline kept in each, cap " + a.window_cap, bar, "Together they cover " + a.windows_cover_body_chars.toLocaleString() + " of " + a.body_chars.toLocaleString() + " body characters (" + Math.round(a.windows_cover_share * 100) + "%). The green mark is where the old reader stopped."]));
  const tb = el("table", ""); const hr = el("tr"); ["Window", "Characters", "Pieces", "Topic, top two", "Story type"].forEach(h => hr.appendChild(el("th", "", h))); tb.appendChild(hr);
  a.windows.forEach((w, i) => {{ const r = el("tr"); [i + 1, w.start + "-" + w.end, w.pieces, w.topic.map(x => x[0] + " " + x[1]).join(", "), w.story[0] + " " + w.story[1]].forEach(x => r.appendChild(el("td", "", String(x)))); tb.appendChild(r); }});
  box.appendChild(step("3", "BitMob Domain (v6b) (" + T.reader_ms.toFixed(0) + " ms)", "the windows", [tb, "Averaged answer: " + a.topic_avg.map(x => x[0] + " " + x[1]).join(", ") + "; story type " + a.story_avg.map(x => x[0] + " " + x[1]).join(", ") + ". Old reader (first 64 pieces only): " + a.old_reading.topic.map(x => x[0] + " " + x[1]).join(", ") + "."]));
  const fl = el("div", ""); if (!a.facts.length) fl.appendChild(el("p", "", a.parse_ran ? "The parser ran and found no amount or date." : "No number or date word, so the parser was skipped.")); a.facts.slice(0, 12).forEach(f => fl.appendChild(el("p", "fact-row", f.kind + ": " + f.text.trim() + " -> " + (f.kind === "amount" ? "value " + f.value + ", counts " + (f.noun || f.verb || "nothing") : "date " + f.value) + " [" + f.status + "]"))); if (a.facts.length > 12) fl.appendChild(el("p", "src", "and " + (a.facts.length - 12) + " more"));
  box.appendChild(step("4", "Extract facts (" + T.solver_ms.toFixed(0) + " ms)", "the clean text", [a.facts.length + " amounts and dates found", fl]));
  const c = {{stated: 0, unbound: 0, invalid: 0}}; a.facts.forEach(f => c[f.status]++);
  box.appendChild(step("5", "Validator", "the " + a.facts.length + " facts", "stated " + c.stated + ", unbound " + c.unbound + ", invalid " + c.invalid + ". Each stated fact passed: literally in the text, value reads back, bound to a noun or verb, one sentence."));
  const dt = el("table", ""); const h2 = el("tr"); ["Field", "Outcome", "Answer", "Source"].forEach(h => h2.appendChild(el("th", "", h))); dt.appendChild(h2);
  Object.entries(a.decider).forEach(([k, v]) => {{ const r = el("tr"); [k, v.outcome, v.answer || "-", v.how].forEach(x => r.appendChild(el("td", "", String(x)))); dt.appendChild(r); }});
  box.appendChild(step("6", "Decider (" + T.decider_ms.toFixed(3) + " ms)", "answers, confidences, facts, field markers", dt));
}}
sel.onchange = () => render(DATA[+sel.value]); render(DATA[0]);
</script>

<div class="act"><div class="kick">Act 4</div><h2>A faster first look</h2><p>A small keyword model could answer first and leave only the hard articles to the big one.</p></div>

<p><b>BitMob Domain (sparse)</b> ({M}, candidate, not registered) would read first and give the topic in about {sp['word12_median_us']/1000:.0f} ms. The BitMob Domain (v6b) would only see what BitMob Domain (sparse) won't answer. In a test on 1,600 human-labelled articles it answered {pct(sel['share_070'])} of them and was right within two categories on {pct(sel['right_070'])} of those. It is tested alone and not wired in.</p>
<p class="src">Sources: runs/pulse/sparse_selective_flat.json#share_070, #right_070; runs/pulse/sparse_topic_human.json#word12_median_us</p>

<div class="act"><div class="kick">Act 5</div><h2>The loop that makes it better</h2><p>One round goes left to right and starts again. Opus decides, Sonnet or Haiku run it, the files give the score. Status is my reading of the files named in each card.</p></div>
{loophtml}
<h3 style="margin-top:30px">Step 6 today: what each head settles</h3><p>Four numbers per head. The model answers almost everything, so almost nothing is left for the teacher: the model does not yet hand hard cases on. No tool settles a head alone in anything we have measured.</p>{hctab}<p class="src">Sources: runs/pulse/head_coverage.json (made by head_coverage.py from end2end_v6b-student_sealed.json, anchor_mnds_fresh_v6b-student.json, topic_gate_mnds.json); each value has its file key in that file</p>
<h3 style="margin-top:30px">Round 1 (the first loop round): put the cheap step in front</h3><p>Question: if a small keyword model answers the articles it is most sure of, and v6b answers the rest, what happens to the topic score against human labels (MN-DS, 1,600 articles)? Predicted 78 to 83%. Result: a hit. Sparse head answering half the articles keeps the score at {100*R1["cascade_at_share50"]["top2"]:.1f}%, the same as v6b alone, so about half of the slower model calls can be skipped. Even at 75% the drop is inside the noise. The sparse head was trained on Sonnet labels only; MN-DS is used for scoring.</p>{r1tab}<p class="src">Sources: runs/pulse/round1_cascade.json (round1_cascade.py); ledger L1117 prediction, L1119 score. Not yet wired into analyze2.py.</p>\n<p>The permissions list the Opus picker reads: kit/live/loop_permissions.json. A card is checked against it by kit/live/loop_gate.py.</p>
<p>Stop rules: anything that costs money, uses the 5090 or Kaggle, or goes outside waits for the owner's yes. No job runs over one hour unattended.</p>
<p class="src">Sources: playbook/15-bitmob-stack.md; lean/BitMobFlow.lean; kit/live/run_round.py; .claude/skills/captain/SKILL.md; ledger L1022, L1057</p>

<div class="act"><div class="kick">Act 6</div><h2>To do: make the toolchain work and start learning</h2><p>In order. Items marked "I can do now" are free and on CPU. Items marked "needs your yes" spend money, use Kaggle, or need your decision.</p></div>
<div class="step"><h3>The first lap: what "done" means</h3><p>The first lap is done when each step of the loop has run once on real data, with its result, or with the recorded reason it failed. We are getting through the process first; the loop is improved after it has run. A failure is written down with its reason (LESSONS_LEARNED.md) and is fixed only if it blocks the lap. Not in the first lap unless blocked: fixing the weak tools, replacing triples, the change lexicon, the Opus picker running unattended.</p>
<p><b>Lap checklist:</b> (1) evidence pool over the historical feed, with label strength: done (20,000 articles in 243 s, 92.0% with at least one proved item; runs/harvest/pool_v1/summary.json). (2) live path uses span rules and the sparse heads behind a switch: done. (3) models and teacher answer what is left: teacher part waits on your yes (Track C). (4) retrain: waits on your yes (Track D). (5) score on outside anchors and four numbers per head on the Reading gates page: done. (6) the advisor picks the next change and it is recorded: advisor ready.</p></div>\n{todohtml}\n<div class="act"><div class="kick">Words</div><h2>What the terms mean</h2><p></p></div>

<dl><dt>BitMob toolchain</dt><dd>The set of tools that read the text with fixed rules, listed one by one in Act 1. Each has a point, a definition and a measured answer to "does it add value".</dd>
<dt>BitMob Solver</dt><dd>The whole chain: rules and tools plus BitMob models. Code: analyze2.py.</dd>
<dt>BitMob model</dt><dd>One of our small trained models that runs on a normal CPU.</dd>
<dt>Rules</dt><dd>Fixed instructions. Same input, same output.</dd>
<dt>Trained model</dt><dd>Learned from labelled examples. It can be wrong in ways nobody wrote down.</dd>
<dt>Label</dt><dd>The right answer for one example, from a person or from Claude.</dd>
<dt>Stated fact</dt><dd>A fact written in the text that passed all four checks.</dd>
<dt>Abstain</dt><dd>Decline to answer, and say why.</dd></dl>
<p class="src"><a href="../state/index.html">Pulse state</a> · <a href="../gates/index.html">Gates</a> · <a href="../decider/index.html">Decider</a></p>
</main></body></html>"""
open("/workspace/demo/mockups/solver/index.html", "w", encoding="utf-8").write(page); print("ok", len(page))
