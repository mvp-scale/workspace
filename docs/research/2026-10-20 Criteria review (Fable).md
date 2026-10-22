# Criteria review: what is wrong with the acceptance criteria, and a proposed replacement set

Date 2026-10-20. Author: Claude Fable 5.1, review only. **Status: PROPOSAL.** Nothing here is in force. No code, bar, scorecard row or ledger item was changed; no job was started. The owner approves before any bar moves (GO.md "Next steps" item 5; the scorecard fingerprint `017dc4c3784a` stays until then).

What was read: the draft `docs/research/2026-10-20 Acceptance criteria draft.md` (rev 2); the enforced rows in `newsreader/bitmob/scorecard.py` (lines 56-93); the live view `demo/mockups/trainer/live.json`; the ontology `exports/world-engine-ontology.yaml`; the engine code that consumes the labels (`probes/world-engine/classify.py`, `world_service2.py`, `sensitivity.py`); the skill `ontology-trainer` §1 and §1b; ledger D-0017, D-0022, D-0024, F-0020, F-0048, F-0049, F-0052, F-0062, F-0072, N-0019, N-0020; results `data/scorecard/models.json` and the last card in `data/scorecard/history.jsonl`.

One correction to the brief: F-0001 is "old students plateaued at 35-37% of Clef's hits", not the tolerance fact. The engine-tolerance fact is **F-0020** (Step 1), and that is what this review cites.

## Terms used in this document

- **Reader**: the CPU program that reads a headline plus the first 250 characters of the description (D-0009) and outputs labels. **Teacher**: the large model whose labels the reader is trained to copy, Jev (D-0024). **Engine**: the World engine (`probes/world-engine/`), which consumes the labels.
- **Frozen test set (F)**: stories with teacher labels that are never trained on, used only to score. The draft says "~2,000"; the measured set is 11,997 stories from 125 outlets (F-0072). The scorecard uses the night1 held-out 2,000 plus testA. The size should be stated once and used everywhere.
- **Probe set**: a small set of stories chosen to test one behaviour (for example, 100 stories that mention Georgia the US state).
- **Recall**: of the things that are really there, the share the reader found. **Precision**: of the things the reader claimed, the share that were right. **False alarm**: a claim that was wrong, usually counted per 1,000 stories. **Miss**: a real thing the reader did not claim.
- **AP (average precision)**: a ranking score from 0 to 1: how well the reader puts true cases above false ones, over every possible cut-off. It does not say what happens at any one cut-off.
- **TPR / FPR**: true-positive rate (= recall) and false-positive rate (false alarms as a share of stories that do not have the condition). F-0020 is stated in these.
- **Tolerance (F-0020)**: how much reader error the engine can absorb before its outputs move more than the engine's own run-to-run noise. Measured in Step 1 for the 78 condition keys only: pass at TPR 0.95 with FPR up to 0.0025, or TPR 0.90 with FPR 0.001.
- **Ceiling**: how often two competent judges agree on the same items. A reader cannot be expected to agree with one judge more often than that judge agrees with another, unless the goal is to copy one judge's quirks. Measured so far: Jev vs Sonnet, topic 42/50 = 0.84, country 46/50 = 0.92, type/scope/focus 0.71 per label, conditions overlap 0.41 (F-0049). Jev vs Clef: not measured yet (D-0024).
- **Calibration**: when the reader says "90% sure", is it right 90% of the time?
- **Gate**: a check that must be true before scoring makes sense (definitions agreed, enough test items, fast enough). A gate is not evidence that the reader reads well.
- **Wilson bound**: the statistical lower edge of what a measured share could really be, given how few items were measured. 0 swaps in 30 items still allows a true swap rate of up to about 10%.

---

## 1. Verdict

The owner's instinct is right. The draft has the right shape (every area has rows, scorers are named, regression and sample-size rules exist, and both MM3 reviews praised that, N-0019) but most of its numbers are not criteria: they are round numbers with no reason attached, measured in a unit the engine does not use, and padded with rows that cannot fail. The result is a scorecard where 5 of 50 rows pass (F-0060; GO.md calls the honest count 2-3) and nobody can say whether passing all 50 would make the engine work.

### 1.1 The three biggest problems

**Problem 1. Bars with no stated reason (28 rows marked "*goal*").** Nearly every pass mark is a round number: 0.97, 0.95, 0.90, 0.85, 0.80, 0.70. The draft itself says a *goal* number "has no measured source yet". Both MM3 reviews flagged this twice and it was not fixed (N-0019 q1, N-0020 q1 "still flagged by both"). Examples: C1/C2 0.97 (why not 0.93 or 0.99?); T2 opinion and forecast 0.85 (baseline 0.71 / 0.64, F-0048, no ceiling known); P2 topic 0.85 while Jev and Sonnet themselves agree only 0.84 (F-0049); K2 "AP 0.70 per key" has no relation to the one tolerance fact we own (F-0020), which is stated in TPR and FPR, not AP. The only well-derived bars in the whole draft are K6 (2.5 false alarms per 1,000, from F-0020) and K7 (tolerance itself).

