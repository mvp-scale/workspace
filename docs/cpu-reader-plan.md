# CPU reader plan: atoms, engines, consensus, rules (draft, 2026-10-18)

Goal: read every story on CPU with zero GPU at run time, accurately enough for the World engine ontology. Clef and Jev teach and audit offline only.
Principle: classifiers detect atomic, observable facts (answerable by pointing at words); the rules engine does every "so what" in tables that can be tuned.

## Engines (names are placeholders)
| Name | What it is | Output | Cost (CPU) | Status |
|---|---|---|---|---|
| Glance | static word vectors (potion) + heads | atom scores, topic, scope per part | ~0.07 ms title, ~3 ms article | built, median F1 ~0.6 |
| Scholar | e5-small transformer (word order) + heads | same, sees negation and order | ~4 ms short part, ~200 ms article | built |
| Sieve | word lists and patterns (our code) | price/change/direction words, numbers, %, currency, dates, hedges, question headlines | microseconds | to build |
| Grammar | parts of speech (spaCy teaches offline) | tense, negation, who did what | a few ms | to build |
| Locate | names and places | countries (100-country list), orgs, people, actor type | us / a few ms | to build |
| Echo | novelty vs recent stories | new or repeat, same event | ~0.1 ms | to build |
| Jury | consensus judge | STRONG yes / STRONG no / SPLIT / WEAK + who disagreed | microseconds | to build |
| Referee | rules engine | condition moves, routes, reactions, decisions, with a trace | ms | tables exist in part |

All engines read the same parts (title, description, lead, body) in parallel; a story costs its slowest engine.

