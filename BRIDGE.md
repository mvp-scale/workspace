# BRIDGE: where we are, for the next session

Updated 2026-09-24. Read `CLAUDE.md` too. Full detail is in the git log (`git log --oneline`) --
everything below is committed, `git status --short` is clean. This file is the narrative.

## Sixth round (new day): World Knowledge (MMLU) -- built, shipped, iterated live with the user;
## a business-domain and a coding/architecture-knowledge extension both explored and correctly
## stopped short of building anything unproven

Started from an exploratory question ("is there a test that measures whether a model actually
knows a domain?") and ended up shipping a full second benchmark dimension alongside the existing
15 published probe sets, plus two honest "we looked, the data isn't there yet" research passes.

### What shipped: full MMLU, no sampling, as its own "World knowledge" view

`probes/v2/build_mmlu.py` (new) pulls the complete public MMLU test split (`cais/mmlu`, Hendrycks
et al. 2021, MIT licence) via `datasets.load_dataset` -- **all 57 subjects, 14,042 items, no
sampling** -- into 57 separate probe sets (`mmlu_<subject>.jsonl`, one per subject, matching this
project's one-file-per-set convention), each item lettered A-D to match the site's own "read the
model's own answer-letter scores" technique. One shared `probes/v2/mmlu.md` (server.py's existing
notes-lookup already resolves shared docs by id prefix, e.g. `sarcasm_*` already did this) covers
licence, sampling (none), format, and checked caveats -- including a grounded one found by actually
reading items, not guessing: `machine_learning` is frozen at 2020-2021 knowledge (item
`mmlu_machine_learning-test-4` literally asks "As of 2020, which architecture is best for
classifying high-resolution images?"), while stable fields barely age in 5 years. Also cites the
real MMLU-Redux audit figure (~6.49% of items have a documented ground-truth error) rather than a
guessed "low single digits."

**A real bug found and fixed while wiring this in**: `server.py`'s `read_jsonl` used
`str.splitlines()`, which also splits on Unicode line/paragraph separators and NEL -- one real
MMLU question (`mmlu_management`) contains a raw NEL character and corrupted that file's parsing.
Fixed to split strictly on `\n` (a JSONL file only delimits records that way); this was a latent
bug in existing infrastructure, not something specific to the new data.

**Kept deliberately separate from "All sets"**: first wired all 57 subjects in as extra columns on
the existing "All sets" heat map (grouped under 4 new categories), but the user pushed back hard --
mixing 57 academic subjects into the page about the 15 curated probe sets (and the Cascade/Baseline
structure views, which iterate the same list) dilutes the thing that page is actually for. Pulled
MMLU back out of `PROBES` entirely and gave it a dedicated **"World knowledge (MMLU)"** overview,
a peer of "All sets" in the rail's Overview section, not nested under it: `renderWorldMap()` in
`demo/scenarios.html`, the transpose of `renderOverview()` -- **subjects as rows** grouped into
MMLU's own **4 official categories** (STEM/Humanities/Social sciences/Other, pulled from
Hendrycks's own `categories.py` on GitHub, not guessed or invented), **models as columns**,
ordered strongest-average-first, same click-through into the per-item explorer "All sets" already
has. `MMLU_PROBES` is now a separate global from `PROBES`; the fallback per-set route (`ST.set`
not matching a known structure) checks both lists.

**Then iterated to "compact and consistent" over several live rounds**, each verified with a
browser screenshot before moving to the next:
- Model headers: dropped the code+name pattern (`mtagLive`) for code-only (`mtagShort`, the same
  pattern every other dense table on this page already uses) -- full name still on hover.
- Subject column capped at 150px with ellipsis truncation (was unbounded `white-space:nowrap`, so
  "High school government and politics" was setting the width for all 57 rows).
- Column headers switched from the "All sets" page's rotated/vertical style (built for dozens of
  narrow set columns) to plain horizontal text -- unnecessary with only 6-9 model columns.
- Added model **size** and **base model** under each code, so base-model overlap is visible at a
  glance: SemIf, so1 and kev-4b all read `Qwen3.5-4B(-Base)`, confirming they share one foundation
  model despite three different read-out techniques -- directly visualizes the "How they work"
  page's own "reading isn't knowing" thesis. Trimmed the base-model string down to just the model
  class (`Qwen/Qwen3.5-4B (frozen, BF16)` -> `Qwen3.5-4B`; `GLiClass ModernBERT-base, fine-tuned
  (heman10x/...)` -> `GLiClass ModernBERT-base`) after the user flagged the redundant HF org
  prefix and trailing clauses.
- Top-aligned every header cell (`vertical-align:top`, scoped via `:has(th.mcolh)` so the
  unrelated "All sets" table isn't touched) after the user noticed Jev's shorter 2-line block
  (no base model, since it's undisclosed) wasn't lining up with the 3-line columns next to it.
- Every heat-map cell (both "All sets" and World knowledge) now prints its accuracy percentage as
  visible text, and empty ("no results") cells switched from a subtle border-grey stripe to a
  distinct amber stripe (`color-mix` with `--warn`) plus a plain "-" mark -- the user correctly
  flagged that a real, badly-scoring cell and a genuinely-empty cell looked identical at a glance
  (confirmed with a real example: `jev x machine_learning` was 0/112 attempted, not just low-
  scoring, and looked the same as a real near-chance cell elsewhere on the row).
- Replaced the prose subtitle with a bold headline stat ("14,042 questions across 57 subjects --
  the complete public MMLU test set, nothing sampled") plus three provenance badges (Published
  2021, Unrevised since, The field's original general-knowledge benchmark) -- the user wanted
  MMLU's pedigree "celebrated," not buried in a sentence. Also made the page-wide caveat banner
  (previously static HTML shared across every Scenario Lab view, so it wrongly said "each set has
  only 64 to 154 items" on this page) view-aware instead.
- **A real class-name collision caught mid-fix**: the new header class was named `.mh`, which
  turned out to already be used elsewhere in `scenarios.html` for an unrelated flex row. Renamed
  to `.mcolh` before it caused a real bug, not after.

### Budget ledger: a real structural discovery, not a workaround

Running the full 6-model set surfaced a genuine design fact in `jevbench/budget.py`: `Ledger.cap`
is `min(every cap_usd ever recorded in this ledger file, plus the current call's cap_usd)` -- a
**ratchet that only ever tightens, never loosens**. The very first Jev run (via `bench.sh`'s
hardcoded `--cap-usd 1`) permanently capped the shared ledger at $1; passing a higher `--cap-usd`
on a later call is silently ignored, confirmed by directly reading the ledger's own `cap` events
rather than guessing. This is clearly deliberate (CLAUDE.md already calls the ledger "shared
across all runs" on purpose) so the fix was not to route around it quietly -- asked the user first,
who authorized a **separate ledger file** (`ledger-jev-topup.jsonl`) as an explicit, one-time,
user-approved exception, scoped only to finishing Jev's known gap (24 subjects, ~$0.31).

**Two real operational mistakes made and fixed in the same pass, both disclosed live as they
happened**: (1) `demo/lineup.sh down` stops all 5 lineup services, not just the 4 intended for the
local in-process batch -- killed kev-4b's own concurrent MMLU run mid-flight. Cleaned up the 27
corrupted (0-result) output directories it left and queued a watcher script
(`logs/mmlu-run-kev4b-after.sh`) that waited for the lineup to restart and then resumed kev-4b
automatically (it did, unattended, and finished correctly). (2) An overly broad `pkill` aimed at
the broken kev-4b process also matched and killed the legitimate Jev run -- relaunched immediately;
`bench.sh`'s skip-if-exists behaviour correctly avoided re-charging the one subject that had
already completed.

### Parallelization: user explicitly funded and authorized this ($30 total on the account, ~$1.14
### spent across everything by the end), then asked whether Jev could be parallelized

Checked TypeSafe's own docs (`docs.typesafe.ai` and its `llms.txt` index) directly rather than
assume: **no published numeric rate limit exists** -- their own docs list "rate limit thresholds"
and "quota information" as explicitly missing sections. `jevbench/runner.py` already stops a given
subject's run cleanly on HTTP 429/401/403 or 3 consecutive failures (no retry storm), and the
harness's own traffic pattern is already one-request-at-a-time within a subject. Built
`logs/jev-parallel-topup.sh`: parallelizes **across subjects** (each an independent
`jevbench.cli run` process, the shared ledger already handles concurrent reserve/settle safely via
`fcntl.flock`), not by touching the harness's own serial per-item loop. Started at a conservative
4-way concurrency with an explicit circuit breaker (`grep`s each finished subject's log for the
harness's own "STOP: access/rate limit" message; if found, stops launching new subjects but lets
in-flight ones finish, leaving the rest as honest gaps rather than pushing through). Result: **all
9 remaining Jev subjects finished, zero rate-limit hits** -- real evidence there's headroom to push
concurrency higher next time.

**Final state: Jev and kev-4b both fully complete, 0/57 gaps each** (kev-4b's last straggler,
`computer_security`, was a leftover from the lineup-restart mistake above, fixed with one direct
`jevbench.cli run` call once the kev-4b service was confirmed healthy again). SemIf, so1, Laya and
Verdict were already complete from the original batch run earlier in this round. Total spend
across the whole MMLU effort plus everything already in the shared ledger: **~$1.14**.

### Two "should we extend the taxonomy" explorations -- both correctly stopped short of building
### anything, on the evidence, not on hesitation

**Business/decision-relevant domains** (forked research, `subagent_type: fork`, not inline): the
user had another AI agent draft a proposal for ~10-15 additional MMLU-adjacent domains (Art, Vet
Medicine, Sports Science, Agriculture, Environmental Science, Urban Planning, Tourism, Metrology,
Fire/Safety Engineering, Education, Language & Literature). Reviewed it before researching anything
-- flagged that C-Eval/CMMLU/ArabicMMLU are language-*localized* MMLU variants (same subjects,
different language, not new knowledge, and the user explicitly doesn't want "languages"), and that
Metrology/Fire-Safety-Engineering look like they'd fail the proposal's own "don't count vertical
specializations" rule. User then reframed the actual filter: **business/decision relevance**, and
a much leaner target (~500-600 items, not thousands). MMLU already covers core business subjects
(business_ethics, marketing, management, professional_accounting, econometrics, both macro/micro-
economics, professional_law, international_law, public_relations) so the fork searched genuinely
missing business-adjacent ground instead: finance/CFA, insurance, HR/employment law, project
management, supply chain, ESG. **Finding: the strict bar (real, public, licensed, human-authored,
fixed-choice, publisher-supplied gold answer) is much harder to clear for professional/business
knowledge than it was for MMLU's academic subjects** -- almost everything valuable there is gated
behind proprietary certifying bodies (CFA Institute, SHRM, PMI) with no free public question bank.
Only one domain cleanly survives: **contract/practical legal reasoning via LegalBench** (CC BY 4.0,
real, low hundreds of usable items after curating down to actual fixed-choice subtasks -- most
LegalBench tasks aren't classic MCQ -- and must explicitly exclude any subtask built on ContractNLI
since that's already used by this project's `checklist_contractnli` set). One tempting compromise
flagged, not resolved: **ESG/ESGenius** (1,136 real, recent-2025 items, genuinely new ground) but
its questions are LLM-*generated*, only expert-*validated* afterward -- a real deviation from the
"no manufactured content" standard every other set here holds to. **Not decided**: whether to take
just LegalBench (~100-250 items), also accept the ESG exception, or search the domains the fork
didn't get to (real estate, corporate governance, risk management, auditing-vs-accounting).

**Coding/architecture decision-making** (identified as a real gap, research explicitly deferred to
a fresh session -- nothing built yet): user asked "is there a security coding dataset," which
turned out to already exist and already be fully run -- `memsafety` (NIST SARD Juliet Test Suite
for C/C++, public domain, 154 items) and `websec` (OWASP Benchmark Java v1.2, GPL-2.0, 80 items)
are both complete across all 9 models today, currently living under "Security audit" in the main
"All sets" page, not yet folded into World Knowledge. **A striking real finding surfaced while
checking this**: most models sit at or near 50% (chance) on real vulnerability detection --
Verdict 50/48%, kev-0.5b/0.8b 50%/50-51%, jeff 49%/55%, Laya 54%/50% -- only Jev (82%/76%), so1
(66%/61%) and kev-4b (66%/61%) show real signal above chance on memsafety/websec respectively.
Proposed folding these into World Knowledge as a 5th "Security & code" category (zero new spend,
pure UI wiring, same pattern as the 4 MMLU categories) -- **not yet built, needs user confirmation**.

But the user then clarified that's not actually the gap they meant: memsafety/websec test "is this
code vulnerable," not the "computer software problem solving, algorithmic detection" they're after
for routing coding decisions inside an agentic framework -- something closer to solutions-architect
judgment (does the model know that "healthcare + audit trail" points toward a modular monolith on
managed Kubernetes rather than JAMstack, that edge compute means a per-request CPU cap rather than
a wall-clock timeout, etc.). User shared a real external reference file (`kit_playbooks.yaml`, from
an unrelated project of theirs -- architecture patterns, hosting models, tooling, industry
defaults) purely as an illustration of the target depth, not as source material -- correctly flagged
that this file itself can't be used as a benchmark source even though it's well-constructed,
because its "gold answers" are self-authored defaults, not an independent published benchmark
(the same reasoning that already downgraded this project's own old `probes/build.py` hand-written
sets). **No public, licensed benchmark for architecture/systems-design decision reasoning is known
to exist yet** -- closest real-world analog (cloud certification exams: AWS/Azure/GCP solutions
architect) is vendor-proprietary, same "gated behind a certifying body" pattern the business-domain
search kept hitting. Also surfaced, but not yet acted on: Humanity's Last Exam (flagged and set
aside during the business-domain pass) might fit a *different* axis -- "esoteric synthesis" of
disjoint sparse knowledge (the user's own SIMD-MIMD/hyperplane/multi-zone-crypto example) rather
than general world-knowledge coverage, and probably shouldn't be conflated with the architecture-
decision-reasoning search into one "hard questions" bucket.

**A conceptual thread worth preserving, not yet formalized into anything built**: the user's own
"shotgunning" framing (break a compound, unanswerable question into atomic binary sub-decisions,
compose the final answer deterministically from primitives each answered with real confidence) is
already exactly what "Decompose and loop" does in this codebase -- not a new mechanism to build,
a new way to *frame* validating existing decomposition capability. Reframes "should we test compound
architecture-decision knowledge" into two more tractable, separable questions: is the model
well-calibrated on atomic technical primitives (MMLU-subject-style, more findable), versus can it
safely synthesize sparse disjoint knowledge under compound constraints (harder, maybe no clean
dataset exists, HLE is the closest known candidate).

**Explicitly told to stop here and start fresh**: user wants a new session/context before either
research thread (architecture-decision benchmark search, or the LegalBench/ESG decision) is
picked up, plus a forward-looking note about eventually deploying this console publicly (mentioned
Cloudflare) "so people could see the overall approach" -- not scoped or started, just the stated
direction for whenever that comes up.

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

## Fifth round: the same readability pass, extended to Monte Carlo and Custom Decomposition

The user liked the Decompose page's redesign and asked for the same treatment on the other two
"Decomposition structures" pages, for consistency across the whole group. Both now use the same
`chapterHeader()`/`soWhat()` vocabulary from the Decompose pass, adapted to each page's own shape:

- **Monte Carlo**: now 3 numbered chapters, same pattern as Decompose --
  "Chapter 1 of 3: Where this comes from" (data provenance, so-what: this only works because real
  durations/edges exist for this one plan), "Chapter 2 of 3: One number becomes a range" (histogram,
  so-what: the deterministic-vs-sampled gap), "Chapter 3 of 3: What actually drives the risk"
  (Gantt + criticality table + hidden-risk finding + release-train recommendation, so-what: the
  release train's #1 pick, restated crisply). Three so-whats, three different `--sN` tones (amber,
  rose, orange), none repeating each other's wording.
- **Custom Decomposition**: adapted rather than copied verbatim, since this page is an interactive
  tool, not a fixed report -- results only exist after a run, so the chapter headers for its two
  result phases ("Chapter 1 of 2: What we found" / "Chapter 2 of 2: What it might cost") are now
  injected as the first child of `readoutBox`/`scheduleBox` on the `ev.t === "end"` (and, for
  chapter 1, also the streaming `"node"`) handler, rather than as static page furniture -- so they
  only appear once there's real content to sit under. `customReadout()`'s existing "highest risk"
  paragraph became a proper `soWhat()`; `customScheduleSection()` gained a closing so-what for its
  own top-criticality item, mirroring Monte Carlo's chapter 3.
- **A real CSS bug caught and fixed along the way**: the original `.chapter:first-of-type` rule
  (added during the Decompose pass) zeroes a chapter's top margin so the very first chapter of the
  page sits flush under the cover section. That's correct for Decompose/Monte Carlo, where the
  first chapter really is the first `.chapter` element on the page -- but Custom Decomposition's
  `readoutBox`/`scheduleBox` are separate re-rendered `<div>`s, so their chapter headers would also
  have matched `:first-of-type` (scoped per parent, not per page) and lost their spacing right
  after real content (the map). Fixed by replacing the automatic `:first-of-type` selector with an
  explicit `chapter-first` modifier class, passed only on the two calls that are genuinely first on
  their page (Decompose's Chapter 1, Monte Carlo's Chapter 1) -- Custom Decomposition's two chapter
  calls correctly keep normal spacing.

Verified live: ran a real decomposition (60 then querying at completion, cf-memory text, 68/111
items reached) and confirmed both chapters render with correct spacing and both so-whats show
real computed data (highest-risk item, top-criticality schedule item); Monte Carlo's three
chapters and three so-whats all render with distinct tones; no console errors on either page.
Real server restarted via `./start.sh restart`.

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
