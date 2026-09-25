# Plan: live audio in Conversation flow, proven first in an isolated mock-up

Status: plan v2, not started (decisions confirmed by the owner 2026-09-25). Read `CLAUDE.md`, then
`BRIDGE.md` ("Voice pipeline"), then this file. Source of truth for the voice models is
`voice/reference/` (NVIDIA's guide and model cards).

## Decisions

1. **Two modes, not three.**
   - **Replay**: a saved conversation (real scene, library dialogue, pasted text). Words already
     exist, answers are precomputed, instant and free. Today's "Live" (scripted words at speaking pace,
     real model calls) was never truly live; it becomes an option inside Replay ("use saved answers" /
     "run the models fresh"), not a mode.
   - **Live**: real audio, transcribed by the NeMo pipeline as it plays. Sources: microphone / call
     audio, an **uploaded audio file**, or a **YouTube link**. A file or link is just another source.
2. **Mock-up first.** Build an isolated page, prove the behaviour with real audio, then refactor
   `demo/flow.html` using what was learned. `flow.html` is not touched in the mock-up phase.
3. **Detectors can be added while it is running**, and they run on hosted (paid) Jev correctly.
4. No share link for Live (there is no fixed script to link to). Keep the Request view. Add
   **Save as recording** later (a live session becomes a replayable scene).

## The mock-up: `demo/flow-lab.html`

Served by `demo/server.py` at `/flow-lab` (add to `PAGES`, do NOT add to the nav, not in the static
build). Same origin as `/api/batch` and `/api/status`; the audio/words come from the voice server's
WebSocket on `:8200` directly. A recon instrument, deliberately disposable: it carries its own small
copy of the checkpoint runner (per-person window, cadence) so the constants are proven before they
are ported into the real flow page.

What is on the page:
- **Source picker**: YouTube link (primary), audio file, microphone/call. Start / Stop. Pace for
  files and recorded videos: real time or as fast as it processes (about 17x); a live stream is
  real time by nature.
- **Thread** with V1..V8 chips as voices appear, committed words in normal weight and the
  not-yet-settled tail in italic; speaker cards showing who is speaking now.
- **Detectors**: a few library ones on by default plus **Add detector** (name, what it should
  detect, example) at any moment. Level bars per person, flags, the exact request in a Request tab.
- **Counters**: audio time vs wall time (lag), checks in flight, rewrites of already-committed words,
  speaker flips, checks made, estimated hosted spend.

## Audio ingest (server side, in `voice/server.py`)

Why server side: the box has ffmpeg, the browser needs no audio routing, it works for live
streams and is repeatable. New WebSocket commands (existing binary frames stay raw PCM):

- `{"cmd":"ingest","kind":"youtube","url":"...","pace":"realtime"|"max"}`: run
  `yt-dlp -f bestaudio/best --no-playlist -o - <url>` piped into
  `ffmpeg -i pipe:0 -f s16le -ar 16000 -ac 1 -`, and feed the PCM into the session queue at the chosen pace.
- `{"cmd":"ingest","kind":"file","name":"...","pace":"..."}` followed by binary frames of the **file
  bytes** and `{"cmd":"ingest_end"}`: bytes go to `ffmpeg -i pipe:0 ...`. Sending the file over the same
  WebSocket avoids a new upload endpoint (the websockets `process_request` hook cannot read a
  request body) and avoids paths on disk.
- `{"cmd":"ingest_stop"}` kills the process group. Progress events back to the page (position, duration if known).

Safeguards (required, not optional): allow only `youtube.com`, `www.youtube.com`, `m.youtube.com`,
`youtu.be`, `youtube-nocookie.com` hosts over https; arguments as a list, never a shell; one ingest
per session; duration cap (proposed 2 h); file size cap (proposed 300 MB); timeouts; kill on
disconnect. Install `yt-dlp` into `voice/.venv` (`pip`, no system change; it is not installed today).
Known fragility: YouTube can block or change formats and yt-dlp needs updates; a failed fetch must
show a clear message. Third-party content: fine for an internal demo, not for the public static
site, and saved transcripts stay out of the repo (`data/` is not in git). Fallback if YouTube fetch
is blocked: play the video in a browser tab and capture tab audio (`getDisplayMedia`).

## Live detectors on paid Jev, done properly

- **One call per checkpoint, all questions together.** A checkpoint sends every active detector's
  question in one `POST /v1/systemone` (TypeSafe's composite answers), as `flow.html` does. Adding
  a detector adds a question to the next request, not another call, so cost grows with tokens, not call count.
- **Applies from the next checkpoint**, plus an optional **"test it on what was just said"**: on
  add, score each active person's current window once (one call) so the new detector shows something immediately.
- **Custom detector definition** uses the same shape as `flow.html`'s `addCustom` (a `noul` question
  "Does the text match this description: ..." with true/false criteria, flagged unvalidated).
