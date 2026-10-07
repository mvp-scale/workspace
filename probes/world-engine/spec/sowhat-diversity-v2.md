# So-what v2 diversity harness (HARNESS-2): results

Question: does the shipped v2 composer meet the targets committed in `so-what-v2-design.md` section 13, measured the same way as the v1 baseline (`sowhat-diversity.md`)? Nothing existing was changed. New files only: `tests/sowhat_diversity/v2/` (`run_requests.py`, `compose_runs.js`, `analyse.py`, `extras.py`; the 120 stories are the same `stories.json`), this report, and raw outputs in the session scratchpad `diversity2/` (`sNNN.resp.json`, `test1.json`, `test2.json`, `metrics.json`, `extras.json`, `extras_strict.json`).

Reproduce: start an engine (`WE_RULES=rules_v2 ./service.sh start world --port 8141`), `python3 run_requests.py`, `node compose_runs.js`, `python3 analyse.py`, `python3 extras.py` (and `python3 extras.py strict`). The engine on :8141 was stopped at the end.

## What was run

- **TEST 1, real run.** The same 120 stories, posted to `/request` (mode event), 3 in parallel. HTTP failures 0 of 120. Each story composed at world focus and two more foci (hardest-hit country if the entry is a country, hardest-hit audience, a second audience otherwise): 120 world outputs, 360 over all foci. Tables are the live `GET /sowhat` (version 2: 11 frames, 79 hooks, 92 templates, 450 lexicon plus 133 v1 lexicon rows), checked row-count-equal to the CSVs. The composer was fed what the page feeds it (story, places, rank, significance, significance_rows, if_true, readings, weight, text), with story.seed from the backend.
- **TEST 2, cross-combination of real components.** 46 base responses, evenly spaced over the 120 real ones. Rows, places, rank, if_true, weight, seed and entry from base A; frame, trigger, certainty, scale and topic from base B; 2070 pairs at world focus, 2002 returned a statement. Combinations are not coherent stories (a trigger about one thing with a response to another), so incoherence here only measures structure. Different from v1: v1 used 22 golden fixtures plus 24 review responses; these bases are the 120 real responses (no fixtures exist for if_true).
- **Anchor checker** (`extras.py`): independent of the composer. It re-reads each response and, for every statement with an anchor, (1) parses every digit run in the headline and line 2, (2) finds the source number by looking up the anchor's decision in the numbers the rule says it must use (`if_true.places` when the story is hedged and weighted under 1, otherwise `places`; A3 also needs the world row), at the focus row or the entry row, (3) recomputes the rounded value and the threshold, (4) checks the verb is the lexicon `act` verb for that decision and sign, that the anchored decision is not under half of the row's biggest move, and that a hedged anchor carries a modal. It flags any digit that is not the shown value, any statement with a second figure, any anchor under its threshold, and any digit in a statement without an anchor.

## Targets table (world focus, n=120)

