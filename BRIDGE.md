# BRIDGE: where we are, for the next session

Updated 2026-09-23, continuing the same day's session, after a second live-feedback round from the
user. Read `CLAUDE.md` too. Full detail is in the git log (`git log --oneline`) once this is
committed — this file is the narrative.

## Third round: honesty audit + the harder ask (live Gantt for custom decomposition)

The user then asked directly: is the Decompose page's "31 nodes" plan actually derived from real
data, or did a past Claude session embellish it? Audited by reading `probes/lab_decompose.py` and
`data/probe-runs-v2/_decompose/tree_scored_edge.json` directly (not from memory). Finding: **not
embellished** — the page's existing `SRC`/`srcNote()` system (already in `scenarios.html` before
this session) already correctly labels three distinct sources: the plan text/durations/edges are
hand-authored by Claude (disclosed as such, never claimed to be measured or model-generated), the
schedule is real deterministic `cpm()` math over those inputs, and the per-node scoring is real
live `POST /v1/systemone` calls (verified: `tree_scored_edge.json` has high-precision floats like
`0.4073334000459302` from 5 real running models, timestamped from this session). The only
"AI-generated" content is the plan's prose and duration estimates themselves — and that was
already disclosed plainly ("I wrote the plan..."), just not prominently enough. Fixed by adding a
`dataDrivenBanner()` — a loud "Not a theoretical demo" callout right under the h2 on both the
Decompose and Monte Carlo pages, listing exactly which of the `SRC` entries each page's numbers
trace to, with hover detail. Also added two new `SRC` entries (`durations`, `sampling`) for Monte
Carlo specifically, since it deserves an even stronger claim than Decompose — zero live model calls
anywhere in the computation, 100% arithmetic over hand-authored inputs.

