# Acceptance criteria per ontology area (DRAFT, 2026-10-20)

Status: revision 2 after MM3-0482 (local) and MM3-0483 (hosted), both 'revise then approve'; splits in N-0019. Draft for the user's approval; then MM3 check (`tools/mm3local`, `tools/mm3hosted`) and into the ledger. Nothing is trained against these before approval.

Method (D-0013, D-0014, D-0015, skill `ontology-trainer` step 1):
- Criteria are judged against the ontology itself: did the reader give the right label. World engine tolerance (F-0020) is a separate downstream check, listed per area where it applies.
- Per area, first ask what a **script** can read and what the story's **context** (outlet, date, channel) supplies; the text overrides the context, never both. Script-scored criteria are scored by the script, whose own errors are measured on the pilot. The rest are scored by the jury (one vote per vendor family) or an Opus reviewer.
- Input: headline + first 250 characters of the description (D-0009). Speed: < 100 ms per story on CPU (D-0007), all areas together.
- Test sets: **F** = frozen jury test set (~2,000 fresh stories, never trained on). **P-x** = a probe set built for one criterion (targeted stories, mined by script, size stated).
- **No criterion is scored by the tool that makes the label** (MM3-0482/0483 q6): where a script produces a label, an Opus reviewer labels the probe set from the text alone, without seeing the script's output, and the script is scored against that.
- **Pass rule with sample size** (q4): a pooled criterion passes when its estimate meets the bar and the lower 95% Wilson bound is within 0.05 of it. Per-element sets of 20 are screens only (20/20 still has a lower bound of 0.84): screen bar 18/20 for bars of 0.90 and above, with the formal bar checked on the pooled region or group.
- **Regression rule** (q1): an accepted criterion is reopened when it drops below its bar by more than its 95% interval.
- Numbers marked *goal* have no measured source yet; numbers marked with an id come from the ledger.
- **Not stable** (3-round rule, D-0013): after 3 rounds a criterion has changed direction at least twice, or its net change is smaller than its 95% interval on F. Then it goes to consensus (Opus investigator, then the user).

Baselines (agreement with Jev, frozen e5-small, F-0048): story type happened AP 0.975, announced 0.916; country 0.79; topic 0.69; condition keys mean AP 0.45.

---

## 1. Country (rule D-0015)

Named countries in the text are the label; if none, the outlet's home country (`newsreader/bitmob/source_country.json`; agencies and international outlets = world); never both. No inference from clues. Script: `newsreader/bitmob/country_check.py` (F-0050). A trained model may not be needed.

| # | Criterion | Scored by | Test set | Bar |
|---|---|---|---|---|
| C1 | Named countries found (recall, per story) | reviewer labels, script scored | F | >= 0.97 *goal* |
| C2 | No false country (precision, per mention) | reviewer | F | >= 0.97 *goal* |
| C3 | Every one of the 100 works when named | reviewer labels, script scored | P-country: 20 stories per country, mined from CC-News | screen 18/20 per country; pooled per UN region recall >= 0.95 *goal* |
| C4 | Name, demonym, city, region each work | reviewer labels, script scored | P-how: >= 50 each | >= 0.95, 0.95, 0.90, 0.90 *goal* |
| C5 | Look-alikes never swapped (Niger/Nigeria, Sudan/South Sudan, DR Congo/Congo, North/South Korea, Guinea/PNG) | reviewer labels, script scored | P-lookalike: >= 20 per pair | 0 swaps |
| C6 | Ambiguous words go to review, not to a country (Georgia, Jordan, Chad, turkey, club names) | reviewer labels, script scored | P-ambig: >= 50 | >= 0.95 routed *goal* |
| C7 | Fallback correct when nothing is named | table check | all F stories with no named place | 100% match the table |
| C8 | Places outside the 100 recorded, never forced onto a neighbour | reviewer labels, script scored | P-outside: >= 50 (Ireland, NZ, Singapore, Switzerland...) | 0 forced *goal* |
| C9 | Source table complete | script | every source in the training pool and live feed | 100% covered, `check` rows decided by the user |
| C10 | Speed | timer | F | < 20 ms per story (F-0050: 10.8 ms) |
| C11 | Regression | scorecard | F | regression rule above |

