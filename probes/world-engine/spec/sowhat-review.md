# So what: independent review on 24 new stories (2026-10-06)

**Question.** The new So-what (frames, lexicon, templates, `sowhat.js`, `sowhat_story.py`) was designed and tested on 22 fixture stories. Does it carry over to stories it was not written around, and is every phrase backed by the engine's numbers?

**Short answer.** No, not yet. The sentence machinery works: 21 different openers across 24 world headlines, no "likelier" lists, and the coherence guard fired twice, both times correctly. But 7 of 24 world headlines are **wrong** and 10 are **weak**. Three of the wrong ones come from So-what's own files (one template, the hedge source, the word budget). Four come from upstream: the engine put a single-country story at world level, so the sentence makes a worldwide claim. Most of the weak ones are honest about the numbers but read badly, because a handful of lexicon phrases carry the wrong meaning, or because tiny moves are shown with no size word.

Verdict: **ship after 6 fixes** (list in section 5). None of them needs a change to the guessed engine weights.

## 1. Method

- Started a private engine with `WE_RULES=rules_v2 ./service.sh start world --port 8137` and stopped it afterwards. No other port was touched.
- Wrote 24 stories that are deliberately unlike the 22 fixtures: other countries (Denmark, Italy, France/Lyon, Ireland, Ethiopia, Mexico, Sudan, South Korea, Spain/Portugal, Australia, Vietnam, Ghana, Poland, the EU, Nigeria, India/Pakistan, Turkey, Bangladesh, China, Estonia), other sectors, and other tones. They cover every type the brief asked for. Each was POSTed to `/request` with `mode: event`. Responses: `scratchpad/review/r01..r24.json`; tables from `/sowhat`: `sowhat_tables.json`.
- `scratchpad/review/compose.js` loads `demo/static/sowhat.js` and calls `SoWhat.compose` with the same input shape as `demo/tests/sowhat.test.js`, for three foci per story: **World**, the **hardest-hit country** (the country with the largest peak move) and the **hardest-hit audience**. That makes 72 outputs, saved in `composed.json`. `oldline.py` re-runs the old page rule (`paintCard`: "Worldwide, people are likelier to X, Y and Z", or "Concentrated in C: ...") on the same responses, saved in `oldlines.json`.
- Two extra probes for the known "approved reads pending" defect: `x25a.json` (dengue vaccine) and `x25b.json` (TB drug).
- Terms: **points** = percentage points of likelihood against the no-event control run. **Peak** = the largest of Now, Next and Later. **Entry** = the country the engine thinks the story is about (`identify.entry`), or WORLD.

**Side finding (engine, not So-what).** The first structural story ("Japan's working-age population has shrunk ...") returned HTTP 400. The traceback is `KeyError: 'news_overload'` in `classify.severity`, because `news_overload` has no row in `impact_phrases.csv` (in either rules dir). It was replaced with an Italy story. `sowhat_story.build_story` has the same blind spot: its trigger criteria use `phr[x["dial"]]` without the `in phr` check that `moves_line` has.

## 2. All 24 at world focus

Frame p = the classifier's probability for the frame that was used. When the guard fired, the raw top frame is shown in brackets. Template codes: SQ squeeze, RL relief, SC scare, BL blow, SU surge, FR freeze, RP ripple, BO boost, NO quiet; -T trigger lead, -W who lead, -S scale lead, -C certainty lead.