**The harder ask, not yet built — genuinely blocked on the user's choice, not on effort**: the user
wants Custom Decomposition (the orbit map, arbitrary pasted text) to also produce a live, real-time
Gantt chart with risk bands, "the wow factor" proving this isn't theoretical. Recon finding: this
directly runs into an **existing, deliberate design decision** documented in
`docs/custom-decomposition-design.md` ("It also refuses a schedule, as lab_decompose and foundry's
`monte-carlo.yaml` both do: no durations exist, so no dates, critical path or forecast are
computed") and mirrored in `foundry/monte_carlo.py`'s own explicit qualitative-only scoping
(PMBOK's real distinction: qualitative risk prioritization needs no units; quantitative Monte
Carlo/schedule forecasting needs real time units this project doesn't have for arbitrary text).
Why: `probes/lab_custom_decompose.py`'s live leaf battery (`leaf_questions()`) already asks
`complexity` and `risk` (5-level score, live, real) and `dependency` (choice, live, real) per leaf
— but `dependency`'s options are `none`/`needs-user-decision`/`needs-other-item`/
`needs-external-check`, never *which* other item, and `parallel` was deliberately dropped for this
structure (module docstring: "the siblings here are whichever items the priority queue happened to
reach, not a real group"). So there is no live signal from which a true predecessor-edge graph (the
one real ingredient `build_tree_edge.py`'s Monte Carlo needs) can be built for arbitrary text.
A live Gantt here is achievable, fast (`cpm()` + a few thousand triangular samples over ~20-90
leaves is comfortably sub-second), but only honestly as an explicitly-labeled *heuristic*: duration
bands derived from the live `complexity` answer via a stated, disclosed conversion rule (not
measured, not fabricated — a rule, same honesty pattern as `foundry/monte_carlo.py`'s "illustrative
scale" disclaimers), and a default sequencing assumption (e.g. categories sequential, siblings
within a category parallel unless one's own live `dependency` answer said `needs-other-item`) that
would need to be labeled as loudly as the `SRC` banners above, everywhere it appears — never
presented as a measured dependency graph. Asked the user to choose between that heuristic path and
a more conservative "relative effort/risk board" (no day units at all, bar length ∝ complexity ×
risk, explicitly not a schedule) before building anything.

**User chose the heuristic path. Built and verified live this same session.** New code, all in
`demo/scenarios.html` (no Python changes needed — this runs entirely client-side, in-browser, over
data the live walk already fetched, so it's instant with zero extra model calls):
- `customDurationBand()` — the stated rule: each leaf's own live `complexity` answer (mean, 0-1)
  maps to a duration band via `CUSTOM_DURATION_ANCHORS = [0.25, 0.5, 1, 2, 4]` days (very low →
  very high), interpolated continuously; optimistic/pessimistic use the band one complexity level
  either side. The mirror image of `build_tree_edge.py`'s own `complexity_band()`.
- `mcCpm()`, `mcTriangular()`, `mulberry32()`/`seedFromString()`, `mcRunSimulation()` — verbatim JS
  ports of `build_tree_edge.py`'s `cpm()` and `build_monte_carlo.py`'s sampling loop. Seeded from
  the live run's own `run_id` (itself a hash of text+who+models+budget), so re-running identical
  settings reproduces identical numbers — the "repeatable" the user asked for.
- `customScheduleData()` — builds the predecessor graph from real live signal only: category order
  = the real live priority-queue `queue_rank` (an actual ranking, not invented); within a category,
  leaves are parallel by default, except a leaf whose own live `dependency` answer is
  `needs-other-item`, which gets scheduled after its category siblings instead (still a stated
  default, since the live answer never says *which* sibling).
- `customScheduleSection()` — renders a loud `callout warn` stating the rule in full before any
  numbers, then reuses `mcHistogram()`/`mcGanttBoard()` unchanged (both were made to tolerate a
  missing `horizon_working_days`, since arbitrary text has no external deadline to check against),
  plus a criticality-index table. Wired into `renderCustom()`'s existing `ev.t === "end"` handler.
- Fixed the now-outdated closing line in `customReadout()` ("No schedule is computed either,
  because no durations exist") and added a dated addendum to `docs/custom-decomposition-design.md`
  pointing at this change, so the original design rationale stays intact but isn't stale.

**Two real bugs caught and fixed during live verification** (both in this new code, not
pre-existing): (1) `mcGanttBoard`'s per-bar tooltip references `data.n_runs` for its label, which
`customScheduleSection` forgot to pass through — threw `Cannot read properties of undefined
(reading 'toLocaleString')` on every render, silently caught by `renderCustom`'s own error
handling and displayed in a `callout bad` box that was easy to miss above the fold. Fixed by
passing `n_runs: mc.n_runs` into the `mcGanttBoard` call. (2) A **pre-existing, unrelated** bug
was also found while testing: the example-pill buttons on the Custom Decomposition page set
`textarea.value` directly without dispatching an `input` event, so `updateRunState()` never
re-enables the Run button after picking an example — the button silently stays disabled and
clicks do nothing, with no visible error. Not fixed this session (out of scope of what was asked);
worth a one-line fix (`textarea.dispatchEvent(new Event("input"))` after setting `.value`, or just
calling `updateRunState()` directly in the example click handler) next time someone's in this file.

Verified live end-to-end against the real `cf-memory` example (68 of 111 library items reached,
60 then 80 calls): schedule section renders correctly (disclosure callout, histogram, Gantt with
real category lanes and real parallel/sequential bars, criticality table), no console errors,
re-running with more budget (the "Spend 20 more" button) recomputes cleanly. Real server on 8100
restarted with all changes.

## Second round: Gantt risk visualization + rail reorganization

After the first Monte Carlo ship (below), the user asked for two more things, live, in plain
language (not a written spec) — both now done:

1. **A Gantt chart showing impact on the critical path**, not just the histogram/table. Built
   `mcGanttBoard()` in `demo/scenarios.html`: same grouped-lane row layout as the existing
   `ganttBoard()` on the Decompose page, but for every task it draws a pale **risk band** (p10
   start to p90 finish across all 10,000 sampled runs, colour intensity = criticality index,
   independent of whether the task is on the single deterministic path) behind a solid
   **idealistic bar** (the single-estimate deterministic schedule, red-outlined if it's on the
   deterministic critical path). This required extending `build_monte_carlo.py` to track each
   task's `start_p10/p50/p90` and `finish_p10/p50/p90` across all sampled runs (previously it only
   tracked the aggregate span distribution and a binary per-task critical-path count), plus each
   task's own `deterministic_start_day`/`deterministic_finish_day`. It's inserted into
   `renderMonteCarlo()` under a new "Impact on the critical path" heading, above the existing
   criticality-index table (which stays, as the exact-numbers detail under the chart).
2. **Regroup the rail into "Basic structures" vs. "Decomposition structures"**: decompose-and-loop,
   Monte Carlo and custom decomposition all now sit together under their own rail section, since
   they all build on the same real hand-authored plan tree rather than a published probe set.
   `STRUCTURES` in `scenarios.html` is now derived from a new `STRUCTURE_SECTIONS` array (label +
   items); `buildRail()` loops over sections instead of one flat list, for both the desktop rail
   and the mobile `<select>`'s optgroups.

Also added a **narrative cross-link both directions**: Monte Carlo's "Where this comes from" card
now links to Decompose and loop ("this page doesn't decompose anything itself, it samples schedule
risk over the plan that page's decomposition already produced"); Decompose's sensitivity paragraph
now links forward to Monte Carlo ("samples each task's own real optimistic/likely/pessimistic
range instead ... and turns this single 13-day figure into a probability distribution").

**A real bug caught and fixed in this pass**: the horizon marker label ("20d target") on the new
Gantt chart was centre-anchored and got clipped at the SVG's right edge whenever the horizon
exactly equalled the chart's rightmost day (the common case, since no task's p90 finish exceeds 20
days here). Fixed by right-anchoring the label instead of centering it — same fix class as the
verb-label clipping bug documented from the earlier "How this works" diagram pass.

**Verified live** the same way as the first round: temporary server on port 8188 (real instance on
8100 untouched until the very end), `claude-in-chrome`, screenshots at multiple scroll positions,
zoomed in on the previously-clipped label to confirm the fix, clicked the cross-links both
directions and confirmed they navigate and re-render correctly, checked console for errors (none).
**The real server on 8100 was then restarted** (it needed to be anyway — a user report of a 404 on
`/api/monte-carlo` earlier in the session revealed it was still running pre-edit code) to pick up
all of this session's changes; confirmed `/api/monte-carlo` serves the new fields afterward.

## What shipped earlier this session: "Monte Carlo (schedule risk)" as a 10th Scenario-lab structure

Both open questions from the previous update were asked and answered directly by the user before
any code was written:

1. **Placement**: 10th Scenario-lab structure in `demo/scenarios.html` (not a separate page under
   `probes/decompose`), reusing the flow-diagram template shipped earlier in the day.
2. **Duration ranges**: hand-authored real three-point (optimistic/likely/pessimistic) estimates
   for all 24 leaf tasks, not a derived-from-a-formula approach. Each estimate carries its own
   one-line `duration_basis` rationale tied to that specific task's real failure mode (e.g.
   `spike-sharedmem`'s pessimistic case is "try several near-misses before writing down a
   confident no"; `ingest-loader`'s is "typical first-integration slip"), not a uniform multiplier.

**What was built, in order**:
- `probes/decompose/build_tree_edge.py`: added `duration_optimistic_days`, `duration_pessimistic_days`,
  `duration_basis` to all 24 `LEAVES` entries. Verified `optimistic <= duration_days <= pessimistic`
  for every leaf. Regenerated `tree_ref_edge.json` (unrelated fields unchanged; span/critical path
  identical to before since the point estimate itself didn't move).
- `probes/decompose/build_monte_carlo.py` (new): imports `LEAVES`/`GROUPS`/`cpm()` straight from
  `build_tree_edge.py` rather than duplicating the CPM logic. Triangular-samples every leaf's
  duration 10,000 times (`random.triangular(optimistic, pessimistic, most_likely)`, seeded
  `20260101` for reproducibility), reruns `cpm()` on every sampled set, and writes
  `probes/decompose/monte_carlo_schedule.json`: the deterministic pass, a completion-day
  distribution (percentiles, histogram, `P(finish within the 20-day horizon)`), and a per-task
  **criticality index** (share of sampled runs where that task was on that run's own critical
  path). Runs in well under a second.
- `demo/server.py`: `monte_carlo_schedule()` reader + `/api/monte-carlo` route. Pure computation
  over hand-authored data, no live model calls (unlike `decompose_tree()`, which also scores nodes
  through the loaded models) -- correctly the simpler of the two.
- `demo/scenarios.html`: `montecarlo` added to `STRUCTURES` and given its own rail icon (a
  bell-curve/histogram glyph, distinguished from `baseline`'s icon); `monteCarloFlow()` built from
  the existing `flowBox`/`flowArrow`/`flowLoop` toolkit (task durations → sample → one sampled
  schedule → figure out → run the critical path → loop "thousands of times" → check → completion
  range + criticality); `mcHistogram()` (new small SVG histogram helper, its own `.mchist` CSS
  block modeled on the existing `.gantt` rules) draws the completion distribution with p10/median/
  p90/horizon marker lines; `renderMonteCarlo()` assembles the page: deterministic-vs-sampled
  framing, the histogram, a criticality-index table (using the existing `Jev.meter` bars, sorted
  descending), a dynamically-computed "what sampling reveals that one CPM pass doesn't" callout
  (tasks that are never on the deterministic critical path but *are* critical in a real share of
  sampled runs), and a "release train" recommendation (tasks with criticality index ≥ 50%).

**A real finding the simulation surfaced, worth knowing about** (seed `20260101`, 10,000 runs):
5 tasks — `spike-sharedmem` (the pitch's central platform claim!), and the whole `orch-*` chain
(`orch-primitive`, `orch-delta`, `orch-reduce`, `orch-impl`) — are *never* on the single
deterministic critical path but are each critical in 23–25% of sampled runs. `train-impl` is
similar. This is a genuine example of Monte Carlo schedule risk analysis catching something a
plain CPM pass misses, not a contrived one. `ops-e2e` and `ops-launch` sit at 100% (as expected,
since they're the plan's terminal serial chain), and the sampled median (15.7d) and p90 (17.4d)
both land above the deterministic 13.0d, which is the expected right-skew of triangular schedule
sampling, not a bug.

**Verified live**: temporary `demo/server.py` on port 8188 (the real instance on 8100 was never
touched), navigated with `claude-in-chrome`, confirmed the page renders fully (diagram, histogram,
table, both callout sections), confirmed navigating away to another structure and back re-renders
correctly (the SPA same-hash gotcha didn't bite here since the hash actually changed each time),
no console errors. Temporary server process killed afterward.

## Not yet done

**Nothing has been committed.** `git status --short` at the end of this session:
```
 M BRIDGE.md
 M demo/scenarios.html
 M demo/server.py
 M probes/decompose/build_tree_edge.py
 M probes/decompose/tree_ref_edge.json
?? probes/decompose/build_monte_carlo.py
?? probes/decompose/monte_carlo_schedule.json
```
Ask the user before committing (per this repo's own norms — commits are opt-in, not automatic).

Nothing else about this feature is known to be incomplete. If picking this back up: read this
section, then diff the files above before touching anything else, in case the user made manual
edits in between sessions.

## Fourth round: readability pass on Decompose and loop (the densest page)

The user's feedback, paraphrased: the content on the Decompose and loop page is good, not wrong,
but too dense and compact for a first-time reader -- no breathing room, twelve flat sections in a
row, only one "so what" at the very end, an inconsistent one-off SVG for "how a model scores one
node", and prose that assumes too much patience. Asked for: bigger high-level sections that tell a
story going down the page (why we're about to show you this, in plain human language, before any
detail), content distilled rather than explained at length, and a "so what" bridge after each
section -- deliberately not always the same blue callout, so a page of them doesn't itself become
visual noise.

Built, all in `demo/scenarios.html`:
- **`pipelineHero()` rewritten** to use the same `flowBox`/`flowArrow`/`flowLoop` toolkit as every
  other diagram on the page, instead of its own bespoke `stage()`/`arrow()` shapes and a separate,
  less-refined CSS style (`.pipeline .arrow`/`.pipeline .loopback`, now removed as dead code). It's
  literally the same atomic/stop/split loop as `decomposeFlow()` at the top of the page, just
  labelled for the model's own classifier call -- now it visually reads as the same family instead
  of two unrelated diagram styles explaining related things.
- **`chapterHeader(kicker, title, why)`** -- a big, spaced-out section divider (48px top margin,
  border-top rule) with a plain-language "why we're about to show you this" sentence before any
  detail. The Decompose page is now 3 numbered chapters ("Chapter 1 of 3: The pitch", "Chapter 2 of
  3: The plan and the schedule", "Chapter 3 of 3: Can a model help review it?") plus a compact
  closing "Caveats" chapter, instead of 12 flat, undifferentiated `h3` sections.
- **`soWhat(tone, title, detail)`** -- the one-line takeaway that bridges to the next chapter, in a
  left-accent-bar card, bold headline + short supporting clause. `tone` cycles through the app's
  own categorical `--s1`..`--s8` tokens (the same palette the flow-diagram verbs already use) so
  the three so-whats on this page render in three different colours (violet, rose, amber) instead
  of one repeated blue `callout`.
- **`bottomLine()` rewritten** to stop repeating Chapter 2's so-what verbatim (both used to say
  "spend one day on X, rest is a routine N-day build" -- exactly the redundancy the user was
  pointing at). It now synthesizes across all three chapters instead: schedule margin (fine),
  model-review trustworthiness (fine), platform assumption (still open) -- one distinct, final
  "so what of so-whats" for the whole page, not a repeat of an earlier one.
- Folded the old sections 10+11 ("Why five models" / "What this page does not measure") into one
  compact "Caveats" chapter instead of two separate `h3` sections with their own intro paragraphs.
- Trimmed the wordiest intro paragraphs (the model-scoring methodology paragraph went from five
  sentences to two; the "why five models" note and a few others similarly cut). Did **not** touch
  any of the actual content/tables/numbers underneath -- `gateCard`, `resourceTable`,
  `openItemsSection`, `loopResultsPanel`, `disagreeTable`, `scorecardTable`, `buildTreeView` are
  all unchanged, since the user was explicit that the content itself is good, only the density and
  structure needed work.

**A real bug caught while wiring this in**: the first pass added the "CHAPTER 2 of 3" *comment* in
the code but never actually called `chapterHeader()` for it -- the divider silently vanished from
the rendered page between Chapter 1's so-what and the Gantt board. Caught on the live screenshot
(content jumped straight from the so-what into "31 nodes, six workstreams..." with no chapter
break), fixed by actually adding the missing `out.append(chapterHeader(...))` call.

Verified live: all three chapters + Caveats render with correct spacing, all three so-whats show
in distinct colours, the fixed `pipelineHero()` diagram visually matches `decomposeFlow()`, no
console errors, and a spot-check of the Monte Carlo page (unrelated, shares the same CSS file)
confirmed nothing else broke. Real server restarted via `./start.sh restart`.

## New: `/workspace/start.sh` -- use this from now on instead of ad-hoc nohup

The back-and-forth above involved a lot of manual `nohup python3 demo/server.py &` / `ss -ltnp |
grep 8100 | ... | kill` on my part, which is exactly the kind of drift the user flagged: no
record of what's running, on what port, or how to stop it cleanly. `start.sh` fixes that --
`./start.sh {start|stop|restart|status}`, pinned to port 8100, tracked by `logs/demo.pid`, sources
`.env` automatically (`TYPESAFE_API_KEY` etc., matching CLAUDE.md's documented startup), and its
`stop`/`start` both detect and clean up anything squatting on the port that wasn't started by the
script itself (covers every stray instance from earlier in this session). Verified: adopted the
untracked process left over from this session, full stop/start/restart/status cycle, double-start
is a safe no-op, log truncates fresh on every start for easy debugging. **Use `./start.sh restart`
after editing anything in `demo/` from now on, in place of manual nohup/kill.** A temporary instance
for testing a change before touching the real one can still use `DEMO_PORT=8188 nohup python3
demo/server.py &` directly (not through this script, which is only for the canonical port-8100
instance) -- same pattern as every verification pass earlier in this session.

## Everything else still open, unrelated to the above (unchanged from before, still true)

`foundry/PLAN.md`'s own backlog: the `ATOMIC_THRESHOLD` drop/re-threshold decision (kev-4b's data
is available now, this is unblocked), the ~15-18 `world-knowledge.yaml` content edits identified
but not applied, `sort_and_rank.py`'s hosted-model-skip bug. `docs/scenario-lab-plan.md`'s original
backlog items 1-4, 14-18 (new probe sets, blind grading, jevbench version sync) remain untouched.
The custom-decomposition stretch goals (Board view, model-subset toggle, Numbers view,
compare-two-texts, ledger replay, leaf-level lift, hosted-model escalation) are still just that —
stretch goals, not started.
