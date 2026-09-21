# Call monitor mock-ups

Static, scripted mock-ups (no server needed): open `index.html`, or `python3 -m http.server -d demo/mockups 8110`.

- `1-live-captions.html` transcript with a tag margin (meeting)
- `2-call-cockpit.html` cue cards + captured facts + playbooks (sales / support)
- `3-intake-board.html` slots that fill as heard (911 / triage)
- `4-pipeline-lab.html` audio → STT → window → models, local vs hosted, window and cadence controls

Shared: `mock.js` (player + helpers), `mock.css`, `data.js` (invented scripts, labelled), `apollo.js` (real Apollo 13 transcript from `probes/v2/scenes/`, generated; tags on it are scripted).

Everything is MOCK: scores in page 4 are generated, lag figures are the earlier measured per-checkpoint times (JEV113 ~0.3 s, KEV4B ~1.1 s, SEMIF4 ~1.8 s). Not wired: microphone/audio, speech-to-text, real prompts to Jev, window optimisation. Rules kept: DOM via textContent only, no hosted calls, models shown by code.
