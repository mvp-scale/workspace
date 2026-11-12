# Knowledge pipeline services

The one list of every knowledge-pipeline page and service. Keep it current: when a page is added, changed, merged or removed, change this file in the same turn. Most pages are mock-ups. Rule (owner, 2026-11-08): no new pages; extend a page listed here, or merge pages, and consolidate later.

Every URL in the workspace, with live status: `/workspace/SERVICES.md`.

Console: http://localhost:8100 (started by `./service.sh up` from /workspace). Pages live in `/workspace/demo/mockups/<name>/`. Builders live in `/workspace/knowledge_pipeline/projects/world-state/`.

## The pipeline view (canonical)

| Page | URL | What it shows |
|---|---|---|
| Ledger viewer, Engine tab | http://localhost:18766/#engine | The engine card: layers and fields (Macro / Pulse, Area, Understanding), their working, what changed, what is next. This is the structure the pipeline is built to. Update it with `node cp.mjs engine <task> --card <json>` (the card is the last engine record on the ledger; read usage with `node cp.mjs help`, never run `engine` bare). Last updated L1168. |
| Ledger viewer, other tabs | http://localhost:18766/ | Story, Live, Map, Work, Quality, Rules |
| Ledger viewer, Training tab | http://localhost:18766/#training | Every model's state (data, input, output, v1 or not), dev-score curve per epoch with the chosen epoch circled for each encoder run, sealed scores against the old sparse heads, entity extractor bake-off. Not from the ledger: built by `projects/world-state/build_training.py` into `training/training.json`. |

The mock-up pages under :8100 are working views; the Engine card is the record. Change the card first.

## Central place (owner, 2026-11-08)

