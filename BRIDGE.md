# BRIDGE: where we are, for the next session

Updated 2026-09-25. Read `CLAUDE.md` first — it's the authoritative map of the repo layout,
commands, and architecture; this file is only the narrative of *why* things are the way they are
and what's still open. Everything described here is committed locally; `main` is **2 commits ahead
of `origin` and unpushed**, and the repo is **public** (check `voice/reference/`, which holds copies
of NVIDIA's docs, before pushing).

This file was compacted on 2026-09-24: the previous version's long round-by-round history (MMLU
world knowledge, the Decompose/Monte Carlo readability passes, the honesty-audit round, etc.) is
still fully recoverable from `git log` if a specific rationale is ever needed again — it isn't
reproduced here because none of it is load-bearing for what's currently in progress (see "Voice
pipeline" below).

## START HERE: priority for the next session

**Status 2026-09-25 (latest, read this first):** the swap is DONE: `/flow` (`demo/flow.html`) is the new page and the original lives at `/flow-classic` (`demo/flow-classic.html`; `/flow-lab-final` is an alias). The new page is the old `flow.html` plus Live audio, Levels, Counters, detector packs, AI-drafted detectors, voice lanes and Jev-assisted coaching. **Next**: (1) a paid check of the whole loop on `data/audio/nanobaiter-5min.m4a` with the Scam call caller + victim packs (about 70 detector calls plus about 20 coaching calls, cap 150) to see real scores, wins and coaching; (2) the static build does not include the flow pages, so nothing to change there (Live cannot run in a static build); (3) still open: the voice server needs a restart to pick up the YouTube 403 retry in `voice/ingest.py`, and `ANTHROPIC_API_KEY` in `.env` is an empty placeholder so name-only detector drafting falls back to a template. Findings so far are in `docs/voice-flow-integration-plan.md` ("Measured so far"). The rest of this section is the original plan, kept for the reasoning.

**Live audio in Conversation flow, proven in an isolated mock-up first.** Do not touch
`demo/flow.html` until the mock-up has measured the open questions. Plan (decisions already made,
phases, safeguards, measured server behaviour): `docs/voice-flow-integration-plan.md`. Read it fully.

The shape, in five lines:
- **Two modes**: *Replay* = a saved conversation (precomputed answers); *Live* = real audio from a
  mic/call, an **uploaded audio file**, or a **YouTube link**. Today's "Live" (scripted words, real
  model calls) was never truly live and folds into Replay as an option.
- **Mock-up** `demo/flow-lab.html`, served by `demo/server.py` at `/flow-lab`, not in the nav, not
  in the static build. It watches voices arrive, has detectors, and lets you **add a detector while
  it runs** on paid Jev (all detector questions in one composite `/v1/systemone` call per checkpoint).
- **Ingest is server-side** in `voice/server.py` (`yt-dlp` piped into ffmpeg for YouTube; file bytes
  over the same WebSocket), with an allowlist and caps. `yt-dlp` is not installed yet (pip into `voice/.venv`).
- **Seed the integration, do not fork it.** The mock-up should look and behave like `flow.html` so
  porting is mostly moving code: load `static/app.css` and `static/app.js` (`Jev.*` helpers), reuse
  the thread markup classes (`msg`, `bub`, `meta`, `words`), the detector colours `--s1..--s8` and
  icon set, the checkpoint rule (`trig`: `((sentence end || turn end) && since >= 3) || since >= 12`
  words), `personWindow`/`callWindow`, and the `QALL` question shapes for library and custom
  detectors. Write the live path as one function with the same shape as flow's `onWord(wd)` (a word
  event `{spk, w, t, turnId, last}` in, thread + runner out) so it lifts across unchanged.
- **Recon questions to answer with numbers** (real panel/stream audio, not the clean clip): rewrite
  rate of committed words, speech-to-detector lag, speaker flips per minute, hosted spend per hour,
  GPU fit, add-a-detector-mid-stream behaviour. Write the answers into the plan file.

