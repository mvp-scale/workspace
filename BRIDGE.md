# BRIDGE: where we are, for the next session

Updated 2026-09-23, end of a long session (started with an overnight autonomous build, continued
into live design collaboration with the user in a real Chrome browser). Read `CLAUDE.md` too. Full
detail for everything mentioned here is in the git log (`git log --oneline`) — this file is the
narrative and the one open decision that needs the user's input before real work starts.

## Where things stand

Everything from the overnight queue (5 Scenario-lab structures + the full custom-decomposition
feature) shipped, is live, and is documented in the git log and in
`docs/scenario-lab-structures-plan.md` / `docs/custom-decomposition-design.md` if you need the
detail. After that, this session did a live design pass on all 9 structures' "How this works"
diagrams together with the user, in a real Chrome session (not just automated screenshots):

1. **v1** (icons + legend): small icon badges above each connector, a legend underneath explaining
   them. Rejected on real feedback — icons weren't reading correctly at small size (the "route"
   fork icon looked like a pedestrian-crossing sign), and it wasn't compact.
2. **v2** (colour + elbow routing): dropped icons entirely — category is now carried by colour
   alone, reusing the app's existing `--s1`..`--s8` categorical tokens, deliberately avoiding
   `--good`/`--bad` (green/red) so a verb is never misread as a correctness signal. Branches and
   merges route as real right-angle "elbow" connectors with rounded corners (the actual flowchart
   standard), not raw diagonal lines. This direction came out of looking at real references
   together: AWS reference-architecture diagrams, C4 model container diagrams, and a Hugging Face
   blog's animated-SVG model visualizer (hfviewer) — the winning technique was "no icons, colour
   + a plain-text verb sitting directly on the line."
3. **v3** (compactness): every one of the 9 diagrams now shares one identical fixed canvas
   (`FLOW_W=760, FLOW_H=104` in `demo/scenarios.html`), with an explicit, deliberate type
   hierarchy (title 12px/700 weight, subtitle 9px, edge label 9px/700) instead of an inherited
   default size. A real shipped bug got caught and fixed in this pass: several verb/branch labels
   were wider than the gap between boxes and were rendering hidden behind the next box — every
   default verb word is now a single short word (ask/figure out/decide/sample/check), and every
   custom label was re-measured against its real available space.

**The shared toolkit** (all in `demo/scenarios.html`, search for these names): `FLOW_VERB_TOKEN`,
`FLOW_VERB_WORD`, `FLOW_W`/`FLOW_H`, `flowBox`, `flowArrow`, `flowElbow` (branch), `flowElbowIn`
(merge), `flowLine` (plain connector into a merge), `flowLoop` (self-loop), `flowHeader` (the
"How this works" card wrapper). Every structure's diagram is its own small `xxxFlow()` function
built from these. Read a couple of them (`hierarchyFlow()` for a branch, `baselineFlow()` for a
merge, `customFlow()` for a loop) before touching any of this — the pattern is consistent and
should stay that way.

**A real gotcha hit twice this session, worth remembering**: `demo/scenarios.html` is a
single-page app that only re-renders on a hash change. Navigating to the *same* `#set=x` hash
twice in a row (or reloading without `ctrl+shift+r`) does **not** re-fetch the file or re-render —
you'll see stale JS and think something's broken when it's actually just cache. Always hard-reload
or navigate away and back when testing a change.

**Also renamed this session**: "Funnel (Monte Carlo)" → **"Funnel (calibration forecast)"**. Real
catch by the user: what that structure does (sample two stored probabilities, forecast a compound
outcome, check calibration against what really happened) is genuine Monte Carlo *sampling* as a
technique, but it isn't the thing "Monte Carlo simulation" means in project planning (PMI/PMBOK),
which is the next task below. Same collision as foundry's own qualitative/quantitative distinction
from two sessions ago — a technique name getting reused for a different technique.

## The next task: build "Monte Carlo (schedule risk)" as its own new structure

This is real, well-defined, and buildable on real data already in this repo — not a foundry-style
fabrication risk, if scoped correctly (see the ground rule below).

**The real technique** (PMI/PMBOK: Monte Carlo Schedule Risk Analysis, aka QSRA): sample each
task's duration from a probability distribution (classically **triangular**: optimistic / most
likely / pessimistic) many thousands of times, run a real critical-path (CPM) pass on every
sampled set, and report two things instead of one deterministic schedule:
1. A **probabilistic completion distribution** ("80% chance of finishing within N days") instead
   of a single number.
2. A **criticality index** per task — the share of simulation runs where that task landed on the
   critical path. High-criticality-index tasks are the real, principled answer to the user's own
   "release train" framing: front-load whatever most consistently drives the schedule, because
   that's where delay cascades downstream most often. This is a standard, named technique, not
   something being invented for this repo.