Open (user): the 9 `check` rows in the source table; whether out-of-list countries join the ontology.

## 2. Story type (happened, announced, opinion, forecast; several may be yes)

Script can supply cue words (tense and modals: "will", "plans to", "announced", "said on Tuesday"; opinion sections and "Opinion:" / "Analysis:" prefixes in headline or URL). Context: the URL path or feed name often marks opinion (`/opinion/`, `/comment/`). Jury decides the rest.

| # | Criterion | Scored by | Test set | Bar |
|---|---|---|---|---|
| T1 | Codebook passes | jury | pilot 50 | Krippendorff alpha >= 0.8 per type |
| T2 | Overall per type | jury | F | AP >= 0.95 happened, >= 0.90 announced (F-0048 baseline 0.975 / 0.916), opinion and forecast *goal* 0.85 |
| T3 | Opinion from context | script | F stories with an opinion URL or feed | recall >= 0.95 *goal* |
| T4 | Announced vs happened on plan words | jury | P-plan: >= 100 ("X plans", "X will", "X approved") | >= 0.90 *goal* |
| T5 | Forecast vs report of a forecast (a forecast story is mainly a prediction) | jury | P-forecast: >= 50 | >= 0.85 *goal* |
| T6 | Flip test: "will raise" vs "raised" | script-made pairs | P-flip: 50 pairs | happened probability drops by >= half on the "will" version |
| T7 | False alarms on non-news (sport scores, listings) | jury | P-nonnews: >= 100 | <= 50 per 1,000 *goal* |
| T8 | Calibration | jury | F | at 0.9 confidence, right >= 90% |
| T9 | Headline-only cases | jury | F stories with empty or 1-line description | within 0.05 of T2 *goal* |
| T10 | Regression | scorecard | F | regression rule above |

## 3. Scope and focus (national, local, new, recent; US focus, foreign focus)

Smart extraction: **US focus and foreign focus can be computed from the country rule** (US focus = country is usa; foreign focus = named country differs from the outlet's home country). Proposed: compute, not read (needs the user's yes, as it changes what the engine receives only if the engine reads these as a model output). "New" and "recent": context gives the publish date; script finds dated references ("in 2015", "last year", "anniversary"). National vs local stays with the jury.

| # | Criterion | Scored by | Test set | Bar |
|---|---|---|---|---|
| S1 | Codebook passes (national, local) | jury | pilot 50 | alpha >= 0.8 |
| S2 | Each label works: national, local, new, recent | jury | F | AP >= 0.85 each *goal* |
| S3 | US / foreign focus from the country rule (a consistency check, not accuracy: accuracy comes from C1-C2) | script | F | 100% consistent with C-rule output |
| S4 | Old events flagged as not recent | script + jury | P-old: >= 100 (anniversaries, "in 2015", trials of old crimes) | recall >= 0.90 *goal* |
| S5 | Local named places (a city or a school) read as local | jury | P-local: >= 100 | >= 0.85 *goal* |
| S6 | National markers (national government, nationwide) read as national | jury | P-national: >= 100 | >= 0.85 *goal* |
| S7 | Calibration | jury | F | at 0.9 confidence, right >= 90% |
| S8 | Regression | scorecard | F | regression rule above |
| S9 | No scope claimed for stories without one (results tables, recipes, listings) | jury | P-nonnews: >= 100 | <= 50 false national or local per 1,000 *goal* |

## 4. Topic (49 labels incl. "other"; one main topic)

