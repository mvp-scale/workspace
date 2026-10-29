# Acceptance and success criteria

Four levels. Each criterion has an ID, a metric, a threshold, the evidence that proves it, and who checks it:
**script** (automatic, blocks the launch or the merge), **evaluator** (a small-model agent or a reviewer checks the
evidence, doesn't redo the work), **owner** (decision line on the ledger).

Thresholds marked **(P)** are proposals until the owner settles them. The baseline column is what the first project
(world-engine news classifier) achieved, so improvement is measurable.

## R · Every compute run (blocks launch)

| ID | Criterion | Threshold | Evidence | Check |
|---|---|---|---|---|
| R1 | Task card complete before launch: question, definition of done, stop rule, caps (GPU-h, CPU-h, $, tokens) | 100% of runs | ledger `task` line earlier than first run | script |
| R2 | Smoke test on ≤ 3 items finished before any run over 30 min | 100% | smoke log id cited on the task | script |
| R3 | Frozen inputs (scorer, gold, model, data manifest) asserted by sha at start and printed in the log | 100% | log lines | script |
| R4 | Only one job per GPU; quota checked before launch | 0 overlaps | status output saved with the launch | script |
| R5 | Spend stays under every cap; hitting a cap stops the run | 0 overruns | spend log vs card | script |
| R6 | Result reproducible: evaluator re-fetches outputs and re-scores; numbers match exactly | 100% of gating runs | evaluator note with run id | evaluator |
| R7 | Run is informative: it ends with pass/fail on its definition of done (not a crash, timeout or void output) | ≥ 80% of remote runs **(P)** | ledger result lines | evaluator |

## D · Data, guideline and labels (before training)

| ID | Criterion | Threshold | Evidence | Check |
|---|---|---|---|---|
| D1 | Agreement (IAA) measured per layer on doubly-annotated items, with interval | ≥ 30 items per layer and a 95% interval reported for every layer | IAA table + item list | script |
| D2 | Guideline fit to scale up labelling | κ ≥ 0.6 go; 0.4–0.6 go with review of disagreements; < 0.4 fix the guideline first | IAA table | script |
| D3 | Gold set: ≥ 20–30 human-reviewed items per source type, split by publisher/time/event cluster, 0 near-duplicates with training | as stated | split manifest + overlap check output | script |
| D4 | Teacher qualifies before bulk labelling: teacher vs gold clears the same gate as the student (0.8 × IAA) on every layer it labels | all layers | teacher gate report | evaluator |
| D5 | Ruler independence: a consensus ruler doesn't include the student's own teacher for the layer being judged | 100% | ruler config | evaluator |
| D6 | Every label carries provenance (teacher, prompt version, date); licence/terms checked for training use | 100% | label manifest; licence note | evaluator |

## M · Model (to ship)

| ID | Criterion | Threshold | Evidence | Check |
|---|---|---|---|---|
| M1 | Every gated layer: lower bound of the 95% bootstrap interval (by item) ≥ 0.8 × IAA | all layers | gate report | script |
| M2 | Beats the zero-model lexical baseline and the previous model with non-overlapping intervals, or the claim is "no change" | as stated | gate report | evaluator |
| M3 | Selection rule written before test scoring | ledger timestamp of rule < timestamp of test score | ledger | script |
| M4 | int8 vs fp32 on dev: max per-layer drop ≤ 0.01 F1 and inside the interval | ≤ 0.01 (baseline .0007) | quantization report | script |
| M5 | Speed meets the per-item budget from the owner's target on reference hardware; p50 and p95 reported with CPU flags | budget met **(P: owner sets target)** | speed report | evaluator |
| M6 | Tokenizer parity between training and runtime | 100% ids and offsets on all eval items | parity log | script |
| M7 | Clean-environment ship test: output identical to the evaluation harness | identical | ship log | script |
| M8 | Variant comparisons exceed run noise | difference ≥ 2 × run-to-run sd, else "no difference" | ≥ 3 seeds per arm | evaluator |
| M9 | Model card and gate report filled; release scope approved | 100%; public release needs owner line | `templates/` copies | owner |

## P · Program success (did the process improve?)

| ID | Measure | Target **(P)** | Baseline (first project) | Source |
|---|---|---|---|---|
| P1 | GPU-hour yield: share of GPU-h in runs whose result was used or answered the question | ≥ 70% | under 50% (est., `playbook/10-lessons.md`) | ledger + quota logs |
| P2 | First-attempt success of remote runs (R7 on the first push) | ≥ 80% | not recorded; frequent re-pushes | ledger |
| P3 | Cost per gated head: GPU-h and API $ from task card to passing gate report | ≤ 3 GPU-h and ≤ $10 | ~32 GPU-h and ~$6 for the first 6-layer student, incl. dead ends | ledger |
| P4 | Elapsed time from task card to gate report for a new head | ≤ 5 working days | ~3 weeks for the first student (topic work earlier) | ledger timestamps |
| P5 | Agent token caps respected | 0 overruns | 34M vs 6M cap once (L390) | wave lines |
| P6 | Traceability: every published number has a ledger id, file or MM3 id | 100% | high, not audited | evaluator sample of 20 numbers |
| P7 | Guideline-first: no model training on a layer whose IAA hasn't been measured | 0 violations | event nouns trained before IAA known | ledger |

## S · Pipeline system (PRD v0.2, for later stages)

| ID | Criterion | Threshold | Check |
|---|---|---|---|
| S1 | Envelope validity on supported formats | ≥ 99%, zero silent losses | script |
| S2 | Every committed graph update has a resolvable evidence span | 100% or write blocked | script |
| S3 | Anchor linking on held-out mentions | precision ≥ .90, recall ≥ .80, else abstain | evaluator |
| S4 | Cross-source event merges | precision ≥ .95, false merge < 1% | evaluator |
| S5 | Throughput | owner's items/min on the agreed hardware, p95 latency reported | evaluator |

## How the levels connect

A head ships when R holds for every run that produced it, D1–D6 hold for its data, and M1–M9 pass. P is reviewed
once per project phase to decide whether the playbook itself needs a change. Proposed thresholds become binding
through an owner `decision` line.
