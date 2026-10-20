# World engine reader check: is what goes in correct?

Date: 2026-10-19. Ledger: F-0026..F-0029, D-0007, D-0008, T-0001. Reviewed by Fable (sound with fixes; fixes applied).

## Bottom line

The engine had never checked what it reads. On this sample (29 live stories, one afternoon, no human check), the clearest problem is **what it is fed**: 12 of 29 stories had little or no text, and 15 failed the engine's own "is it news?" gate, yet 10 of those still moved the world. Hosted Jev is faster than local Clef and more confident, but **not shown to be more accurate**: both make the same kinds of mistakes. MM3 flags input problems consistently (the "is it news?" questions) but its verdict on a reading depends on how the question is worded. A human reference (Fable method Step 3) is still the only judge.

## What was done

1. **Read log added to the engine** (`data/world-engine/reads.jsonl`): every story, all 328 reader answers, the readings, the reader. Before this, nothing was kept. The log now holds 39 feed stories; 29 were analysed.
2. **The 29 stories replayed through Jev** (F-0028).
3. **MM3 check** of the 20 stories with readings (MM3-0030..0050, F-0029).

## Findings

| Finding | Evidence |
|---|---|
| Thin input: 2 of 29 headline only, 10 more under 250 characters (12/29); also ads, sports, 1 non-English, 1 multi-story roundup | read log |
| 15 of 29 fail the news gate; 10 of those still produce readings, because the gate is "a weight, not a wall" (a power-bank sale pushed prices down at 0.92) | read log, `classify.py:100` |
| Jev: 29 stories in 18 s with 4 in parallel (~100/min; 56 s if one at a time, ~31/min). Clef: ~13/min with 6 in parallel | F-0028 |
| Jev and Clef share 19 readings; Jev is more confident on 17 of the 19; Jev drops 4 of Clef's doubtful readings and adds new doubtful ones (e.g. an attack on an MP read as "crime down") | F-0028 |
| MM3, Clef readings: pass 6, unsure 6, fail 5 (17 stories). Jev: 6, 6, 4 (16 stories). Reviewers split on 12 of 20 | F-0029 |
| MM3's "is it news?" answer was stable on the sales post (0.04-0.10); its "is the reading supported?" answer was not (0.02-0.20 with a specific question, 0.67-0.95 with a generic one) | MM3-0030, MM3-0035; requests in `data/world-engine/mm3/` |
| Headline + description alone carries 40% of full-text key positives | F-0027 |
| 6 of the 16 keys that matter most have 3 or fewer positives in 1,736 feed stories. CC-News (708k articles) may supply volume, but projections rest on 0-6 hits per key (range ~50-1,600) and its 2017-19 rates differ from our feed | F-0026, F-0027 |
| Jev cost per story: not yet measured (17 calls per story) | D-0008 |

## Limits

One afternoon, 29 stories. Right/wrong calls come from MM3 or the assistant, not humans. MM3's reviewers are the same model families as the readers.

## Proposed next steps (in Fable-method order)

1. **Input filter** (no body, teaser-only, non-English, ads, roundups): record as a decision, then build in the news reader.
2. **Gate-failed stories**: whether they should move the world at all is an engine change; the user decides.
3. **Step 3 as the method defines it**: ~100 predicted positives per key plus a stratified pool of predicted negatives, 2 raters, a third to adjudicate, Krippendorff's alpha. MM3 flags go to the raters as an extra input (Step 6), not as the sample.
4. **Step 4**: re-score Clef and Jev against that reference. This, not MM3, answers "which reader is right".
5. **Then rows 7, 8, 10** (CC-News pool, student bake-off, learning curve), with Jev cost per story measured first.