**Runtime state right now**: the voice server is **running** (`:8200`, started from
`/workspace/voice` with `.venv/bin/python -u server.py`) and the classifier lineup is **down**
(voice plus the full ~30 GB lineup runs out of GPU memory; plan adds a smaller `lineup.sh voice`
profile). Hosted Jev works with no GPU. To get the lineup back: stop the voice server, then
`demo/lineup.sh up`. The demo console (`:8100`) runs from `/workspace` with `.env` loaded
(`set -a; . ./.env; set +a; python3 demo/server.py`).

**Also done this session, relevant here**: Baseline compare now has ten simple scenarios, two of
them code-security *batteries* (a snippet plus ten yes/no checks and a decision answered in one
composite request; `/api/compare` accepts `questions`) — the same composite mechanism the
mock-up's detectors will use. A stylesheet bug that let `.field { display:flex }` override the
`hidden` attribute was fixed in `compare.html`.

## Where things stand

**The benchmark side** (published probe sets, MMLU World Knowledge, the Leaderboard, Report, and
"How they work" pages) is stable and unchanged from what `CLAUDE.md` already describes. Nothing
about it needs revisiting to start the next project.

**Custom Decomposition** (Scenario lab) was substantially rebuilt this session:
- Jev (hosted) can now be selected alongside the local models — it was previously hard-refused as
  a cost-safety default; the run's own budget parameter (3-113 calls) already bounds the cost, so
  the refusal was removed in both the server and the CLI.
- The old Map + Outline (a tiny side detail panel, only reachable from the Map, never wired up
  from Outline) was replaced with **Results**: a real table, one column per model actually run,
  grouped **Shape → Category → Leaf** with a rollup row per shape/category, a **Decision** column
  (a disclosed, stated rule combining each item's live phase/gap answer with its real agreement
  level — low agreement overrides everything else), and an **Agreement** column (1 − spread).
  Starts fully collapsed; click anywhere on a group row (not just a tiny caret) to expand; each
  table gets its own Expand-all/Collapse-all.
- The schedule table (Chapter 2, "What it might cost") got the same shape/category grouping and
  collapse behavior, dropped a duration-range column and the now-redundant "models split" badge
  (Results already shows per-model agreement), and its day-precision axis was softened to
  "relative effort, not a calendar" language throughout, since the heuristic duration-band rule
  never supported calendar-level precision in the first place.
- Budget slider now defaults to 113 (the full library) instead of 60 — a full run against local
  models is a couple of seconds, so there was no reason to default to a partial one.

