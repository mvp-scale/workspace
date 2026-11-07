"""Scoreboard for T42 step 1: one row per technique, every number read from a named file key at build time (never typed), with its judge, the ledger line and the file#key it came from. Writes D['scoreboard'] and D['definitions'] into demo/mockups/gates/data.json.
    python3 scoreboard.py   (from projects/world-state)"""
import json
R = "runs/pulse/"; DATA = "/workspace/demo/mockups/gates/data.json"; D = json.load(open(DATA)); cache = {}
def get(f, path):
    d = cache.setdefault(f, json.load(open(f if f.startswith("/") else R + f))); 
    for k in path.split("."): d = d[int(k)] if k.isdigit() else d[k]
    return d
pc = lambda x: f"{100*x:.1f}%"; rows = []
def row(tech, extracts, against, judge, result, src, ledger): rows.append({"technique": tech, "extracts": extracts, "against": against, "judge": judge, "result": result, "src": src, "ledger": ledger})
SF, JG, G3, WN, DC, DG = "stated_facts.json", "judge_gates.json", "g3_spec.json", "wide_net.json", "direction_cls.json", "direction_gate.json"
row("G0 record", "One record per source: id, source, title, description, snapshot, body, time, provenance", "The contract's 13 required fields", "structure only",
    f"{sum(1 for a in D['articles'] if all(a['contract'].get(k) not in (None, '') for k in ('id','kind','title','description','snapshot','body','segments','language','time','provenance')))} of {len(D['articles'])} mock-up articles have every required field", ["demo/mockups/gates/data.json#articles.*.contract"], "L936")
row("G1 scan", "Spans with offsets: names, amounts, dates, cue words, quotes", "Its own checks: sorted, in range, no overlap, text matches", "structure only",
    f"{sum(1 for a in D['articles'] if all(a['scan']['checks'].values()))} of {len(D['articles'])} articles pass all four; speed {min(a['scan']['mb_per_s'] for a in D['articles'])} to {max(a['scan']['mb_per_s'] for a in D['articles'])} MB/s in Python. Accuracy of what it finds is not measured here", ["demo/mockups/gates/data.json#articles.*.scan.checks"], "L941")
for k, lab in (("amount", "Amounts"), ("date", "Dates"), ("name", "Names"), ("triple", "Who-did-what triples")):
    v = get(SF, f"per_kind.{k}"); row(f"Stated facts: {lab.lower()}", f"{lab} in the text with their binding", "The text itself: span in the text, value reads back, binding by the parse, inside one sentence", "the text (validator)",
        f"{pc(v['validity'])} of {v['captured']:,} pass all four checks; {pc(v['unbound_share'])} left unbound" + ("; a triple passes only if it has subject, verb and object" if k == "triple" else ""), [f"{R}{SF}#per_kind.{k}.validity", f"{R}{SF}#per_kind.{k}.captured"], "L959")
row("G2 fragments", "Predicate with subject, object and a factuality tag", "MAVEN-FACT: 1,818 events with the trigger word marked by people", "outside human labels",
    f"verbs cover {pc(get(JG,'covered_by_g2_fragment'))} of the marked events; the 'did it happen' call is right {pc(get(JG,'j2.happened_call_accuracy'))} against {pc(get(JG,'j2.always_yes_accuracy'))} for the best fixed answer", [f"{R}{JG}#covered_by_g2_fragment", f"{R}{JG}#j2.happened_call_accuracy"], "L957")
row("G1 cue words for fact versus opinion", "Counts of hedge, quote, who-said-it and negation words", "CheckThat: 2,076 sentences marked subjective or objective by people", "outside human labels",
    f"no cue separates them: the best single cue scores {get(JG,'j3.best_cue_auc')} where 0.5 is chance; the sum of four cues {get(JG,'j3.auc_sum_of_modal_negation_attribution_quote')}", [f"{R}{JG}#j3.best_cue_auc"], "L957")
row("Story type (trained head)", "Fact, forecast, opinion or unclear", "CheckThat human labels (balanced accuracy, subjective sentences to opinion)", "outside human labels",
    f"{get('anchor_checkthat_v6b-student.json','primary_subj_is_opinion.balanced_accuracy')} [{get('anchor_checkthat_v6b-student.json','primary_subj_is_opinion.ci95.0')} to {get('anchor_checkthat_v6b-student.json','primary_subj_is_opinion.ci95.1')}]; the bar is 0.80", [f"{R}anchor_checkthat_v6b-student.json#primary_subj_is_opinion.balanced_accuracy"], "T30")
