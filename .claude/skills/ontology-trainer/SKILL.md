---
name: ontology-trainer
description: Train and accept fast CPU classifiers for every element of an ontology (topics, places, story types, conditions or any label set) from LLM teacher labels, with pre-stated acceptance criteria per area, a multi-vendor jury test set, hour-boxed targeted training rounds, regression checks, and hard resource caps. Use when asked to train, fine-tune, distil or validate classifiers for an ontology, or to build labelled training/test data with Jev, Clef or Claude jurors.
---

# Ontology trainer

Goal: a classifier per ontology area that passes stated acceptance criteria on a frozen, jury-labelled test set, within time and spend caps, without regressing areas already accepted.

Work in the Fable-method way (CLAUDE.md): every claim cites a ledger item, a pinned file with its command, or an MM3 run id; predict before each run, score after.

## 0. Caps first (never skip)

Before any job: record in the ledger the total time window, per-step limit (under 1 hour), hosted spend cap, GPU use, and what happens to other services. Every step runs under `timeout`; long cascades also get an independent stop (`systemd-run --on-active=<window> ...` that kills this run's processes by verified PID) and a memory cap (`systemd-run -p MemoryMax=...`). Bound every producer/consumer queue (an unbounded queue of hidden states was OOM-killed once). Ask the user for the window and caps if none are recorded.

## 1. Define areas and acceptance criteria (pre-registered)

- List the ontology areas that are read from text (not those computed by rules from other areas).
- For each area write about 10 acceptance criteria, each with a number and a probe set: overall score on the frozen test set; behaviour probes (e.g. for places: named in headline only, demonym only, city only, several places, none, false-alarm rate on generic text, per-region recall, calibration); for directional labels a flip test (claim reversed should drop the probability by at least half); a false-alarm rate per 1,000 items tied to what the downstream system tolerates.
- Store them in a dated doc and the ledger before training. Get an MM3 verdict on the criteria (`tools/mm3local` and `tools/mm3hosted`, report splits).

## 1b. Validate each element's definition before labelling at scale

- Write a codebook entry per element: definition, what counts, what does not, one real example of each. Put these rules inside the question text every judge receives (never in a side note to some judges).
- Pilot ~50 items with at least two judges from different vendor families, identical text and instructions, strict machine output (lists of question ids or schema-checked JSON, validated by a script; positional 0/1 strings fail).
- Measure agreement per element (Krippendorff's alpha). Accept a definition at alpha >= 0.8; rewrite and re-test below it; below 0.667 after two rewrites, record the element as not reliably readable from this input and raise it with the user (input length or ontology change).
- Fix wording and question grouping once accepted; changing either later changes the labels.

## 2. Source data and its checks

- Training pool: a large public corpus filtered to the target domain (here CC-News, `data/ccnews/`, filter D-0010) plus live data. Keep a training-set spec with automatic checks (`newsreader/bitmob/audit_trainset.py` as the model) and run it on every build.
- Labels must be made from exactly the text the classifier will read.

## 3. Teachers and the jury

- Bulk teacher: the fastest consistent model, asked the whole question set in one call per item (Jev: `newsreader/bitmob/build_trainset.py`, ~450 items/min).
- Jury for the frozen test set: one vote per vendor family (e.g. Claude Sonnet subagent, Jev, Clef). Same-family models count as one vote; a cheaper sibling (Haiku) may replace its family's vote only after a pilot shows it agrees with the stronger one.
- Rule: 3/3 agree = accepted; 2/3 = accepted, split recorded; otherwise an investigator (Claude Opus subagent) classifies the case as question unclear / data lacks it / classifier could not know, and the user decides the rest.
- One human step stays: the user spot-checks about 50-100 jury answers to measure the jury's own accuracy.
- Pilot every juror on ~50 items before scaling (agreement per pair, time per item).

## 4. Frozen test set

- About 2,000 fresh items, never trained on, labelled by the jury. Never add them to training. All scores are reported against it, per area and per criterion.

## 5. Hour-boxed targeted rounds

Each round, under the caps:
1. Score every area against its criteria (scorecard: area x criterion, pass/fail).
2. Pick failing criteria only. Get new items aimed at them (mined from the pool by similarity, keywords or the classifier's uncertain cases), label them with the bulk teacher, keep items where teachers agree.
3. Retrain (start with frozen-encoder baselines, then fine-tuned encoder; `newsreader/bitmob/bakeoff_baseline.py` as the model), tune thresholds per label on held-out data.
4. Re-score on the frozen test set. Regression check: any accepted criterion that drops below its bar is reopened.
5. Record the round (ledger fact, predictions scored). Stop an area when all its criteria pass; stop the cascade when all pass, a cap is hit, or two rounds bring no gain.

## 6. Reporting

Show proof, not only averages: per-item examples (item, teacher label, classifier label, probability, match) for each area (`newsreader/bitmob/show_examples.py` as the model), plus the scorecard and the regression table.