| # | Story (type) | Frame p | Headline | Line 2 | Tpl | Verdict | Reason |
|---|---|---|---|---|---|---|---|
| r01 | Danish gene therapy cures 30 in a trial (good news) | boost 0.99 | Health risks fall, and people stick to the rules and travel a bit more. | Fades slowly. | BO-T | WEAK | A 30-patient trial becomes "health risks fall" for everyone, in plain present. Size is Negligible (10.3) but line 2 has no size word (Negligible salience 0.2 < 0.3). "Stick to the rules" is break_rules -0.47, a guessed-weight side effect. Traceable, but it overstates. |
| r02 | Italy's population falls 10th year (slow burn) | ripple 0.58 | Barely a ripple: more people should move away, and few people change what they do. | — | RP-S | OK | Honest quiet answer: Italy peaks at 0.24, under the 0.25 bar. "Should" hedges something the story reports, because the engine marks the reading as expected. The old line ("Concentrated in Italy: ... give less to causes, stay away from protests ...") overclaimed from Now values of 0.05 or more. |
| r03 | Lyon makes buses free (local city) | relief 0.96 | If this forecast comes true, prices would fall, and people in France would get room to breathe: they would spend a bit more. | Elsewhere, barely a ripple. A quick jolt that fades. | RL-C | WRONG | A council **vote** (gate happened 0.97, announced 0.99) is hedged as a forecast, because `weight.type` = forecast (gate forecast 0.83). It should read "will". The headline is **23 words**, over the 22 limit even after dropping theme 2. "would ... would" repeats. Lyon becomes all of France (the engine has no city rows). |
| r04 | Ransomware shuts 3 Irish hospitals (cyber) | scare 0.87 | Hospitals and clinics should come under strain, so people travel a bit less and give a bit less to causes. | A quick jolt that fades. | SC-T | WRONG | Ireland is not one of the 100 rows, so the entry is WORLD and the claim is worldwide. The hardest-hit country is Tanzania. The trigger picked two readings (care_strain 0.55, expected; cyber 0.38, reported), and the word budget then dropped the **reported** one and kept the expected one, so "should" is used for cancelled surgeries the story reports. |
| r05 | Ethiopia–Tigray ceasefire | boost 0.93 | This boost stays in Ethiopia: armed conflict eases, and people there open their wallets and keep their heads down. | Elsewhere, barely a ripple. A quick jolt that fades. | BO-W | WEAK | The numbers are right (spend +1.11, share -0.72, vote -0.45). But "keep their heads down" (the voice theme, down) means fear or repression, which contradicts "boost". |
| r06 | Mexico raises minimum wage 20% | boost 0.70 | Wages grow faster, and people open their wallets and keep their heads down. | Sticks around. A minor shift that reaches most people. | BO-T | WRONG | `ask_country` returned "global", so a Mexico story moves every country about equally (Mexico 1.38, India 1.40, Pakistan 1.53). The headline says the world's wages grow. The hardest-hit country is Rwanda. "Keep their heads down" again. The old line made the same place error. |
| r07 | UN warns of famine in Sudan | scare 0.96 | If the forecast is right, food shortages would spread, and people in Sudan would push back in public to stay safe. | Elsewhere, barely a ripple. Fades slowly. | SC-C | WRONG | The SC-C template hard-codes "to stay safe" after any response. With a voice response (share +0.45, protest +0.41) it produces "push back in public to stay safe", which is nonsense. Trigger and hedge are right. |
| r08 | Korea stock index record | surge 0.87 | Only South Korea feels this surge: shares and property gain value, and people there open their wallets a little. | Elsewhere, barely a ripple. Fades slowly. | SU-W | OK | Matches the entry row (spend +0.67, invest +0.62). Theme 2 dropped for the budget. |
| r09 | Heatwave forecast for Spain/Portugal | scare 0.98 | If this forecast comes true, weather hazards would get worse, but no decision moves enough to matter. | — | NO-F | OK | Honest. Forecast at 0.3 weight, world max 0.07. |
| r10 | "Opinion: central banks are wrong ..." | squeeze 1.00 | If this forecast comes true, prices would rise, and people would spend less. | A minor shift that reaches most people. Fades slowly. | SQ-C | WRONG | The gate says opinion 1.0, but `weight.type` = forecast (forecast 0.93 wins in `type_weight`), so an op-ed is called a forecast. The NO-O and opinion hedges never fire on a real opinion piece. `banned()` also flags this sentence as a comma list, which is a false positive (see 4.2). |
| r11 | Taylor Swift engagement (celebrity) | ripple 1.00 | The United States takes this ripple almost alone, and even there the change is small: people there stick to the rules. | Elsewhere, barely a ripple. Fades slowly. | RP-W | WEAK | The RP-W template's "even there the change is small" is honest. But the response comes from one expected reading (public information gets more reliable) at 0.29 points, which is meaningless for a celebrity story. "Ripple" appears in both lines. |
| r12 | Australian farms short of workers (labour) | squeeze 0.95 | Australia takes this squeeze almost alone: food shortages should spread, so people there cut back and keep savings in cash. | Elsewhere, barely a ripple. A clear shift there. | SQ-W | WEAK | The actual news (labour shortage) has no reading. The trigger is an expected reading (food shortages in Australia), which overreaches. Two readings were picked (0.55 vs 0.38) and the second was dropped. On the audience focus the quiet path keeps **both** ("food shortages should spread and farmland and forests should get damaged") because the quiet path skips the budget. |
| r13 | US 25% tariff on Vietnamese steel | squeeze 0.98 | Vietnam takes this squeeze almost alone: supply lines clog up, so people there cut back sharply. | Elsewhere, barely a ripple. A big shift there. | SQ-W | OK | Matches the numbers (Vietnam spend -4.23). The US side is not modelled because the entry is a single country, but nothing is claimed for the US. |
| r14 | Ghana reading scores rise (school win) | boost 1.00 | Only Ghana feels this boost: skills and schooling improve, and people there stick to the rules and stay off the streets. | Elsewhere, barely a ripple. Fades slowly. | BO-W | WEAK | 0.28 points (just over the bar) with **no size word**: the band "small" (salience 0.3) loses the tie to "Fades slowly" (0.3, earlier order). "Stay off the streets" sounds like a curfew. Side-effect responses. |
| r15 | Poland shelters and cash for refugees | ripple 0.20 [raw squeeze 0.66] | Poland takes this ripple almost alone, and even there the change is small: people there stick to the rules. | Elsewhere, barely a ripple. Sticks around. | RP-W | WEAK | The guard fired correctly (squeeze vs sense up +0.32, so the runner-up ripple was used). The relief for refugees is invisible to the engine. "Ripple" appears twice. The trigger picked an expected reading (public services) over reported ones. |
| r16 | EU AI labelling and audit law | boost 0.41 | Public information should get more reliable, and people stick to the rules and seek care and get tested. | A minor shift that reaches most people. Fades slowly. | BO-T | WEAK | Three "and"s in a row, because the decision phrase "seek care and get tested" has its own "and". health_action +0.37 from a trust reading is a side effect. The EU is not a country, so the claim is worldwide (hardest hit: Iran). |
| r17 | Nigeria ends fuel subsidy: petrol doubles, money for schools (mixed) | squeeze 0.98 | Nigeria feels the squeeze most: fuel and power costs rise, so people there spend far less and shop around. | Fades slowly. | SQ-W | WEAK | The numbers are right (Nigeria spend -9.28, world -0.27). But the good half (public services up, care strain down, both reported) is gone: no frame or template can say "X, but Y". The world -0.27 sits just over the 0.25 local cut, so it says "feels it most" instead of "almost alone", although Nigeria moves 34 times as much. |
| r18 | "Markets wobble" (vague, 2 words) | squeeze 0.99 | Shares and property should lose value, and people feel the squeeze: they cut back a little and keep savings in cash. | Fades slowly. | SQ-T | WEAK | Two vague words become a worldwide squeeze, with gate happened 0.95. No size word, although the tier is Negligible (7.2). "Feel the squeeze" over a 0.5-point move overstates it. |
| r19 | India and Pakistan exchange fire (two countries) | scare 0.96 | Armed conflict escalates, so people travel a bit less and speak out a bit more. | A quick jolt that fades. | SC-T | WRONG | Two countries → entry WORLD → a worldwide claim. The hardest-hit country is **Sweden** (0.45). India is at 0.34. Neither India nor Pakistan is named. |
| r20 | Turkey raises rates to 50% | squeeze 0.99 | Loans get dearer, and people feel the squeeze: they move home and avoid new debt. | A minor shift that reaches most people. Fades slowly. | SQ-T | WRONG | `ask_country` returned "global" for Turkey, so the claim is worldwide (hardest hit: Cameroon). "Feel the squeeze: they move home" (move +0.80) reads as a contradiction. The guard passed because sense is flat (+0.23) and squeeze only needs "not up". |
| r21 | Bangladesh floods | blow 0.89 | Bangladesh takes this blow almost alone: weather hazards get worse, and people there spend less and travel less. | Elsewhere, barely a ripple. Fades slowly. | BL-W | OK | The first live use of **blow** (no golden case had one), and it fits. |
| r22 | China home prices fall 18th month | freeze 0.16 [raw relief 0.70] | Only China feels this freeze: housing costs fall, so people there play it safe with money and stay where they live. | Elsewhere, barely a ripple. Sticks around. | FR-W | OK | The guard fired correctly: "relief" over people cutting back would have been wrong. "Housing costs fall, so ..." is a slightly odd causal link, but defensible. |
| r23 | Korean doctors end 7-month strike | boost 0.96 | This boost stays in South Korea: hospitals and clinics get relief, and people there travel more. | Elsewhere, barely a ripple. A quick jolt that fades. | BO-W | WEAK | Travel +2.59 is the only response shown (break_rules -1.00 is under 0.4 times it). Faithful to the guessed weights, but not what the story means. |
| r24 | Estonian recipe app (quiet tech) | shake-up 0.61 | New digital tools should spread, but no decision moves enough to matter. | — | NO-Q | OK | Honest quiet answer. The old line said "barely moves". |