| Target (design 13) | v1 baseline | Committed | Measured | |
|---|---|---|---|---|
| top three-word opener share | 13.5% | <= 5% | 3.3% ("taking the writer/forecast", "hospitals and clinics", 4 each) | PASS |
| distinct three-word openers per 100 stories | 38 | >= 60 | 68 (82 distinct in 120; 115 over all 360) | PASS |
| hook evenness: top hook share, any family with >= 10 uses | n/a | <= 30% | by hook phrasing (the id the composer picks, e.g. IF01.5): IF 20% (n=40), WHO_LOCAL 23.5% (17), TRIGGER 15.4% (13). By hook row: **IF01 = 75% of IF** (30 of 40) | PASS by phrasing, FAIL by row (see hot spot 1) |
| top body share (all statements) | 16% | <= 15% | 12.5% (B32, 15 of 120); 11.1% over all foci | PASS |
| quiet forms excluding true no-impact (NOTHING, QUIET_VAGUE) | 47% | <= 40% | 30.8% (37 of 120); 33.0% of counted stories. All quiet 45 (37.5%) | PASS |
| quiet forms (non-vague) containing the trigger clause | 0 (NO-O) | 100% | 37 of 37 have a trigger beat | PASS |
| repeats of any one quiet sentence | 16 | <= 3 | 2 | PASS |
| random triples sharing any 5-word run | 37.5% | <= 15% | 7.0% (all foci 7.0%; TEST 2 13.5%) | PASS |
| same-frame triples sharing any 5-word run | 60.3% | <= 25% | 17.2% (all foci 17.2%; TEST 2 27.3%) | PASS (TEST 2 over, not the target's measure) |
| statements with an anchor | 0 | 10% to 20% | 14.2% (17; 8 in the headline; A1 10, A4 7). All foci 13.9% (50) | PASS |
| anchors that pass their significance test | n/a | 100% | 17 of 17 (50 of 50 over all foci) | PASS |
| digits not equal to the anchor's shown value | 0 | 0 | 0 untraceable. But every anchor also carries the fixed unit "100" (see anchor integrity) | PASS, with caveat |
| numbers per statement | 0 | <= 1 | one figure per statement plus the unit "every 100"; 0 statements with a second figure | PASS, with caveat |
| hushed headlines with a soft word | n/a | 100% | 31 of 31 | PASS |
| stock tails (the four retired phrases) | 17% to 41% | 0 | 0 (world, all foci, TEST 2) | PASS |
| headline words | <= 22 | <= 22 | max 22 (also in TEST 2) | PASS |
| composer nulls | 1 | 0 | TEST 1: 0 of 120 (0 of 360). TEST 2: 68 of 2070, see below | PASS on real stories |
| golden v2 cases reproduced | n/a | 33 of 33 | not re-run here (outside this brief) | NOT MEASURED |

TEST 2 nulls: 62 of 68 come from base responses that are no-impact stories (no places in the response: a harness artefact, they cannot be composed). The other 6 are real: bases s019, s081, s097 (quiet or small effect) combined with story parts of s027 (announced, weight 1) or s040 (announced, weight 0.3) return null. Probably the quiet branch for an announced story; I did not trace it. Owner: `demo/static/sowhat.js` quiet branch or `sowhat2_templates.csv` announced quiet forms (QA rows).

## Other baseline-report metrics

| | TEST 1 world (n=120) | TEST 1 all foci (n=360) | TEST 2 (n=2002) | v1 world |
|---|---|---|---|---|
| distinct 3-word openers | 82 | 115 | 155 | 45 |
| top opener share | 3.3% | 3.3% | 3.8% ("should it come" 76) | 13.5% |
| distinct bodies used (hook rows not counted) | 50 | 61 | 74 | 25 templates |
| body entropy bits (max for that count) | 5.13 (5.64) | 5.39 (5.93) | 5.32 (6.21) | 4.05 (4.64) |
| top body share | 12.5% (B32) | 11.1% | 13.6% (B11) | 16.0% |
| distinct headlines | 116 (96.7%) | 334 (92.8%) | 1337 (66.8%) | 95 (79.8%) |
| distinct line2 (incl. empty) | 25 | 58 | 101 | 35 |
| line2 empty | 75.0% | 70.8% | 71.5% | 53.8% |
| headline words median / p90 / max | 17 / 22 / 22 | 17 / 22 / 22 | 16 / 21 / 22 | 15 / 20 / 22 |
| line2 words (non-empty) median / max | 6 / 16 | 6 / 16 | 10 / 16 | 9 / 14 |
| triples with 5-word run, any pair | 7.0% | 7.0% | 13.5% | 37.5% |
| same-frame triples, same measure | 17.2% | 17.2% | 27.3% | 60.3% |
| mean pairwise trigram Jaccard, all / same frame | 0.007 / 0.019 | 0.008 / 0.018 | 0.013 / 0.028 | 0.049 / 0.094 |
| headline only, 5-gram triples all / same frame | 5.0% / 14.2% | 5.6% / 15.3% | 10.1% / 24.4% | 27.4% / 54.1% |
| "Elsewhere" tails | 0 | 0 | 0 | 20 |
| banned() hits | 0 | 0 | 5 (false positives, see defect 6) | 0 |
| quiet share | 37.5% | 46.9% | 43.7% | 53.8% |

Line 2 of 16 words is the anchor-only line 2 (limit 16 by design). Over all foci quiet is higher (46.9%) because a country or audience focus often sees nothing move; the target is stated at world focus.

Lead (hook family) at world focus: quiet 45, IF 40, WHO_LOCAL 17, TRIGGER 13, TURN 2, CONTRAST 2, SCALE 1; **STAKE, WHO_MOST and WHO_OPP 0 of 120 and 0 of 360 foci**. Only 34 of the 79 hook rows were ever used (TRIGGER 11 of 14, WHO_LOCAL 10 of 10, IF 4 of 5, CONTRAST 4 of 7, TURN 4 of 13, SCALE 1 of 8, WHO_MOST 0 of 9, WHO_OPP 0 of 6, STAKE 0 of 7). Register: hushed 31, plain 43, stark 1, quiet 45. This reflects the engine's sizes on these stories (as in v1, most are Negligible), so the stark-only SCALE, and the STAKE and WHO_MOST gates, are not exercised by this set. That is a limit of the stories, not proof the families are broken; they are untested here.

Share of statements by hook family, world focus: IF 33.3%, WHO_LOCAL 14.2%, TRIGGER 10.8%, TURN 1.7%, CONTRAST 1.7%, SCALE 0.8%, quiet 37.5% (QUIET_FORECAST 13.3%, QUIET_SMALL 11.7%, QUIET_OPINION 5.8%, QUIET_VAGUE 4.2%, NOTHING 2.5%). Hook families are not even: IF alone is one third. About a third of the stories are forecasts or opinions by design (design weak spot), which inflates IF; over all foci IF is 28.6%.

Per frame, same-frame pairs sharing 5 words (TEST 1 world): ripple 5.5% (n=30), boost 4.1%, squeeze 12.3%, relief 7.9%, scare 8.5%, plain 4.0%, shake_up 0%. TEST 2: scare 47% (n=141) is the one frame well above the rest (squeeze 13%, ripple 12%, boost 9%).

Top repeated 4-word phrases at world focus (document frequency of 120): "in every 100 people" 8 (the fixed unit), "feel it almost alone" 6, "on much as before" 6 (QS02, QA02), "though too faintly to change" 5 (QS05, QF06). Nothing is above 7%. Single words and short stock phrases at world focus: "almost alone" 10, "those living there" 10, "rein in spending" 10, "loosen their budgets" 9, "if only slightly" 7, "habits would hold" 5, "Short-lived." 5.

## Anchor integrity

Result: **no digit is untraceable, no anchor is under its threshold, no anchor contradicts the response's own numbers.** 17 anchored statements at world focus (50 over all foci), 0 flagged, 0 statements with digits and no anchor. Details of the checks: every anchor value was found as the peak of that decision at the response row (or the entry row) in the numbers the rule requires; every A4 (hedged) anchor comes from `if_true.places` and every A1 from `places`; every shown value equals the rounded peak (half up under 10, nearest 5 from 10); every A1/A4 is at least 2.0 points; the lexicon act verb for the decision and sign is in the text; every hedged anchor carries a modal ("would", "could", "will"); none is under half of the row's biggest move. All 10 A1 anchors are unhedged stories and all 7 A4 are hedged. No A3 anchor appeared (0 of 50), so A3 (the "times the world" rule) is not exercised here.

**The unit "100".** Read strictly (contract section 4: "at most one digit run per statement, and it equals the anchor's shown value"), all 17 anchored statements fail, because every sentence says "in every 100 people" or "for every 100 people". The design (section 14) says the unit repeats on purpose and treats it as a fixed unit, so my headline check does not count `every 100`. The strict result is in `extras_strict.json` (17 of 17 flagged on this alone, nothing else). Defect: the contract wording and the composer disagree. Owner: `spec/so-what-v2-contract.md` section 4 (say "one figure, plus the fixed unit 100"), or the composer should phrase the unit in words.

**Anchors that say more than the words around them.** The checker found 0 anchors the numbers do not support, but a critical read found 4 of 17 where a loud degree word sits beside a small figure: s001 "rein in spending sharply ... Roughly 3 in every 100 people in Brazil cut spending", s031 "spend a lot more ... about 4 more could loosen their budgets", s012 "rein in spending markedly ... roughly 6 more", s063 "cut back markedly ... About 7 more in every 100 people". The degree word comes from the theme, the figure from the peak decision, so the two can disagree. Owner: composer degree choice in `sowhat.js` (`putDeg`, when an anchor is shown) and `sowhat2_lexicon.csv` degree rows.

## Critical read

I read 40 random non-quiet and 20 random quiet world-focus statements (seed 2026; lists are reproducible from `test1.json`). Honest summary: the openers are varied and plain; most statements are readable and sound like a human wrote them. The recurring problems are below.

### The 10 worst-sounding statements (verbatim)

1. s031: "Taking the writer at their word, prices could fall, and people could spend a lot more. / For every 100 people, about 4 more could loosen their budgets than otherwise. Short-lived." Misleading anchor against its own words ("a lot more" versus 4 in 100); "spend more" and "loosen their budgets" say the same act twice; bare "Short-lived." Owner: `sowhat.js` degree and anchor, `sowhat2_lexicon.csv` l2_arc.
2. s001: "This squeeze stays in Brazil: shares and property should lose value, so residents rein in spending sharply and sit on their savings. / Roughly 3 in every 100 people in Brazil cut spending who otherwise would not." "Sharply" against 3 in 100; Brazil named twice; "rein in spending" then "cut spending".
3. s100: "Supply lines clog up, leaving people to spend more. / Short-lived." Misleading causal ("leaving" claims clogged supply makes people spend more; the engine's decision weights say so, a reader will not believe it). Clipped line 2. Owner: `decision_weights.csv`, `sowhat2_lexicon.csv`.
4. s051 (quiet): "Little follows from this: the news flow gets lighter and wildlife and fish stocks should decline, and routines hold." Awkward fill: two triggers joined by "and" then a third clause with "and"; a one-sentence list. Owner: `sowhat2_templates.csv` QS06.
5. s035: "As soon as it starts, pollution levels will fall: people in Thailand will rein in spending slightly. / Against that, factories will produce less." "Against that" is not an opposite (factories producing less is not a downside of pollution falling); pollution falling then cutting spending is a decision-weight artefact. Owner: `sowhat2_lexicon.csv` l2 contrast opener, `decision_weights.csv`.
6. s099: "Poland carries this one alone: wildlife and fish stocks will decline, and those living there will open their wallets. / Against that, jobs will get more secure." Wrong valence on both lines: a decline then "open their wallets"; "Against that" for an upside that is not set against anything the headline said. Stock "carries this one alone".
7. s039: "Health risks could rise if the writer is right: people in Poland could protect themselves, and hardly anyone elsewhere could." This brings back the retired "elsewhere" idea inside a body, and "could" twice reads as two separate guesses. Owner: `sowhat2_templates.csv` B13.
8. s020: "An opinion piece; if enough people agree, jobs could get less secure, and people could rein in spending and claim benefits. / Roughly 2 in every 100 people could cut spending who otherwise would not." Double modal ("could ... who otherwise would not") is a stumble, and "rein in spending" then "cut spending" repeats. Owner: `sowhat2_lexicon.csv` anchor rows (hedged "who otherwise would not").
9. s073: "Social divides should heal, and in turn people share their views less and spend slightly more." "In turn" asserts a causal chain nobody would accept, and "share their views less" after healing sounds wrong. Owner: `sowhat2_hooks.csv` TR04, decision weights.
10. s072 (quiet): "Taking the forecast at face value, government budgets would come under strain; even then, habits would hold." Stock skeleton: QF03 "Taking the forecast at face value, X; even then, habits would hold." appeared 4 of 16 quiet forecasts at world focus (12 across all foci) and "habits would hold" is an odd end for budget strain. Owner: `sowhat2_templates.csv` QF03 (needs alternates, or the composer's pick should spread over the 11 QF forms).

Other mild stock runs: "feel it almost alone" and "those living there" (10 of 17 WHO_LOCAL statements), "Sharp at first, then mostly gone" / "Short-lived." / "Felt at once, gone soon after." / "A quick jolt, soon gone." (four phrasings of one idea, 10 of the 30 line 2s at world focus), "if only slightly" (7), and verb phrases for spending (rein in, loosen, step up, open their wallets, tighten their belts).

### Do three statements in a row now sound different?

Mostly yes by words, not always by shape. Measured: random triples share a five-word run 7.0% of the time (v1 37.5%), same-frame 17.2% (v1 60.3%). Read as a human: openers differ; the verbs and sentence skeletons still repeat within a family. The worst stretch is where three hedged stories sit together. Five random consecutive triples (world focus, story order):

Triple 1 (s062 to s064)
- "Supply lines should clear, and a small number of people respond: they open their wallets a touch."
- "Fuel and power costs could rise if the writer is right: people could cut back markedly. / About 7 more in every 100 people could cut spending than without it."
- "Even once it takes effect, food shortages will spread, and few people will change course."
Sound different: yes.

Triple 2 (s066 to s068)
- "The news flow would get lighter if forecasters are right, but choices would barely move."
- "If forecasters have it right, wages would grow faster, and Poland would feel it almost alone: people there would step up spending."
- "Supply lines could clog up if the argument holds: people could cut spending a touch."
Partly: all three open on a "forecasters/argument" hedge and two use "if ... right/holds"; different words, same rhythm.

Triple 3 (s067 to s069)
- "If forecasters have it right, wages would grow faster, and Poland would feel it almost alone: people there would step up spending."
- "Supply lines could clog up if the argument holds: people could cut spending a touch."
- "If the forecast holds, prices would fall: people would step up spending, in a small way."
Mostly alike: three "if the forecast/argument holds, X would/could ..., people would step up / cut spending" statements. This is the case the target does not capture: no shared five-word run, still the same shape.

Triple 4 (s104 to s106)
- "Egypt takes this squeeze almost alone: wages grow faster, but government budgets come under strain; on balance, those living there cut back. / Sharp at first, then mostly gone."
- "If it plays out as forecast, prices would fall, and people would spend more. / Short-lived."
- "A story for Mexico alone: supply lines should clear, and people there step up spending and stick with their brands. / Felt at once, gone soon after."
Headlines differ; the three line 2s say the same thing in three phrasings.

Triple 5 (s004 to s006)
- "Taking the writer at their word, prices could fall, and people could spend a bit more."
- "Were the forecast to come true, loans would get dearer: people in Canada would rein in spending."
- "Loans get cheaper, and in turn people open their wallets and put savings to work."
Sound different: yes (the first two share "could/would fall ... spend" structure only).

Answer: three statements in a row now sound different in about four of five cases by this sample; the hedged-story runs (triples 2 and 3) are where they still sound alike, because IF is a third of all statements and one hook row (IF01) is three quarters of it.

## Hot spots, ranked, with owner

1. **The IF family is a third of statements and one hook row (IF01 "{Hedge},") is 75% of it.** Its 6 phrasings keep the rate per phrasing at 20% but a reader sees one shape: "If/Taking/Were ..., X would ..., people would ...". Owner: `sowhat2_hooks.csv` IF01 (split into 3 to 4 rows with different shapes), `sowhat.js` hook choice, and the stories (a third forecast/opinion by design).
2. **Quiet forecast form QF03 is the top body of its family** (4 of 16 at world focus, 12 of 48 over all foci) and QS02/QA02 "carry on much as before" plus QS05/QF06 "too faintly to change what people do" are the repeated 4-grams. Owner: `sowhat2_templates.csv` quiet rows, `sowhat.js` quiet pick.
3. **STAKE, WHO_MOST, WHO_OPP never led and SCALE once** (over 360 outputs); 45 of 79 hook rows never appeared. This set lacks big-effect stories (engine Size mostly Negligible), so I cannot say whether they work. Owner: needs a stress set with Major stories; or the test composer fixtures (golden v2) cover them.
4. **Degree word versus anchor figure** (4 of 17 anchored statements; see anchor integrity). Owner: `sowhat.js` degree choice, `sowhat2_lexicon.csv` degree.
5. **Line 2 arcs are four phrasings of one idea** and "Short-lived." alone reads clipped. Owner: `sowhat2_lexicon.csv` l2_arc.
6. **`banned()` false positive**: 5 TEST 2 outputs of the form "While crime falls, water supplies run short: on balance, people go out and about more, if only slightly." are flagged "comma list" by `banned()` but are not lists (the pattern sees "balance, people go out and about"). The composer itself does not self-check on this. Owner: `demo/static/sowhat.js` `banned()`.
7. **Contract wording on digits** (unit "100"): see anchor integrity. Owner: `spec/so-what-v2-contract.md`.
8. **Engine side effects still in headlines** ("pollution levels will fall: ... rein in spending", "supply lines clog up, leaving people to spend more", "social divides should heal, and in turn people share their views less"). Known (design weak spots); owner `decision_weights.csv`. The causal joins ("in turn", "leaving", "so") make a weak weight into a stated cause.
9. **TEST 2 nulls** (6 real, see table). Owner: `sowhat.js` quiet branch for announced.

## Weak spots in this harness

- Tags (good/bad, local/world, large/small) are my intent, not engine output; the engine's sizes were mostly Negligible, so the loud families are barely exercised.
- Triples over all foci are not independent of those at world focus; world focus is the primary row.
- The critical read is 60 statements of 120 and is my judgement; a second editor would pick a different 10.
- The anchor checker re-derives numbers from the same response the composer used, so it proves the composer is faithful to those numbers, not that the engine's numbers are right.
- TEST 2 bases are the real responses, evenly spaced (not v1's fixtures), so its figures are not exactly comparable to v1's TEST 2.
- A3 anchors and the stark register did not occur in the real set (0 and 1), so those code paths are untested by this run.
