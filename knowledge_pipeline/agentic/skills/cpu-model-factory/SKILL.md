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
8. Asking Clef or Jev a typed question: write it by the question rules in `mm3 agent probe` (one narrow judgment, at most 160 characters, positive wording, a "cannot tell / none fits" option) and test the wording on the gold set for EACH model, because wording that works for one model can fail on another. Report, per wording: how many yeses, how many sure cases it finds, how many yeses are right. MM3 itself is a reviewer of code and process (consensus across three perspectives), never a labeller; use it to review scripts and steps, citing the run id. Wording results go in `playbook/08` "How to ask Clef and Jev".
8. Never print credentials. Load them per process from the vault.
9. Evaluators judge evidence; they never redo or fix the work. The worker never judges its own task.
10. Before first using any key or login, list what it can see and confirm it is the account or workspace on the card. Check a helper's claim against the source before relying on it (in one review, 4 of 41 claims were wrong).
11. Owner communication follows `## Owner communication` below. A report that breaks it is rewritten before it is sent.

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
- Close every task with `python3 knowledge_pipeline/.ledger/close_task.py <task> --evidence <ref> --step "1|what was done|evidence" ...`. It records each step first and `done` last, because the ledger refuses step lines after done (T5, T6, T14 stayed unchecked for this reason). Start the task with `cp.mjs start` before the work; record steps as they finish, not at the end.
- When a task produces evidence for a quality gate (the Quality page, Q01 to Q29), record it the same turn: `node knowledge_pipeline/.ledger/cp.mjs measure <task> --who claude --measures '[{"gate":"Q14","pass":true,"value":"98.6% rows valid"}]'`. A gate with no measure shows as unmeasured.

## Report format (to the coordinator or owner)

One table: criterion ID · threshold · measured · pass/fail · source. Then one line: next action. No narrative.

## Owner communication (rule 11; each line comes from a complaint, 2026-10-30 to 2026-10-31)

Run this checklist before sending any update.

1. **Answer the exact question first**, in the shape asked (usually one small table), then stop. No side experiments, no different question.
2. **Keep results and requests apart.** A result is stated. A request is one yes/no with what it commits the owner to and what the ledger shows after. If nothing is needed, say "Need from you: nothing".
3. **No contradictory signals.** Never put a pass next to a fail without saying which rule decides. Define a word before using it ("consensus" means the reviewer's own reads agreed, not that the task passed).
4. **Every number says what it is measured against and where it came from** (file, ledger id, MM3 id). Define every term on first use.
5. **Say what was verified and how.** Check the viewer data or the file, not just the append. If a page was not seen in a browser, say so.
6. **Fixed update shape:** Where we are (one phase row), Why it matters (one sentence), Next (what and about how long), Need from you. Under about 12 lines; longer detail goes in a file or page and is linked.
7. **Not reactive.** State the plan and the order before doing it, and what you will report when it finishes.
8. **Screens (viewer, pages):** one concept per column, with job, state, cost and time in their own columns; compact one-line rows with the full text on hover; the same structure on every page that shows the same thing; empty cells stay empty (no filler).
9. **Capture each new complaint the same day:** add it to this list, to the memory file `feedback_communication_balance.md`, and as a ledger note on the task it came from.

## When to stop and ask the owner

A target is missing or contradictory; a cap would be exceeded; a public release of weights or data is involved;
three guideline rounds haven't reached κ ≥ 0.4; a result contradicts a recorded owner decision.
