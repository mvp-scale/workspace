# CLAUDE.md

Index for Claude Code in `/workspace`. Full product notes: `docs/reference/2026-10-18 CLAUDE.md archive (full product notes).md`.

## Goal
Run the World engine on a CPU reader instead of Clef on the GPU.
- Engine: `probes/world-engine/` (service `world_service2.py`, :8112; page `/worldengine`). Reads each story with 328 yes/no questions to Clef (~6 s a story).
- Target: a CPU reader whose errors keep engine outputs inside the tolerance measured in Step 1 (`ledger show F-0020`).

## How work is done
- Method: `docs/research/2026-10-18 Fable method.md`. 12 steps, in order, as written.
- Record: the ledger, for the Fable-method work only (not a system-wide log). `ledger help`, `ledger board`, `ledger show <id>`, `ledger score`. Code `tools/ledger.mjs`, store `ledger/ledger.jsonl`. No Markdown trackers.
- Evidence: during the Fable-method work, no claim, verdict or agreement without evidence: a ledger item, a pinned file with its command, or an MM3 run id.
- Decision rule: act inside the current step's method or a recorded decision (`--authorised-by method:N|D-....`). MM3 flags and weak results are evidence: record and route them to their step. Close a step when its pass bar is met. Ask the user only for human raters, the engine change (step 5), hosted Jev with article text.
- Before each run: a prediction in the ledger. After: score it. No job runs unattended over 1 hour.
- MM3: verdicts on our own write-ups from local Clef and hosted Jev (Jev never sees article text). Splits are recorded, not resolved by picking one. See `AGENTS.md`.

## Layout
| Path | Contents |
|---|---|
| `probes/world-engine/` | Engine, `sensitivity.py` (Step 1), `step2_labels.py` (Step 2) |
| `newsreader/` | News queue service (:8140), `bitmob/` labelling and CPU-reader experiments |
| `data/` | Weights, labels, results (git-ignored). `data/newsreader/labels/`, `data/step1/`, `data/step2/` |
| `demo/` | Console (:8100) and its pages; model registry `demo/models.json` + `demo/backends.py` |
| `kev/`, `jeff/`, `jevbench/` | Separate git repos. Read `kev/AGENTS.md`, `jevbench/IMPLEMENTATION.md` before changing them |
| `voice/` | Voice server (:8200) |
| `tools/` | `ledger.mjs`, `service.py`, `check_models.py` |
| `docs/research/` | Fable method and supporting reports |

## Services
- `./service.sh up | reset | down`; `./service.sh start <name>` for on-demand services. Config `service.yaml`. Details `START.md`, `docs/service-architecture.md`.
- Ports: console 8100, Clef 8018, World engine 8112, news queue 8140, CPU classifier 8020, voice 8200.
- Python for the engine: `/workspace/kev/.venv/bin/python` with `WE_RULES=rules_v2`. CPU only: `WORLD_GPU=0`.

## Rules
- Do not start GPU models or legacy models (Winnow) without the user's yes. Local Clef is approved.
- Models come from the registry by name. No model ids or addresses in code or pages (`python3 tools/check_models.py`).
- Pages: `Jev.el` and `textContent`, never `innerHTML` with data. Shared styles `demo/static/app.css`, helpers `demo/static/app.js`.
- Hosted models cost money: no hosted calls in tests or checks without asking.
- Probe runs go to `data/probe-runs-v2/`, never `data/bench/`.
- Kill processes by verified PID.
- Commit only when the user asks.
