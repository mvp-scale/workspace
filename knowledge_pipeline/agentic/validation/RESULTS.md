# MM3 validation results (2026-10-29)

MM3 0.1.5 (TypeSafe, model jev-1.13.0), `class` and `replay` runs on the high-risk parts of the kit. Every run is in
the repo's `.mm3/log.jsonl`; check one with `mm3 view MM3-####`. `pass: no` probes clear at ≤ 0.30, `pass: yes` at ≥ 0.70.

| Part | First run | Found | Fix (commit) | Re-check | Now |
|---|---|---|---|---|---|
| Launch hook `agentic/hooks/pre_launch.mjs` | MM3-0019 fail | Q5 (.42): exit code on unreadable input unclear; Q4 (.88): a launcher outside the regex gets through | fail closed on bad input or missing checker; regex covers kit entry points, ssh, docker --gpus, sbatch, vllm, CUDA_VISIBLE_DEVICES; runners re-check the card (fb56d26) | MM3-0020: Q5 fixed, route → adopt; Q4 still | **Residual by design:** any regex hook can be bypassed by an unlisted command; the kit's runners are the second gate |
| Card checker `agentic/scripts/check_card.mjs` | MM3-0021 fail | Q5 (.95): smoke log accepted without the file; Q4 (.70): low declared caps skip the smoke test | log must exist; smoke required on every tier except a short local-CPU job (9816b1f, a5c65bb) | MM3-0025, MM3-0028: Q5 fixed; Q4 still | **Residual by design:** a local-CPU card capped ≤ 0.5 h needs no smoke log |
| Batch labeller `kit/teacher/claude_batch.py` | MM3-0022 unsure | Q5 (.39): key-file keys only redacted by pattern; Q1 (.54) cap order unclear | every key read is redacted; any run failure exits scrubbed, no raw traceback (9816b1f, b6d9449) | MM3-0029: all 9 probes pass (exposure ≤ .23) | Goal "never, whatever fails" not provable from excerpts (p .28); no specific gap named |
| Scaffold `kit/ops/new_project.sh` | MM3-0023 unsure | all 9 probes pass; severity call weak (high p .31) | — | — | Adopt |
| Design: SKILL.md, stages.yaml, ACCEPTANCE.md | MM3-0024 fail | Q7 (.67): not every criterion has a numeric/yes-no threshold; Q3 (.78) on-fail coverage | D1 threshold made explicit (9816b1f) | MM3-0027: Q3 fixed; Q7 still | **Open by design:** M5, S5, R7 and P1–P7 targets are proposals until the owner sets them |
| GPU runner `kit/ops/local_gpu_run.sh` | MM3-0030 fail on severity | all 9 probes pass (one job per GPU, secrets, private data, card check first) | — | — | Adopt; severity call weak (high p .47) |

Not covered by MM3 yet: `kit/eval/` (18 unit tests), `kit/student/` (16 unit tests incl. a cross-check against the
shipped decoder), `kit/teacher/open_model.py`, `kit/ops/kaggle_run.sh`. None of the kit has run on real data, a GPU or
the live API; first use needs the smoke tests in `kit/teacher/README.md` and `kit/student/README.md`.

`mm3-loop-factory.yaml` is kept as a design-stage example; `loop` reads no files, so `class` on the real files was used.
