---
name: cpu-model-factory
description: Use when asked to build, improve, evaluate or speed up a small CPU model (ONNX/int8 encoder, classifier, span tagger) trained from LLM or human labels; when planning labelling, training, quantization or benchmark runs on local GPUs, RunPod, GCP or Kaggle; or when judging whether such a model is ready to ship.
---

# CPU model factory

You turn a question into a small, fast, verified CPU model. Large models are teachers only. Follow the stage machine
in `knowledge_pipeline/agentic/stages.yaml`; gates are defined in `knowledge_pipeline/ACCEPTANCE.md`. Tools are in
`knowledge_pipeline/kit/` (eval, teacher, student, ops; each has a README). The human-length reasoning behind each rule is in
`knowledge_pipeline/playbook/` (read a chapter only when a rule below is unclear).

## Hard rules (never break; a broken rule fails the task)

1. No compute starts without a task card that passes `node knowledge_pipeline/agentic/scripts/check_card.mjs <card>` (R1–R5).
2. No training on a layer whose agreement (IAA) hasn't been measured. Low IAA (κ < 0.4) = fix the guideline (S2).
3. Gold and scorer are frozen by sha before any score is produced. Never tune against gold. Pick variants on dev
   with a rule logged before test scoring (M3).
4. A layer passes only if the lower bound of its 95% bootstrap interval (resampling items) ≥ 0.8 × IAA (M1).
5. Smoke test (≤ 3 items, ≤ 10 min) before any run over 30 min (R2). One job per GPU (R4). Stop at any cap (R5).
6. Every number you report carries its source: ledger id, file path, run id or MM3 id. Unsourced numbers are opinions.
7. Publisher text never leaves private storage: not in git, public datasets, notebooks, pages or model cards.
8. Never print credentials. Load them per process from the vault.
9. Evaluators judge evidence; they never redo or fix the work. The worker never judges its own task.

## Default recipe (deviate only with a reason on the card)

| Step | Default | Escalate when |
|---|---|---|
| Labels | CPU candidates → small API model verifies: Message Batches, guideline in a cached prefix with 1 h TTL (≥ 512 tokens; confirm cache reads), strict JSON schema, validate every row, dedicated workspace key + spend limit | teacher fails its gate on gold → add second model family → larger model |
| Ruler | two model families' consensus on 200+ items, plus 20–30 human-reviewed items | judges disagree (κ < 0.4) → guideline work |
| Student | one encoder (≤ 30M params), one head per question, 254-token windows stride 192 | dev gain stops → stop growing |
| Distillation | hard labels from consensus; soft targets from a fine-tuned large encoder when available | — |
| Export | fp32 ONNX → several int8 options → pick on dev (max layer drop ≤ 0.01) | encoder intolerant of int8 → per-channel or partial int8 |
| Runtime | ONNX Runtime, N processes × 1 thread for throughput | target CPU has VNNI/AMX → benchmark OpenVINO |
| Compute | local GPU (5090/3090) → API → RunPod/GCP burst → Kaggle fallback | local busy or job > 32 GB VRAM |

## Workflow per task

1. Read the card and the stage entry/exit in `knowledge_pipeline/agentic/stages.yaml`. If an entry item is missing, stop and report which.
2. Run the cheapest test that could kill the idea first (`risk_first` on the card).
3. Smoke test; then the full run via a script that fails loudly (requires explicit success text, checks inputs,
   case-insensitive status). Don't poll inside your turn; let the script block.
4. Write results as numbers only, with shas, to the output paths on the card; append one ledger result line.
5. Hand to the evaluator role with the task id and evidence paths. Done means the evaluator's verdict says pass.

## Report format (to the coordinator or owner)

One table: criterion ID · threshold · measured · pass/fail · source. Then one line: next action. No narrative.

## When to stop and ask the owner

A target is missing or contradictory; a cap would be exceeded; a public release of weights or data is involved;
three guideline rounds haven't reached κ ≥ 0.4; a result contradicts a recorded owner decision.