The knowledge pipeline viewer (http://localhost:18766) is derived from the ledger, so it is where work is changed and recorded: tasks with steps (Work, Map and Story tabs), the engine card (Engine tab), and heartbeats for runs (Live tab). The improvement loop is recorded there as one task per stage of the journey: T43 pool (Teach), T44 labels (Teach), T45 train (Train), T46 score (Prove), T47 review (Learn). Notes alone do not move the Story, Live or Work tabs; steps, heartbeats and the engine card do.

## The two pages we monitor (owner, 2026-11-08)

1. Ledger viewer, Engine tab: the record. 2. Reading gates (:8100): the working view with the loop map and the lap. Both are kept current and checked at every loop tick with `python3 kit/live/monitor_pages.py` (OK, STALE or DOWN per page). Change the Engine card first, then rebuild the gates page (`python3 projects/world-state/gates_heads.py`).

## Main mock-up page (where "how good is it" is reported)

| Page | URL | What it shows | Built by | Data |
|---|---|---|---|---|
| Reading gates | http://localhost:8100/mockups/gates/index.html | Scoreboard: each field, its gate result, its source; the first-lap board (six steps, status, result, reason), four numbers per head and the improvement-loop rounds (added 2026-11-08). The page to extend with Tracks C and D and the formal stack | `scoreboard.py`, `gates_mockup_data.py`, `pulse_assemble.py` | `gates/data.json` |

## How it works

| Page | URL | What it shows | Built by | Data |
|---|---|---|---|---|
| The BitMob Solver | http://localhost:8100/mockups/solver/index.html | The whole chain, step by step, and the improvement loop (8 boxes, each marked built or not; a four-numbers-per-head table) | `solver_shape_page.py` | inline |
| How an article is read | http://localhost:8100/mockups/bitmobs/index.html | The BitMob map: tools and models per head | `bitmob_map_page.py` | inline |
| Pulse state | http://localhost:8100/mockups/state/index.html | Pulse fields and their state | `pulse_state_page.py` | inline |
| Decider demo | http://localhost:8100/mockups/decider/index.html | The Lean/Rust decider on test vectors | `decider_mockup_data.py` | `decider/data.json` |

## What we learned

| Page | URL | What it shows | Built by | Data |
|---|---|---|---|---|
| What we learned | http://localhost:8100/mockups/learned/index.html | Ten cards of foundation results, each number with its source | `learned_page_data.py` | `learned/data.json` |

## Working pages (one article at a time; candidates to merge into "What we learned")

| Page | URL | What it shows | Built by | Data |
|---|---|---|---|---|
| One article, four beats | http://localhost:8100/mockups/article-beats/ | Title, first sentence, first 250 words, full text, raw | `article_beats.py` | `data.json` |
| One article, four levels | http://localhost:8100/mockups/article-levels/ | Lettered groups across the four levels, plus the gist | `article_levels.py`, `gist.py` | `data.json`, `gist.json` |
| Techniques on one article | http://localhost:8100/mockups/article-techniques/ | Keyphrases, themes, coverage, NLI on 9 articles | `article_techniques.py` | `data.json` |
| Sentences to relations | http://localhost:8100/mockups/article-relations/ | Triples, chains, noise-word test | `spo_chains.py`, `relations_run.py` | `relations.json`, `judged.json` |
| Topic shape test | http://localhost:8100/mockups/clusters/ | Corpus clustering. Superseded by the one-article pages; kept, not extended | `topic_shape*.py` | `data.json`, `dims.json`, `walk.json` |

## Live status

| Page | URL | What it shows | Built by | Data |
|---|---|---|---|---|
| Trainer live | http://localhost:8100/mockups/trainer/index.html | Training and ledger status | `kit/live/poll_live.py` (poller) | `trainer/live.json`, `status.json`, `ledger.json` |

## Other services (ports from /workspace/CLAUDE.md)

| Service | Port | Note |
|---|---|---|
| CPU classifier (BitMob) | 8020 | local classifier |
| pulse_reader | 8023 | not the default; owner's yes needed |
| Ledger viewer | 18766 | `./service.sh start ledger-viewer` |
| Local Clef | 8018 | approved |

## Not knowledge pipeline

`/workspace/demo/mockups/` also holds the older cockpit and voice mock-ups (`1-live-captions.html` to `4-pipeline-lab.html`, `cockpit-variants`, `image-lab.html`, `vector-walkthrough*`, `state-depth.html`). They are not listed above.

## Consolidation plan (later)

1. Reading gates is the one report page. Foundation results, Tracks C and D, and the formal stack (playbook 15, `lean/BitMobFlow.lean`, `PulseDone.lean`, `FieldGate.lean`, `GistSelect.lean`, `SpanDates.lean`) go there as sourced rows.
2. How-it-works pages merge into one.
3. Working pages merge into the education page or are retired.

## Update expectations (2026-11-09)
Every row on the Live tab states how often it should report, and the page only calls a row "no update" when it passes that.
- Jobs set `every_s` in their heartbeat (poller, Kaggle rows, improvement-loop: 180 s). A row is stale after 2.5 times that, never under 10 min.
- Services (always-on processes, e.g. the pulse reader) set `service: true`: checked on each poll, not expected to finish.
- Idle or waiting rows (finished runs, tasks waiting on the owner) are never stale.
- Pages: `kit/live/monitor_pages.py` lists each page as rebuilt-on-results (solver, bitmobs, state, learned, gates) or frozen (article pages, clusters, decider, training curve). The Engine card is stale when an engine result (expert1 head, compare_v6b, learn_loop, field_table) is newer than the card, not after a count of notes.
- The poller runs `kit/live/tick.py` every 3 minutes: Training tab data, T68 Kaggle row, improvement-loop row.

## Health check (2026-11-09)
`kit/live/health.py` runs every poll (3 min, called from `tick.py`) and writes the heartbeat row `health`, shown as the first line on every ledger tab and at the top of `tools/hw.py`. Verdict: BROKEN (poller, ledger viewer, console, Clef or pulse reader not answering) > WORKING (a job is running and reporting on time) > WAITING (nothing running; names the Kaggle queue age and the owner-blocked tasks) > IDLE (nothing running and nothing waited on: start the next piece). Flags: a kernel queued over an hour, a running job past its promised update time, failed jobs in 24 h, disk under 50 GB, no ledger write for 30 min while nothing runs. History: `projects/world-state/runs/health_history.jsonl`. Tested on fake rows for all six paths. If the line itself is missing or marked OVERDUE, the poller or health.py is not running.
