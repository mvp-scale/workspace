# 14 · Routing, soft targets and outside anchors

**Goal:** how disagreement among labelling models is handled, and how a field is checked against something outside the models. Ledger T27, owner 2026-11-04: disagreement is normal input; handle it per item; do not change the pipeline because of one split. Position: it sits with the Label stage, between chapter 03 (teacher labels) and chapter 12 (cross-family test).

## Rules

1. **Route each item by agreement.** All labellers agree: accept the label. They split: keep the item with a soft target (vote shares), down-weighted; never drop it silently. Checked in `projects/world-state/lean/Routing.lean`. *Evidence in our code:* `consensus_rescore.py` leaves split items out (MM3-0601); the fix is this rule.
2. **Agreement is a report, not a gate.** Krippendorff alpha bands (0.667, 0.80) describe a field; the field gate (chapter 13) is the only stop.
3. **Agreement is not accuracy.** Where Clef and Gemma gave the same topic, 0.689 of those answers matched the human labels (MN-DS, L748); models share views. Every field needs an outside anchor, even a one-sided one, or a written reason there is none.
4. **Anchors in use.** Topic: MN-DS human IPTC labels (T28). Presence: MAVEN-FACT, one sided, refutes a yes and never confirms one (`lean/MavenFactFit.lean`, T29). Story type: none found (T30). Anchor files stay in `data/anchors/`, git-ignored, internal scoring only, licence line recorded.
5. **Guard the anchor itself.** Key items by row position plus URL, never an id alone (MN-DS data_id collides in 818 rows). Draw a fresh sample for any change of mapping; never score a change on the sample that suggested it. An empirical crosswalk learned from the raters answers is rejected: it rewards their confusions.
6. **Aggregation.** Majority vote or the mean of probabilities. Dawid-Skene and Snorkel style label models assume independent labellers and LLM labellers are not (arXiv 2601.22336; LREC 2026 study, aclanthology 2026.cas-1.11); use them only with a dependency model. Newest sources are single studies; treat them as warnings.
7. **Confident tier.** Calibrate a confidence cutoff on the development set only, apply once to the held-out set. Sealed result: story type 0.950 at coverage 0.921, topic two guesses 0.955 at 0.870 (`runs/pulse/selective_check.json`). Under the Ready rule (a skipped item is a miss) this changes no verdict; it gives consumers a tier they can trust.
8. **Leakage.** Near-duplicate check of every test set against the training pool before it is called clean (`projects/world-state/leakage_check.py`; sealed 0.0053).
9. **Change control.** One change per round, a prediction on the ledger first, revert on a miss, never re-open another field because of it.

## What is not settled
Soft-target training is unproven for presence (T27 steps 3 and 4). Topic confidence needs recalibration (calibration error about 0.09). No published source gives a go or no-go threshold for these rules; the lines marked ours are ours.
