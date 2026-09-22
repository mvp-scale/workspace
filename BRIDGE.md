# BRIDGE: where we are, for the next session

Updated 2026-09-22. Read `CLAUDE.md` too (commands, architecture, gotchas); this file is the narrative and the next task. `START.md` has the run and measure commands.

## Starter prompt for the next session (paste this)

```
Read /workspace/BRIDGE.md, /workspace/CLAUDE.md and /workspace/docs/scenario-lab-plan.md first. Then verify the state
before touching anything: run `demo/lineup.sh status`, `curl -s localhost:8100/api/status` (start the demo server per
CLAUDE.md if it is down) and `git status`. Report in a few lines what is loaded and whether the tree is clean.

The task is to build out the Scenario lab (demo/scenarios.html) so that every loaded model can be run on every set and
every test structure, offline with the full GPU and live through the demo server. Do not start coding.
1. Read BRIDGE.md section "THE NEXT TASK" and the plan. Ask me which family and which structure to build first, and
   confirm the set groups and the per-set template.
2. Propose the run-record format and the offline runner (one model at a time, per-item records, resumable) and the live
   path, and show how the existing set page (model comparison, calibration chart, examples/item explorer) stays the
   template every new set follows. Wait for my go before implementing.

Constraints: no spending on the hosted model (JEV113) from scripts, only through a UI confirmation; never restart
demo/server.py while an experiment runs through it; timeout on every wait and check `ps` afterwards; show models only
through Jev.tag/Jev.codeOf; DOM through Jev.el/textContent; keep the honest framing (signals, not verdicts) and Wilson
intervals; commit locally with the Co-Authored-By trailer (there is no remote).
```

## Git state (read this first)

- `/workspace` is a small git repo with **local commits only. There is no remote; nothing has been pushed.** `git log` is the history. Tracked: `setup.sh`, `CLAUDE.md`, `BRIDGE.md`, `START.md`, `docs/`, `demo/`. The nested repos `kev/`, `jeff/`, `jevbench/` and `data/`, `models/`, `logs/`, `.env` are git-ignored. `research/` (a clone of mrmps/classifier-dev plus notes) is untracked on purpose.
- Before any push: `probes/v2/` contains licensed third-party data (OWASP Benchmark GPL-2.0, dark-patterns repo GPL-3.0, MentalManip CC BY-NC, LOGIC no declared licence). Each set's `.md` records its licence.
- Author identity is set globally to `corey <test@Test.com>`.

## What exists

A six-page local console at `http://127.0.0.1:8100` (`set -a; . ./.env; set +a; python3 demo/server.py`, stdlib only) for typed decision models: a model gets a state plus typed questions (noul, choice, score) and returns a probability per option.

| Page | Purpose |
|---|---|
| `/` Leaderboard | public JevBench tiers, measured GPU memory, planner, answer agreement |
| `/compare` Baseline compare | one question to every loaded model (its Run includes the hosted model: never run it in tests) |
| `/scenarios` Scenario lab | accuracy, pair accuracy, calibration and risk-coverage on 15 published labelled sets; **the next task** |
| `/flow` Conversation flow (was Cockpit) | the reworked call view: voices, detectors, coaching, cue cards, heat strip; described in CLAUDE.md. Detectors show only at or above the minimum threshold and fade without support |
| `/models` How they work | explainer of the techniques |
| `/report` Report | computed benchmark report |

Shared layer: `demo/static/app.css` (tokens), `demo/static/app.js` (`window.Jev`: `el`, `mount`, `tag`, `codeOf`, `modelSelect`, `ready`, status panel). Pages build DOM with `Jev.el` and `textContent`, never `innerHTML` with data. Each page is one file. Console cleanup candidates (redundant pages, per-page style blocks, a dead `/api/results`, retired ids in `index.html`) are listed in the last message of the 2026-09-22 session and in "Cleanup" below.

## Models and naming (important)

One registry: `demo/models.json`. Stable ids (leaderboard ids) map to six-character codes shown everywhere through `Jev.tag(id)` / `Jev.codeOf(id)`; never print a raw id. Codes: JEV113 (hosted Jev, id `jev`), SEMIF4 (`semif`), OAJEV4 (`so1`, open-alternative-jev), KEV4B, KEV8H, KEV5H, JEFF4H, LAYA4H, VERD2H. Rule: family letters + size, B = billions of parameters, H = hundreds of millions.

