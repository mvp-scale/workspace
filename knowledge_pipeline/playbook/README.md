# Playbook: training small, fast CPU models with LLM teachers

For any task where you want a model that runs on plain CPUs (server, laptop, browser) at thousands of items per
minute, with no GPU and no LLM at inference. Large models do the expensive thinking once, offline; a small student
learns from them.

Chapters, in the order you use them. The number is a stable file ID (scripts and the ledger cite it), not the position: read down the rows.

| Stage | ID | Chapter | Answers |
|---|---|---|---|
| Define | 01 | [Frame the task](01-frame-the-task.md) | What exactly is the model deciding, and what speed/cost/quality does the product need? |
| Define | 02 | [Guidelines and gold](02-guidelines-and-gold.md) | How do humans mark it, how well do they agree, what is the test set? |
| Define (gate) | 13 | [Field qualifier](13-field-qualifier.md) | Can this field be classed and measured at all? GO, REVISE or PARK on a small pilot, BEFORE any teacher labelling |
| Define | 15 | [The BitMob stack](15-bitmob-stack.md) | What are the tools, models and router, in what order do they run, and what does Lean prove about that order? |
| Label | 03 | [Teacher labels](03-teacher-labels.md) | How do LLMs produce training labels cheaply and trustworthily? (needs a GO from 13) |
| Label | 14 | [Routing, soft targets and outside anchors](14-routing-and-anchors.md) | How is disagreement handled per item, and how is a field checked against something outside the models? |
| Label | 12 | [Cross-family test](12-cross-family-test.md) | One test, run unchanged on any model family, that returns comparable scores? |
| Build | 11 | [Model selection](11-model-selection.md) | Which trunk, span and claim models, chosen on measured fit from live sources? |
| Build | 04 | [Student model](04-student-model.md) | What small architecture, heads and training recipe? |
| Build | 05 | [Quantize and export](05-quantize-and-export.md) | How to get an int8 ONNX file without losing quality? |
| Judge | 06 | [Evaluate and gate](06-evaluate-and-gate.md) | How do we decide it's good enough, honestly? |
| Judge | 07 | [Speed and cost](07-speed-and-cost.md) | How to measure and budget items per second per vCPU? |
| Ship | 09 | [Ship and monitor](09-ship-and-monitor.md) | What is shipped, how it runs in Python and the browser, how it stays honest? |
| Any stage | 08 | [Compute and runs](08-compute-and-runs.md) | Where do jobs run (local 3090/5090, RunPod, Google, Kaggle) and how do we not waste hours? |
| Any stage | 10 | [Lessons](10-lessons.md) | What cost us time and GPU hours, and the rule each one produced |
| Any stage | 16 | [The working loop](16-the-working-loop.md) | How does one round run (card, prediction, smoke test, score, record), how do we see whether we are working or waiting, and how does the loop improve itself safely? |

## Words we use

One word, one meaning. Tag every status line and every ledger note with one of the first three.

| Word | Means | Example |
|---|---|---|
| **Main loop** | Train the reader on the best labels, score it on a clean held-out set, mine its mistakes, change ONE thing, retrain, repeat. A ledger prediction before each round, a number on the page after. Nothing else is called a loop. | Round 1 on the 46k pool labels |
| **Ceiling** | What Sonnet scores against its own rerun on a field: the most any reader can score as agreement with Sonnet | story 0.99, presence alpha 0.94 |
| **Registered student** | The reader the Engine page names (now `v6b-student`); every comparison uses its own score file | `runs/pulse/end2end_v6b-student_devq.json` |
| **Check** | Work that tests how we measure | Agreement scores, codebook tests, planted-bug tests |
| **Groundwork** | Preparing data or tools for the main loop | Pool labelling, picking a labeller |
| **Scheduler** | The timer that wakes the agent (`/loop` wakeups) | A wakeup that finds nothing to do |
| **Owner decision** | Only the owner can approve it | The engine switch, condition tiers, capability sources |
| **BitMob stack** | Tools + models + router, in that order (chapter 15) | Clean, Scan, Validator; BitMob Domain; BitMob Router |
| **BitMob tools** | Command-line tools that find, tie down and check things in the text; not classifiers | Scan, Fact extractors, Validator |
| **BitMob model** | A small CPU classifier focused on one head: BitMob Domain, Function, Condition, Area, Capability, Novelty. Versions are tagged (Domain v6b, Domain sparse) | BitMob Function = story type |
| **BitMob Router** | Reads what the tools found and calls a model only for a head they left open | Decider is its second half |

Why: in 2026-11-03 the scheduler, the pipeline and the improvement cycle were all called "the loop". Checks and
groundwork looked like loop work, and the best built reader (v6b-student, story type 0.888 to 0.918 on the clean
holdout, GO.md, item 1 under "NOW") sat un-adopted while we measured the measuring stick. Chapter 10 has the rule.

## One-page checklist

Before any compute:
- [ ] Say which part of the main loop the step moves, or tag it check or groundwork (README, Words we use)
- [ ] One-sentence question per head, and the product target: items/min, hardware, $ per million items, quality floor (01)
- [ ] Guideline written; 30–50 items doubly annotated; agreement (IAA) measured per layer (02)
- [ ] If IAA κ < 0.4: fix the guideline, not the model (02)
- [ ] Frozen scorer and test set, sha recorded; test set never used for choices (02, 06)
- [ ] Task card with definition of done, stop rule, budget caps (`../templates/task-card.md`)

Labels:
- [ ] Cheap CPU pass proposes candidates; LLM verifies them, not raw text (03)
- [ ] Two model families label; keep agreement, review disagreement (03)
- [ ] Batch API + prompt caching; spend logged per job (03)

Model:
- [ ] Small encoder, one shared pass, one head per question; chosen on measured CPU fit from live, dated sources, licence read from the LICENSE file (04, 11)
- [ ] Variants compared on dev only; the pick rule written before test scoring (04, 06)
- [ ] int8 export; quantized vs fp32 agreement checked on dev; fused ops noted (05)

Decide:
- [ ] Score once on gold; gate = 0.8 × IAA on the lower 95% bound (06)
- [ ] Ceiling measured first (Sonnet against itself, per field); bar = 0.8 × ceiling, written before scoring (06, rule 13)
- [ ] Baseline = the registered version's score file, named and cited; gains inside its 95% interval or run noise are "no gain" (06, rules 12, 16)
- [ ] Rare fields: curves (AUC, recall at fixed precision), not one cut-off (06, rule 14)
- [ ] Speed: ms per call, ms and vCPU-s per item, items/s with the process × thread layout (07)
- [ ] Gate report + model card filled (`../templates/`)
- [ ] Ledger line with every number and its source; run `kit/live/note_guard.py` first; predictions before, scores after, corrections name what they supersede (`.ledger/AGENTS.md` rules 8 to 10)
