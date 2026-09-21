# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this workspace is

`/workspace` is a small git repo of its own (tracking only `setup.sh`, `CLAUDE.md`, `.gitignore` and `demo/`; everything else is ignored). It is a dev-container root holding three independent, separately cloned git repos that all revolve around "Jev-class" typed-decision models (a model gets a `state` plus typed questions — `noul` = P(yes), `choice`, `score` — and returns probabilities, no prose). All three speak or measure the TypeSafe `POST /v1/systemone` wire format.

| Dir | Upstream | Role |
|---|---|---|
| `kev/` | jaredpalmer/kev | Qwen (LoRA) decision model: training, evals, server (Python ≥3.12, uv) |
| `jeff/` | logan-markewich/jeff | GLiFormer-based `/v1/systemone` server (Python 3.12 only, uv) |
| `jevbench/` | fstandhartinger/jevbench | Benchmark harness that scores any of the above (stdlib-only, Python ≥3.10) |
| `data/` | — | Model weights and HF caches (`data/kev/runs/kev`, `data/jeff/models/gliformer-large-v1`); not in any repo |
| `logs/` | — | systemd service logs (`kev*.log`, `jeff*.log`) |

Each repo has its own git history, `.venv`, and docs — run git/uv/pytest commands from inside the specific repo. `kev/AGENTS.md` is that repo's authoritative agent guide (commands, layout, gotchas); read it before working in `kev/`.

## Environment / running services

`setup.sh` is the one-shot, hand-run bootstrap (installs tooling, clones repos, downloads weights, writes systemd units). It is not wired to container startup; re-run sections individually if needed.

Three systemd services are created by it (logs in `/workspace/logs/`):
- `kev.service` — `python -m kev.serve --run /workspace/data/kev/runs/kev --port 8008`. kev hardcodes `127.0.0.1`, so `kev-proxy.service` (socat) republishes it on `0.0.0.0:8009`.
- `jeff.service` — `jeff` entrypoint on `:8000`, `JEFF_DEVICE=cuda`, `JEFF_API_KEYS` default `devkey`, model at `data/jeff/models/gliformer-large-v1`.

Use `systemctl restart|status kev kev-proxy jeff` and `tail` the logs. Torch is force-installed with the CUDA wheel (`TORCH_CUDA_TAG`, default `cu124`) into kev's venv — kev's own docs assume Mac/MPS or Modal, so anything MPS-specific there (e.g. `KEV_ATTN=sdpa`, `KEV_SHAPE_BUCKET`) doesn't apply on this CUDA box.

## Commands

**kev** (`cd /workspace/kev`)
- Unit tests (no weights): `uv run --extra serve python -m pytest tests/test_unit.py tests/test_research.py -q`
- Single test: `uv run --extra serve python -m pytest tests/test_unit.py::test_name -q`
- API tests need a running server: `KEV_BASE_URL=http://127.0.0.1:8009 uv run --extra serve python -m pytest tests/test_api.py -q`
- Serve: `uv run --extra serve python -m kev.serve --run runs/kev --port 8008`
- Smoke train: `uv run python -m kev.train --n_per_source 40 --accum 4 --out runs/smoke`; eval: `uv run python -m kev.evaluate --run runs/kev --n_per_source 150`
- Anything beyond smoke is meant to run on Modal (`modal_app.py`, `uv run modal run modal_app.py::{smoke,study,evaluate}`). Only one training process at a time.

**jeff** (`cd /workspace/jeff`)
- `uv sync --extra dev`; tests: `uv run pytest -q` (single: `uv run pytest tests/test_core.py::test_name`)
- Model-backed integration tests need `models/gliformer-base-v1` and skip if absent; `tests/test_sdk_live.py` spins up a live server with a fake backend.
- Lint/typecheck: `uv run ruff check .` (line length 120), `uv run ty check`
- Run: `JEFF_API_KEYS=devkey uv run jeff`; all config is `JEFF_*` env vars (see `jeff/README.md` and `src/jeff/server/config.py`).

**jevbench** (`cd /workspace/jevbench`)
- Tests: `python -m unittest discover -s tests -v` (single: `python -m unittest tests.test_protocol.ClassName.test_name`)
- Run a benchmark: `python -m jevbench.cli run --tasks datasets/public/original.jsonl --adapter typesafe --endpoint http://127.0.0.1:8000 --key-env '' --model jev-latest --results RUN/results.jsonl --raw-dir RUN/raw --ledger RUN/ledger.jsonl ...`, then `python -m jevbench.cli summarize ...`. See its README "Reproduce".
- To benchmark the local servers use the `typesafe` adapter against `:8000` (jeff) or `:8009` (kev via proxy).

## Demo

`demo/server.py` (stdlib only) serves a seven-page console at `http://127.0.0.1:8100`: Leaderboard (`/`), Baseline compare (`/compare`, one question to every model), Scenario lab (`/scenarios`, accuracy and confidence on published labelled sets), Text windows (`/windows`, detector batteries over speeches, conversations and pasted text), Call monitor (`/stream`, replays a real transcript word by word through about a dozen perspectives with a chosen trailing window), How they work (`/models`) and Report (`/report`). Start with `set -a; . ./.env; set +a; python3 demo/server.py`; without `TYPESAFE_API_KEY` the hosted column reports an error. The key is used server-side only, and the server binds to `127.0.0.1` unless `DEMO_HOST` is set.