**Conversation flow got a real recorded dataset**: `data/flow-recordings/` holds genuine
`POST /v1/systemone` exports (via `flow.html`'s own "Export" button) — Apollo 13 across all four
models (jev/semif/so1/kev-4b), plus two MentalManip library dialogues (`mmwin-85514422`,
`mmwin-85515526`, jev only, chosen for having real manipulation-detector signal — the first replay
choice, Apollo 13 alone, was too quiet to be a good demo and got called out for it). Only 6
recordings exist; adding more is just running the live page once and dropping the export in.

## The static site: live, public, done

The console now has a public static export, separate from the live `demo/server.py` instance:

- **`demo/build_static.py`** regenerates the static build by calling `demo/server.py`'s own
  functions directly (never reimplemented) for Leaderboard, Scenario lab (all 72 published +
  MMLU sets), How they work, and Report — genuinely zero live model calls, no key, no GPU needed
  to view them. Baseline compare has no static equivalent (a live, free-typed question has no
  static form). Conversation flow ships as the recorded-summary page above
  (`flow-recordings.html`), not the live word-by-word player.
- Output goes to **`docs/`** (not `dist/` — GitHub Pages' simple branch-deploy mode only serves
  from the repo root or a folder literally named `docs/`). `docs/` also holds real hand-written
  project docs (`custom-decomposition-design.md` and others) that predate this build — the script
  only ever deletes the specific paths it generates (`api/`, `static/`, the named page files),
  never the whole directory (it did once, by accident, and silently deleted those docs; restored
  from git history, now structurally prevented).
- Every internal link (nav, the Leaderboard's per-model deep links) is a **relative path** on
  purpose, so the same build works whether it's served from a domain root or from a path prefix
  (a GitHub Pages *project* site lives at `<user>.github.io/<repo>/`, not the root — an absolute
  `/models.html` resolves to the wrong place there).
- **Live at <https://mvp-scale.github.io/workspace/>**, via GitHub Pages on `main:/docs`. The repo
  (`github.com/mvp-scale/workspace`) is public. Audited before pushing — no secrets, keys, or
  `.env` content anywhere in the tracked tree, `docs/`, or full git history.
- A real, unrelated pre-existing bug was found and fixed along the way: `research/classifier-dev`
  was tracked as a broken git submodule reference (gitlink, no `.gitmodules` entry) from an
  earlier commit. GitHub's Pages Actions deploy does a submodule-recursive checkout and was
  failing on it before ever reaching the site content. Untracked (the directory itself is
  untouched on disk); this is why the first two deploy attempts failed with no obvious connection
  to anything in `docs/`.

**Known limitations of this setup, worth remembering:**
- Not a CI pipeline — updating the live site means re-running `build_static.py` and manually
  `git add docs/ && git commit && git push` again. Nothing rebuilds automatically on data changes.
- `docs/` is committed (not gitignored) specifically so GitHub can see it; this means every
  rebuild that changes data adds a real diff to the repo's history, unlike a normal gitignored
  build artifact.
- Genuinely static: no live status, no live GPU state, no way to ever add Baseline compare or
  live Conversation flow to this specific deployment without adding a real backend.

## Other open threads, not touched this session, still just where they were

Two research questions were explicitly parked mid-investigation and never picked back up:
1. **A business/decision-relevant knowledge benchmark** — LegalBench (CC BY 4.0, real, ~100-250
   usable items after excluding ContractNLI-derived subtasks) is the one domain that cleanly
   survived a strict-sourcing bar; ESGenius (1,136 items, real/recent, but LLM-*generated* then
   expert-validated) is a tempting but not-yet-accepted exception to the "no manufactured content"
   standard every other set here holds to. Not decided: take LegalBench alone, also accept ESG, or
   keep searching (real estate, corporate governance, risk management, auditing-vs-accounting).
2. **An architecture/systems-design decision-reasoning benchmark** — no public, licensed benchmark
   for this is known to exist (cloud certification exams are the closest real-world analog, and
   they're vendor-proprietary, same "gated behind a certifying body" problem as most business
   domains). Humanity's Last Exam was flagged as a possible fit for a *different* axis ("esoteric
   synthesis of sparse knowledge") that probably shouldn't be conflated with this one.

`foundry/PLAN.md`'s own backlog (the `ATOMIC_THRESHOLD` re-threshold decision, ~15-18
`world-knowledge.yaml` content edits, `sort_and_rank.py`'s hosted-model-skip bug) and
`docs/scenario-lab-plan.md`'s original items 1-4 and 14-18 are untouched, unchanged from before.

## Voice pipeline: live speaker-attributed transcription, in progress

The "next: voice" project from the previous update is now a real, working prototype at
`/workspace/voice/` (separate from `demo/`, not yet wired into the console). Not a finished
feature — read this section before touching it, several non-obvious things were learned the
hard way.

**The code has moved past a simpler design mid-session — treat current files as ground truth.**
What's running now is NVIDIA's actual coupled multitalker pipeline (`mt_pipeline.py`, using
`LiveMultitalkerSession`/`SpeakerTaggedASR` per NVIDIA's own `ASR_INTEGRATION_GUIDE.md`), not the
earlier two-independent-models version this session started with. `voice/reference/` holds
verbatim copies of NVIDIA's guide, both model READMEs, and a `PROD_BEST_PRACTICES.md` +
`SOURCES.md` — read those for the current architecture's rationale, not this file's blow-by-blow.

**Models**: `nvidia/Nemotron-3-Diarization` (8-speaker Sortformer, needs NeMo installed from
GitHub `main` — PyPI's 3.0.0 release predates the RoPE support this model's encoder needs) +
`nvidia/multitalker-parakeet-streaming-0.6b-v1` (coupled streaming ASR, not the standalone
`parakeet_realtime_eou_120m-v1` this session tried first).

**Real pitfalls hit and fixed, worth knowing before changing settings or chunk sizing**:
- Both streaming services' internal feature buffers advance by a **fixed stride** set at init
  (derived from `chunk_size_in_secs`/`chunk_len`) — call `.diarize()`/`.transcribe()` with
  anything other than exactly that many samples and the feature window silently desyncs from the
  real audio (no exception, just empty/garbled decoding).
- NVIDIA's own published "very low latency" diarization preset (chunk_len=6) was A/B tested here
  under real-time-paced audio and measurably broke ASR output (word fragments vanished) — likely
  a real-time compute-budget issue (640ms window too tight for this heavier buffer config on this
  hardware), not a wrong-parameters issue. The "low latency"/"Balanced" preset (chunk_len=9,
  1.04s budget) verified working correctly and is the current default. Re-verify before trusting
  Fast/Ultra presets for a live mic rather than assuming NVIDIA-published means safe here.
- Lowering `max_num_speakers` below the checkpoint's trained 8 does **not** reduce compute — it
  silently breaks diarization output entirely (confirmed by direct test). Not exposed as a
  setting for this reason.
- Audio transport is a single persistent WebSocket with a decoupled recv/inference/send 3-loop
  architecture (matches NVIDIA's own reference and a real production streaming-Parakeet
  deployment) — an earlier single-blocking-loop version caused connection resets under real load,
  because inference blocking the same loop that receives audio backs up the mic-side buffer.
- The ASR's `<EOU>`/`<EOB>` end-marker can appear inside the decoded text string itself, not just
  as a separate flag — strip it, but only when present (an earlier unconditional `.strip()` broke
  word-boundary spacing between fragments).
- Real diarization jitter (a continuous speaker's label flipping chunk-to-chunk) is expected and
  was never exercised until a real multi-speaker test — an EMA smoother over per-speaker
  confidence is in place; tune `SPEAKER_EMA_ALPHA` if it's too sluggish or too jittery.

**What the mockup UI has**: live-reconfigurable settings (sliders with shaded "verified-good"
bands, not raw numbers), preset buttons for NVIDIA's four latency profiles labeled honestly
(verified vs. untested-here), a mic self-test (record 3s, play back, download WAV — bypasses the
whole ML pipeline, for isolating capture-quality problems from model problems), and known-content
test clips (`warmup.pcm`, `twovoice.pcm`) to replay without needing a live mic.

**Audio capture options** (the user wants to demo live Zoom/Teams call audio, said "tomorrow" as
of 2026-09-24): the audio-source selector supports mic-only, a virtual-loopback-device path
("both"/"dev" — needs Stereo Mix, VB-CABLE, or similar), and a **no-install** path via Chrome's
`getDisplayMedia` screen-share dialog ("screen"/"tab" — pick "Entire Screen" + "Share system
audio", zero drivers, zero reboot, already verified working end-to-end). The user is installing
VB-CABLE as the more polished option for the actual demo but confirmed the no-install path works
as a fallback. **VB-CABLE requires a reboot** (their own install page says so — an earlier claim
in this session that it usually doesn't was wrong and got corrected).

**Where things stand right now**: see "Runtime state right now" under START HERE.

**Next (planned, not started)**: two modes in `demo/flow.html` (Replay = saved conversation, Live = real audio from mic/call, an uploaded file, or a YouTube link), proven first in an isolated `demo/flow-lab.html` with live-added detectors on paid Jev. Full plan: `docs/voice-flow-integration-plan.md` (measured transcript behaviour, ingest design and safeguards, phases; test fixture `voice/fixtures/twovoice-snapshots.json`).

**Not yet done**: wiring this into `demo/flow.html`'s transcript-source abstraction (still the
long-term integration target per the original plan) — this is still a standalone prototype at
`voice/`, deliberately not touched in `demo/` yet.
