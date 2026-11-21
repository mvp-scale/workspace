# Self-improvement loop for the topic step (design v2)

2026-11-20. v2 folds in two things:
- the Opus review: `scratchpad/team/loop_review/review.md`, numbers checked (ledger L2750);
- the owner's decision on MN-DS training (L2751).

Library practice: `scratchpad/team/loop_research.md` (Context7). Evidence: ledger T158, L2719–L2751.

## Goal it serves
Better topic answers on **live news**, so the world state counts topics correctly. MN-DS is the only human topic truth. It trains one small model and judges it on a clean part, but live checks decide adoption.

## Data split (made once, versioned, hashed)
- **MN-DS** (T28 + fresh2 + fresh, de-duplicated by title and body prefix):
  - split by **publisher** into `train` (~70% of publishers) and `test-clean` (~30%), with no shared publisher and no near-duplicate across the split;
  - `test-clean` is split again into `select` and `confirm` halves;
  - nothing ever trains on `test-clean`.
- **Live checks** (no MN-DS):
  - publisher-section agreement on the latest live run (reference map);
  - topic-share error on live-mix days;
  - dated events, once the list exists.
- **Queue IDF and kNN pools:** queue articles only.

## Each round (one CPU run under 1 hour, no hosted spend)
1. **Cached inputs:** landing card scores, bge vectors, TF-IDF (queue IDF), teacher labels (r1, r2) where they exist.
2. **One pre-registered primary option,** named with its prediction before scoring, plus a few secondary options, all reported.
   - Round 1 primary: a **card-score re-ranker** (logistic regression on the landing's 1,059 card scores, `class_weight="balanced"`, C chosen on a publisher-held-out split of `train`), trained on MN-DS `train`.
   - Secondary: teacher–landing blends and disagreement routing, scored on the 500 pilot items, which are in `train` and so are reported as in-train, not as a test.
3. **Scoring:**
   - main: topic-share error (live-mix days) and per-topic recall, plus top-2;
   - guard rail: top-1;
   - each student cell has a declared class-prior correction.
4. **Keep rule:** adopt the primary only if all of these hold:
   - paired one-sided test vs the landing on `confirm`, minimum +2 points, Holm across candidates;
   - no loss on any live check;
   - a gain on at least one live check.
5. **Cause-to-action table** on the errors of `select`. Each error is classed as one of:
   - prior error → correction;
   - landing wrong, teacher right → routing;
   - both wrong (labelling convention) → re-ranker data;
   - card vocabulary miss → node-card text.

   Each class carries a predicted gain. That table writes the next round's primary option.
6. **Calibration** is refit only on a held-out split, never on `confirm`: `CalibratedClassifierCV(FrozenEstimator(clf), method="sigmoid")`. The file is frozen and hashed.
7. **Spend:** none for top-1. Hosted reads only if the table names label quality as the top bucket, with an owner yes per round.
8. **Stall:**
   - two rounds without adoption → report and switch the primary to the next row of the table;
   - stop only when the table has no row with a predicted gain of at least +1 point.

   This reconciles with playbook ch.16: the loop does not stop at a stall, it moves to the next lever.
9. **Runner:**
   - one result key per card (the primary's confirm score);
   - a leakage assertion: no `test-clean` id or publisher in any training input;
   - `loop_permissions.json` updated to record L2751, so MN-DS training cards are allowed for this re-ranker only.

## Process guards (added after round 1 check, L2755)
- prereg.json carries the sha256 of the round script and the split; scoring refuses if either changed.
- Development runs may score `select` only; `confirm` is scored once, by the final run.
- Each adopted result is re-scored by an independent script from the saved model and cached inputs.

## Licence
MN-DS licence checked before any training (result in the ledger). If training is not allowed, the round uses blends only.