**Problem 2. Criteria are measured in a unit the engine does not consume, and three areas were never checked against what the engine does with them.** I read the consumer:
- Story type: the engine does not rank. It cuts each of the four type probabilities at 0.5 and assigns one weight class: fact 1.0, forecast 0.3, opinion 0.3, unclear 0.5 (`classify.py:99-105`, `probes/persona/rules/type_weights.csv`). T2 measures AP, which says nothing about how many stories land on the wrong side of 0.5.
- "Recent": a story with recent < 0.3 (or opinion >= 0.5, or neither happened nor announced >= 0.5) is dropped entirely (`classify.py:61`, used at `world_service2.py:105`). This is the single most expensive error in the pipeline and it has **no criterion** (S4 "old events flagged as not recent, recall 0.90" is the nearest, and it is a probe, not the gate).
- Scope national / local / new: **no engine code reads them** (no consumer of the `s|` answers in `classify.py`, `engine.py`, `engine2.py`, `world_service2.py`, `intake.py`). Nine rows (S1-S9) grade labels that go nowhere, while D-0017 says the target is the engine's outputs.
- US / foreign focus: `classify.py:62` turns them into an entry point, but the live service overrides that with the country answer (`world_service2.py:166`). S3 checks consistency of a path that is not used.
- Country: the only use is the entry point, `COUNTRY:x` if the country is in the list, else `WORLD:world` (`world_service2.py:166`). A miss and a wrong country have different costs (spread over the world vs the wrong country), and neither cost has been measured; C1/C2 use the same 0.97 for both.
- Topic: it limits which conditions a story may move (`world_service2.py:435-436`; the `moves:` lists in the ontology). A confusion between two topics with the same `moves` list costs nothing; a confusion that blocks a real condition reading costs a whole reading. P2 "accuracy 0.85" treats all confusions the same.
- Tolerance was measured for conditions only (`sensitivity.py`, 78 keys). Nothing in the draft ties type, recent, country or topic to the engine's noise band, so D-0014's "downstream tolerance is a separate check" is true for one area and absent for four.

**Problem 3. About 15 of the 50 rows cannot fail, or do not measure the reader, and they sit in the grade's denominator.** Area grade = rows passed / rows in the area (scorecard.py line 4). Rows that are gates, bookkeeping or construction: C7 (fallback matches the table: a table lookup, 100% by construction; the real question, "is the table right", is a human check), C9 (source table complete: bookkeeping), C10 (speed: a requirement, not reading quality), S3 (100% consistent by construction when computed), K3 (enough positives: a property of the test set, not the reader), the five regression rows C11/T10/S8/P10/K10 (a rule, applied to other criteria, not a criterion), and the four codebook rows T1/S1/P1/K1 (a property of the definitions, a gate before labelling at scale; skill §1b). The three "generous" passes GO.md admits (C5, C7, C9) are all of this kind. A reader that reads nothing would pass C7, C9, C10, S3 and all five regression rows: 9 of 50 for free.

### 1.2 Criterion by criterion, where it matters

Country
- C1, C2 (0.97 *goal*): no reason for 0.97; recall and precision given the same bar although misses and wrong countries do different things downstream. Scored against a Sonnet reviewer (F-0062), not Jev; that is a fine choice for a scriptable fact but it is not stated in the draft, and the two reviewer files that exist (`data/country-val/review-a.jsonl`, `review-b.jsonl`) have never been compared to each other to get the ceiling.
- C3 (18/20 per country, 100 countries): 2,000 reviewer-labelled stories to build, not built, and the pooled-per-region bar (0.95 *goal*) has no reason.
- C5 (0 swaps): measured on 30 probes against a stated bar of >= 20 per pair (6 pairs = 120). 0/30 leaves a true swap rate of up to ~10% (Wilson). Marked pass.
- C6 (0.95 routed): the enforced value is `min(club_clean, ambiguous_clean)` over 30 probes each; the draft's name ("go to review") describes a behaviour the checker does not have (it either names a country or not; there is no review queue).
- C7, C9, C10: gates, not criteria (above).
- Missing: multi-country stories. D-0015 says "named countries are the label" (plural) but the engine takes one entry country (`world_service2.py:166`). Which one wins is undefined and unscored. Missing: per-outlet floor (country ranges 0.61 irishtimes to 0.93 by outlet, F-0072).

Story type
- T2: AP, see Problem 2. Opinion 0.85 and forecast 0.85 are *goal* with no ceiling.
- T3 (opinion from URL/feed, 0.95): measures a URL rule, not the reader.
- T6 (flip test, "drops by half"): a good idea; "by half" is a judgement about the probability, but the engine only cares whether it crosses 0.5.
- T7 (non-news false alarms <= 50 per 1,000): "false alarm" of what? A sport score labelled "happened" is correct under the codebook. The criterion is not defined well enough to fail honestly.
- T8 (calibration at 0.9): the engine cuts at 0.5; calibration at 0.9 is the wrong place to look.
- Missing: the weight-class agreement (fact / opinion / forecast / unclear), which is what the engine uses. Missing: the cost direction (an opinion counted as fact enters at 3.3x the weight it should).

Scope and focus
- S1, S2, S5, S6, S7, S9: grade national / local / new, which the engine does not read (Problem 2). Either the engine will read them (then they need a consumer-based bar) or they are informational until the owner says otherwise.
- S3: by construction, and on an unused path.
- S4: the only row near the `recent` gate, and it is a recall on a probe set rather than the gate agreement on the frozen set.

