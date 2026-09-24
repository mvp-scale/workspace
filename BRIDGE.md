# BRIDGE: where we are, for the next session

Updated 2026-09-24. Read `CLAUDE.md` first — it's the authoritative map of the repo layout,
commands, and architecture; this file is only the narrative of *why* things are the way they are
and what's still open. Everything below is committed; `git status --short` is clean.

This file was compacted on 2026-09-24: the previous version's long round-by-round history (MMLU
world knowledge, the Decompose/Monte Carlo readability passes, the honesty-audit round, etc.) is
still fully recoverable from `git log` if a specific rationale is ever needed again — it isn't
reproduced here because none of it is load-bearing for what comes next (see "Next" below).

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

## Next: voice

The user's next project is adding a **new, voice-based demo area** to the console — intentionally
not scoped yet beyond that one sentence. See the starter prompt handed to the next session for
how this should actually begin (investigation before any building, same pattern that worked well
for the static-deployment work above).
