"""Builds demo/mockups/state/index.html: the story of Pulse extraction, one point per chapter.
Every number is read from a result file at build time. Every chapter ends with 'How we know': the file, Lean theorem, ledger line or MM3 run behind it.
    python3 pulse_state_page.py   (from projects/world-state)"""
import json, html, os
R = "runs/pulse/"; OUT = "/workspace/demo/mockups/state/index.html"; E = html.escape; _c = {}
def F(f):
    if f not in _c: _c[f] = json.load(open(R + f))
    return _c[f]
class Ch:
    def __init__(s): s.src = []; s.n_ = 0
    def v(s, f, *path):
        x = F(f)
        for p in path: x = x[p]
        s.src.append((f + "#" + ".".join(map(str, path)), x)); return x
    def n(s, f, *path, fmt="{:.3f}", scale=1):
        x = s.v(f, *path); return E(fmt.format(x * scale))
    def bar(s, label, f, *path, lo=None, hi=None, note="", hl=False):
        x = s.v(f, *path); r = ""
        if lo: lo_v = s.v(f, *lo); hi_v = s.v(f, *hi); r = f' <span class="rg">range {lo_v:.3f} to {hi_v:.3f}</span>'
        return (f'<div class="b{" hl" if hl else ""}"><span class="bl">{E(label)}</span><span class="tr"><i style="width:{x*100:.1f}%"></i></span>'
                f'<span class="bv">{x:.3f}</span>{r}{(" <span class=nt>" + E(note) + "</span>") if note else ""}</div>')
    def know(s, extra):
        li = "".join(f"<li>{E(a)} <span class='ref'>{E(b)}</span></li>" for a, b in extra)
        fs = "".join(f"<li><span class='ref'>{E(k)}</span> = {E(str(round(v,4)) if isinstance(v, float) else str(v))}</li>" for k, v in dict(s.src).items())
        return f'<div class="know"><b>How we know</b><ul>{li}{fs}</ul></div>'