Least scriptable: the jury carries it. Context can help: feed or section (`bbc-business`, `/sport/`, `guardian-technology`) as a prior, overridden by the text. Script can supply keyword lists per topic for mining only, not for scoring.

| # | Criterion | Scored by | Test set | Bar |
|---|---|---|---|---|
| P1 | Codebook passes (definition, counts, does not count, example per topic) | jury | pilot 50 + targeted 150 | alpha >= 0.8 per topic; below 0.667 after two rewrites -> raise with the user |
| P2 | Overall accuracy | jury | F | >= 0.85 *goal* (baseline 0.69, F-0048; jury pairs agree 40-42/50, F-0049) |
| P3 | Every topic works | jury | P-topic: >= 20 per topic, mined by keywords and section | recall >= 0.70 each *goal* |
| P4 | Confusable pairs (growth vs jobs, markets vs banking, crime vs justice...) | jury | P-confuse: >= 30 per pair, pairs taken from the round-1 confusion table | >= 0.80 *goal* |
| P5 | "Other" not used as a dump | jury | F | "other" <= 10% of stories and precision >= 0.80 *goal* |
| P6 | Section prior agrees with the text where the text is clear | script + jury | F stories with a section | >= 0.90 *goal* |
| P7 | Non-news (shopping, listings) not given an economic topic | jury | P-nonnews | <= 20 per 1,000 *goal* |
| P8 | Calibration | jury | F | at 0.9 confidence, right >= 90% |
| P9 | Top-2 contains the jury topic | jury | F | >= 0.95 *goal* |
| P10 | Regression | scorecard | F | regression rule above |

## 5. Conditions (39 conditions x up/down = 78 keys; several may be yes)

The hardest area: jury overlap 0.34-0.41 across vendors (F-0049), so the codebook comes first. Script supplies cue lists per key for mining rare positives and a directional check (rise words vs fall words). Downstream engine tolerance exists here: all-keys pass at TPR 0.95 with false-positive rate <= 0.0025, or TPR 0.9 with <= 0.001 (F-0020).

| # | Criterion | Scored by | Test set | Bar |
|---|---|---|---|---|
| K1 | Codebook passes per key | jury | pilot 50 + targeted 150-200 | alpha >= 0.8; below 0.667 after two rewrites -> "not readable from headline + description", raise with the user |
| K2 | Per-key quality | jury | F + P-key | AP >= 0.70 per accepted key *goal* (baseline mean 0.45, F-0048) |
| K3 | Enough positives to score | count | F + P-key | >= 30 jury positives per key, or the key is reported as unscored |
| K4 | Direction: up vs down never swapped | script-made pairs + jury | P-flip: 20 pairs per key ("prices rose" / "prices fell") | probability of the wrong direction drops by >= half |
| K5 | Passing mention does not count (codebook rule) | jury | P-passing: >= 100 | false alarms <= 50 per 1,000 *goal* |
| K6 | False alarms on stories with no condition | jury | F | <= 2.5 per 1,000 per key (from F-0020 FPR 0.0025) |
| K7 | Downstream: engine tolerance | `sensitivity.py` | F | all-keys inside tolerance (d) (F-0020), separate check per D-0014 |
| K8 | Calibration | jury | F | at 0.9 confidence, right >= 90% |
| K9 | Per-item proof | `show_examples.py` + reviewer | 20 stories | >= 18 of 20 false alarms given a cause (input lacks it / codebook / model) |
| K10 | Regression | scorecard | F | regression rule above |

## Out of scope unless the user adds them

Impact levels (minor..extreme) and impact modes (reported, expected) are in `story_labels` but not in BitMob's stated goal (GO.md: story type, scope/focus, topic, country, conditions).

## Decisions needed

1. Approve, change or reject each area's criteria and bars.
2. US/foreign focus: compute from the country rule instead of reading it.
3. Impact levels and modes: in or out.
4. Country: the 9 `check` sources; out-of-list countries in the ontology or not.
