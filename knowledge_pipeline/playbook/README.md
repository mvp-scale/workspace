# Playbook: training small, fast CPU models with LLM teachers

For any task where you want a model that runs on plain CPUs (server, laptop, browser) at thousands of items per
minute, with no GPU and no LLM at inference. Large models do the expensive thinking once, offline; a small student
learns from them.

Chapters, in the order you use them:

| # | Chapter | Answers |
|---|---|---|
| 01 | [Frame the task](01-frame-the-task.md) | What exactly is the model deciding, and what speed/cost/quality does the product need? |
| 02 | [Guidelines and gold](02-guidelines-and-gold.md) | How do humans mark it, how well do they agree, what is the test set? |
| 03 | [Teacher labels](03-teacher-labels.md) | How do LLMs produce training labels cheaply and trustworthily? |
| 04 | [Student model](04-student-model.md) | What small architecture, heads and training recipe? |
| 05 | [Quantize and export](05-quantize-and-export.md) | How to get an int8 ONNX file without losing quality? |
| 06 | [Evaluate and gate](06-evaluate-and-gate.md) | How do we decide it's good enough, honestly? |
| 07 | [Speed and cost](07-speed-and-cost.md) | How to measure and budget items per second per vCPU? |
| 08 | [Compute and runs](08-compute-and-runs.md) | Where do jobs run (local 3090/5090, RunPod, Google, Kaggle) and how do we not waste hours? |
| 09 | [Ship and monitor](09-ship-and-monitor.md) | What is shipped, how it runs in Python and the browser, how it stays honest? |
| 10 | [Lessons](10-lessons.md) | What cost us time and GPU hours, and the rule each one produced |

## One-page checklist

Before any compute:
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
- [ ] Small encoder (≤ 30M params), one shared pass, one head per question (04)
- [ ] Variants compared on dev only; the pick rule written before test scoring (04, 06)
- [ ] int8 export; quantized vs fp32 agreement checked on dev; fused ops noted (05)

Decide:
- [ ] Score once on gold; gate = 0.8 × IAA on the lower 95% bound (06)
- [ ] Speed: ms per call, ms and vCPU-s per item, items/s with the process × thread layout (07)
- [ ] Gate report + model card filled (`../templates/`)
- [ ] Ledger line with every number and its source