Topic
- P2 (0.85 *goal*): above the only measured ceiling (Jev vs Sonnet 0.84, F-0049). Also accuracy over 49 classes hides collapse on small topics: the same reader scores 0.757 accuracy but 0.675 average per-topic F1 (models.json, e5tfidf).
- P3 (recall >= 0.70 per topic on keyword-mined probes): mining by keyword selects the easy, keyword-bearing stories, so the probe set is biased in the reader's favour. The frozen set already has per-topic counts; use those.
- P4 (confusable pairs): the pairs should come from the confusion table on F, and the bar should depend on whether the pair shares a `moves` list (free confusion) or not (costly).
- P6 (section prior agrees with text, 0.90): measures the feed metadata, not the reader.
- P9 (top-2 contains the jury topic, 0.95): the engine takes one topic; top-2 is not consumed.
- Missing: per-outlet floor (topic 0.63 nbcnews to 0.86 japantimes, F-0072); the condition-mask cost of a wrong topic.

Conditions
- K1 (alpha >= 0.8 per key): recorded as fail from juror overlap 0.34-0.41 (F-0049), which is overlap, not alpha; the definition test (T-0011) has not been run. A gate, not a criterion.
- K2 (AP >= 0.70 on every accepted key): the only bar not tied to F-0020 in the one area where F-0020 exists. 4 of 48 keys pass (F-0058); nobody can say whether an AP-0.70 key is inside tolerance.
- K3: a test-set property.
- K6 (<= 2.5 per 1,000 per key): the one well-derived bar in the draft. Keep.
- K7 (engine tolerance): the actual goal, listed last and "not built".
- K8 (calibration at 0.9): the engine uses the probability as the reading's strength (`sensitivity.py` `presence`: readings count when m >= ATTR_MIN 0.65, strength = max m), so calibration matters from 0.65 upward, not only at 0.9. The 0.9 band currently holds 48 items (k6k8.json), too few for a bar.
- K9 (per-item proof): good; keep.
- Missing: the conflict rule. When both directions of a dial clear the bar on one story, the engine drops the dial (`sensitivity.py` `readings_of`; `C.read`). A reader that fires both directions silently loses readings. No criterion counts conflicts.
- Missing: key tiers. F-0020's companion rankings (S-0003: 16 keys that appear in at least 2 of the 5 Step 1 rankings) say which keys move the engine. The draft treats all 78 alike.

---

## 2. Principles of good acceptance criteria

Each with a one-line reason and a good / bad example from this ontology.

1. **Every bar has a derivation, written next to it.** Reason: a number without a reason cannot be defended, raised or lowered; it can only be argued about. Bad: C1 "recall >= 0.97 *goal*". Good: K6 "<= 2.5 false alarms per 1,000 per key, because F-0020 shows the engine's outputs stay inside its noise band at FPR 0.0025 with TPR 0.95".

2. **Measure what the consumer consumes, in the consumer's unit.** Reason: a metric the engine never sees can pass while the engine breaks. Bad: T2 "AP 0.95 for happened" (the engine cuts at 0.5 and assigns a weight). Good: "share of stories whose weight class (fact / opinion / forecast / unclear) matches Jev's".

3. **A criterion must be able to fail, and a failure must point at the reader.** Reason: rows that pass by construction inflate the grade and hide the real count. Bad: C7 "fallback matches the outlet table" (a lookup of the same table). Good: C1 "named countries found", scored against reviewer labels made without seeing the script's output.

4. **Gates are not criteria; keep them out of the grade.** Reason: "the definitions are agreed", "there are enough positives", "it runs in 10 ms" are preconditions for scoring, not evidence of reading quality. Bad: K3 counted as 1 of 10 condition rows. Good: K3 listed under "prerequisites" and the area graded on the remaining rows.

5. **Bars sit between a measured baseline and a measured ceiling.** Reason: below the baseline the bar is empty; above the ceiling the reader is being asked to copy one judge's noise. Bad: P2 topic 0.85 with ceiling 0.84 (Jev vs Sonnet, F-0049). Good: "P2 bar = Jev-vs-Clef agreement on the same 500 items minus 0.05, recomputed when that agreement is measured" (D-0024 names this measurement; it has not been run).

6. **Count errors where they cost, separately by direction.** Reason: a miss and a false alarm usually do different things downstream; one bar for both hides the expensive one. Bad: C1 and C2 both 0.97. Good: "opinion counted as fact (enters at weight 1.0 instead of 0.3): <= N per 1,000" and "fact counted as opinion: <= M per 1,000", with N and M set from the type-tolerance run.

7. **Worst case, not only average: a floor per element and per source.** Reason: a pooled score can pass while whole topics, countries or outlets fail (topic 0.63 to 0.86, country 0.61 to 0.93 by outlet, F-0072). Bad: P2 as one number. Good: "every topic with >= 30 positives in F has recall >= x; every outlet with >= 60 stories in F scores >= y".

8. **Probe sets are sized for the claim, chosen without the reader's help, and labelled blind.** Reason: "0 swaps in 30" supports "under 10%", not "never"; keyword-mined probes favour the reader. Bad: C5 "0 swaps" on 30 items; P3 on keyword-mined stories. Good: "0 swaps on 120 look-alike items (6 pairs x 20), reported with its Wilson upper bound"; per-topic recall on the frozen set.

