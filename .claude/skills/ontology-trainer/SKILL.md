---
name: ontology-trainer
description: Train and accept fast CPU classifiers for every element of an ontology (topics, places, story types, conditions or any label set) from LLM teacher labels, with pre-stated acceptance criteria per area, a multi-vendor jury test set, hour-boxed targeted training rounds, regression checks, and hard resource caps. Use when asked to train, fine-tune, distil or validate classifiers for an ontology, or to build labelled training/test data with Jev, Clef or Claude jurors.
---

# Ontology trainer

Goal: a classifier per ontology area that passes stated acceptance criteria on a frozen, jury-labelled test set, within time and spend caps, without regressing areas already accepted.

Work in the Fable-method way (CLAUDE.md): every claim cites a ledger item, a pinned file with its command, or an MM3 run id; predict before each run, score after.

## 0. Caps first (never skip)

Before any job: record in the ledger the total time window, per-step limit (under 1 hour), hosted spend cap, GPU use, and what happens to other services. Every step runs under `timeout`; long cascades also get an independent stop (`systemd-run --on-active=<window> ...` that kills this run's processes by verified PID) and a memory cap (`systemd-run -p MemoryMax=...`). Bound every producer/consumer queue (an unbounded queue of hidden states was OOM-killed once). Ask the user for the window and caps if none are recorded.

## 0b. The replacement contract is the parent of everything (never skip)

A trained reader that replaces another component must produce everything that component's consumer needs, the way the consumer uses it. Before any labels, heads, criteria or training: list the consumer's contract from its own code and spec (every input, output, cardinality such as "one or more topics", value range, and how each output is used downstream). Every acceptance criterion descends from a contract row. Any deviation (fewer labels, single- instead of multi-label, top-N only, a skipped output) is NOT allowed unless it has a recorded exception approved by the user, or is raised for discussion first. A deviation without one is a defect, not a design choice.

## 1. Define areas and acceptance criteria (pre-registered)

Write and review every criterion with the `acceptance-criteria` skill (`.claude/skills/acceptance-criteria/SKILL.md`): atomic sentence template, four levels, circling, bar rules, sources.

- List the ontology areas that are read from text (not those computed by rules from other areas).
- For each area write about 10 acceptance criteria, each with a number and a probe set: overall score on the frozen test set; behaviour probes (e.g. for places: named in headline only, demonym only, city only, several places, none, false-alarm rate on generic text, per-region recall, calibration); for directional labels a flip test (claim reversed should drop the probability by at least half); a false-alarm rate per 1,000 items tied to what the downstream system tolerates.
- Judge criteria against the ontology itself (did the reader pick the right label); downstream tolerance is a separate check.
- Smart extraction first: per area, ask what a script can read (place lists, entity recognition, cue words) and what the item's context supplies (source, channel, destination) as a stated fallback. Text overrides the fallback, never both. Script-checkable criteria are scored by the script (measure the script's own errors on the pilot); the rest by the jury or an Opus reviewer. Some areas are subjective and lean on the jury: this is one method, not the only one.
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

## 5. Targeted rounds by count

A round is a fixed number of new labelled items (1,000 by default), not a time box; the time caps of step 0 stay only as a safety stop. Each round:
1. Score every candidate model on every area and criterion (scorecard: model x area x criterion, pass/fail, plus ms per item, RAM, size).
2. New items: about half random, half aimed at failing criteria (mined from the pool by script, similarity, keywords or uncertain cases). Label with the bulk teacher, keep items where teachers agree.
3. Retrain every candidate (frozen-encoder baselines, fine-tuned encoder, static models; `newsreader/bitmob/bakeoff_baseline.py` as the model), tune thresholds per label on held-out data. Refit the learning curve.
4. Re-score on the frozen test set. Regression check: any accepted criterion that drops below its bar is reopened.
5. Record the round (ledger fact, predictions scored, pins: prompt version, teacher version, training set, code). Every run ends with the acceptance scorecard (`newsreader/bitmob/scorecard.py` as the model, D-0018): each criterion pass/fail/not measured against its pre-stated bar, grade per area (done at >= 90%), changes since the last card, "possibly too weak / too hard" diagnoses, a fingerprint of the criteria so a moved bar is flagged; the card is recorded as a ledger fact with the card file pinned, and `--history` shows every criterion across every iteration. A criterion with no stable trend after 3 rounds (rule stated with the criteria) goes to consensus: Opus investigator, then the user. Stop an area when all its criteria pass on at least one candidate; stop when all pass, a cap is hit, or the learning curve predicts no useful gain.
6. Prioritise the next window (never skip; the lead drives this, it does not wait). Mine everything from this round and the ledger for patterns: per-area error clusters (confused label pairs, slices, outlets), judge disagreement and reliability per element, criteria that stayed flat, failed predictions. Use MM3 (`scan` / `drill`) where reading by hand would miss a pattern. Rank the candidate levers (more targeted data, definition fix, calibration, model change, criteria fix) by expected gain toward a failing criterion per hour of work, write the top one as a prediction, and launch it. Only items on the user's stop list (raters, engine change, hosted spend beyond approval) wait for the user.

## 6. Reporting

Show proof, not only averages: per-item examples (item, teacher label, classifier label, probability, match) for each area (`newsreader/bitmob/show_examples.py` as the model), plus the scorecard and the regression table.
