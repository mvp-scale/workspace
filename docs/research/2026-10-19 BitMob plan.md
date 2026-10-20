# BitMob plan: from labelled headlines to a checked CPU reader

Date: 2026-10-19. Method: `docs/research/2026-10-18 Fable method.md`. Every claim cites a ledger item (`node tools/ledger.mjs show <id>`) or a source.

## Goal and pass bar

A CPU reader for the World engine's read layers (story type, scope/focus, topic, country, 78 condition keys) from headline + description (D-0009): no GPU, a few GB RAM, under 100 ms per article (D-0007), with detection measured against human labels. Target the user set: 65-70% or better per element; the engine-level target stays Step 1's (F-0020), reached through Step 5's rate correction.

## Where we are (evidence)

| Fact | Evidence |
|---|---|
| Steps 1-2 closed; Step 3 open, blocked on raters | S-0001, S-0002, S-0003 |
| Training-set spec R1-R26 and checker, reviewed twice by Fable | D-0010; `docs/research/2026-10-19 BitMob training set spec.md` |
| Pilot: 1,000 records in 10.9 min, $0.87, audit 20/23 (builder bugs fixed), Jev 0 flips in 20 replicates | F-0030 |
| Rare keys: only 1 of 16 priority keys >= 30 positives in 1,000 random records | F-0030, F-0026 |
| Topic -> condition map holds for 39% of records: topic is a model input, not a filter | F-0030 |
| Headline carries ~40% of full-text signal (accepted cost) | F-0027, D-0009 |
| Jev ~7x faster than Clef, consistent, not shown more accurate | F-0028, F-0029, F-0030 |

## Steps

| # | Step (method row) | What | Pass bar | Cost / time | Sources |
|---|---|---|---|---|---|
| 1 | Mine rare keys (row 7) | Per priority key: expanded word lists from the attribute definitions + nearest neighbours (CPU embeddings) of known positives, over 70,546 filtered CC-News; Jev labels the top candidates; stop a key at 100 positives | Hit rate >= 5x the random rate (F-0030) for >= 10 of 16 keys | <= 16k candidates, <= $16, ~3 h | Attenberg & Provost 2010 (guided search beats random/active at high skew); method 6.2 |
| 2 | Full training set (rows 2, 7) | Random CC-News + feed + mined records to spec; inclusion probabilities kept | Audit: 0 automatic failures | 10-20k records, $10-20, 2-4 h | F-0030; spec R1-R23 |
| 3 | Per-element CPU models (row 8) | Shared fine-tuned small encoder, one head per ontology layer; baselines TF-IDF + logistic regression and potion; sidecar features as one entry | Screen only, not accuracy: per element, agreement with held-out Jev labels (AP, recall at fixed precision); CPU ms and RAM within D-0007 | GPU minutes to train; ~1 day | Hartley 2025 (fine-tuned encoder +46% F1 over bag-of-words on news); POLECAT (one model per event class); model2vec README (N-0008) |
| 4 | Learning curves (row 10) | 5 training sizes per element; fit error = a + b n^-c | Screen only: labels needed to reach 65-70% agreement with Jev per element, or "not reachable"; the accuracy figure comes from step 6 | CPU hours | Figueroa et al. 2012; method 6.4 |
| 5 | Human reference (Step 3) | Sample = student-predicted positives per key + stratified negatives with inclusion weights (C-0011), mined CC-News stratum flagged; 2 raters + adjudicator | Krippendorff alpha >= 0.667 per key used | 2 raters x 30-48 h + ~5 h (N-0004 estimate) | Krippendorff; method 4.1-4.2 |
| 6 | Pick the teacher (Step 4) | Score Jev and Clef against the reference, Wilson intervals | The teacher with higher per-key precision and recall | CPU | method row 4; F-0028, F-0029 (confidence is not accuracy); C-0009 (label rule decided here) |
| 7 | Retrain, correct, monitor (Steps 5, 9, 11, 12) | Retrain from the chosen teacher; rate correction in the engine; thresholds; final comparison; drift monitor | Engine outputs within F-0020 tolerance | Engine change (user yes) | method rows 5, 9, 11, 12; F-0020 (tolerance); D-0009 (headline loss to correct); LeQua 2022 via method 3.1 |

Order: 1 -> 2 -> 3 -> 4 run on machine labels and report agreement with Jev only; 5 needs a first student (3) for its sample, so 5 starts after 3; 6 needs 5; 7 needs 6. **No step claims a model is accurate before step 6** (scores against the human reference).

## Decisions needed from the user

1. Raters: two raters and an adjudicator (blocks step 5).
2. Engine gate: whether gate-failed stories still move the world.
3. Live input filter: apply D-0010 to the live feed (news reader change).
4. CC-News licence: unknown; research and training only until checked (spec R26).

## Risks

- Mining may not reach 100 positives for keys that are rare in news itself (private debt, health risk down).
- Per-element scores against Jev labels measure agreement with Jev, not truth, until step 5.
- CC-News is 2017-19; the feed is 2026: domain shift, checked by the live-feed stratum in step 5.
- Headline-only input caps detection (~40% of full-text signal); step 7's correction must account for it.
