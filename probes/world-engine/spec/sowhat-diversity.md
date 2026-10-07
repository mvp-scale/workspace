# So-what diversity harness: results

Question: do any three so-what statements sound alike? Measured on real engine output (TEST 1) and by stress-running the composer on cross-combined parts (TEST 2). Nothing in the repo was changed. Scripts are in `probes/world-engine/tests/sowhat_diversity/`; raw outputs are in the session scratchpad `diversity/` folder (`test1.json`, `test2.json`, `metrics.json`, one `sNNN.resp.json` per story).

Reproduce: `build_stories.py` (stories from `stories_src.txt`), start an engine on :8139, `run_requests.py`, `node compose_runs.js`, `python3 analyse.py`. The engine on :8139 was stopped at the end. The live `/sowhat` tables were checked equal to the three CSVs (columns the composer reads).

## What was run

**TEST 1, real run.** 120 new headline-style stories (`stories.json`): 49 topic ids (every row of `domains.csv`, which has 49 rows including `other`, not 48) x 2 = 98, plus 8 mixed, 6 vague and 8 extra. The 98 topic stories are balanced by design: good/bad 49/49, one country/worldwide 49/49, happened/announced/forecast/opinion 24-25 each, large/small effect 49/49. Those tags are my intent, not engine output. Where I can compare, the engine's certainty matched my tag for 79 of 98 (the rest: announced read as forecast or happened, and so on). Each story was posted to `/request` (mode event) with 3 in parallel. **HTTP failures: 0 of 120.** Composer failures: 1 of 120 (s106, see hot spot 8). Each story was composed at WORLD, and at two more foci: the hardest-hit country if the entry is a country, and the hardest-hit audience (a second audience when there is no country entry). That gives 119 world outputs and 357 outputs over all foci.

**TEST 2, composer at scale.** 46 base responses (22 fixtures with the golden classifier answers, plus 24 review responses). Each response's rows, places and rank were paired with the story-level parts (frame, trigger, certainty, scale) of each of the other 45, at world focus: 2070 combinations, 0 returned null. **These combinations are not coherent stories** (a trigger about one thing is paired with a response to another). They measure the composer's lexical and structural variety only, never accuracy.

Metrics use the whole output (headline plus line2) unless marked "headline only". A "triple" is 3 outputs from different stories (for TEST 2, different base pairs). 20000 seeded random triples per cell. "Same frame" draws all three from one composer frame (weighted by how many triples each frame offers), the hardest case.

## Headline numbers

| | TEST 1 world (n=119) | TEST 1 all foci (n=357) | TEST 2 (n=2070) |
|---|---|---|---|
| distinct 3-word openers | 45 | 68 | 88 |
| top opener share | 13.5% ("An opinion piece:") | 13.7% (same) | 5.9% ("If this forecast") |
| distinct templates used (of 48) | 25 | 28 | 36 |
| template entropy (bits; max for that count) | 4.05 (4.64) | 3.96 (4.81) | 4.62 (5.17) |
| top-1 template share | 16.0% (NO-F) | 16.5% (NO-F) | 10.3% (NO-Q) |
| distinct headlines | 95 (79.8%) | 270 (75.6%) | 1599 (77.3%) |
| distinct line2 strings (incl. empty) | 35 | 62 | 85 |
| line2 empty | 53.8% | 59.7% | 15.0% |
| headline words: median / p90 / max | 15 / 20 / 22 | 16 / 21 / 22 | 18 / 21 / 23 |
| line2 words (non-empty): median / max | 9 / 14 | 8 / 14 | 8 / 13 |
| **triples with a shared 5-word run, any pair** | **37.5%** | **38.1%** | **53.3%** |
| **same-frame triples, same measure** | **60.3%** | **62.9%** | **66.8%** |
| mean pairwise word-trigram Jaccard, all / same frame | 0.049 / 0.094 | 0.055 / 0.102 | 0.040 / 0.066 |
| headline only: 5-gram triples, all / same frame | 27.4% / 54.1% | 33.2% / 60.1% | 23.8% / 48.3% |
| headlines with a digit or % | 0 | 0 | 0 |
| outputs with "Elsewhere" or "Little changes elsewhere" in line2 | 20 (16.8%) | 20 (5.6%) | 852 (41.2%) |
| banned-pattern hits (`banned()`) | 0 | 0 | 0 |
| headline over 22 words | 0 | 0 | 3 (23 words) |