9. **One criterion = one named set, one scorer, one number, one example of failure.** Reason: if a reader fails the row, the next action must be obvious. Bad: K2 "F + P-key" (two sets mixed, no stated split). Good: K9 "20 false alarms from F, each given a cause (input lacks it / codebook / model); 18 of 20 explained".

10. **Grade only labels that go somewhere, or say they are informational.** Reason: nine scope rows grade labels no engine code reads; that is effort and a false sense of coverage. Bad: S2 "national, local, new, AP >= 0.85 each". Good: "recent gate agreement >= 0.97 (the engine drops stories below 0.3); national / local reported, not graded, until the owner decides whether the engine will read them".

---

## 3. Proposed criteria set

Common definitions for this section:
- **F**: the frozen test set, 11,997 stories, Jev labels (F-0072).
- **J (jury subset)**: 500 stories drawn at random from F, labelled by Jev (have), Clef (to run, local, approved), and Opus as tie-break where they differ (D-0024). J is the "gold" set: where Jev and Clef agree the label is treated as settled; where they differ, Opus decides. 500 items give about +/- 4 points at 95% confidence for a share near 0.85, enough for pooled bars; probes cover rarer behaviour.
- **Ceiling (per area)**: Jev-vs-Clef agreement on J, measured once. Every "ceiling - x" bar below is provisional until that number exists; the provisional value in brackets uses Jev-vs-Sonnet (F-0049) as a stand-in.
- **Per-outlet floor**: every outlet with >= 60 stories in F (51 outlets, F-0072).
- **Gates (not graded, listed once per area)**: codebook agreement alpha >= 0.8 (skill §1b), enough positives (>= 30 in F per element), speed < 100 ms per story for all areas together (D-0007), regression rule (an accepted criterion is reopened when it drops below its bar by more than its 95% interval).

### 3.1 Country

Engine use: entry point only (`COUNTRY:x`, else `WORLD:world`, `world_service2.py:166`). Rule D-0015: named country wins; else the outlet's home country; never both.

