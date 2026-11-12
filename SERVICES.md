# Workspace URLs

Every URL we use, checked from this machine at 2026-11-10 15:17. `up` = answered, `down` = not running (on-demand or stopped). Nothing here was started to check it.
Start and stop: `./service.sh up | reset | down`, `./service.sh start <name>`. Knowledge-pipeline page detail (what each shows, what builds it): `knowledge_pipeline/services.md`. Ports and rules: `CLAUDE.md`.


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