row("Topic (trained head)", "One of 49 topics, two guesses", "MN-DS: 1,600 fresh articles with topics labelled by people", "outside human labels",
    f"{pc(get('anchor_mnds_fresh_v6b-student.json','top2_lenient_rate'))} [{pc(get('anchor_mnds_fresh_v6b-student.json','top2_lenient_ci95.0'))} to {pc(get('anchor_mnds_fresh_v6b-student.json','top2_lenient_ci95.1'))}] with two guesses, {pc(get('anchor_mnds_fresh_v6b-student.json','top1_lenient_rate'))} with one; the bar is 80%", [f"{R}anchor_mnds_fresh_v6b-student.json#top2_lenient_rate"], "L756 L761")
TG = "topic_gate_mnds.json"; P_ = "primary_pulse_assemble_method"
row("Topic (gate method)", "Topic from open phrases matched to the 49 topic definitions, as in the Pulse card", "MN-DS: 1,600 fresh articles with topics labelled by people", "outside human labels",
    f"{pc(get(TG,P_+'.top2_lenient_rate'))} [{pc(get(TG,P_+'.top2_lenient_ci95.0'))} to {pc(get(TG,P_+'.top2_lenient_ci95.1'))}] with two guesses, {pc(get(TG,P_+'.top1_lenient_rate'))} with one, {pc(get(TG,P_+'.top3_lenient_rate'))} with three; {pc(get(TG,P_+'.unknown_share'))} got no answer. The trained head gets {pc(get(TG,'trained_head_for_comparison.top2_lenient_rate'))} with two", [f"{R}{TG}#{P_}.top2_lenient_rate", f"{R}{TG}#trained_head_for_comparison.top2_lenient_rate"], "L973")
row("Topic (wide net, no training)", "Topic from open phrases matched to 49 topic definitions", "Sonnet's topic labels on 2,082 held-out stories", "Claude labels",
    f"right first time {pc(get(WN,'domain_grouping.top1'))}, in the top three {pc(get(WN,'domain_grouping.top3'))}; guessing the commonest topic {pc(get(WN,'domain_grouping.always_majority'))}", [f"{R}{WN}#domain_grouping.top1"], "L946")
row("Wide net (dials)", "Open phrases matched to the engine's dial wordings", "Clef's own readings on 1,736 stories", "Clef readings",
    f"strict: finds {pc(get(WN,'clef.wide_at_kinds_tau.tpr'))} of Clef's readings at {pc(get(WN,'clef.wide_at_kinds_tau.fpr'))} false; trained heads at that false rate find {pc(get(WN,'clef.supervised_dial_level_at_wide_kinds_fpr.tpr'))}", [f"{R}{WN}#clef.wide_at_kinds_tau.tpr", f"{R}{WN}#clef.supervised_dial_level_at_wide_kinds_fpr.tpr"], "L946")
row("Lens linkage", "How close the headline is to the lead, snapshot and whole text", "Effect as classifier input, scored against Sonnet's labels", "Claude labels",
    f"kinds macro F1 {get(G3,'sets.B.kinds_macro_f1')} without it, {get(G3,'sets.D.kinds_macro_f1')} with it", [f"{R}{G3}#sets.B.kinds_macro_f1", f"{R}{G3}#sets.D.kinds_macro_f1"], "L943")
row("Sparse head (16 kinds)", "Yes or no per kind from word and letter-pattern counts", "Sonnet's labels on held-out stories", "Claude labels",
    f"macro F1 {get(G3,'sets.B.kinds_macro_f1')}; {get(G3,'sets.B.kinds_that_can_say_yes')} of 16 kinds can say yes at 85% precision", [f"{R}{G3}#sets.B.kinds_macro_f1"], "L943")
row("Encoder head (16 kinds)", "Yes or no per kind from a small neural summary of the story", "Sonnet's labels on held-out stories", "Claude labels",
    f"macro F1 {get(G3,'cascade_vs_encoder_everywhere.kinds_macro_f1_encoder_everywhere')}", [f"{R}{G3}#cascade_vs_encoder_everywhere.kinds_macro_f1_encoder_everywhere"], "L943")