Loaded now (systemd, `demo/lineup.sh install|up|down|status`; kev-4b must start first, its load spike is ~17 GiB): KEV4B :8010 (bf16 through `demo/serve_kev.py`), SEMIF4 :8012, OAJEV4 :8013, LAYA4H :8014, VERD2H :8015 (CPU). About 30 of 31.8 GiB used. KEV8H, JEFF4H, KEV5H are **not loaded** (the old `kev`, `kev-proxy`, `jeff` services were disabled); their stored results remain. `/api/status` reports live state, real identity (asked of the running server) and GPU memory per process.

SEMIF4/OAJEV4/LAYA4H/VERD2H are served by `demo/serve_inproc.py`, a stdlib server wrapping the same jevbench adapters that produced their benchmark numbers (live vs stored answers matched exactly on the items checked).

## Findings worth remembering

- On **published** labelled data (`probes/v2/`, 15 sets, ~1,400 items) mean accuracy: Jev 76.5%, SemIf 67.5, kev-4b 66.8, open-alt-jev 64.8, Laya 58.4, kev-0.8b 56.9, jeff 51.5, kev-0.5b 50.6, Verdict 46.7. My earlier hand-written probes were far too easy (>90%); ignore them.
- SemIf is #2 on the public leaderboard but weak on memory-safety *pairs* (5% pair accuracy): it is not reading the code. Jev 66%.
- Jev's confidence is usable for routing (accepting >=0.9 gives ~91% accuracy on half the items); small models' confidence is not.
- kev serves fp32 by default (kev-4b 17 GiB). `KEV_DTYPE=bf16` gave the same accuracy on 372 items (97-100% identical answers) and, launched through `serve_kev.py`, needs 8.5 GiB loaded / 9.8 peak.
- Window study (200 real MentalManip dialogues, manipulation only, dialogue-level labels): last 5 words / 1 sentence are weakest (AUC ~0.60-0.64); ~20-40 words, 2 sentences or 2-3 turns are best (0.67-0.70); "everything so far" adds nothing. Results in `data/window-study/`.
- Cost: a 9-question checkpoint is ~1,450 input tokens on hosted Jev whether the window is 10 or 40 words (question text dominates); the levers are checkpoint count and question count. Tariff $0.042 per million input tokens.

## THE NEXT TASK: build out the Scenario lab

Full plan: `docs/scenario-lab-plan.md` (18 items, decisions needed at the end). Summary of what the user wants:

**Principle (user's words, paraphrased): every test the lab defines must be runnable on every loaded model.** Two run paths:
1. **Offline runner.** A script that goes through sets and structures one model at a time with the full GPU (stop the other services first with `demo/lineup.sh down`; running several together caused CUDA OOM on the hard tier), writes per-item records, is resumable and skips finished runs, and never touches `data/bench/` (the leaderboard averages it). Probe runs live in `data/probe-runs-v2/`; `demo/bench.sh` and `demo/bench-batch.sh` are the existing pattern. Check `results.jsonl` for failed items after every run: a server still loading gives silent 0%.
2. **Live path.** Some tests must run live in the page against loaded local models via `/api/batch` (cached, capped at 400 items, hosted model costs money, confirm in the UI). Batch-size, cascade and decompose-and-loop tests are the natural live ones.

**Keep as the template every set follows (user: "paramount to be consistent"):** the decomposition, the model comparison and model selection, the graphs and charts, the worked example of what actually happened, and the item explorer. Confirm with the user exactly which existing pieces they mean by "decomposition" (the per-set breakdown by pair/group, or the decompose-and-loop test in the plan). Existing set page sections: model comparison, "Does confidence mean anything?" calibration, examples. Do not redesign these; build new sets and structures so they drop into them.

**Hierarchy (proposed, agreed in outline):** Overview heat map (models x sets, numberless, 7-step scale, numbers in tooltips; already built) -> Families (Security, Conversation flow, Reasoning and looping, Subtext, Fraud, Documents, Emotion and persuasion) -> Set page (header with source/licence/caveats/n/classes/chance; results heat strip per model that expands to intervals; confidence; cost and baseline; item explorer). **Structures** (single decision, batch, cascade, funnel, decompose-and-loop, blind run) are tags on a set, not a second navigation tier (recommended; the user has not ruled).

**Structures, in the user's terms:** *batch performance* (not "batteries"): one state with 5, 10, 20, 40, 80, 160 questions; record latency per answer, accuracy, and where the context limit or question cap bites; local models first, hosted only after approval. *Funnel*: atomic questions rolled up into a Monte Carlo forecast with sensitivity (needs labelled outcomes; correlations between atoms must be handled or tested). *Decompose and loop*: score the whole, split into halves/sentences/turns, recurse into pieces above threshold; keep the whole-text score. *Cascade*: cheap model first, escalate below a confidence threshold. *Blind run*: fixed seed, sealed key file, n of 60-100, grades revealed afterwards. Every claim needs a baseline (generative LLM or single question) on the same items with intervals.

**New sets:** each is a seeded `probes/v2/build_*.py` from a published dataset -> `.jsonl` + `.md` (source, licence, label caveats). Candidates: Gretel PII, ABCD support escalation, ProsocialDialog, toxicity, negotiation, CUAD. Check outbound access to Hugging Face and GitHub first (never verified from this box).

**Open decisions for the user:** first family and structure; overview orientation (models across the top and sets down as rows, expandable); family names; structures as tags vs tier; whether the empty family header strip gets labels or is removed.

**Known ceilings:** demo server 400 items per batch; Beam-hosted models 32 questions per request; Laya state plus question within 512 tokens; KEV4B answers 1 to 8 questions in about 60 ms total while SEMIF4 costs about 60 ms per question (serial under a lock).

**Model lineup facts:** upstream has moved on (JevBench v1.3.0 changes scoring; SemIf/OpenJev added CPU, EXL3 and calibration; new systems Winnow-12B Q8, reflex 4B, Open-Jev 2B/9B, djev). Nothing was pulled. Decide before re-scoring.

## Cleanup (asked for: after the lab, remove redundancy)

Nothing removed yet. Candidates: `demo/mockups/` (superseded by the cockpit; committed, recoverable), per-page `<style>` blocks (cockpit 165 lines, scenarios 94, stream 93) that belong in `app.css`, three pages patching the old `jev (typesafe)` id separately, raw ids (`so1`, `verdict`) in `stream.html` text, `/api/results` in `server.py` unused, `index.html` still lists retired `jeff`, `kev-0.5b`, `kev-0.8b`. Ask before deleting.

## Done recently

Conversation flow (`/flow`, was Cockpit) built and wired to the local models (measured on unseen dialogues: KEV4B check lag p50 65 to 123 ms, keeps up at 30x; SEMIF4 p50 about 265 ms, keeps up to 4x). Scenario lab: set list names only, numberless 7-step heat map. Research: `research/classifier-dev-notes.md` (classifier.dev is a wrapper around Jev, Laya and Kev on Beam; no model of its own).

## Gotchas learned the hard way

- **Never restart `demo/server.py` while an experiment runs through it** (`probes/window_study.py` dies; results are cached in server memory only).
- After starting/restarting a model server, **check `results.jsonl` for failed items**: a server still loading produces silent 0% runs.
- One heavy model at a time when benchmarking on the GPU; running several together caused CUDA OOM.
- Sub-agents can leave orphaned wait loops (`until grep ...; do sleep`); tell them to use `timeout` on every wait and check `ps` afterwards.
- The environment's permission classifier **blocks spending on the hosted backend from scripts**. Hosted runs are for the user to confirm in the UI (Play/Run twice); tests should use a loaded local model (SEMIF4, KEV4B).
- Do not run the Baseline compare "Run" in tests: it includes the hosted model.
- kev-4b's GPU memory grows as it warms (8.5 to 9.6 GiB); only ~1.7 GiB is spare, so do not load anything else.
- Playwright/Chromium used for visual checks lived in the previous session's scratchpad; reinstall in the new one (`python3 -m venv pw && pw/bin/pip install playwright && PLAYWRIGHT_BROWSERS_PATH=... pw/bin/playwright install --with-deps chromium`). There is no browser otherwise.

## Useful commands

```
demo/lineup.sh status                       # loaded lineup
curl -s localhost:8100/api/status           # live state, identity, GPU per model
python3 probes/report_v2.py                 # accuracy/calibration over published sets
python3 probes/window_study.py --backend kev-4b   # window study (server must stay up)
python3 demo/vram.py                        # measure GPU memory (stop servers first)
```
