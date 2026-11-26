# Workspace URLs

Every URL we use. Knowledge-pipeline rows checked from this machine at 2026-11-24 13:00 (the other rows at 2026-11-10 15:17). `up`/200 = answered, `down` = not running (on-demand or stopped). Nothing here was started to check it.
Start and stop: `./service.sh up | reset | down`, `./service.sh start <name>`. Knowledge-pipeline page detail (what each shows, what builds it): `knowledge_pipeline/services.md`. Ports and rules: `CLAUDE.md`.

## Knowledge pipeline: pages in current use (2026-11-24, playbook 00.1 rounds E/A/D done, B/C/V running)

Most recently changed first. Plan: `knowledge_pipeline/playbook/00.1-knowledge-enhancement-v1.md`. Record: ledger L3010-L3016.

| URL | What | File (last changed) | Status |
|---|---|---|---|
| http://localhost:8100/mockups/knowledge-raw/index.html | Knowledge pipeline page: Status, Knowledge, Concepts, Developments views; staged areas c1, mix, u1 (u1 added by round A). Reads the bench through the console at `/sim-api/` | `demo/mockups/knowledge-raw/index.html` (2026-11-24 12:49; round V is editing it now) | 200 |
| http://localhost:8100/mockups/knowledge-raw/executive-brief.html | Morning Brief mock-up (consume design D1, L3003) | `demo/mockups/knowledge-raw/executive-brief.html` (2026-11-23 23:08) | 200 |
| http://localhost:8100/mockups/knowledge-raw/brief-mockup.html | Knowledge Ladder mock-up | `demo/mockups/knowledge-raw/brief-mockup.html` (2026-11-23 09:21) | 200 |
| http://localhost:18770/ | Simulation bench (owner's task; started by hand, not by service.sh): one article or a stream through the chain; serves the `/api/raw/*` feeds the knowledge-raw page reads. It loads pipeline code at start, so round E/A/D code changes reach it only after a restart. Restart: `/workspace/models/embed-zs/.venv/bin/python /workspace/knowledge_pipeline/simulation/server.py` | `knowledge_pipeline/simulation/index.html` (2026-11-20 12:19) | 200 |
| http://localhost:8100/mockups/structure-live/index.html | Structure pack, live (temporary, T158); also holds the staged area stores `area-c1`, `area-mix`, `area-u1` | `demo/mockups/structure-live/index.html` (2026-11-20 08:10) | 200 |
| http://localhost:8100/mockups/target-state/index.html | Target state per element | `demo/mockups/target-state/index.html` (2026-11-18 15:57) | 200 |
| http://localhost:18771/ | TEMPORARY: a second bench started by `check-raw-complete.py` for round V (page on :18772 while the check runs); stops when the check ends. Never the owner's :18770 | none | 200 (while round V runs) |
| https://claude.ai/artifact/SnzE3t8XAREphM9z3VCeet | Reader-first briefing method (published page, L3004) | `knowledge_pipeline/playbook/design/reader-first-briefing-method.md` | not checked |

## Ledger viewer (knowledge pipeline record, port 18766, `./service.sh start ledger-viewer`)

| URL | What | Status |
|---|---|---|
| http://localhost:18766/ | Home (Story, Live, Map, Work, Quality, Rules tabs) | 200 |
| http://localhost:18766/#engine | Engine tab: the engine card, the record | 200 |
| http://localhost:18766/#training | Training tab: every model's trust grid, curves, live jobs | 200 |
| http://localhost:18766/data | Raw ledger data (JSON; the page and health check read it) | 200 |

## Console (port 8100, `./service.sh up`): pages

| URL | What | Status |
|---|---|---|
| http://localhost:8100/ | Console home | 200 |
| http://localhost:8100/worldengine | World Engine | 200 |
| http://localhost:8100/worldengine-how | How the World Engine works | 200 |
| http://localhost:8100/flow | Flow | 200 |
| http://localhost:8100/flow-classic | Flow, classic | 200 |
| http://localhost:8100/flow-lab | Flow lab | 200 |
| http://localhost:8100/compare | Compare models | 200 |
| http://localhost:8100/scenarios | Scenarios | 200 |
| http://localhost:8100/models | Model registry | 200 |
| http://localhost:8100/report | Report | 200 |
| http://localhost:8100/latent | Latent | 200 |
| http://localhost:8100/handcheck | Hand check | 200 |
| http://localhost:8100/imagelab | Image lab | 200 |
| http://localhost:8100/personalab | Persona lab (moves to /worldengine) | 200 |

## Console: knowledge-pipeline mock-ups (`/mockups/<name>/`)

| URL | What | Status |
|---|---|---|
| http://localhost:8100/mockups/gates/index.html | Reading gates: scoreboard, loop map, four numbers per head (the working view) | 200 |
| http://localhost:8100/mockups/solver/index.html | BitMob Solver: the chain step by step | 200 |
| http://localhost:8100/mockups/bitmobs/index.html | How an article is read: tools and models per head | 200 |
| http://localhost:8100/mockups/state/index.html | Pulse state | 200 |
| http://localhost:8100/mockups/learned/index.html | What we learned | 200 |
| http://localhost:8100/mockups/decider/index.html | Decider demo (Lean/Rust decider) | 200 |
| http://localhost:8100/mockups/trainer/index.html | Trainer live status | 200 |
| http://localhost:8100/mockups/training-curve/ | Training curve | 200 |
| http://localhost:8100/mockups/article-beats/ | One article, four beats | 200 |
| http://localhost:8100/mockups/article-levels/ | One article, four levels | 200 |
| http://localhost:8100/mockups/article-techniques/ | Techniques on one article | 200 |
| http://localhost:8100/mockups/article-relations/ | Sentences to relations | 200 |
| http://localhost:8100/mockups/clusters/ | Topic shape test (superseded) | 200 |
| http://localhost:8100/mockups/index.html | Older mock-up index | 200 |

## Services behind the console (ports; internal, not pages)

| URL | What | Status |
|---|---|---|
| http://localhost:8018/health | Local Clef Flash Q4 (approved; MM3 local reviewer, labelling) | 200 |
| http://localhost:8112/live?since=0 | World Engine service | 200 |
| http://localhost:8020/health | BitMob CPU classifier | 200 |
| http://localhost:8023/health | BitMob Domain / pulse reader (v6b-student); not the default, network exposure needs a yes | 200 |
| http://localhost:8021/health | BitMob reader for the World engine (on demand) | down |
| http://localhost:8140/health | News reader queue (on demand) | down |
| http://localhost:8200/api/status | Voice server (reached through the console at /voice/ws) | 200 |
| http://localhost:8091/health | Winnow-12B, GPU; legacy, needs a yes | down |
| http://localhost:8010/v1/models | kev-4b, GPU | down |
| http://localhost:8017/healthz | Clef Flash bf16, GPU, runs alone | down |
| http://localhost:8038/healthz | Clef Flash NVFP4, GPU | down |
| http://localhost:8019/health | Clef Flash Q2_K, GPU | down |

## External

| URL | What | Status |
|---|---|---|
| https://api.typesafe.ai | Hosted Jev API (code and questions only for reviews; costs money; needs a yes) | not checked |
| https://www.kaggle.com/code/coreygorman/kp-t67-ner-bakeoff | Kaggle kernel kp-t67-ner-bakeoff (queued) | not checked |