Plain reading: the Jaccard figures are low (0.04 to 0.10), so outputs rarely overlap broadly; the problem is short stock runs, not whole-sentence copies. But in about 4 of 10 random triples two outputs already share a five-word run, and in 6 of 10 when the three share a frame. The target (three statements never sound alike) is not met.

The TEST 1 "all foci" openers are not independent: the same story at three foci mostly gives the same opening, so that column is the world column restated, not a fresh sample.

The numbers rule holds: no headline or line2 contains a digit or percent (all three runs). That is by design (see contract) and is reported as asked.

## What the outputs look like (TEST 1 world, non-quiet, random sample)

- `SQ-S` A major squeeze: fuel and power costs rise, so people cut back sharply. / Fades slowly.
- `RL-C` If the forecast is right, prices would fall: people would spend a bit more. / A tiny shift that reaches a large minority. A quick jolt that fades.
- `SQ-W` Only Brazil feels this squeeze: shares and property should lose value, so people there cut back sharply and keep savings in cash. / Little changes elsewhere. A big shift there.
- `RL-W` Portugal takes this relief almost alone: public services should improve, and people there speak out less and take on debt. / Elsewhere, barely a ripple. A small shift there.
- `SQ-T` Prices rise, and people feel the squeeze: they cut back sharply. / A notable shift that reaches nearly everyone. Fades slowly.

## Where TEST 1 outputs concentrate

Lead beat at world focus: quiet 64 (53.8%), trigger 19, who 18, certainty 17, scale 1. The engine rated 107 of 119 stories Negligible size (8 Minor, 3 Notable, 1 Major), so most outputs are small or quiet. Quiet outputs are `NO-F` 19, `NO-O` 16, `RP-S` 13, `NO-Q` 8, `NO-X` 8 (the 6 vague stories plus 2 hedged ones the engine counted as no impact). Quiet shares by my tags (world focus): forecast 72%, opinion 71%, announced 58%, happened 24%; small effect 73%, large effect 39%. Among the non-quiet outputs only the SQ, RL, BO, SH, SC and PL families show up regularly; at world focus there is 1 rift output and no blow, freeze or surge output. This reflects the engine's answers to my stories as much as the composer; I cannot separate the two with this data.

Frame spread at world focus: ripple 31, boost 26, squeeze 20, relief 14, scare 10, none (NO-X) 8, shake_up 5, plain 4, rift 1.

## Top 25 repeated 4-word phrases

Counts are outputs containing the phrase (document frequency). TEST 1 world (n=119) and TEST 2 (n=2070); the source column says which row produces it. The dozen "no decision moves enough to matter" or "an opinion piece on our numbers" phrases are one sentence counted several times; they are grouped.

| phrase (group) | TEST 1 world | TEST 2 | produced by |
|---|---|---|---|
| no decision moves enough to matter / but no decision moves | 27 (22.7%) | 243 (11.7%) | `sowhat_templates.csv` NO-Q, NO-F; lexicon `line2:quiet` |
| an opinion piece on our numbers no one changes what they do (9 phrases) | 16 (13.4%) | 5 | template NO-O (one fixed sentence) |
| a tiny shift that reaches / tiny shift that reaches | 16 | 587 (28.4%) | lexicon `tier:Negligible` word ("tiny") in `line2:scale_world` |
| if the forecast is right / the forecast is right | 15 | 103 | lexicon `certainty:forecast.text` |
| if this forecast comes true | 14 | 122 | lexicon `certainty:forecast.text_alt` |
| a quick jolt that fades / quick jolt that fades | 14 | 342 | lexicon `arc:jolt` |
| a small shift there | 13 | 484 | lexicon `line2:scale_focus` (with "there") |
| few people change what they do (3 phrases) | 13 | 17 | template RP-S |
| elsewhere barely a ripple / ripple a small shift | 9 | 434 | lexicon `line2:elsewhere.text` |
| little changes elsewhere a small shift | 11 | 384 | lexicon `line2:elsewhere.text_alt` |
| shift that reaches a / most / nearly everyone | n/a | 278 / 250 | `line2:scale_world` plus `reach` rows |
| stick to the rules | few | 220 | lexicon `decision:break_rules.down`, `theme:rules.down` |
| people there cut back | few | 211 | template `{there} {resp}` plus `decision:spend.down` |
| most people fades slowly / reaches most people | few | 200 / 191 | `reach:r90` plus `arc:sticks` ("Fades slowly") |

