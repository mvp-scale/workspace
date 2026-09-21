# Call monitor mock-ups (v2)

Static, scripted mock-ups; no server needed. Open `index.html`, or `python3 -m http.server -d demo/mockups 8110`.
Read `SPEC.md` first: principles, definitions and the measurable outcomes the rework is judged on.

- `1-live-captions.html` captions + tag margin, signals, moments, 60 s chart (meeting)
- `2-call-cockpit.html` waveform, chat, signal strip, cue cards, captured sheet (sales / support)
- `3-intake-board.html` slot cards that fill as heard, attention level (911 / triage)
- `4-pipeline-lab.html` audio → text → window → models, window/cadence controls, raw model answers vs held signal

Shared: `mock.js` (Session clock, Signals, Moments, Stack, Glide, Chart, Transcript, WatchEditor), `mock.css` (tokens, both themes; categorical palette validated with the dataviz validator), `data.js` (invented scripts, labelled), `apollo.js` (real Apollo 13 transcript from `probes/v2/scenes/`; its tags are scripted).

## How it stays fluid

One rAF loop and one call clock. Words are revealed from timestamps. Levels ease with exponential smoothing. The transcript and card stacks move by `transform` only (no scrollTop, no reflow of neighbours); the chart is a canvas whose x axis is call time. Space for new items (watch chips, cards, slots) is reserved up front.

## Measure it

`tools/measure.py page.html [seconds] [speed] [screenshot-prefix]` (needs playwright + chromium; set `PLAYWRIGHT_BROWSERS_PATH`) prints frame pacing, layout shift, glide jump, first-word time, flag dwell, a mid-run "add a watch item" test, overflow at 400 px, and non-font network requests.

## Not wired

Microphone/audio, speech-to-text, real prompts to Jev, window tuning per scenario, saved playbooks. Custom watch items fire on keyword overlap (mock heuristic). Rules kept: DOM via textContent only, no hosted calls, models shown by code (SEMIF4, KEV4B, JEV113).