## Steps
1. Consensus (Jury): three detectors per atom from different angles and engines (Clef's a, b and reversed answers exist for 2,400 stories). Only STRONG verdicts move the world; SPLIT is logged with who disagreed.
2. Several engines as separate votes, not an average (averaging five models did not help, 2026-10-18).
3. Drill into SPLIT: cause = wording / too few examples / engine weak spot (negation, order) / story ambiguous.
4. Decompose atoms that stay SPLIT into support atoms (e.g. prices.consumer_up = price mentioned AND it changes AND upward AND (who pays is consumers OR an everyday purchase); tense and numbers set strength). Clef labels support atoms offline with MM3 batteries.
5. Minimum viable set: remove engines and angles one at a time; keep the smallest set that holds the bars.

## Bars (per atom, held-out stories, against Clef's agreed labels)
Accuracy on STRONG verdicts; false-positive rate cap; share of atoms reaching STRONG; CPU ms per story; zero GPU at run time.

## Rules engine (Referee) design notes
- Stats, flags (bitmasks), modifiers with stacking (count events, not articles, diminishing, capped) and durations (half-lives). Replaces random gains and per-person random sensitivity.
- Story parts: four atom masks per story (title, description, lead, body). World moves from the whole story; perception and reactions from the parts each reading-depth bucket reads.
- Normalizer: a story sheet of numbers (story type, specificity, claim signals, concreteness, actor types, country, novelty) used as modifiers. No content kept downstream.

## Evidence so far
data/mm3-train/NIGHT.md (overnight log, 2026-10-18), data/mm3-train/coverage.md, data/mm3-train/route-current.json.

## Result 1: consensus test (2026-10-18, newsreader/bitmob/consensus_test.py -> data/mm3-train/consensus-test.json)
44 atoms, 486 held-out stories, scored where Clef's two wordings agree. Engines: Glance and Scholar only (Sieve, Grammar, Locate not built yet).
| | precision | recall | false positives per 100 stories |
|---|---|---|---|
| single head (today) | 0.43 | 0.53 | 74.7 |
| majority, 2 of 3 | 0.57 | 0.47 | 36.8 |
| jury, STRONG yes only | 0.80 | 0.31 | 8.0 |
Jury reaches STRONG on 94.9% of pairs; STRONG no is right 99.4% (median atom). Of 351 Clef yes the jury did not call, 210 are SPLIT (flagged for drilling) and 141 are wrongly STRONG no.

## Result 2: removal tests and cascade (newsreader/bitmob/ablation_jury.py -> data/mm3-train/ablation-jury.json)
| Jury variant | precision | recall | false positives / 100 stories |
|---|---|---|---|
| full jury + veto | 0.80 | 0.31 | 8.0 |
| without Scholar | 0.62 | 0.36 | 23.7 |
| without Glance lead | 0.72 | 0.38 | 15.6 |
| without Glance full | 0.73 | 0.35 | 13.6 |
| without the veto | 0.79 | 0.36 | 9.7 |
| cascade A: two Glance yes accepted without Scholar | 0.57 | 0.47 | 36.8 |
Cascade B (Glance settles NO only; any Glance yes needs Scholar to agree) = the full jury's verdicts, Scholar on 4.5% of story-atom pairs but 74.7% of stories (one read covers all atoms, and most stories have at least one Glance yes).
Cards: Glance = SUPPORTS + Stage 1 (cheap no-settler: STRONG no 99.4% right). Scholar = SUPPORTS, Stage 2 (removing it triples false positives; the value is a different engine's vote). Veto = SIGNAL ONLY so far (-1.7 false positives / 100 for -5 points recall; better as a strength modifier than a hard veto). Two votes from the same engine share blind spots: cascade A shows Glance agreeing with itself is not confirmation.
Open: Scholar on title + description + lead only (a few ms instead of ~200 ms) - does it keep its value?

## Result 3: every engine, compared fairly (2026-10-18)
Scripts: engines_features.py (features + CPU cost), engines_eval.py (cards), engines_frontier.py, combiner_ablation.py, final_pattern_crossfit.py,
matched_compare.py (final comparison), echo_pairs.py + echo_eval.py, locate_scope.py, grammar_scoped.py, decompose_eval.py. Data in data/mm3-train/.
CPU cost per story, one thread: Glance 0.1-0.75 ms; Echo 0.9; Locate countries 0.2; scoped Sieve 6.2; Sieve 8.8; spaCy 41.6; Scholar lead 48; Scholar full 160.
Recall of Clef's agreed hits at the same false positives per 100 test stories (44 atoms, 486 stories):
| option | <= 4 | <= 9 | <= 15 | ms |
|---|---|---|---|---|
| single Glance head | 0.238 | 0.320 | 0.404 | 1.1 |
| single Glance + scoped Sieve | 0.244 | 0.336 | 0.381 | 7.3 |
| jury all-agree: Glance a, Scholar full b, Glance lead | 0.299 | 0.359 | 0.422 | 161 |
| jury all-agree: Glance+scoped a, Scholar lead b, Glance lead | 0.295 | 0.344 | 0.406 | 56 |
| learned combiners (all variants) | 0.07-0.17 | 0.23-0.34 | 0.28-0.39 | 1-225 |
Cards: Glance KEEP (stage 1); Scholar KEEP (stage 2, lead only: same value, 1/3 cost); Sieve FEATURE not voter (as a voter it vetoes true hits;
inside Glance -11.7 false positives / 100 at equal recall; sentence-scoped counts -17.5); Grammar SIGNAL ONLY (whole-text counts showed nothing;
scoped to the atom's sentences the gain came from the sentence count, tense/negation add -1.2); Locate SIGNAL ONLY for atoms and scope (alone below
the majority guess, +2 points with Glance); naming the country is untested (no ground truth); Echo KEEP for same-event (AUC 0.89; with title overlap
0.93; ~1 ms; Clef consensus on 143 of 160 MM3-labelled pairs); Jury KEEP all-agree, modest gain (+4-6 recall points at equal false positives);
learned combiner NO GAIN when compared at equal false positives; Referee untested (needs outcome data).
Method corrections that changed conclusions: (1) "supports" must beat the base jury's own tightening curve, not raw deltas; (2) Grammar scoped to
the atom's sentences; (3) combiner on 465 stories overfitted, cross-fitted on 1,850; (4) test scores from the same fold models as training scores;
(5) the "9x fewer false positives" for the jury was mostly a stricter cut-off: a single head with a strict cut-off is nearly as clean.

## Result 4: decomposition (support-v1, 9 building blocks, 2,568 stories labelled by Clef via MM3 in 23 min)
Direct heads beat rules over CPU building blocks for 3 of 4 targets (average precision: consumer prices 0.69 vs 0.21; energy prices 0.64 vs 0.28;
supply cut 0.48 vs 0.39; wrongdoing 0.43 vs 0.45). Cause, at teacher level: Clef's answers are not logically consistent across questions: among
stories Clef calls "consumer prices up", Clef says "mentions a price" (both wordings) in only 26%. So Clef can teach each building block but cannot
validate a rule that combines them. To test decomposition fairly, the rule must be checked against a coherent reference (a human-checked sample),
or the rule becomes the definition and Clef only validates each block.