All 25 phrases, with exact counts, are in `metrics.json` (`top4grams`) for each of the three runs.

## Per-frame repetition (same-frame pairs, TEST 1 all foci and TEST 2)

| frame | TEST 1 n | distinct headlines | distinct openers | pairs sharing 5 words | TEST 2 n | TEST 2 distinct openers / top opener | TEST 2 pairs sharing 5 words |
|---|---|---|---|---|---|---|---|
| squeeze | 60 | 54 | 20 | 16% | 491 | 24 / "this squeeze stays" 83 | 28% |
| ripple | 93 | 69 | 13 | 31% | 155 | 23 / "this ripple stays" 18 | 50% |
| boost | 78 | 62 | 22 | 27% | 147 | 15 / "this boost stays" 19 | 34% |
| relief | 40 | 35 | 17 | 14% | 42 | 12 | 38% |
| scare | 30 | 25 | 8 | 25% | 315 | 21 | 28% |
| plain | 14 | 14 | 4 | 41% | 317 | 45 / "this shift stays" 44 | 32% |
| shake_up | 15 | 13 | 7 | 4% | 209 | 27 | 37% |
| rift | 3 | 3 | 2 | n/a | 97 | 23 / "social divides should" 22 | 51% |
| blow | 0 | n/a | n/a | n/a | 35 | 14 / "weather hazards get" 18 | 70% |
| freeze | 0 | n/a | n/a | n/a | 70 | 14 | 38% |
| surge | 0 | n/a | n/a | n/a | 147 | 21 | 43% |

The "this X stays" openers in TEST 2 come from the who-lead variant `local_c` ("This {frame} stays in {place}"): in 876 of 2070 TEST 2 outputs a who-lead opens the headline. In TEST 2 the world entries often name a country because the combined story keeps one base's entry; in real TEST 1 only 18 of 119 world outputs lead with who.

## Hot spots, ranked (what makes outputs sound alike, and who owns the fix)