P = []
def chap(num, point, body, ch, extra): P.append(f'<section class="ch"><div class="num">{num}</div><div class="cb"><h2>{E(point)}</h2>{body}{ch.know(extra)}</div></section>')
P.append("""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pulse state</title><link rel="stylesheet" href="../mock.css">
<style>
 main{max-width:860px;margin:0 auto;padding:14px 16px 56px} h1{margin:0 0 4px;font-size:24px;line-height:1.25}
 .lead{color:var(--ink-2);margin:0 0 6px;font-size:15px;line-height:1.55} .rule{margin:10px 0 18px;padding:8px 12px;border-left:3px solid var(--accent);background:var(--surface-2);border-radius:6px;font-size:13px;color:var(--ink-2)}
 .ch{display:flex;gap:14px;margin:0 0 26px} .num{flex:0 0 34px;height:34px;border-radius:50%;background:var(--accent);color:#fff;font:600 16px var(--sans);display:flex;align-items:center;justify-content:center}
 .cb{flex:1 1 auto;min-width:0} h2{margin:4px 0 8px;font-size:19px;line-height:1.35} .cb p{margin:0 0 10px;font-size:15px;line-height:1.6;color:var(--ink-2)}
 .b{display:flex;flex-wrap:wrap;align-items:center;gap:4px 10px;margin:6px 0;font-size:13px} .bl{flex:0 0 230px;color:var(--ink-2)} .tr{flex:1 1 200px;height:12px;background:var(--surface-2);border:1px solid var(--line);border-radius:6px;position:relative;min-width:120px}
 .tr i{position:absolute;left:0;top:0;bottom:0;background:var(--s3);border-radius:6px;opacity:.55} .hl .tr i{opacity:1;background:var(--accent)} .bv{font:600 13px var(--mono);color:var(--ink)} .rg,.nt{font-size:12px;color:var(--ink-3)}
 .know{margin:12px 0 0;padding:8px 12px;background:var(--surface);border:1px solid var(--line);border-radius:8px;font-size:12px;color:var(--ink-3)} .know ul{margin:4px 0 0;padding-left:18px} .know li{margin:2px 0;line-height:1.5} .ref{font-family:var(--mono);font-size:11px;color:var(--ink-2)}
 table.t{width:100%;border-collapse:collapse;font-size:13px;margin:6px 0 10px} table.t th{text-align:left;font:600 11px var(--sans);letter-spacing:.07em;text-transform:uppercase;color:var(--ink-3);padding:3px 8px 3px 0;border-bottom:1px solid var(--line-2)}
 table.t td{padding:6px 10px 6px 0;border-bottom:1px solid var(--line);vertical-align:top;color:var(--ink-2);line-height:1.5} td b{color:var(--ink)} .tag{font-size:12px;font-weight:600;border-radius:999px;padding:0 8px;border:1px solid var(--line-2);white-space:nowrap}
 .gl dt{font-weight:600;color:var(--ink);margin-top:8px;font-size:14px} .gl dd{margin:2px 0 0;color:var(--ink-2);font-size:14px;line-height:1.55} .nav a{margin-right:16px;font-size:13px} .ne li{margin:4px 0;font-size:14px;color:var(--ink-2);line-height:1.55}
</style></head><body><main>
<h1>Pulse: how we read a news story, step by step</h1>
<p class="lead">The goal is to read a news article on an ordinary computer and answer five questions about it, fast and honestly. This page tells how far we got, in order. Each chapter makes one point.</p>
<p class="nav"><a href="../decider/index.html">Decider walk-through</a><a href="../gates/index.html">Reading gates scoreboard</a><a href="http://localhost:18766/#engine">Ledger and engine page</a></p>
<p class="lead"><a href="../solver/index.html">The BitMob Solver: watch real articles go through each step</a></p>
<div class="rule"><b>The rule for this page:</b> a statement is here only if a file, a Lean proof, a ledger line or an MM3 run backs it, and that source is listed under it. What we believe but cannot show is kept apart in chapter 8, under "not established".</div>""")

c = Ch()
chap(1, "The goal: five answers from every article, on a normal CPU", '<p>For each news article we want five answers: what kind of story it is, what topic, what changed and in which direction, how big it is, and a few traits. The answers must come quickly from a computer without a graphics card. A small model, called the BitMob Domain (v6b), was built to do this.</p><p>One more rule: an answer only counts if we can show evidence that it is right. Claude agreeing with it does not count as evidence.</p>', c,
     [("The goal and the CPU-only rule", "/workspace/CLAUDE.md, section Goal"), ("The five answers and the done rule", "knowledge_pipeline/playbook/00-knowledge-pipeline-v1.md; projects/world-state/lean/PulseDone.lean"), ("The BitMob Domain (v6b-student), 22.6M parameters, CPU only", "demo/models.json, code PULSEB")])

c = Ch()
n_lim = c.n("input_length_check.json", "64", "items_at_the_limit", fmt="{:,.0f}"); n_all = c.n("fulltext_topic_flat.json", "n", fmt="{:,.0f}")
chap(2, "We found the reader was only reading the start of each story", f'<p>The BitMob Domain (v6b) reads at most 64 word pieces, which is about the headline and the first lines. It was also taught on headline plus a short teaser, not on whole articles. On our test set, {n_lim} of {n_all} items were already cut off at that limit.</p><p>Real articles are much longer, so the reader was missing most of the story. Making the limit bigger on these short test items did not help much, because the items were short to begin with.</p>', c,
     [("The reader was taught on headline plus short description", "ledger L774, engine card, field 'domain'"), ("The limit of 64 word pieces is the max_pieces setting; it is the key '64' in input_length_check.json", "projects/world-state/article_reader.py and runs/pulse/input_length_check.json")])