**Counts (world focus):** OK 7, WEAK 10, WRONG 7. Of the 7 wrong: 3 are owned by So-what (r03 hedge and budget, r07 template, r10 hedge source) and 4 are upstream place errors (r04, r06, r19, r20).

### Country and audience foci (summary)

| # | Hardest-hit country: headline (verdict) | Hardest-hit audience: headline (verdict) |
|---|---|---|
| r01 | Canada: same as world with the subject swapped (WEAK; a Danish story) | Older, tech-wary: "... ease off on precautions and travel a bit more." + "About twice as much as most people." (OK vs numbers) |
| r02 | Italy: identical to world (RP-S has no `{for_subj}`) (WEAK) | identical to world (WEAK) |
| r03 | France: same 23-word forecast hedge (WRONG) | Retirees: NO-F quiet (WRONG hedge) |
| r04 | **Tanzania** (WRONG) | Busy rural parents: 22 words (WRONG place) |
| r05 | Ethiopia: "Armed conflict eases ... keep their heads down." (WEAK) | NO-Q (OK) |
| r06 | **Rwanda** (WRONG) | Big-city high earners: "invest more and spend more" (WRONG place) |
| r07 | Sudan: same "to stay safe" (WRONG) | NO-F (OK) |
| r08 | South Korea: 22 words, "respond: they open their wallets a little and invest a bit more." (OK) | NO-Q (OK) |
| r09 | India NO-F (OK) | NO-F (OK) |
| r10 | Brazil: forecast hedge (WRONG) | Young rural early adopters: forecast hedge (WRONG) |
| r11 | USA: "Public information should get more reliable, but daily life barely changes ..." (WEAK) | RP-S (OK) |
| r12 | Australia (WEAK) | Retirees: NO-Q with **two** triggers (WEAK) |
| r13 | Vietnam: "A big squeeze: supply lines clog up ..." (OK) | NO-Q (OK) |
| r14 | Ghana (WEAK) | NO-Q (OK) |
| r15 | Poland (WEAK) | RP-S (OK) |
| r16 | **Iran** (WRONG place) | Young rural early adopters: 21 words, triple "and" (WEAK) |
| r17 | Nigeria: "A huge squeeze ... Many times as much as most people." (OK) | Young big-city parents: "More than most people." (OK) |
| r18 | Rwanda (WEAK) | Older, tech-wary (WEAK) |
| r19 | **Sweden** (WRONG) | Retirees (WRONG place) |
| r20 | **Cameroon** (WRONG) | Young rural early adopters (WRONG) |
| r21 | Bangladesh: BL-T "the blow lands on people in Bangladesh" (OK) | NO-Q (OK) |
| r22 | China: FR-T (OK) | Retirees: "About twice as much as most people." (OK) |
| r23 | South Korea (WEAK) | NO-Q (OK) |
| r24 | Pakistan NO-Q (OK) | NO-Q (OK) |

