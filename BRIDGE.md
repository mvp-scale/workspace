# BRIDGE: where we are, for the next session

Updated 2026-09-22. Read `CLAUDE.md` too (commands, architecture, gotchas); this file is the narrative and the next task. `START.md` has the run and measure commands.

## Starter prompt for the next session (paste this)

```
Read /workspace/BRIDGE.md and /workspace/foundry/README.md first. Then verify the state before touching anything:
`demo/lineup.sh status`, `git status`, and confirm the loaded local models (kev-4b, semif, so1, laya, verdict) are up
-- foundry's live calls depend on them. Report in a few lines what's loaded and whether the tree is clean.

The active thread is /workspace/foundry -- a live, tool-driven idea-decomposition pipeline. Read foundry/README.md's
"the one rule that matters most" before doing anything else: you author exactly two things, an idea and an ideal
customer/user, nothing else -- every piece of an actual decomposition has to come from the tools running live, never
from you writing plausible content and slotting it in as if the tools produced it. This was violated repeatedly in the
session that built this before being understood properly; don't repeat it.

Open, unresolved question to resolve first (see foundry/README.md's "oncall-rotation" section): a recursive Grinder
walk on the oncall-rotation idea's single-point-of-failure branch left 7 of 8 leaf checks stuck at "needs further
splitting, no deeper library" under the current 0.6 atomic threshold. Look at those 7 stuck requirement texts and
judge: do they already read as good, actionable atomic requirements (threshold's too strict), or do they genuinely
need a Level 3 built under them? Ask the user before building more library content either way.

The Scenario lab task (demo/scenarios.html, see docs/scenario-lab-plan.md) is still queued but paused this session --
don't pick it up unless asked.

Working pattern: once the end state for a piece of work is clear and agreed, run it yourself and report when it's
ready -- don't hand over commands that have no real decision point left in them. While something is still being
decided (a threshold, a library's shape, whether an approach is right), let the user run it themselves if they want
to see it directly, rather than running ahead of them.

Constraints: no spending on the hosted model (JEV113/P0) from any script, ever -- the environment's permission
classifier blocks it outright, not just convention. Never restart demo/server.py while an experiment runs through it.
Timeout on every wait and check `ps` afterwards. Commit locally with the Co-Authored-By trailer (there is no remote).
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

Text windows and Call monitor pages removed; Cockpit renamed to Conversation flow (`/flow`). Remaining candidates: `demo/mockups/` (superseded by `/flow`; committed, recoverable), per-page `<style>` blocks (flow.html 165 lines, scenarios ~120) that belong in `app.css`, `/api/results` in `server.py` unused, `index.html` still lists retired `jeff`, `kev-0.5b`, `kev-0.8b`, `/api/speeches` and `/api/window-study` now unused now that Text windows is gone (still read by `/flow`, check before removing). Ask before deleting.

## Done recently

Conversation flow (`/flow`, was Cockpit) built and wired to the local models (measured on unseen dialogues: KEV4B check lag p50 65 to 123 ms, keeps up at 30x; SEMIF4 p50 about 265 ms, keeps up to 4x). Scenario lab: set list names only, numberless 7-step heat map. Research: `research/classifier-dev-notes.md` (classifier.dev is a wrapper around Jev, Laya and Kev on Beam; no model of its own).

**2026-09-21/22 session:** Removed Text windows (`/windows`) and Call monitor (`/stream`); Cockpit renamed to Conversation flow (`/flow`). Built the first structure, **batch performance** (`probes/lab_batch.py`, `/api/batch-perf`, a "Batch performance" entry in the lab under a new Structures rail section): one state, N filler questions added to the one labelled question (sizes 1-160), scored on the labelled question only, resumable, one model at a time with the full GPU, never touches `data/bench/`. On 40 manipulation-dialogue items: KEV4B, SEMIF4, OAJEV4 and VERD2H hold flat accuracy from 1 to 160 questions/state (latency scales roughly linearly with size); LAYA4H's latency *drops* sharply at 160 questions, consistent with its 512-token limit truncating most of the added filler questions rather than processing them (worth a real check, not just an inference). Also restyled the lab's rail into Overview/Structures/Sets sections with icons, a divider, and a stronger current-item highlight; fixed the mobile dropdown, which was missing the Structures entry. Gotcha confirmed the hard way: the `demo/lineup.sh`-installed inproc services (`semif`, `so1`, `laya`, `verdict`) have `ExecStartPre` wait on kev-4b being up on :8010 — if kev-4b is stopped, those services hang "activating" forever with the GPU idle; run them directly (`.venv/bin/python demo/serve_inproc.py --model <m> --port <port>`) when kev-4b isn't loaded.

**2026-09-22 session (separate thread, Scenario lab untouched): built `/workspace/foundry`,** a live idea-decomposition pipeline, from scratch. Started as a CLI prototype exploring a factory-themed tool vocabulary (Slicer/Grinder/Sorter/Conveyor/Spotlight, capped at 5 tools x 5 variants by explicit request), but the real work of the session was methodological: repeatedly writing hand-authored decomposition content and having it correctly called out as invalid — first for authoring an idea and its pieces together in one pass (proves nothing about decomposition quality), then for authoring "neutral" pieces that still embedded a specific solution design instead of a real decomposition. The fix that actually works: a fixed, generic, reusable candidate library (`tools/gap-library.yaml`, 12 categories, plus a nested per-category library for deeper levels) that gets *selected from live*, per idea, via real noul calls to the loaded models — Claude authors the library once (generic, front-loaded, fine) and the two-question intake per idea (idea + customer, also fine), nothing else. `slicer_live.py` (Level 0 selection) and `grinder_live.py` (recursive, budget-capped, breadcrumb-accumulating) both work end to end on a real worked example (`oncall-rotation`). Full state, the one hard rule, and the open unresolved question (is the current atomic threshold too strict, or does the tree need another level) are in `foundry/README.md` — read that before touching foundry again. All 5 of the original hand-authored example problems were moved from `foundry/problems/` to `foundry/ideas/` (stripped of their invalid pieces) during end-of-session cleanup; only `oncall-rotation` is a validated, live-produced decomposition.

## Gotchas learned the hard way

- **Never restart `demo/server.py` while an experiment runs through it** (`probes/window_study.py` dies; results are cached in server memory only).
- After starting/restarting a model server, **check `results.jsonl` for failed items**: a server still loading produces silent 0% runs.
- One heavy model at a time when benchmarking on the GPU; running several together caused CUDA OOM.
- Sub-agents can leave orphaned wait loops (`until grep ...; do sleep`); tell them to use `timeout` on every wait and check `ps` afterwards.
- The environment's permission classifier **blocks spending on the hosted backend from scripts**. Hosted runs are for the user to confirm in the UI (Play/Run twice); tests should use a loaded local model (SEMIF4, KEV4B).
- Do not run the Baseline compare "Run" in tests: it includes the hosted model.
- kev-4b's GPU memory grows as it warms (8.5 to 9.6 GiB); only ~1.7 GiB is spare, so do not load anything else.
- Playwright/Chromium used for visual checks lived in the previous session's scratchpad; reinstall in the new one (`python3 -m venv pw && pw/bin/pip install playwright && PLAYWRIGHT_BROWSERS_PATH=... pw/bin/playwright install --with-deps chromium`). There is no browser otherwise.
- **`foundry/`: never hand-author decomposition content, not even "neutral" pieces** — the fix is a generic, reusable candidate library selected live, not more careful writing by hand. See `foundry/README.md`'s "the one rule that matters most."
- **`foundry/`: a Bouncer/noul question's exact wording changes the answer distribution more than the model does.** "True today, without further verification" collapses almost every forward-looking claim toward 0 regardless of model; "a reasonable assumption to build on" doesn't. Always note which phrasing produced a given number before drawing a conclusion from it.
- **`foundry/`: model output tables must use the P0-P5 mapping, stated once, never a raw model code or name after that** — caught as a real bug (`render_table` reverted to codes after the legend), not just a style preference.

## Useful commands

```
demo/lineup.sh status                       # loaded lineup
curl -s localhost:8100/api/status           # live state, identity, GPU per model
python3 probes/report_v2.py                 # accuracy/calibration over published sets
python3 probes/window_study.py --backend kev-4b   # window study (server must stay up)
python3 demo/vram.py                        # measure GPU memory (stop servers first)
```