c = Ch()
b = c.bar("Headline only", "fulltext_topic_flat.json", "title_only") + c.bar("Headline plus teaser (as built)", "fulltext_topic_flat.json", "title_teaser") + c.bar("Whole article", "fulltext_topic_flat.json", "whole_article", lo=("whole_article_low",), hi=("whole_article_low",), hl=True)
b = c.bar("Headline only", "fulltext_topic_flat.json", "title_only") + c.bar("Headline plus teaser (as built)", "fulltext_topic_flat.json", "title_teaser") + c.bar("Whole article", "fulltext_topic_flat.json", "whole_article", hl=True)
chap(3, "Reading the whole article helps the BitMob Domain (v6b), by about three points", '<p>"Right within two guesses" means the correct topic is one of the reader\'s two best guesses. We scored the reader on ' + n_all + ' articles whose topics were labelled by people. Reading the whole article scored ' + c.n("fulltext_topic_flat.json", "whole_article") + ' against ' + c.n("fulltext_topic_flat.json", "title_teaser") + ' for headline plus teaser.</p>' + b + '<p>The gain is ' + c.n("fulltext_topic_flat.json", "diff_whole_minus_teaser") + ', and the likely range is ' + c.n("fulltext_topic_flat.json", "diff_low") + ' to ' + c.n("fulltext_topic_flat.json", "diff_high") + '. It is real but small. We also found the headline was pushing some body text out of each window; fixing that changed the score by ' + c.n("fulltext_fixed.json", "diff", fmt="{:+.4f}") + ', so it did not matter.</p>', c,
     [("Scored against human topic labels (MN-DS), mapped to our topics", "projects/world-state/fulltext_topic.py; ledger L1007 for the window fix")])

c = Ch()
b = c.bar("BitMob Domain (v6b), whole article", "sparse_baseline_flat.json", "neural_whole_top2") + c.bar("Plain keyword model, whole article", "sparse_topic_human.json", "word12_top2", lo=("word12_top2_range", 0), hi=("word12_top2_range", 1), hl=True)
c2 = Ch()
b2 = c2.bar("Publishers it never saw", "sparse_leak_check.json", "publisher_holdout_within_two", lo=("publisher_holdout_low",), hi=("publisher_holdout_low",)) if False else c2.bar("Publishers it never saw", "sparse_leak_check.json", "publisher_holdout_within_two", note="low end " + str(c2.v("sparse_leak_check.json", "publisher_holdout_low"))) + c2.bar("A later time period", "sparse_leak_check.json", "time_holdout_within_two", note="low end " + str(c2.v("sparse_leak_check.json", "time_holdout_low")))
c2.v("sparse_leak_check.json", "near_duplicate_share_cos_0_8"); c.src += c2.src
chap(4, "A plain keyword model, taught on human labels, did better", '<p>We then tried the simplest thing: count words and word pairs, and let a basic statistical model learn from ' + c.n("sparse_topic_human.json", "n_train", fmt="{:,.0f}") + ' articles that people had labelled. It is not a neural network. It takes about ' + c.n("sparse_topic_human.json", "word12_median_us", fmt="{:.0f}") + ' microseconds an article.</p>' + b + '<p>It might be a trick of the test, so we checked. We removed three whole publishers from training and tested only on them, and we trained on earlier months and tested on later ones.</p>' + b2 + '<p>Three limits. It predicts the 16 topics in the human data, not our 49. The test articles are 2019 UK and Russian outlets. And part of the gap may simply be that it was taught on human labels while the BitMob Domain (v6b) was taught on Claude\'s.</p>', c,
     [("Same test articles for both readers. It predicts the 16 MN-DS categories (gold_T28b.json, field l1) and the test articles are 2019 UK and Russian outlets (MN-DS train.jsonl source and date fields)", "projects/world-state/sparse_topic_human.py; ledger L1008 and L1010"), ("Leak checks. The share of test articles with a near-copy in training was above the 5 percent that was predicted: a miss", "projects/world-state/sparse_leak_check.py; ledger L1010")])