## 3. Judgement by criterion

### 3.1 Accuracy and traceability
- **Every response phrase traces to a peak at the response row.** I checked all 24 against `places`: no decision was invented, no sign was wrong, and degree words match the cut points (0.75 and 3). The composer itself never added a fact.
- **Wrong place (upstream, 6 of 24 at world, more at other foci):** r04 Ireland (not among the 100 rows), r06 Mexico and r20 Turkey (`ask_country` → "global"), r16 the EU (no bloc entry), r19 India + Pakistan (only one entry is allowed). In each case the event is applied worldwide and the sentence says "people" with no place. So-what is faithful to the numbers, which are wrong. The old line made the same mistake ("Worldwide, people are likelier to ...").
- **Wrong hedge (So-what owned, 3 stories):** r10 (opinion → forecast) and r03 (a council vote → forecast). Both happen because CERTAINTY reads `weight.type`, which mixes "how much to count it" with "what kind of story it is". The gate already holds the right answer (opinion 1.0; happened 0.97 and announced 0.99).
- **Overclaim from size:** r01, r04, r18, r19 are Negligible-tier stories, and line 2 never says so (Negligible salience 0.2 is under the 0.3 floor). r14 (0.28 points) loses its "small" band to the arc on a tie. A reader cannot tell a 0.3-point story from a 3-point one unless the headline happens to carry "a bit".
- **Trigger prefers an expected reading over a reported one** in r04, r12, r15 and the TB-drug probe. The lead change is then something the engine inferred and hedges with "should", while the thing the story reports is dropped (r04 by the budget).

### 3.2 Language
- **Grammar breaks:** r07 "push back in public to stay safe" (SC-C template); r16 "stick to the rules and seek care and get tested" (a lexicon phrase with its own "and"); r03 "would get room to breathe: they would spend" (RL-C repeats the modal).
- **Loaded lexicon words:** voice down = "keep their heads down" (r05, r06) and protest down = "stay off the streets" (r14) read as fear or curfew. In the engine they mean "less political activity". "Feel the squeeze: they move home" (r20).
- **Stock phrases in line 2:** "Elsewhere, barely a ripple." appears in **12 of 24** world line 2s, and "Fades slowly." in 11. "Ripple" shows up twice in the same card on RP-W (r11, r15).
- **Comma-list skeleton:** gone. No real list of three in 72 outputs.
- **Budgets:** one break. r03 has 23 words at both world and France, because the composer has no shrink step after "drop theme 2". Line 2 always fit within 14 words.
- **Repeated openers:** "If this forecast comes true" opens 3 of 24 world headlines (r03, r09, r10). The variety rule ((offset + text length) mod 2) chose the same variant for all three. The feed rule, simulated in story order, flipped one (r10).

