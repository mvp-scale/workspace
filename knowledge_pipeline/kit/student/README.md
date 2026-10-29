# Student kit (S4 train, S6 speed, S7 ship)

Project-agnostic CPU student: shared encoder (default MiniLM-L12 cut to 4 layers, h384; alt `jhu-clsp/ettin-encoder-17m`),
one BIO head per span label (extra channels for overlapping spans), optional multi-label sequence head. Labels come
from your config; the kit has none built in. Distilled from the first project's student v2 (`pipeline/kaggle/student/`,
`pipeline/ship/we_classifier.py`). Stages and gates: `../../agentic/stages.yaml`, `../../ACCEPTANCE.md`.

**Compute:** training runs on a GPU host (local RTX 5090 / 3090, RunPod, Kaggle), never on the dev machine
(`train.py` exits without CUDA unless `--smoke`). Export and bench run on the reference CPU (Kaggle CPU or the target box).

Data (JSONL, char offsets, end exclusive):
`{"id", "text", "spans": [{"start", "end", "label", "p"?}], "labels": [...], "probs": {"LABEL": 0.8}?}`.
`p` / `probs` (teacher probabilities) turn on the soft-target KL loss.

| Stage | Command | Writes | Gates |
|---|---|---|---|
| S4 smoke | `python train.py --config cfg.yaml --smoke` | `out/smoke/smoke.json` (cite `smoke_id` on the card) | R2 |
| S4 train | `python train.py --config cfg.yaml --all-seeds` | per seed: `inputs.json` (shas), `selection_rule.json` (before training), `dev_curve.json`, `last.pt`/`best.pt`, `tokenizer/`, `backbone/` | R3, M3, M8 (≥3 seeds) |
| S4 export | `python export.py --run-dir out/seed42 --out-dir ship/` | `pick_rule.json` (before scoring), `export_report.json`, `model.int8.onnx`, `model.fp32.onnx`, `tokenizer.json`, `labels.json` | M3, M4 |
| S4 parity | `python tokenizer_parity.py --tokenizer-dir out/seed42/tokenizer --runtime-tokenizer ship/tokenizer.json --jsonl dev.jsonl gold.jsonl` | `tokenizer_parity.json`, exit 1 unless 100% | M6 |
| S6 speed | `python bench.py --model-dir ship/ [--model-dir old/] --jsonl sample.jsonl --vcpu 4 --items-per-min N` | `speed_report.json` | M5 |
| S7 harness | `python ship_check.py --model-dir ship/ --fixture fx.jsonl --write-expected expected.jsonl` | reference output | M7 |
| S7 ship | `python ship_check.py --model-dir ship/ --fixture fx.jsonl --expected expected.jsonl` | `ship_log.json`, exit 1 unless byte-identical | M7 |
| run | `python runtime.py --model-dir ship/ --jsonl in.jsonl --workers 4 > out.jsonl` | spans + labels + model sha | – |
| web | serve `web/` with the ship dir copied to `web/model/`; open `index.html` (`?model=path/`) | – | – |

Rules the scripts enforce or record:
- Selection rule (`train.selection`, and the int8 pick rule) is written with a timestamp before scoring (M3).
- int8 pick: max per-head dev drop vs fp32 ≤ 0.01, then lowest token flip rate, then lowest 1-thread window p50.
  Drop is F1 vs dev gold with a paired bootstrap 95% interval (M4). Calibration text is never dev.
- fp32 ONNX must match torch on dev (token agreement ≥ `parity_min_agreement`) before quantizing.
- Fused graphs (`optimize: auto/bert`) hold `com.microsoft` ops: they run in ORT and onnxruntime-web, not in OpenVINO.
  `optimize: none` gives a portable file. `export_report.json` lists the ops for each option.
- Speed: compare models only inside one `bench.py` call (same machine). `--compare` gives ratios only when the
  machine fingerprint matches. Record CPU flags (VNNI / AVX-512 / AMX) with every number. Use N×1 processes for throughput.
- Runtime = `runtime.py` + `core.py` + pinned `requirements.txt`; never ship on a failed `ship_check.py`.

Files: `core.py` (windows / owner / BIO / decode / snap, numpy only, shared by every script), `config.example.yaml`,
`train.py`, `export.py`, `runtime.py`, `tokenizer_parity.py`, `bench.py`, `ship_check.py`, `requirements.txt`,
`web/` (`index.html`, `runtime.js`), `tests/test_core.py` (`python -m unittest discover -s tests`; checks core against
`pipeline/ship/we_classifier.py`).

Limits: the web runner implements WordPiece only (MiniLM / BERT tokenizers; Ettin uses BPE, so use `runtime.py`), and its
offsets are UTF-16 indices (they differ from Python's after emoji / astral characters). The sequence head reads the
[CLS] vector of each window, pooled by max (or mean) over windows.