c = Ch()
b = c.bar("Answered when sure: share of articles", "sparse_selective.json", "by_line", "0.7", "share") + c.bar("Right within two on those", "sparse_selective.json", "by_line", "0.7", "top2_right", hl=True) + c.bar("Right within two on the ones held back", "sparse_selective.json", "abstained_top2_right_at_070")
chap(5, "Knowing when to trust an answer is done by proved rules, not by guessing", '<p>If the keyword model only answers when its two best guesses carry at least 70 percent of its confidence, it answers ' + c.n("sparse_selective.json", "by_line", "0.7", "share", fmt="{:.0f}%", scale=100) + ' of articles and is right on ' + c.n("sparse_selective.json", "by_line", "0.7", "top2_right", fmt="{:.0f}%", scale=100) + ' of those. The rest go on to the BitMob Domain (v6b).</p>' + b + '<p>The rules that decide what counts as evidence, and what may become training data, are written in Lean 4 and checked by the computer. They say, for example, that Claude agreeing with itself is never evidence, and that an answer from a trained model is never used as a training label. The same rules are copied into Rust, and every build replays all ' + c.n("rust_decider_flat.json", "lean_cases", fmt="{:.0f}") + ' of Lean\'s cases; one deliberately wrong rule made the build fail.</p><p>One topic misses its bar: arts, culture, entertainment and media reaches only ' + c.n("sparse_selective.json", "per_category_top2", "arts, culture, entertainment and media", fmt="{:.2f}") + ', so topic still counts as provisional.</p>', c,
     [("Claude agreement is never admissible", "lean/Admit.lean:33, theorem claude_agreement_never_admissible; MM3-0621"), ("Trained-model answers never become training labels", "lean/Decide.lean:55, head_never_trains; :57 provisional_never_trains; :59 train_label_needs_full_answer"), ("What a number does and does not license", "lean/Certainty.lean; MM3-0620"), ("Rust copy and the failing-build test", "projects/world-state/rust_pulse/build.rs; ledger L1013"), ("Test of the confidence line, prediction made first (one part missed). The 70 percent line is the key by_line.0.7 in sparse_selective.json", "ledger L1011, L1012")])

c = Ch()
chap(6, "Speed: about 77 ms an article today, and why Rust alone will not make it a millisecond", '<p>The whole tool takes a median ' + c.n("timing_analyze2.json", "t8_total_median", fmt="{:.0f}") + ' ms an article on 8 threads and ' + c.n("timing_analyze2.json", "t1_total_median", fmt="{:.0f}") + ' ms on one. Of that, the BitMob Domain (v6b) takes ' + c.n("timing_analyze2.json", "t8_reader_median", fmt="{:.0f}") + ' ms and the number-and-date solver, mostly the spaCy parser, takes ' + c.n("timing_analyze2.json", "t8_solver_median", fmt="{:.0f}") + ' ms. The decider is ' + c.n("timing_analyze2.json", "t8_decider_median", fmt="{:.3f}") + ' ms.</p><p>The Rust decider takes ' + c.n("rust_decider_flat.json", "ns_per_call", fmt="{:.0f}") + ' nanoseconds, but nothing calls it yet, and it was never the slow part. The keyword model is about ' + c.n("sparse_topic_human.json", "word12_median_us", fmt="{:.0f}") + ' microseconds. A rule-based stand-in for spaCy took ' + c.n("binder_rules.json", "rule_ms_median", fmt="{:.1f}") + ' ms but agreed with spaCy only ' + c.n("binder_rules.json", "amount_agree") + ' of the time on amounts, below the ' + c.n("binder_rules.json", "amount_baseline_all_stated_agree") + ' you get by calling every fact stated, so it is not good enough.</p>', c,
     [("Timing method: 200 reference articles, after 3 warm-up runs", "projects/world-state/timing_analyze2.py"), ("The rule stand-in for spaCy missed its pre-registered bar", "ledger L1006")])