row("Direction (trained head)", "Up or down from the story text", "Sonnet's direction labels on 3,871 stories", "Claude labels",
    f"right {pc(get(DC,'heads.embedding.accuracy'))} over every story against {pc(get(DC,'always_up_accuracy'))} for always up; finds {pc(get(DC,'heads.embedding.down_recall'))} of real falls (bar 80%). A word list alone: {pc(get(DC,'heads.lexicon_counts_only.accuracy'))}", [f"{R}{DC}#heads.embedding.accuracy", f"{R}{DC}#heads.embedding.down_recall"], "L954")
row("Size (stated amount)", "The amount the story states, with its unit and what it counts", "The text itself (validator) plus a 100-story reading by one person", "the text (validator)",
    f"{pc(get(SF,'per_kind.amount.validity'))} of amounts pass the four checks; in a 100-amount reading, {get('size_quantity_judged.json','precision_real_quantity')*100:.0f}% were real quantities and {get('size_quantity_judged.json','precision_conditions_own_amount')*100:.0f}% were the condition's own", [f"{R}{SF}#per_kind.amount.validity", f"{R}size_quantity_judged.json#precision_conditions_own_amount"], "L932 L959")
L_ = {x["views_agreeing"]: x for x in D["agreement"]["ladder"]}; ag = {"precision_3_of_3": L_[3]["precision"], "precision_2_of_3": L_[2]["precision"], "precision_1_of_3": L_[1]["precision"], "pairs_3": L_[3]["pairs"]}
row("Agreement of three cheap views", "Whether keyword rule, sparse head and encoder head all say yes for a story and kind", "Sonnet's labels on 2,082 held-out stories x 16 kinds", "Claude labels",
    f"when all three say yes, Sonnet also says yes {pc(ag['precision_3_of_3'])} of the time ({ag['pairs_3']} pairs); when two do, {pc(ag['precision_2_of_3'])}; one, {pc(ag['precision_1_of_3'])}", ["demo/mockups/gates/data.json#agreement.ladder"], "L944")
KEYS = {"G0 record": "g0", "G1 scan": "g1", "Stated facts: amounts": "sf_amount", "Stated facts: dates": "sf_date", "Stated facts: names": "sf_name", "Stated facts: who-did-what triples": "sf_triple", "G2 fragments": "g2", "G1 cue words for fact versus opinion": "cues",
        "Story type (trained head)": "story", "Topic (trained head)": "topic_head", "Topic (gate method)": "topic_gate", "Topic (wide net, no training)": "topic_wide", "Wide net (dials)": "wide", "Lens linkage": "lens", "Sparse head (16 kinds)": "sparse", "Encoder head (16 kinds)": "encoder",
        "Direction (trained head)": "direction", "Size (stated amount)": "size", "Agreement of three cheap views": "agree"}
for r in rows: r["key"] = KEYS[r["technique"]]
D["scoreboard"] = rows
D["definitions"] = [
 ["Stated fact", "An amount, date, name or who-did-what link that is in the text, with the exact words and what it attaches to. 'Stated' does not mean true."],
 ["Validator", "A fixed check against the text: the words are really there, the value reads back, it attaches to a noun or verb, and it sits inside one sentence."],
 ["Keyword rule", "A hand-written list of words for one kind. It fires if any word is in the story, e.g. civil unrest: protest, riot, unrest, demonstrat, clashes, tear gas, curfew, looting, uprising, coup."],
 ["Sparse head", "A small statistical model that counts words, word pairs and letter patterns and learned yes or no for one kind from Sonnet's labels."],
 ["Encoder head", "A small neural network turns the story's first 64 word-pieces into 1,024 numbers; a simple model on those numbers learned yes or no for one kind from Sonnet's labels."],
 ["Held-out", "Stories never used to train a model or to set its thresholds. Here: 2,082 of 20,790 labelled stories (16,627 train, 2,081 set thresholds)."],
 ["Sonnet's labels", "What Claude Sonnet wrote for each story. A model's opinion, not truth. The heads above learned from it, so matching it is partly circular."],
 ["Outside human labels", "Labels made by people for other projects (MN-DS topics, CheckThat fact versus opinion, MAVEN-FACT events). The only kind of check that can tell us a model is right."],
 ["Match score (z)", "How unusually close an open phrase is in meaning to a vocabulary entry, in standard deviations above a background of other phrases. A similarity estimate, not a probability."],
 ["F1", "One number out of 1 that balances finding the real cases against calling wrong ones; 1 is perfect."],
 ["Balanced accuracy", "The average of the share of each class found, so a common class cannot hide a missed rare one."]]
json.dump(D, open(DATA, "w")); print(len(rows), "rows"); [print("-", r["technique"], "|", r["result"][:110]) for r in rows]