1. **The quiet branch is one sentence per row.** About half of real world outputs (64 of 119) take the quiet path; `NO-O` gives the identical string "An opinion piece: on our numbers no one changes what they do." (16 times, 13.4% of everything, the top opener), `NO-F` and `NO-Q` share "but no decision moves enough to matter" (22.7% of outputs), `NO-X` is one fixed line (6.7%, expected for the 6 vague stories but also hit twice by hedged stories). Owner: `sowhat_templates.csv` rows NO-O, NO-F, NO-Q, NO-X, RP-S need several variants each, and the composer quiet branch in `run()` (the `var1` choice, `sowhat.js` lines 184 to 200) picks only the hedge variant, not a template variant. If quiet is honest, vary the sentence by what the story was about (trigger, frame noun), not only the hedge.
2. **Line2 is assembled from the same few lexicon tails.** In TEST 1, 48 of 55 non-quiet line2s say "a ... shift" and 24 say "shift that reaches"; in TEST 2, "A tiny shift that reaches" is in 28% of outputs and "Elsewhere / Little changes elsewhere" in 41%. The two elsewhere strings are the two variants of one row, chosen by a headline hash. Owner: lexicon `line2` rows (`elsewhere`, `scale_world`, `scale_focus`, `quiet`, `alone`), `arc` rows ("A quick jolt that fades.", "Fades slowly.", "Builds, then eases."), `tier` and `reach` words; composer rule at `sowhat.js` lines 283 to 301, which almost always picks the scale tail plus an arc tail. Note that the "tiny" word is the Negligible tier word, and 90% of TEST 1 stories rated Negligible, so this hot spot is amplified by the engine's size scores.
3. **Two hedge variants per certainty.** 29 of 119 headlines (24%) open "If the forecast is right," or "If this forecast comes true,", and 23 (19%) open "An opinion piece;/:" or "One writer's view;". So 44% of real headlines start with one of four openers; 52 of 119 TEST 1 stories were forecast or opinion by my design, so some concentration is expected, but four openers is too few. Owner: lexicon `certainty` rows (forecast, opinion, unclear, announced, pending, happened: `text` and `text_alt`), and the composer's one-bit choice (`hv`, `HEDGE_OFFSET`, `sowhat.js` lines 252 to 255).
4. **One skeleton per frame and lead.** Every squeeze trigger-lead headline is "{Trigger}, and {subj} feel the squeeze: they ..." and each frame repeats its own noun and verb phrase ("feel the squeeze", "take sides", "wait and see", "adjust", "take this X almost alone"). Same-frame triples share a 5-word run 60% of the time (TEST 1) and 67% (TEST 2), against 37% and 53% across frames. TEST 2 worst frames: blow 70%, rift 51%, ripple 50%. Owner: `sowhat_templates.csv` (48 rows, only 25 reached in real world outputs; add 2 to 3 alternates per frame and lead, with the composer picking by a rule) and the 6 `who_lead` lexicon rows (`local`, `local_b`, `local_c`, `more`, `opposite`).
5. **Response clauses reuse the same verb phrases.** "people there cut back", "spend a bit more", "cut back sharply", "stick to the rules" (220 TEST 2 outputs) and "travel less" recur because the response is built from 20 `decision` rows, 10 `theme` rows and 3 `degree` words ("a bit", "sharply", and so on). Owner: lexicon `decision`, `theme`, `degree` rows (add alternate wordings per row), composer `themesOf`, `degree`, `putDeg` (`sowhat.js` lines 51 to 55, 89 to 100).
6. **Certainty and trigger clauses share one noun per dial.** 39 `condition` rows provide one noun and one verb phrase each ("prices rise", "housing costs rise"), so any two stories on the same dial share a clause. Owner: lexicon `condition` rows (`down`, `up`, `down_bare`, `up_bare`).
7. **Length is narrow.** Headline words cluster at 12 (83 of 357 outputs), then 18 to 20; line2 sits at 6 to 9 words. Outputs differ little in rhythm. Minor; owner: template rows (add a short and a long form).
8. **Engine and composer interface gap (not a diversity item, but found here).** s106 ("Mexico approved a trade deal ...", mixed) returned `null` at every focus. Cause (traced by instrumenting a copy, not the repo file): the engine's `impact.story.frame.id` is `"plain"`, and `sowhat_frames.csv` has no `plain` row, so `run()` hits `!frameRow` and returns null (`sowhat.js` line 178). The composer already uses `plain` as an internal fallback family, so the frames CSV or the engine's frame id needs to agree. 1 of 120 stories (0.8%).

## Weak spots in this harness

- TEST 1 triples across foci are not independent of each other; I report world focus as the primary row.
- Tags (good/bad, local/world, large/small) are my intent. The engine's certainty differs from my tag in 19 of 98; its size mostly came out Negligible, so "large" stories mostly did not produce large outputs. I did not check whether an output was right.
- The top-25 phrase counts treat an output as a bag of 4-grams; overlapping phrases from one sentence appear as separate rows (grouped above).
- TEST 2 inflates "who" leads and the elsewhere tail because the combined stories mix places; it shows the composer's reach, not what users will see.
- Same-frame rows with fewer than 10 outputs (rift, blow, freeze, surge in TEST 1) are too small to judge.
- 120 stories is a small sample for the rarer templates; 23 of the 48 never appeared in real output.