| # | Name | Measured, on what | Pass mark, and why | Fails when | Example |
|---|---|---|---|---|---|
| C-a | Named country found | Recall of named countries on the J stories that name at least one (about 85% of stories do: 279 of 300 fresh, `country-val.json`); reviewer labels made blind to the script | >= ceiling - 0.02, where the ceiling is reviewer-a vs reviewer-b agreement on the same items (`review-a.jsonl`, `review-b.jsonl`, never compared). Provisional 0.95. Reason: a miss sends the story to the whole world instead of one country; the exact cost needs the country-tolerance run (§4) | the script skips a country written as a demonym, a city, or inside a club name | "Sudan" vs "South Sudan" (review-a item 2); current recall 0.88 fresh (F-0062) |
| C-b | Wrong country | Wrong-country claims per 1,000 stories on J (false alarms, not precision, so the number is in the engine's unit: stories that enter the wrong country) | <= 30 per 1,000 provisional, to be set by the country-tolerance run; reason: a wrong country moves the wrong population | club names, Georgia the state, Jordan the person, "turkey" | club probes: precision 0.53 (F-0062) |
| C-c | Multi-country stories | On P-multi (200 stories from F naming >= 2 countries, mined by script, labelled by reviewer): does the reader's single entry country match Jev's | >= 0.85 provisional (ceiling unknown; this is a judgement, e.g. "US sanctions on Iran" is about both). Reason: the engine takes one country; the rule for choosing is unstated today | the reader always takes the first name, or the outlet's country | "Trump meets Kim in Singapore" |
| C-d | Look-alikes never swapped | 0 swaps on P-lookalike, 120 items (6 pairs x 20: Niger/Nigeria, Sudan/South Sudan, DR Congo/Congo, North/South Korea, Guinea/PNG, Dominica/Dominican Rep.), reported with the Wilson upper bound | 0 of 120 (upper bound ~2.5%). Reason: a swap is a wrong country with a predictable cause; 120 is the draft's own stated size (C5), which the current 30-item pass does not meet | a swap | "Niger" read as Nigeria |
| C-e | Ambiguous words give no false country | On P-ambig (100 items: Georgia, Jordan, Chad, Turkey the bird, club and team names), the share with no wrong country | >= 0.95. Reason: this is the known failure mode (C6 club clean 0.70 today); 100 items make 0.95 a claim of "no more than ~10%" at the lower bound, honest for a probe | a club or a person name is read as a country | "Georgia Tech beats Clemson" |
| C-f | Per-outlet floor | C-a recall per outlet, on F (reviewer labels on the per-outlet sample, or Jev's named-country labels as stand-in) | >= 0.85 for every outlet with >= 60 stories. Reason: country ranges 0.61 (irishtimes) to 0.93 by outlet (F-0072); the engine's feed is outlet-heavy (the-hindu 971 of 7,702 queue items) | one outlet's style (e.g. Irish place names) defeats the script | irishtimes 0.61 |

Gates: fallback table checked by a human once (the 9 `check` rows; today's C7/C9); speed (10.8 ms, fine). Dropped from the grade: C3 (2,000 reviewer labels for a per-country screen; replace with C-f plus a per-UN-region recall report), C7, C9, C10, C11.

### 3.2 Story type

Engine use: weight class from the four probabilities at 0.5 (fact 1.0 / forecast 0.3 / opinion 0.3 / unclear 0.5) and the drop gate (opinion >= 0.5 or neither happened nor announced >= 0.5 drops the story).

| # | Name | Measured, on what | Pass mark, and why | Fails when | Example |
|---|---|---|---|---|---|
| T-a | Weight class agrees | On J: the reader's four probabilities put through `type_weight` give the same class as Jev's | >= ceiling - 0.03 (provisional 0.90; Jev-vs-Sonnet is 0.71 per label on type/scope/focus, F-0049, but class-level agreement is not known). Reason: the class is the only thing the engine takes from this area | opinion or forecast probability crosses 0.5 the wrong way | an analysis piece ("What the rate rise means for you") read as fact |
| T-b | Opinion counted as fact | Per 1,000 J stories: Jev class opinion, reader class fact | <= 20 per 1,000 provisional; to be set by a type-tolerance run (§4). Reason: the costly direction, the story enters at 3.3x its weight | columns without an "Opinion:" prefix | "Why the Fed is wrong about inflation" |
| T-c | Fact down-weighted | Per 1,000 J stories: Jev class fact, reader class opinion or forecast | <= 30 per 1,000 provisional (same run). Reason: a real event enters at 0.3; cheaper than T-b but a loss | reports quoting a forecast ("IMF predicts...") | "Bank of England raises rates, warns of more to come" |
| T-d | Tense flip | 100 script-made pairs from F ("X raised rates" / "X will raise rates"): the class must change from fact to forecast | >= 90 of 100 pairs flip. Reason: proves the reader reads tense, not topic; crossing 0.5 is what the engine sees, so "drops by half" (T6) is replaced by "changes class" | the reader keys on "rates" and ignores "will" | "Fed raises rates" vs "Fed will raise rates" |
| T-e | Headline only | T-a on the J stories with a description under 40 characters | within 0.05 of T-a. Reason: feed items often have no description; the reader must not depend on it | the reader uses description cues only | AP wires with headline only |
| T-f | Per-outlet floor | T-a per outlet on F | >= 0.80 for every outlet with >= 60 stories. Reason: type agreement ranges 0.79 (bloomberg, cnbc) to 0.93 by outlet (F-0072); business wires are forecast-heavy | one outlet's house style | bloomberg 0.79 |

Gates: codebook alpha (T1), regression (T10). Dropped: T2 (AP), T3 (URL rule, not the reader; keep the rule as an input feature), T7 (undefined false alarm), T8 (calibration at 0.9; the cut is 0.5 and T-a covers it).

### 3.3 Scope and focus

Engine use: `recent` is a hard gate at 0.3 (`classify.py:61`, `world_service2.py:105`). National / local / new: not read by any engine code. US / foreign focus: overridden by the country answer on the live path. The owner has a decision to make here (draft "Decisions needed" item 2 plus this new fact); until then two criteria carry weight and the rest are reported, not graded.

| # | Name | Measured, on what | Pass mark, and why | Fails when | Example |
|---|---|---|---|---|---|
| S-a | Recent gate agrees | On J: reader recent >= 0.3 matches Jev recent >= 0.3 | >= 0.97, and wrongly dropped (Jev yes, reader no) <= 10 per 1,000. Reason: a wrong "no" deletes the story from the engine, the only error with no partial credit; feeds are almost all recent, so a high bar costs little | the reader reads "in 2015" or an anniversary as current, or a terse wire as not current | "Ten years after the crash, what changed" |
| S-b | Old events not recent | On P-old (100 stories: anniversaries, retrospectives, trials of old crimes, "in 2015"; mined by script, reviewer-labelled): reader recent < 0.3 | >= 0.90. Reason: the only realistic way the gate fails in practice; the draft's S4 kept | an old event with a fresh verb | "Court hears 2015 fraud case" (recent: the hearing is now) |
| S-c | National / local (informational) | Agreement with Jev on J, per label | reported, no bar, until the owner decides whether the engine will read scope (D-0017 target = engine outputs; these are not outputs the engine uses) | - | - |
| S-d | US / foreign focus | dropped as a criterion; computed from the country rule if the engine ever needs it (draft decision 2) | - | - | - |

Gates: codebook alpha for whatever stays graded. Dropped: S2, S3, S5, S6, S7, S9 (grade labels nothing reads; S9's "no scope on non-news" belongs with the topic non-news probe).

### 3.4 Topic

Engine use: one main topic; it limits which conditions may move (`world_service2.py:435-436`; `moves:` per topic in the ontology). "other" is allowed. D-0022: finer labels are allowed and rolled up to these 49 before scoring.

| # | Name | Measured, on what | Pass mark, and why | Fails when | Example |
|---|---|---|---|---|---|
| P-a | Topic agrees | Accuracy on J after roll-up (D-0022) | >= ceiling - 0.05 (provisional 0.80; Jev-vs-Sonnet 0.84, F-0049). Reason: above the ceiling the reader is copying Jev's noise; today's best is 0.785 (ensemble, models.json), so the bar is reachable and still meaningful | - | - |
| P-b | Costly confusions | On F: share of Jev's condition readings that the reader's topic would block (the reader's topic's `moves` list does not contain the condition) | <= 5 per 100 readings provisional; to be set by a topic-tolerance run (§4). Reason: this is what a wrong topic does to the engine; a confusion between two topics with the same `moves` list costs nothing and should not count | growth read as markets when the story moves job_security | "Factory output falls, layoffs expected" read as markets_investment |
| P-c | Per-topic floor | Recall per topic on F (Jev labels), every topic with >= 30 positives | >= 0.60. Reason: pooled accuracy hides small topics (accuracy 0.757 vs per-topic F1 0.675); F is unbiased where keyword-mined probes are not (replaces P3) | a small topic collapses into a neighbour | sport stories (F-0051 gap) into culture_leisure |
| P-d | Named confusions bounded | The 5 largest off-diagonal cells of the confusion table on F, named each round | each <= 3% of its row's stories, and none between topics with different `moves` lists above 2%. Reason: confusions are where rounds are aimed (D-0013); naming them makes the next round's target explicit (replaces P4) | one pair dominates the errors | growth vs jobs; crime vs courts |
| P-e | "Other" honest | On F: reader's "other" rate vs Jev's, and precision of "other" | within 5 points of Jev's rate, precision >= 0.70. Reason: "other" is the dump; the right rate is Jev's, not 10% | the reader says "other" when unsure | - |
| P-f | Per-outlet floor | P-a per outlet on F | >= 0.65 for every outlet with >= 60 stories. Reason: 0.63 (nbcnews) to 0.86 (japantimes), F-0072 | one outlet's mix | nbcnews 0.63 |
| P-g | Non-news gets no moving topic | On P-nonnews (200: sport results, recipes, listings, shopping; mined by section, reviewer-checked): share given a topic whose `moves` list is non-empty, other than culture_leisure / consumer_retail where correct | <= 20 per 1,000. Reason: a non-news item with an economic topic can move prices or jobs in the engine | a listicle read as inflation | "10 best air fryers under $100" read as consumer prices |

Gates: codebook alpha (P1). Dropped: P6 (section metadata, not the reader), P8 (calibration; the engine takes one topic, not a probability), P9 (top-2 not consumed).

### 3.5 Conditions

Engine use: 78 condition|direction keys; a reading when exactly one direction clears 0.65; both directions = conflict = the dial is dropped; strength = the probability. Tolerance measured (F-0020). Key importance ranked in Step 1 (16 key keys, S-0003).

| # | Name | Measured, on what | Pass mark, and why | Fails when | Example |
|---|---|---|---|---|---|
| K-a | Inside engine tolerance (the goal) | Per key on F: the reader's (TPR, FPR) against Jev at the reader's operating threshold | inside the F-0020 passing region: TPR >= 0.95 with FPR <= 0.0025, or TPR >= 0.90 with FPR <= 0.001. Reason: this is the measured fact; AP 0.70 (K2) is a proxy with no known relation to it. Graded on the 16 key keys first; the rest report | a key's recall is below 0.90 at any usable threshold (today the best key, asset_values\|up, has recall 0.67 at its K6 threshold, k6k8.json) | asset_values\|up |
| K-b | False alarms per key | Per key on F: false alarms per 1,000 stories that do not have the key | <= 2.5 per 1,000 (F-0020; today's K6, kept as is). Reason: the one bar in the draft with a derivation; 19 of 48 keys pass (F-0068) | a cue word fires without the condition | "prices" in a sport transfer story |
| K-c | Conflicts | On F: stories where the reader clears 0.65 for both directions of one dial, per 1,000, vs Jev's own conflict rate | <= Jev's rate + 5 per 1,000. Reason: a conflict silently drops the dial (`readings_of`); nothing counts it today | the reader fires prices\|up and prices\|down on "prices rose then fell" | - |
| K-d | Direction flip | P-flip: 20 script-made pairs per key for the 16 key keys (320 pairs; "prices rose" / "prices fell"): the up probability must fall below 0.65 and the down probability rise above it | >= 90% of pairs flip cleanly. Reason: the engine acts on direction; the cross-over at 0.65 is what it sees ("by half", K4, replaced) | the reader keys on the noun and ignores the verb | "Rents fall for first time in a decade" |
| K-e | Readable keys only | Gate turned into a report: a key is graded only once Jev-vs-Clef agreement on its positives in J is >= 0.6; below that after two codebook rewrites it is recorded as "not readable from headline + description" and raised with the owner (skill §1b) | - (a status, not a score). Reason: juror overlap 0.34-0.41 (F-0049) means many keys may not be readable from 250 characters; training against them wastes rounds | - | information_reliability\|down (AP 0.09) |
| K-f | Strength honest | On F, readings with probability >= 0.65: calibration error in the 0.65-0.8, 0.8-0.9, 0.9-1.0 bands | each band's true share within 0.10 of its stated probability (replaces K8's single 0.9 point). Reason: the probability becomes the reading's strength; today the 0.9 band is right 0.77 of the time on 48 items (k6k8.json) | over-confidence at the top | - |
| K-g | Per-item proof | 20 false alarms from F each round, each given a cause (input lacks it / codebook / model) by a reviewer | >= 18 of 20 explained (K9, kept). Reason: the round's aim comes from the causes | causes cannot be found | - |

Gates: enough positives (K3), codebook alpha (K1), regression (K10). Dropped from the grade: K2 (AP 0.70; keep as a progress number on the card, not a pass bar), K5 (a passing mention is a false alarm; covered by K-b, keep the probe as a view of K-b).

---

## 4. What it takes, and keep / change / drop

### 4.1 Measurements and sets to build

| Item | What | Size | Labels needed | Rough time and cost |
|---|---|---|---|---|
| J, the jury subset | 500 random stories from F | 500 | Jev (have); Clef locally (approved, ~64 stories/min, F-0047: ~10 min); Opus tie-break on disagreements: roughly 75 topic, 150 type/recent, up to 300 condition items | half a day of agent time; Opus about 500 short calls, order of $10-25 (to confirm before running, hosted = money) |
| Ceilings | Jev vs Clef agreement per area on J; Jev test-retest (re-ask the same 500) | 500 | Jev re-ask ~$0.25 (GO.md: ~$0.5 per 1,000) | 1 hour |
| Two-reviewer ceiling, country | compare `review-a.jsonl` vs `review-b.jsonl` | exists | none | 15 minutes |
| P-multi | F stories naming >= 2 countries | 200 | reviewer (Sonnet `[S2]`) blind | 1 hour, cents |
| P-lookalike | 6 pairs x 20 | 120 | reviewer | 1 hour, cents; CC-News mining exists (country_check) |
| P-ambig | Georgia, Jordan, Chad, Turkey, clubs | 100 | reviewer | 1 hour |
| P-old | anniversaries, retrospectives, old trials | 100 | reviewer | 1 hour |
| P-flip (type) | script-made pairs from F | 100 pairs | none (script-made; 20 spot-checked) | 1 hour |
| P-flip (conditions) | 20 pairs x 16 key keys | 320 pairs | none (script-made; 40 spot-checked) | 2 hours |
| P-nonnews | sport results, recipes, listings, shopping | 200 | reviewer | 1 hour |
| Per-outlet floors | F per outlet | exists (`source_analysis.py`, F-0072) | none | 30 minutes |
| Tolerance runs (type, recent, country entry, topic mask) | three new modes of `sensitivity.py`: inject class errors, entry errors, topic-mask errors at set rates, compare drift to the noise band exactly as F-0020 did | - | none; CPU only; needs a code change in a probe script (not the engine), owner's yes | about one Step-1-sized run each, chunked under the 1-hour cap; a day in total |
| Human | the 9 `check` rows in the source table; the scope decision; the "which country wins" rule for multi-country stories | - | owner | minutes |

Everything above fits the standing rules: local Clef is approved; hosted Opus and Jev calls are flagged here and run only after the owner says yes; no run longer than one hour unattended.

### 4.2 Keep, change, drop (current 50 rows)

| Decision | Rows |
|---|---|
| Keep as is | K6 (false alarms per 1,000, F-0020), K9 (per-item proof), S4 (old events, becomes S-b), T9 (headline only, becomes T-e), C5 (look-alikes, at 120 items not 30) |
| Change the unit or the bar | C1 -> C-a (bar from reviewer ceiling), C2 -> C-b (per 1,000, cost-based), C6 -> C-e (100 items, name fixed), T2 -> T-a/T-b/T-c (class, not AP), T6 -> T-d (class change, not "half"), P2 -> P-a (ceiling-based), P3 -> P-c (on F, not mined), P4 -> P-d (from the confusion table, cost-aware), P5 -> P-e (Jev's rate), P7 -> P-g (moves-aware), K2 -> K-a (tolerance, not AP; AP stays as a progress number), K4 -> K-d (cross-over at 0.65), K7 -> K-a (promoted to the main bar), K8 -> K-f (bands from 0.65) |
| Move to gates (not graded) | C7, C9, C10, T1, S1, P1, K1, K3, and the five regression rows C11, T10, S8, P10, K10 |
| Drop | C3 (replaced by C-f and a per-region report), C4 (demonym/city already pass; fold into C-a's reviewer set), C8 (D-0022 made off-list countries their own codes; what remains is C-b), T3, T7, T8, S2, S3, S5, S6, S7, S9, P6, P8, P9, K5 (folded into K-b) |
| New | C-c multi-country, C-f / T-f / P-f per-outlet floors, S-a recent gate, P-b costly confusions, K-c conflicts, K-e readable keys |

Net: 50 rows become 6 + 6 + 2 (+2 informational) + 7 + 7 = 28 graded criteria, every one with a reason, a named set and a way to fail, plus a short gate list per area.

### 4.3 What this changes about the current scorecard reading

Against the proposed set, today's best readers would stand roughly: country C-a 0.88 vs provisional 0.95 (fail), C-d 0/30 (not yet measured at 120); story type T-a unknown (class agreement never computed; AP cannot be converted); scope S-a unknown; topic P-a 0.785 vs provisional 0.80 (near), P-c and P-f unknown but F-0072 says some outlets and topics will fail; conditions K-a 0 of 16 key keys (recall 0.67-0.74 at the K6 thresholds on the best keys), K-b 19 of 48. That is a harder card than 5/50, and an honest one: it says exactly which measurement to run next and why.

---

*Proposal only. Approval of bars, sets and the scope decision rests with the owner (GO.md step 5). After approval: MM3 check of this set (`tools/mm3local`, `tools/mm3hosted`, splits recorded), then the ledger, then the scorecard fingerprint moves.*

---

## Addendum (2026-10-21): sourced criteria method — Haiku and Sonnet research

Added at the owner's request. The review above cites no outside sources; this addendum does. Research: two Haiku researchers (practitioner docs; "circling" methods) and one Sonnet researcher (primary papers, skill). Only pages the researchers opened are cited. Full notes: `docs/research/2026-10-20 Criteria best practices (sources).md`, `docs/research/2026-10-21 Criteria practitioner sources (Haiku).md`, `docs/research/2026-10-21 Criteria circling methods (Haiku).md`. The method is written as a skill: `.claude/skills/acceptance-criteria/SKILL.md`.

### What the sources say

| Source | Rule we take from it | Fable principle it backs |
|---|---|---|
| Breck et al., *The ML Test Score*, Google, 2017 (research.google/pubs/pub46555) | Thresholds per slice ("error for slice x must be <5%"), regression limits, beat a simple baseline, calibration, grade = minimum over sections, not average | 5, 7, and a new rule: grade = minimum |
| Ribeiro et al., *CheckList*, ACL 2020 (arXiv 2005.04118) | Three test types: minimum functionality (small focused probes), invariance (irrelevant edits keep the label), directional (edits move the label the expected way) | 3, 8 |
| Gardner et al., *Contrast Sets*, 2020 (arXiv 2004.02709); Kaushik et al., ICLR 2020 (arXiv 1909.12434) | Small manual edits that flip the gold label probe the decision boundary | 3, 6 |
| Chen et al., *Slice-based Learning*, NeurIPS 2019 (arXiv 1909.06349); Mitchell et al., *Model Cards*, 2019 (arXiv 1810.03993) | Report every metric per application-critical slice and subgroup | 7 |
| Krippendorff, 2011, *Agreement and Information in the Reliability of Coding* | Agreement thresholds α 0.667 / 0.800; size the reliability sample by the RAREST label (e.g. 103 values at 50/50 vs 560 at 5% for α 0.8) | 5 (ceiling), 8 |
| Gebru et al., *Datasheets for Datasets*, 2021 (arXiv 1803.09010) | Write down composition, collection process and labeller for every set | 8, 9 |
| Kiela et al., *Dynabench*, NAACL 2021 (arXiv 2104.14337) | Keep adding the model's newest failures to the test ring each round | new: refresh the ring per round |
| Cucumber, *Gherkin reference* | Given / When / Then: a criterion names its context, action and expected outcome | 9 (atomic) |

**Practitioner finding (Haiku, 13 sources: Hugging Face, Unsloth, Axolotl, TRL, LightEval, Cleanlab, Great Expectations, Deepchecks, Evidently):** they agree on held-out evaluation, early stopping on a validation signal, hand inspection of flagged items, and model/dataset cards. **None publishes a numeric acceptance threshold** — the method for setting bars comes from the papers above, not from tooling docs.

**Not found or not verified:** a primary source for source-stage checks and for the none/abstain case (these rest on our own review); the Krippendorff 2004 book wording; the Wilson-interval paper (the formula is used as standard statistics).

### The optimised criteria method

1. **One atomic sentence per criterion, every field required:**
   *On [probe set: name, size, how chosen, who labelled it], [reader]'s [measure, in the unit the engine uses] for [element or slice] is [≥ bar], because [baseline / ceiling / tolerance, with its id]; it fails when [one real failing item].*
2. **Four levels, each with its own rows:** SOURCE (where texts come from), DATA (the labelled set: agreement, balance, leakage), MODEL (the reader), PIPELINE (labels from the same text the reader sees; the engine's tolerance downstream). Source and data rows are usually gates; pipeline rows hold the real goal.
3. **Circle each element from six directions:** left/right along the pipeline (source → data → labels → model → engine); up/down from area → element → slice (per outlet, region, rare label); sideways to near-miss look-alikes, edits that must not flip the label, edits that must, and the none case. An empty direction is a missing criterion or a written reason.
4. **Bars sit between a measured baseline and a measured ceiling** (teacher-vs-teacher agreement), or come from the engine's tolerance when measured (F-0020). Round numbers are marked provisional with the measurement that replaces them.
5. **Sample size decides what a pass proves:** print the Wilson bound next to every share (0 of 30 still allows up to 11%; 0 of 120, 3.1%); size agreement sets by the rarest label.
6. **Gates stay out of the grade; the grade is the minimum over areas.** A row that a reader reading nothing would pass is a gate, not a criterion.
7. **Refresh each round:** add the reader's newest near-misses to the sideways ring.

### What this changes in the proposal above
- Fable's 10 principles now each have a published source, except the source-stage and none-case rules.
- Added: invariance tests per element, calibration per band and slice, grade = minimum over areas, Wilson bounds on every share, agreement sets sized by the rarest label, and a refresh of probe sets each round.
- The worked examples in the skill (country, story type, conditions) use this review's numbers and stay provisional until the measurements in §4 run.
