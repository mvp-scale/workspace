# GO — session handoff

Written 2026-10-18 23:20. Overwritten at each handoff.

## Tone
- Run the Fable method to the end: `docs/research/2026-10-18 Fable method.md`, steps 3 to 12. The goal is the World engine running on a CPU reader.
- Follow the decision rule in `CLAUDE.md`. Inside the current step's method: act. Outside it: record a concern on the step it belongs to. Flags and weak results are evidence, not tasks.
- Every claim cites a ledger item, a pinned file with its command, or an MM3 run id. Predict before each run, score after.
- Short replies: what was done, the number, the ledger id, what's next. No option lists unless a decision below is due.
- The resource schedule below is the full ask. Raise nothing new mid-step; if the schedule must change, update it here and in the ledger (N-0004) and say so once.

## Start of session
1. `ledger board` and `ledger score`.
2. Get the user's answers to Decisions 1-3 below in one message, then work.
3. Check the labelling chunk (below) and continue Step 3.

## Where things stand
- Step 1 closed (S-0001). All-keys target for a CPU reader: TPR >= .95 with FPR <= .0025, or TPR >= .9 with FPR <= .001 (F-0020). False alarms cost more than misses (F-0019). Key ranking unsettled (F-0021).
- Step 2 closed (S-0002). Majority vote over 3 Clef wordings in `data/step2/labels.jsonl`, every vote kept. It changes 65% of current positives vs the engine's mean-of-2 rule (F-0022). Which rule is right is decided by Step 3's raters (C-0009, C-0010).
- Step 3 open (S-0003). Human reference set for the 16 keys in >= 2 Step 1 rankings. Pool labelling in progress.
- Predictions: 29 made, 25 scored, Brier 0.196. Misses come from predicting before measuring scale.

## Running at handoff
- Labelling chunk 1 of 3 (engine battery, local Clef) on the 1,262 unlabelled queue stories. Started 22:45, hard stop 23:40. Log `data/newsreader/labels/label.log`. Resumable: reruns skip labelled stories.

## Resource schedule, steps 3-12 (the full ask)
Measured rates: Clef answers the 328-question battery at 12.9 stories/min and the 159 definition wordings at 25/min (8.5 stories/min for both). The queue adds 800-1,300 full-text stories a day.

| Step | GPU (local Clef) | Human time | Money | Other |
|---|---|---|---|---|
| 3 Reference set | 2.5 h (pool labelling; 0.3 h done) | 2 raters x 30-48 h + adjudicator ~5 h | – | Rating tool (hand-check page, Decision 3) |
| 4 Re-score vs reference | – | – | – | CPU, ~1 h |
| 5 Corrected rates | – | Review of the engine change | – | World engine change: read corrected per-key rates over a window instead of one story at a time (~3-4 h coding); QuaPy install |
| 6 Flag wrong labels | 0.25 h (re-asks) | Flags go to the raters (inside step 3 hours) | – | cleanlab install; needs a first student (step 8) |
| 7 Labelling rounds | ~6 h over 3 rounds (~3,000 stories, both question sets) | – | – | small-text install |
| 8 CPU student | – | – | – | model2vec + potion install; CPU training ~2-3 h |
| 9 Thresholds | – | – | – | CPU, ~1 h |
| 10 Learning curve | – | – | – | CPU, ~2 h |
| 11 Compare students | – | Possibly +5-15 h per rater if the test is too small | – | CPU |
| 12 Monitoring | ~4 min/day once live | – | – | Drift alert in the engine |
| MM3 checks (all steps) | – | – | ~$0.04 (about 40 hosted Jev checks at ~$0.001) | Local Clef checks free |
Totals: GPU ~8.75 h in chunks under 1 h (above the earlier 8 h forecast, R-0017). Human 65-100 h across 2 raters + ~5 h adjudication. Money ~$0.04. One engine change.

## Order: fixed for a reason, or reorder by value?
The method orders steps "by expected return on effort". Hard dependencies (from the method and the ledger):
- 4, 5 (TPR/FPR) and 11 need the human reference (3).
- 6 needs out-of-fold probabilities from a student; today's BitMob students read battery atoms, not engine keys (F-0006), so 6 needs step 8 first.
- 7 positive-hunting needs nothing new; its uncertainty-sampling half needs a student (8).
- 8, 9, 10 need labels only (Step 2's labels exist; 7 adds more).
The human rating in 3 is the long pole (30-48 h per rater, about 1-2 weeks of part-time rating).

## Decisions for the user at session start
1. Order. (a) Strict method order: wait for the raters before steps 4-11. (b) Two tracks: raters do 3 while the machine track runs 7 (positive hunting) -> 8 -> 9 -> 6 -> 10 on Clef labels and builds the step-5 engine change; everything is re-scored against the reference in 4 and 11. Recommendation: (b). Same steps, same pass bars; no idle weeks.
2. Raters: who the two raters and the adjudicator are.
3. Rating tool: finish `demo/handcheck.html` + `/api/handcheck` (not live) as the rating tool, or revert it.
Also open: whether to commit (nothing from 2026-10-17/18 is committed). Hosted Jev labelling with article text stays not approved.

## Next actions (Step 3)
1. Chunk 2: `cd probes/world-engine && timeout 3300 env WE_RULES=rules_v2 /workspace/kev/.venv/bin/python -I /workspace/newsreader/bitmob/label.py 1262 6 >> /workspace/data/newsreader/labels/label.log 2>&1`
2. Chunk 3 (definition wording on new stories): `timeout 3300 env WE_RULES=rules_v2 /workspace/kev/.venv/bin/python /workspace/newsreader/bitmob/label_w3.py 6 >> /workspace/data/newsreader/labels/label_w3.log 2>&1`
3. Score R-0028 and R-0029.
4. Re-run `probes/world-engine/step2_labels.py` on all 2,142 stories; draw the sample per S-0003; write rater guidelines from the attribute definitions; state exact rater hours.
