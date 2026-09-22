# START

Everything to bring the demo back up and look at the output. Run from `/workspace`. Deeper context: `CLAUDE.md` (commands, architecture), `BRIDGE.md` (history).

## 1. Check what is running

```
demo/lineup.sh status                                   # 5 local models: kev-4b :8010, semif :8012, so1 :8013, laya :8014, verdict :8015
curl -s -o /dev/null -w "%{http_code}\n" localhost:8100/   # demo server, expect 200
curl -s localhost:8100/api/status                       # live state, real identity, GPU memory per model
git status --short; git log --oneline -3                # local repo only, no remote
```

## 2. Start things

| What | Command |
|---|---|
| Models (kev-4b must go first: ~17.8 GiB while loading) | `demo/lineup.sh up` (also `down`, `install`) |
| Demo server (real console) | `set -a; . ./.env; set +a; python3 demo/server.py` then open http://127.0.0.1:8100 |
| Mock-ups (static, no server needed) | `python3 -m http.server -d demo/mockups 8110` then open http://127.0.0.1:8110 or open `demo/mockups/index.html` |

Model logs: `tail -f logs/kev-4b.log` (also `semif`, `so1`, `laya`, `verdict`). Restart a model: `systemctl restart kev-4b`.

**Do not**: restart `demo/server.py` while an experiment runs through it (its cache lives in memory); run the Baseline compare "Run" or any script that calls the hosted model (`jev`) without asking; leave wait loops without a `timeout`.

## 3. Where the output is

| Page | URL / file |
|---|---|
| Console: Leaderboard, Compare, Scenarios, **Conversation flow (formerly Call cockpit)**, How they work, Report | http://127.0.0.1:8100 `/`, `/compare`, `/scenarios`, `/flow`, `/models`, `/report` |
| Mock-ups index (4 pages, spec in `SPEC.md`) | `demo/mockups/index.html` |
| Call cockpit variations A, B, C (spec in `cockpit-variants/SPEC.md`). **C was chosen**; it is now built as `/flow` | `demo/mockups/cockpit-variants/index.html`, `c-coach-chips.html` |

Mock-ups are scripted: no audio, no speech to text, no model calls. Press Play (or space). Only Apollo 13 is a real transcript.

## 4. Measure and screenshot the mock-ups

Needs Playwright + Chromium (no browser otherwise). The earlier install lived in a session scratchpad under `/tmp` and may be gone; reinstall:

```
python3 -m venv /tmp/pw && /tmp/pw/bin/pip install playwright
PLAYWRIGHT_BROWSERS_PATH=/tmp/pwb /tmp/pw/bin/playwright install --with-deps chromium
```

Then, per page (prints one JSON line: frame pacing, layout shift, glide step, first word, flag dwell, add-a-watch test, overflow at 400 px, network requests; optional screenshot prefix):

```
PLAYWRIGHT_BROWSERS_PATH=/tmp/pwb /tmp/pw/bin/python demo/mockups/tools/measure.py cockpit-variants/a-lanes-tabs.html 45 2 /tmp/shot
# args: page, seconds, speed (1/2/4), screenshot prefix. VIEW=1920x1080 sets the viewport (default 1440x900)
```

Put a `timeout` on each run and check `ps aux | grep -E "measure.py|chrome-headless"` afterwards.

## 5. Other useful commands

```
python3 probes/report_v2.py                                   # accuracy over the published probe sets
python3 probes/window_study.py --backend kev-4b               # window study (keep the demo server up)
TASKS_DIR=/workspace/probes/v2 BENCH_OUT=/workspace/data/probe-runs-v2 demo/bench.sh <sets>   # probe runs (HTTP models)
python3 demo/vram.py                                          # measure GPU memory (stop servers first)
```

## 6. Where things stand

- **`/flow` (Conversation flow) is built and running** (`demo/flow.html`): detector bar (colour + icon each, up to 20, add your own), person cards showing each person's hits, per-person windows, coaching for the person you pick, cue cards for everyone else, heat-strip history, and a Captured card with tabs (Flagged, Detectors, Settings, Request, Events). Detectors show, flag and chart only at or above the minimum threshold; a detector fades 8 s after its last supporting evidence from that voice; a new different cue from a voice shifts that voice's older cue cards out. Flagged rows match cue cards (icon, cue, voice, %, time) plus the sentence. Not yet in: scrubber and step, a facts extractor, live speech-to-text (the source is an interface: words with speaker and time), narrowed phrase highlights (highlights mark the whole scored sentence).

- The Call monitor and Text windows pages were removed (Conversation flow replaces them). Mock-ups and specs are committed locally.
- Open decisions: narrowed phrase highlights vs whole sentence, a facts extractor, a scrubber and step. Standoff-state idea for spans: `docs/typesafe_standoff_pattern.md` (awareness only, not adopted).
- Measured on unseen dialogues, 8 signals, KEV4B: check lag p50 65 to 123 ms, p95 up to 254 ms, keeps up at every speed including Max (30x). SEMIF4: p50 about 265 ms, keeps up to 4x, falls behind at Max (queue 22, p95 2.0 s). Single runs. The lag figures in the mock-ups (KEV4B 1.1 s, SEMIF4 1.8 s) are older and higher.