c = Ch()
FT = F("field_table.json"); PLAIN = {0: "No evidence we can accept yet", 1: "Too few examples", 2: "Evidence exists, below the bar", 3: "Meets the bar"}
WHY = {"story_type": "Its judge, CheckThat, measures fact versus opinion, not our four story types.", "topic": "Works, and the keyword model scores higher, but one topic is under the bar and the old table still holds short-text numbers.", "change": "Judged only against Claude's labels, which cannot count. The set of changes is not decided.", "size": "The solver can show an amount is written in the text. Whether 'stated amount' is the contract is your decision.", "traits": "No result is wired into the tool yet."}
rows = ""
for k in ("story_type", "topic", "change", "size", "traits"):
    c.src.append((f"field_table.json#{k}.marker", FT[k]["marker"])); c.src.append((f"field_table.json#{k}.judge_name", FT[k]["judge_name"])); rows += f"<tr><td><b>{E(k.replace('_', ' '))}</b></td><td><span class='tag'>{E(PLAIN[FT[k]['marker']])}</span></td><td>{E(FT[k]['judge_name'])}</td><td>{E(WHY[k])}</td></tr>"
chap(7, "Where the five answers stand today", '<table class="t"><tr><th>Answer</th><th>Status</th><th>What it is judged against (from the field table)</th><th>Our reading, not a result</th></tr>' + rows + '</table><p>The status is the Lean evidence filter\'s verdict on the numbers in the field table. A field is done only when it meets the bar.</p>', c,
     [("What 'done' requires", "lean/PulseDone.lean"), ("The filter that produced the status", "lean/Admit.lean; projects/world-state/route.py builds the table; ledger L982")])

P.append("""<section class="ch"><div class="num">8</div><div class="cb"><h2>Not established, and what comes next</h2>
<p>These are beliefs or plans. Nothing below is a result.</p><ul class="ne">
<li><b>Prediction:</b> with the keyword model in front, Rust for the rules and your NER in place of spaCy, most articles would take a few milliseconds. This has not been built or measured.</li>
<li><b>Not built:</b> the Rust version of cleaning, windows, validator and scan; the step that retrains the keyword model on harvested labels; a drift check on live news; human-labelled data with full text for story type, change, size and traits.</li>
<li><b>Waiting on you:</b> whether "stated amount" is the contract for size; the set of changes; whether CheckThat is the right judge for story type; the topic list, 16 or 49; reading whole articles by default in the BitMob Domain (v6b) service; sharing NEEER.</li>
<li><b>Not yet checked by MM3:</b> this page itself. A verdict on its claims comes next.</li></ul></div></section>
<section class="ch"><div class="num">?</div><div class="cb"><h2>Words used on this page</h2><dl class="gl">
<dt>BitMob Domain (v6b-student)</dt><dd>The small neural model, registry code PULSEB, that reads a story and scores story type, topic and more. It runs on a CPU.</dd>
<dt>Keyword model</dt><dd>Counts words and word pairs and uses a basic statistical model. Not in the registry yet.</dd>
<dt>Solver</dt><dd>Rules plus the spaCy parser. It finds amounts and dates and checks the text really says them. It learns nothing.</dd>
<dt>Evidence filter and decider</dt><dd>The Lean-proved rules that say whether a number counts as evidence, and whether to answer or abstain on one article.</dd>
<dt>Human labels, Claude labels</dt><dd>Human labels come from public datasets labelled by people (MN-DS here). Claude labels were written by Claude Sonnet and Haiku to teach the reader; agreement with them is not accuracy.</dd>
<dt>Abstain</dt><dd>Decline to answer and send the article somewhere else.</dd>
<dt>Clef, BitMob classifier</dt><dd>Clef is the GPU model the World engine uses today. The BitMob classifier is an older CPU path. Neither is measured on this page.</dd></dl></div></section>
</main></body></html>""")
os.makedirs(os.path.dirname(OUT), exist_ok=True); open(OUT, "w").write("\n".join(P)); print("wrote", OUT)
