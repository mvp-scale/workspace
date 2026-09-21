# BRIDGE: where we are, for the next session

Written 2026-09-21 at the end of a long session. Read `CLAUDE.md` too (commands, architecture, gotchas); this file is the narrative and the next task.

## Git state (read this first)

- `/workspace` is a small git repo with **local commits only. There is no remote; nothing has been pushed to GitHub.** Latest: `61d229d`. `git log` is the history; the nested repos `kev/`, `jeff/`, `jevbench/` and `data/`, `models/`, `logs/`, `.env` are git-ignored.
- Before any push: `probes/v2/` contains licensed third-party data (OWASP Benchmark code is GPL-2.0, the dark-patterns repo GPL-3.0, MentalManip CC BY-NC, LOGIC has no declared licence). Each set's `.md` records its licence. Decide what may be published.
- Author identity is set globally to `corey <test@Test.com>`.

## What exists

A seven-page local console at `http://127.0.0.1:8100` (`set -a; . ./.env; set +a; python3 demo/server.py`, stdlib only) for typed decision models: a model gets a state plus typed questions (noul, choice, score) and returns a probability per option.

| Page | Purpose |
|---|---|
| `/` Leaderboard | public JevBench tiers, measured GPU memory, "what fits in the GPU" planner, answer agreement between models |
| `/compare` Baseline compare | one question to every loaded model, comparable results kept apart from model-specific extras |
| `/scenarios` Scenario lab | accuracy, pair accuracy, calibration and risk-coverage on 15 published labelled sets |
| `/windows` Text windows | detector batteries over a speech/pasted text at sentence, window and paragraph scale |
| `/stream` Call monitor | replays a real transcript word by word through ~12 perspectives (the next task, below) |
| `/models` How they work | explainer of the four techniques |
| `/report` Report | computed benchmark report |

Shared layer: `demo/static/app.css` (tokens, components), `demo/static/app.js` (`window.Jev`: `el`, `mount`, `tag`, `codeOf`, `modelSelect`, `ready`, status, and the "Models N/9" panel in the top bar). Pages build DOM with `Jev.el` and `textContent`, never `innerHTML` with data. Each page is one file.

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

## THE NEXT TASK: rework the Call monitor (`demo/stream.html`, ~100 KB)

The user's verdict: **it works, but it is not as fluid as it needs to be.** Re-examine the structure. Do not just tweak; find where the fluidity is lost. Ask the user for a concrete example of "not fluid" first (which moment feels wrong), then measure. My own observations, as hypotheses to verify, not conclusions:

1. **Scores arrive in bursts, text does not.** Words reveal continuously but checkpoints score only at sentence ends (Smart policy), so the heat rows and gauges step. In Live mode a checkpoint's result lands 0.3-1.8 s after its text, so cells appear late and jump.
2. **Measured latency per 9-question checkpoint** (Live): hosted Jev ~0.3 s; KEV4B ~1.1 s; SEMIF4 ~1.8 s; VERD2H ~9.4 s (CPU, serial). Sentence cadence is ~4-6 s so it keeps up, but VERD2H does not, and every-word cadence would not on most models.
3. **The in-process servers score questions serially under a lock** (`serve_inproc.py`: one forward pass per question, 9 passes per checkpoint). Ideas: share the state prefix across questions (KV cache), a small screening subset every checkpoint with the full battery only on a trigger (the "Adaptive screen" policy exists but is only a client-side plan), parallelism across models.
4. **Replay makes the user wait for a full precompute before Play.** Start playback once the first few checkpoints are ready and let the rest arrive.
5. **Transport:** the page polls in chunks via `POST /api/batch` and paints when a chunk returns. A streaming endpoint (SSE) that pushes each checkpoint's answers as they complete would let the stage paint per-question and per-model as results land, and make lag visible per model.
6. **Structure:** one 100 KB file mixing scheduling, transport, playback state, layout and cost accounting. Consider splitting scheduling/transport/rendering, an explicit state machine for playback, and a testable core (checkpoint scheduling and windowing are pure functions that mirror `probes/window_study.py`).
7. **No fluidity metric exists.** Define one before changing anything: time to first scored cell, result lag p50/p95 per model, playback frame rate/jank during a 200-word scene, and how long from Play click to first visible score. Measure with Playwright (record a trace) so the rework can be judged, not just eyeballed.
8. Other candidate improvements: interpolate/hold the last score with a "pending" state instead of empty cells; run 2-3 models in parallel and overlay them; adopt punctuation- or pause-driven checkpoints (real speech-to-text partials would need this); trailing-window default from the study (~20-40 words) is already offered.

Constraints: keep the honest framing (technique signals, not verdicts; models return probabilities, not reasons), the trust chips (each perspective's measured accuracy), the documented-events comparison, and the hosted-call confirmation.

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
python3 demo/vram.py                        # measure GPU memory (stops nothing: stop servers first)
```