- Pages share `demo/static/app.css` (design tokens, components) and `demo/static/app.js` (`window.Jev` helpers, injected nav). Use those rather than page-local styles. Pages build DOM with `Jev.el` and `textContent`; never `innerHTML` with data.
- `demo/models.json` is the fact sheet for each model (mechanism, size, licence, how it was served). Unknown fields are `null`; don't add claims that aren't in a model's own repo or card.
- APIs: `/api/leaderboard` (from `data/bench/*/summary.json`), `/api/models`, `/api/status`, `/api/probes` and `/api/probe?set=` (published probe sets plus every model's per-item results from `data/probe-runs-v2/`), `/api/speeches`, `/api/scenes` (real cited scenes), `/api/dialogues` (200 real MentalManip dialogues with turns), `/api/window-study`, `POST /api/compare` (one question, every backend) and `POST /api/batch` (many states each with a question battery to one backend; cached, capped at 400 items because the hosted backend costs money). Only models served over HTTP can answer live: jeff :8000, kev-0.5b :8009, kev-0.8b :8011, kev-4b :8010, hosted Jev. SemIf, open-alternative-jev, Laya and Verdict run in-process and appear in stored results only.

## Probe sets

`probes/v2/` holds probe sets built from published datasets, not written by us: NIST Juliet (memory-safety C), OWASP Benchmark (web security), MentalManip (manipulation in dialogue), LOGIC (fallacies), SNLI, iSarcasmEval and news-headline sarcasm, a phishing corpus, ContractNLI (checklist over contracts), dark patterns (Mathur et al.), plus ASVS and CWE Top 25 question libraries and three public-domain speeches. Each set has a `build_*.py` (seeded, reproducible from raw files under `data/sources/`, which is git-ignored) and a `.md` with source, licence and label caveats. Note the licences before redistributing: MentalManip is CC BY-NC, OWASP Benchmark GPL-2.0, the dark-patterns repo GPL-3.0, LOGIC has no declared licence.

`probes/v2/scenes/` holds four real public-domain scenes (Apollo 13 control, Challenger testimony, Colgan 3407 cockpit recorder, Nixon-Haldeman 23 June 1972), each with documented events backed by a fetched quote; `build_scenes.py` reproduces them. `probes/window_study.py` measures which trailing window (last N words, sentences or turns) best flags manipulation over the 200 labelled dialogues in `manipulation_windows.json`; run it through the demo server and never restart the server while it runs. Perspective validation sets: emotion_fear, emotion_anger, politeness_deference, threat_civil (noisy), persuasion_appeals.

`probes/build.py` and `probes/*.jsonl` are the earlier hand-written sets (single author, 18 items each). They were far easier than the published sets and should not be used to judge models. `probes/report_v2.py` summarises published-set runs (accuracy with Wilson intervals, calibration, selective accuracy).

Run probes with `TASKS_DIR=/workspace/probes/v2 BENCH_OUT=/workspace/data/probe-runs-v2 demo/bench.sh <sets>` (HTTP models, `MODELS=...` to pick) and the same env with `demo/bench-batch.sh` (in-process models, `TIERS="..."`). Keep probe runs out of `data/bench/`, since the leaderboard averages everything in it. Check `results.jsonl` for failed items after a run: a model server that is still starting produces silent 0% results.

Benchmarking: `dev-bench-setup.sh` installs each in-process model in its own venv under `models/` (gitignored). `demo/bench.sh` runs the HTTP-served models and `demo/bench-batch.sh` runs `laya verdict semif so1` one at a time; both write `data/bench/<model>-<tier>/` and skip runs that exist. Run one model on the GPU at a time: running several together caused CUDA out-of-memory failures on the hard tier. `semif_direct` needs a pinned commit `--revision` (handled in `bench-batch.sh`).

## Architecture (the parts that span files)

**kev** — `kev/model.py` runs a causal LM prefill-only with a block-causal mask (shared state prefix, isolated question branches) and a pointer head over option-boundary tokens; no generation. `kev/api.py` converts TypeSafe Noul/Choice/Score requests into pointer options, and training data goes through the same `api.to_record()` path so train and serve text are identical. Qwen3.5 backbones are hybrid (Gated DeltaNet) and cannot use the packed block-causal mask; `DecisionModel.hybrid` routes them through per-question rows. Frozen eval suites live in `evals/<version>/` with sha256-pinned manifests — never modify a frozen file; new data means a new version. Changing the serving path must keep the parity tests in `tests/test_v3.py` passing.

**jeff** — `src/jeff/core/` is backend-agnostic (schemas, state rendering, question grouping/isolation, answer construction, `engine.py`); `backends/` holds the torch and ONNX GLiFormer implementations behind the `core/backend.py` interface; `server/` is FastAPI plus a micro-batcher (`batcher.py`) with queue/rate limits (HTTP 529/429). Noul questions get isolated encoder passes; choice/score share one pass unless `JEFF_ISOLATE=all`.

**jevbench** — `jevbench/tasks.py` defines the single canonical task record (validated so the answer can't leak into the state; datasets hashed order-independently and frozen in `datasets/manifest.json`). `adapters/` map each system to a `DecisionResult` (probability map over the exact label set) with no retries or fallbacks. `budget.py` is a file-locked reserve/settle ledger shared across all runs; `runner.py` is serial and stops on 401/403/429 without scoring unattempted items as wrong; `summarize.py`/`composite_v12.py` recompute every published number from per-item records. Results and raw dirs must live **outside** the repo (the runner refuses otherwise). Read `jevbench/IMPLEMENTATION.md` for the invariants before changing scoring or adapters.