- **Per-person state is created lazily**, including for people who already spoke before the detector existed.
- **Cost guard**: show estimated spend and checks made (the backend already caches by content and
  caps a batch at 400 items). A per-session cap (proposed 300 checks) stops submitting with a visible
  "cap reached". Hosted use is confirmed once at Start, not per detector.
- The Jev key stays server-side (`demo/server.py`), as today.

## What the voice server sends (measured)

`ws://<host>:8200/ws`. After every model step, a full snapshot:

```
{"kind":"transcript","segments":[{"speaker":"speaker_0","start_time":1.1,"end_time":6.6,"words":"Hello everyone, ..."}],
 "audio_s":20.16,"step_ms":64.9,"hop_ms":1120}
```

Measured on the two-voice clip (fixture `voice/fixtures/twovoice-snapshots.json`, 18 snapshots):
- One snapshot per 1.12 s hop, about 65 ms compute per step (6% of real time).
- **Append-only in that test: zero previously emitted words were rewritten.** The clip is clean
  synthetic speech with no overlap; NeMo's settings (`fix_prev_words_count = 5`) allow the last few
  words to change on real speech, so the design tolerates tail rewrites and counts them.
- Words carry no per-word timestamps, only per-segment start/end. Sentence-final punctuation is
  unreliable, so the mock-up defaults to a **word window (`w20`) and word cadence**, not sentence windows.
- Speakers are `speaker_0..7`, shown as V1..V8, no names.

### Stabiliser (in the mock-up first; later `demo/static/voice-source.js`)

Input: snapshots. Output: append-only committed words `{spk, w, t, turnId, last}` plus a tentative
tail for display only. A word is committed when at least K = 5 newer words follow it for that
speaker, or its segment is closed (that speaker started a later segment, or `audio_s - end_time` > 3 s),
or on flush. Diff each snapshot against the committed prefix; if a committed word changed, do not
re-emit, count it. `t` is the `audio_s` at commit. New turn on speaker change or a same-speaker segment after a pause.
Fixture tests (node): exact committed sequence for the clip; injected rewrite emits nothing twice; flush commits the tail.

## What the mock-up must answer (with real audio, not the clean clip)

Use a recorded news panel first, then a live stream, then a call:
1. Rewrite rate of already-committed words on real speech (target: near zero after K = 5; if not, raise K).
2. End-to-end lag: speech to committed word to detector result (target under about 4 s).
3. Speaker flips per minute on a panel, and how they move words between people's windows.
4. Hosted spend per hour at the chosen cadence with 5 to 8 detectors (sets the default cap).
5. GPU: voice (about 5.8 GB) plus a reduced lineup; measured today that voice next to the full
   lineup (about 30 GB) runs out of memory. Proposed `lineup.sh voice` = kev-4b, semif, laya, verdict (not so1).
6. Adding a detector mid-stream: applies at the next checkpoint, no stall, no duplicate calls.

## Phases

1. **Ingest**: `yt-dlp` in the voice venv; `ingest` / `ingest_end` / `ingest_stop` in `voice/server.py`;
   safeguards; test with the local clips and one public YouTube video. *Check:* words stream in
   for a YouTube link and for an uploaded file, stop works, a bad URL is refused with a clear message.
2. **Stabiliser + fixture tests** (node). *Check:* tests pass.
3. **`flow-lab.html`**: thread, speaker cards, detectors, counters, Request tab, live Add detector
   on Jev. *Check:* the six recon questions above have written numbers in this file.
4. **Decide and refactor `flow.html`**: modes become Replay | Live (Live sources: mic/call, file,
   YouTube); make the transcript, speakers and clock growable; take `wd.last` instead of reading
   `T.turns[i].words.length`; port the stabiliser and proven constants; add the `voice` entry to
   `/api/status`; `lineup.sh voice`; retire the old "Live" wording. *Check:* Apollo 13 replay and a
   library dialogue give identical checkpoints and flags to before (compare exported request bodies).
5. Docs: `CLAUDE.md` Demo section, `BRIDGE.md`, note that Live is not in the static build; optional Save as recording.

## flow.html couplings to remove in phase 4 (verified by reading the code)

`onWord` reads `T.turns[wd.i]` and builds a `ghost` copy of the whole turn; `runner.feed` decides turn
end with `wd.k === T.turns[wd.i].words.length - 1`; `buildSpeakers()` fixes the list up front;
`DUR`, `EVENTS`, progress, speed, Replay precompute and the cost estimate assume a finite known
script; `S.t` is a synthetic clock that detector decay/hold (`tickDets`, `HOLD`) runs on (Live uses the audio clock).

## Risks

- Real-speech tail rewrites, overlap and speaker flips are untested; the mock-up exists to measure them.
- Mic and call are mixed into one stream, so "you" is not labelled. Later: send them as two sessions.
- Browser microphone needs a secure context (`localhost` is fine, a LAN IP is not).
- The voice server must be started after the lineup is reduced, never alongside the full one.
- YouTube availability (blocking, format changes) and third-party content handling, as above.
