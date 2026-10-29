# Gate report: <task ID> <model name>

| Item | Value |
|---|---|
| Model file + sha | e.g. `student_v2.int8b.onnx` 2bade18d |
| Scorer + sha | e.g. `kit/eval/score_spans.py` 47d2b656 |
| Test set + sha, size | e.g. `esilver.json` ea728dcb, 11 articles |
| Model picked on | dev only (rule written before scoring test) |
| Hardware for speed | CPU model, vCPU, VNNI/AVX-512 present? |

## Quality (one row per layer)

| Layer | Metric | Score | 95% interval (bootstrap by item) | IAA | Gate (0.8 × IAA) | Pass on lower bound? |
|---|---|---|---|---|---|---|
| | exact / overlap F1 | | | | | |

## Speed and cost

| Measure | Value |
|---|---|
| ms per model call (window size) | |
| ms per typical item, p50 / p95 | |
| vCPU-s per item | |
| items/s on N vCPU (process × thread layout) | |
| $ per million items (at stated vCPU price) | |

## Verdict

Pass / fail per definition-of-done criterion, one line each, plus the next action.