### 3.3 Frame and trigger choice
- Frames were sensible in 20 of 24. **Blow was used for the first time** (r21, correct), and so was surge (r08). The guard fired 2 times out of 24 (r15 squeeze→ripple, r22 relief→freeze), and both were correct.
- **Where the guard cannot help:** it checks only the spending direction (spend + buy_new + subscribe + travel). r07 "scare" with a protest response and r20 "squeeze" with "move home" both pass, because sense is flat. The template wording then has to carry a response it was not written for (SC-C's "to stay safe").
- **Close frame margins:** r16 boost 0.41 vs shake-up 0.31, r24 shake-up 0.61 vs boost 0.36, r02 ripple 0.58. Fine as long as the templates stay neutral.
- **Trigger:** mostly sharp (one reading at 0.89 or more in 18 of 22 multi-reading stories). The weak points are the close cases (r04, r12), where the second pick is then dropped by the budget without checking which pick is reported.

### 3.4 Variety
- World headlines: **21 distinct three-word openers out of 24.** Repeats: "If this forecast" ×3, "This boost stays" ×2. **15 distinct template ids out of 24.**
- All 72 outputs: 31 distinct openers and 20 distinct template ids (BO-T 12, NO-Q 10, SQ-T 8, SC-T 6).
- Variety in the headline is good. Line 2 is where it is lost (see 3.2).

### 3.5 Honesty on quiet and mixed stories
- **Quiet stories:** good. r02, r09 and r24, plus 10 audience foci, give the quiet forms with no invented movement. The country focus of a local story gives NO-Q "for people in ..." as designed. Two flaws: RP-S has no `{for_subj}` slot, so a quiet ripple reads the same at every focus, and the quiet path skips the budget and trigger rules (r12 audience keeps two triggers).
- **Mixed stories:** not supported. r17 (fuel subsidy cut plus money for services) shows only the squeeze. There is no beat, frame or template for "X, but Y", and THEMES can only show the two biggest moves, which here all point the same way. The good half is reported readings with no visible decision move, so the composer cannot say it without a new beat.
- **Near-zero but over the bar:** r11 and r14 (0.28 to 0.29 points) get full confident headlines. RP-W is honest ("even there the change is small"); BO-W is not.

### 3.6 Known defect: an approved story reads certainty "pending"
- **It did not show up** in my three approval-type stories (dengue vaccine, TB drug, EU law). Each had at least one reported or `expected_in_effect` reading, so the kind was "happened".
- **It is still live** whenever every reading is `expected_pending`, as in golden 13 ("Regulators approved a new vaccine ..." → "Health risks **will** fall ... **Not in effect yet.**"). The approval happened (gate happened 0.98). Only its effects are pending.
- **Root cause:** `sowhat_story.certainty` (and `deriveStory` in `sowhat.js`) turns "all consequences are pending" into "the story is pending". The lexicon `certainty,pending` row then prints the announced wording ("Not in effect yet.").
- **A second, smaller issue:** the backend checks `happened < 0.5` before pending, while `deriveStory` checks pending first. The two can disagree on the kind (and the hover trace), although the modal is the same.

## 4. The 5 worst failures, with root cause

1. **Single-country stories told as worldwide (r06 Mexico, r20 Turkey, r19 India–Pakistan, r04 Ireland, r16 EU).** Root cause: **backend/engine**. `classify.ask_country` returned "global" for Mexico and Turkey; there is no row for Ireland; there is no multi-country or bloc entry. So-what then reads the WORLD row truthfully ("Wages grow faster, and people open their wallets", hardest hit Rwanda). This is the biggest accuracy hole, and So-what cannot fix it. One mitigation is in reach: when the entry is WORLD and the classifier's best country probability is high, the composer could stay quiet about "people" at large. That needs the backend to send `country_p` in `story.entry`.
2. **Opinion and decided-event hedged as forecasts (r10 op-ed "If this forecast comes true"; r03 council vote; and the inverse in golden 13, where an approval reads "will ... Not in effect yet").** Root cause: **backend rule**, `sowhat_story.certainty`. It takes the kind from `weight.type`, which is a counting weight, instead of from the gate it already has. The fix is not a weight change.
3. **SC-C produces nonsense ("would push back in public to stay safe", r07).** Root cause: **template row** `SC-C` in `sowhat_templates.csv` hard-codes "to stay safe" after any response.
4. **Tiny or Negligible effects shown with no size word (r01, r04, r14, r18, r19).** Root cause: **composer rule** in `sowhat.js`: `TIER_SAL.Negligible = 0.2` is under the 0.3 line-2 floor, and the "small" band (0.3) loses ties to the arc. Confident headlines for 0.3-point stories are the main honesty gap.
5. **Loaded or awkward lexicon phrases ("keep their heads down" after a ceasefire, "stay off the streets" for a school win, "stick to the rules and seek care and get tested").** Root cause: **lexicon rows** `theme,voice` (down), `decision,protest` (down) and `decision,health_action` (up) in `sowhat_lexicon.csv`. (The underlying decision moves come from guessed engine weights. They should stay as they are; the problem is the words.)

Close runners-up: the 23-word headline (r03, composer has no third shrink step); the trigger budget dropping the reported reading and keeping the expected one (r04, composer `build` with dropTrig2); the mixed story losing its good half (r17, no beat for it).

## 5. Ordered fix list (owner file → change)

1. **`probes/world-engine/sowhat_story.py` `certainty()`** (and the mirror in `demo/static/sowhat.js` `deriveStory`): take the kind from the gate, not from `weight.type`. If opinion ≥ 0.5 → opinion. Else if forecast ≥ 0.5 and announced < 0.5 → forecast. Else if happened ≥ 0.5 → happened. Else if announced ≥ 0.5 → announced. Keep the weight as it is. Make the two implementations check in the same order. Update `so-what-ontology.md` §1.2 to match. (Fixes r10 and r03.)
2. **`sowhat_story.py` and `sowhat_lexicon.csv` `certainty,pending`:** a happened story whose readings are all `expected_pending` keeps the plain present for the event, uses "should" for the readings, and line 2 says something like "Effects not felt yet." instead of "Not in effect yet." No modal "will". (Fixes the known defect in golden 13; update that golden case.)
3. **`sowhat_templates.csv`:** SC-C drops "to stay safe". RL-C drops the second `{mod_}` clause ("get room to breathe") or gets shorter. RP-S gains `{for_subj}`. Check every `-C` template for a fixed verb that assumes a theme.
4. **`demo/static/sowhat.js`, line-2 rules:** always show the scale fragment when the world tier is Negligible or the band is small (raise the salience or order it ahead of the arc). Drop "Elsewhere, barely a ripple." when the frame is ripple (RP-W already says it). Add a third shrink step (the shorter hedge variant, then the plain family) so a headline never goes over 22 words. Run the budget and the trigger-drop rule on the quiet path too. When dropping the second trigger, keep the reported reading over the expected one.
5. **`probes/persona/rules_v2/sowhat_lexicon.csv`:** voice down → "speak out less"; protest down → "protest less"; health_action up → a phrase with no internal "and" (for example "get health checks"); consider a second "elsewhere" variant so 12 of 24 cards do not end the same way.
6. **`sowhat_story.py` trigger question:** when any reading is reported, offer only reported readings, or list them first and fall back to expected ones. Also apply the same `in phr` guard as `moves_line`, so a dial without an `impact_phrases` row cannot crash or skip the story.

Upstream, not So-what (listed so they are not lost):
- **`classify.ask_country` / `world_service2.request_event`:** Mexico and Turkey resolved to "global"; there is no entry for the EU or for two-country stories; Ireland has no row. This caused 4 of the 7 wrong headlines.
- **`rules_v2/impact_phrases.csv` (and `rules/`):** add `news_overload`. Without it, `classify.severity` raises KeyError and `/request` returns 400.
- Design gap for a later version: a **mixed** beat (a reported reading of the opposite sign to the frame), so stories like r17 can say "X, but Y".

Not proposed: any change to `decision_weights.csv` or other guessed engine weights to make sentences read better. Odd responses such as "move home" after a rate hike, "travel more" after a doctors' strike and "stick to the rules" after a gene-therapy trial are faithful to those weights. They should be fixed there, on evidence, not hidden by wording.

## 6. Files
- Review inputs and outputs: `/tmp/claude-0/-workspace/cdb40569-0681-424f-99c4-07e70f2075c8/scratchpad/review/` (`stories.json`, `r01..r24.json`, `x25a.json`, `x25b.json`, `sowhat_tables.json`, `compose.js`, `composed.json`, `oldline.py`, `oldlines.json`, `x25.js`).

## After fixes (2026-10-06, fixer pass)

Fixes 1 to 6 applied as written, plus `news_overload`, the place rule (A) and the `ask_country` investigation (B). Method: the 24 saved responses were run through `sowhat_story.build_story` with the **saved classifier answers** (frame and trigger probabilities from the review run; nothing was re-asked) and then through the fixed `sowhat.js` at the same three foci. Verdicts are mine, against the same criteria as above (accurate and traceable, grammar, no stock phrases, honest size, honest place). Files: `scratchpad/fix/composed_after.json`, `after.txt`.

| | Before | After |
|---|---|---|
| World headlines OK / WEAK / WRONG | 7 / 10 / 7 | 9 / 14 / 1 |
| Distinct three-word openers, 24 world headlines | 21 | 23 |
| Distinct openers, all 72 outputs | 31 | 38 |
| Distinct template ids, world / all 72 | 15 / 20 | 14 / 22 |
| Headlines over 22 words (of 72) | 2 | 0 |
| `banned()` hits (of 72) | 1 (false positive) | 0 |

World template ids after: BL-W, BO-W, FR-W, NO-F, NO-Q, PL-T, RL-W, RP-S, RP-W, SC-W, SQ-C, SQ-T, SQ-W, SU-W.

| # | Before | After headline | After line 2 | Tpl | After | Note |
|---|---|---|---|---|---|---|
| r01 | WEAK | Health risks fall, and people stick to the rules and travel a bit more. | A tiny shift. Fades slowly. | PL-T | WEAK | place-free now; a 30-patient trial still reads as 'health risks fall' (and the 'stick to the rules' side effect is the engine's weight) |
| r02 | OK | Barely a ripple: more people should move away, and few people change what they do. | — | RP-S | OK | unchanged |
| r03 | WRONG | France takes this relief almost alone: prices fall, and people there spend a bit more. | Elsewhere, barely a ripple. A small shift there. | RL-W | WEAK | now 'happened' (plain present), no repeated 'would'; but a city becomes 'France' (no city rows) |
| r04 | WRONG | Digital break-in risks rise, and people travel a bit less and give a bit less to causes. | A tiny shift. A quick jolt that fades. | PL-T | WEAK | no 'Ireland is the world' claim, reported trigger kept, size 'tiny'; still 'people travel a bit less' without a place |
| r05 | WEAK | This boost stays in Ethiopia: armed conflict eases, and people there open their wallets and speak out less. | Elsewhere, barely a ripple. A quick jolt that fades. | BO-W | OK | 'speak out less' replaces 'keep their heads down' |
| r06 | WRONG | Wages grow faster, and people open their wallets and speak out less. | Sticks around. A minor shift. | PL-T | WEAK | place-free plain template, 'minor shift'; the sentence still says people in general because ask_country placed Mexico wrongly (upstream) |
| r07 | WRONG | This scare stays in Sudan: food shortages will spread, and people there will push back in public and brush off official rules. | Little changes elsewhere. A small shift there. | SC-W | WRONG | gate says announced 0.94 (forecast 0.99), so 'food shortages will spread': a warning reads as a fact. The stated order does this; the fix is in the gate |
| r08 | OK | Only South Korea feels this surge: shares and property gain value, and people there open their wallets a little. | Elsewhere, barely a ripple. A small shift there. | SU-W | OK | unchanged in meaning; size word added |
| r09 | OK | If this forecast comes true, weather hazards would get worse, but no decision moves enough to matter. | — | NO-F | OK | unchanged |
| r10 | WRONG | An opinion piece; if enough people agree, prices could rise, and people could spend less. | A minor shift that reaches most people. Fades slowly. | SQ-C | OK | opinion hedge now ('An opinion piece; if enough people agree'), no comma-list false positive |
| r11 | WEAK | The United States takes this ripple almost alone, and even there the change is small: people there stick to the rules. | A small shift there. Fades slowly. | RP-W | WEAK | unchanged: engine response of 0.29 points; size shown, 'ripple' no longer repeated in line 2 |
| r12 | WEAK | Australia takes this squeeze almost alone: food shortages should spread, so people there cut back and keep savings in cash. | Little changes elsewhere. A clear shift there. | SQ-W | WEAK | unchanged: the news has no reading; trigger still an expected one |
| r13 | OK | Vietnam takes this squeeze almost alone: supply lines clog up, so people there cut back sharply. | Little changes elsewhere. A big shift there. | SQ-W | OK | unchanged |
| r14 | WEAK | Only Ghana feels this boost: skills and schooling improve, and people there stick to the rules and protest less. | Little changes elsewhere. A small shift there. | BO-W | WEAK | size shown ('A small shift there'), 'protest less' replaces 'stay off the streets'; side effects remain |
| r15 | WEAK | Poland takes this ripple almost alone, and even there the change is small: people there stick to the rules and protest less. | A small shift there. Sticks around. | RP-W | WEAK | 22 words; engine cannot see refugee relief |
| r16 | WEAK | Public information should get more reliable, and people stick to the rules and get health checks. | A minor shift. Fades slowly. | PL-T | WEAK | unresolved (EU): plain place-free, 'get health checks' has no inner 'and'; still a health_action side effect |
| r17 | WEAK | Nigeria feels the squeeze most: fuel and power costs rise, so people there spend far less and shop around. | A tiny shift that reaches very few people. Fades slowly. | SQ-W | WEAK | mixed story still has no 'X, but Y'; 'A tiny shift' (world tier) sits oddly beside Nigeria's large move |
| r18 | WEAK | Shares and property should lose value, and people feel the squeeze: they cut back a little and keep savings in cash. | A tiny shift that reaches a large minority. Fades slowly. | SQ-T | WEAK | size shown ('A tiny shift ...'); the squeeze claim over two vague words remains |
| r19 | WRONG | Armed conflict escalates, and people travel a bit less and speak out a bit more. | A tiny shift. A quick jolt that fades. | PL-T | WEAK | unresolved (two countries): no 'Sweden', plain template; still people 'travel less' with no place |
| r20 | WRONG | Loans get dearer, and people move home and avoid new debt. | A minor shift. Retirees react about half as much as most people. | PL-T | WEAK | unresolved (Turkey, upstream): plain place-free; 'move home' is the engine weight |
| r21 | OK | Bangladesh takes this blow almost alone: weather hazards get worse, and people there spend less and travel less. | Little changes elsewhere. A small shift there. | BL-W | OK | unchanged |
| r22 | OK | Only China feels this freeze: housing costs fall, so people there play it safe with money and stay where they live. | Elsewhere, barely a ripple. Sticks around. | FR-W | OK | unchanged |
| r23 | WEAK | This boost stays in South Korea: hospitals and clinics get relief, and people there travel more. | Little changes elsewhere. A quick jolt that fades. | BO-W | WEAK | unchanged: only travel is shown (engine) |
| r24 | OK | New digital tools should spread, but no decision moves enough to matter. | — | NO-Q | OK | unchanged |

**The 5 worst remaining**
1. **r07 Sudan famine warning, WRONG.** The gate reads announced 0.94 and forecast 0.99, so the stated order (forecast only when announced < 0.5) gives "will spread" for a warning. Root cause: the gate's `announced` question fires on "UN warns". Fix belongs in the gate, not in So-what.
2. **r06 Mexico (and r20 Turkey), WEAK.** The sentence no longer names a place it cannot support, but it still says people in general open their wallets, because `ask_country` placed the story wrongly (section B below). Upstream.
3. **r03 Lyon, WEAK.** A city story is told as France (the engine has no city rows). Needs row support, not wording.
4. **r17 Nigeria mixed story, WEAK.** The good half (schools, hospitals) is invisible, and the world-tier word "tiny" sits beside "Nigeria feels the squeeze most". Needs a mixed beat and a local-aware size.
5. **r01 / r14 / r23 side effects, WEAK.** "Stick to the rules", "protest less" and "travel more" after a trial, a school win and a doctors' strike are faithful to the guessed decision weights. They belong in `decision_weights.csv` on evidence, not in wording.

**What each fix changed in these 24:** fix 1 turned r03 (council vote) and r10 (op-ed) from wrong hedges into plain present and "An opinion piece; ... could" and made r07 the reverse case; fix 2 changed golden 13 only (no review story is pending); fix 3 removed "to stay safe", "room to breathe" and "hold back" (r03, r07 no longer produce nonsense) and gave a quiet ripple its subject; fix 4 added the size word to r01, r04, r14, r18 and r19, dropped "Elsewhere, barely a ripple." under ripple (r11, r15) and brought r03 from 23 to 15 words; fix 5 replaced "keep their heads down", "stay off the streets" and "seek care and get tested", and the two 'elsewhere' lines now split 6 and 4 across the 10 local-story world cards (it was 12 of 24 cards with one line); fix 6 lists reported readings first and cannot crash on a dial without a phrase. Rule A removed every invented country (Rwanda, Sweden, Cameroon, Iran, Tanzania) from the 6 unresolved stories (r01, r04, r06, r16, r19, r20; r09 and r24 are quiet).

### B. Why Mexico and Turkey resolved to "global" (investigation, no change made)
Own engine on :8138 (stopped afterwards), `classify.ask_country` two steps, today's stories, probabilities of the first (region) step then the second (country) step. Both countries are in `countries_world100.csv` (`mex`, `tur` as "Türkiye"), so it is not a missing row.

| Story | Region step (top 2) | Country step | Result |
|---|---|---|---|
| Mexico raised its minimum wage 20% | North America 0.95 (review wording) / 0.74 (other wording); Latin America & Caribbean 0.05 / 0.26 | North America holds only usa and can: other_here 0.97 | global |
| Turkey's central bank raised rates to 50% | Middle East, North Africa, Afghanistan & Pakistan 0.85, Europe & Central Asia 0.14 (other wording: 0.48 vs 0.52) | tur is not in the Middle East list: other_here | global (or tur when Europe wins) |
| Nigeria | Sub-Saharan Africa 0.999 | nga 0.999 | nga |
| Japan | East Asia & Pacific 0.999 | jpn 0.999 | jpn |
| Brazil | Latin America & Caribbean 0.999 | bra 0.999 | bra |
| Egypt | Middle East ... 0.998 | egy 0.999 | egy |
| Indonesia | East Asia & Pacific 0.992 | idn 0.999 | idn |
| Poland | Europe & Central Asia 0.998 | pol 0.998 | pol |

**Cause: not naming.** The region options are bare labels from the data's World Bank grouping, where Mexico sits in Latin America and Türkiye in Europe & Central Asia, but the model reads "North America" and "Middle East" geographically. The country step then only offers that region's countries, so "other_here" wins and the entry becomes the world. `Türkiye` vs `Turkey` plays no part (the country step finds tur at 0.999 once the region is right). Two single-country stories out of eight is the failure rate at the edge of the regions.
**Evidence for a fix:** when the same region question lists each region's member countries in its option text ("Latin America & Caribbean (Mexico, Brazil, ...)"), the same two stories give Latin America & Caribbean 0.993 and Europe & Central Asia 0.995, three runs identical. **Recommendation:** put member country names in the region option text (data side, no threshold change), then re-run the 24 stories and the 100-headline set; I did not apply it, because it changes entry resolution for every story and the brief said to report region problems. Until then the so-what treats these as unresolved (plain place-free) rather than world.

### C. Also fixed
- `news_overload` was missing from `rules_v2/impact_phrases.csv` (HTTP 400 in `classify.severity`); added with v1-style wording. `rules/impact_phrases.csv` (v1, not owned here) has no row for it either. `validate_v2.py` now requires one row per condition-kind **and media-kind** dial.
- `sowhat_story.build_story` filters readings whose dial has no phrase row (the same guard `moves_line` had).

### After certainty rule (lead-approved replacement of fix 1's order)
New order: opinion >= 0.9 is opinion; happened < 0.5 is forecast when forecast > announced, otherwise announced; happened >= 0.5 is happened (pending when all readings are expected_pending). Same in `sowhat_story.certainty` and `deriveStory`. Re-run of the 24 saved stories: only r07 changes (now "If the forecast is right, food shortages would spread, and people in Sudan would push back in public.", forecast, OK). World verdicts: **OK 10 / WEAK 14 / WRONG 0**; no headline over 22 words; r03 stays plain present, r10 stays opinion, r09 stays forecast. Golden changes from this rule: 15 (announced, as before), 20 back to forecast/"would" (original text), 13 pending; see `sowhat-golden.md`.

### B follow-up: ask_country fixed (region option text)
`classify.region_text` puts each region's real member countries (from `countries_world100.csv`, most populous first; all members when under 300 characters, else the 12 largest) into the region option text; keys and thresholds unchanged. Regression on 24 stories (20 single-country, 4 global): before, Mexico and Turkey resolved to global; after, mex 0.996 and tur 0.994. The other 18 single-country stories stay correct (0.99+ before and after) and the 4 global stories still give global at 1.0.