**Where the real data already exists**: `probes/decompose/build_tree_edge.py` — the *only* place
in this repo with real, hand-authored per-task duration estimates (`duration_days`) **and** a real
dependency graph (`fs`/`ss`/`informs` predecessor edges) **and** an existing deterministic CPM
pass (its own `cpm()` function, already computing earliest/latest start/finish, float, and a crude
3-point sensitivity at ×1/×1.5/×2). This is the Cloudflare Edge Workers worked example, 31 nodes,
already live on the "Decompose and loop" Scenario-lab page.

**Ground rule — do not skip this**: foundry's ideas (`oncall-rotation` etc.) have **no** real
duration or dependency data at all. Do not fabricate any to make this technique "work" there too.
This technique can only be honestly built against `build_tree_edge.py`'s one real worked example,
exactly the same discipline that scoped Funnel to memsafety-only and Hierarchy to
persuasion_appeals-only this session — one real dataset, stated plainly, not generalized past what
the data supports.

**A real gap to resolve before writing simulation code — ask the user, don't guess**:
`duration_days` today is a single point estimate per task, not the three-point
(optimistic/likely/pessimistic) range real triangular sampling needs. Two honest options:
(a) hand-author real three-point estimates for the 24 leaf tasks (more work, the most honest);
(b) derive optimistic/pessimistic bounds from the existing point estimate via a stated, cited rule
(e.g. a documented PM heuristic percentage), clearly labelled as a rule, not an independent
estimate — the same honesty pattern foundry's `monte_carlo.py` already used for its COCOMO
illustrative-scale citation. **Ask which one the user wants before building.**

**One real open question, never pinned down — ask this first, before anything else**: does this
live as a **10th Scenario-lab structure** in `demo/scenarios.html`'s `STRUCTURES` array (reusing
the exact "How this works" diagram template just built — `flowBox`/`flowArrow`/`flowElbow`/
`FLOW_VERB_TOKEN`, etc. — for consistency with the other 9), or as a **separate page/section under
`probes/decompose`**, outside Scenario Lab entirely? Claude's own recommendation last session was
the latter (Scenario Lab's other 9 structures are all about benchmarking *model accuracy* on
published datasets; this is project planning, a different kind of tool, driven by hand-authored
data not model output) — the user said "I'm okay with that," but then used phrasing ("that
structure") that could mean they actually want it as a 10th Scenario Lab entry after all. This was
never explicitly confirmed either way. **Ask directly, first thing, in the new session.**

## Starter prompt for the next session (paste this)

```
Read /workspace/BRIDGE.md in full. Then read probes/decompose/build_tree_edge.py in full (the
real CPM/dependency/duration data this task builds on -- its cpm() function is what you're
extending from one deterministic run into many sampled runs). Skim demo/scenarios.html's
FLOW_VERB_TOKEN/flowBox/flowArrow/flowElbow/flowHeader helpers and one or two of the existing
XxxFlow() functions (hierarchyFlow for a branch, baselineFlow for a merge) so you understand the
"How this works" diagram template already shipped this session, in case the new structure needs
to match it.

First, before writing any code: ask the user directly whether "Monte Carlo (schedule risk)"
should be a 10th Scenario-lab structure in demo/scenarios.html, or a separate page/section under
probes/decompose outside Scenario Lab. This was left open at the end of the last session --
BRIDGE.md has the context, but don't guess at the answer.

Second, also before writing simulation code: ask the user which of BRIDGE.md's two options they
want for the optimistic/pessimistic duration gap (hand-author real three-point estimates for the
24 leaf tasks, vs. a stated/cited rule deriving a range from the existing single point estimate).

Then build the real technique: triangular-sample each task's duration many times, run
build_tree_edge.py's cpm() on each sampled set, report a probabilistic completion distribution and
a per-task criticality index (share of runs on the critical path) -- the real, principled basis
for a "release train" recommendation (front-load the highest-criticality-index tasks).

Ground rule, held all of last session, do not break it: only build this against
build_tree_edge.py's one real worked example (Cloudflare Edge Workers, 31 nodes) -- never
fabricate duration or dependency data for any foundry idea to make this "work" there too.

Verify everything live in a real browser before calling it done -- puppeteer is already installed
in this container (/tmp/pptr-test), or use the claude-in-chrome browser tools if available. Test
against a temporary demo/server.py instance on a spare port, never the real running one (port
8100), until the change is a pure static-file edit or you've confirmed the real process is safe to
touch. Remember the SPA gotcha: a same-hash navigate does not re-render -- hard-reload
(ctrl+shift+r) or navigate away and back between checks on the same page.
```

## Everything else still open, unrelated to the above (unchanged from before, still true)

`foundry/PLAN.md`'s own backlog: the `ATOMIC_THRESHOLD` drop/re-threshold decision (kev-4b's data
is available now, this is unblocked), the ~15-18 `world-knowledge.yaml` content edits identified
but not applied, `sort_and_rank.py`'s hosted-model-skip bug. `docs/scenario-lab-plan.md`'s original
backlog items 1-4, 14-18 (new probe sets, blind grading, jevbench version sync) remain untouched.
The custom-decomposition stretch goals (Board view, model-subset toggle, Numbers view,
compare-two-texts, ledger replay, leaf-level lift, hosted-model escalation) are still just that —
stretch goals, not started.
