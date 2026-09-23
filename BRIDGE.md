# BRIDGE: where we are, for the next session

Updated 2026-09-23. Read `CLAUDE.md` too. This file is the narrative; `foundry/PLAN.md` is the
actionable backlog (tagged DONE/DECISION NEEDED/READY/NEEDS DIAGNOSTIC) — read both, don't assume
this file duplicates it. **Two active threads now, not one**: `/workspace/foundry` (the
tool-driven idea-decomposition pipeline) and `/workspace/demo`'s Scenario lab / decompose-and-loop
work (`demo/scenarios.html`, `probes/lab_decompose.py`, `probes/decompose/`) — previously paused,
now explicitly back in scope. The user's own framing for next session: **"learn from our foundry
and update the demo"** — cross-pollinate lessons between the two, direction not yet fully decided
(see "The two threads, and how they relate" below).

## Starter prompt for the next session (paste this)

```
Read /workspace/BRIDGE.md, then /workspace/foundry/README.md, then /workspace/foundry/PLAN.md, in
that order. Read foundry/README.md's "one rule that matters most" before touching anything -- you
author exactly the idea+customer intake and fixed, generic, reusable candidate library content,
nothing idea-specific, ever.

Verify state first: `demo/lineup.sh status` (kev-4b is down -- see "Infrastructure" below, real,
not yet fixed), `git status` (should be clean), and run the FOUR-command pipeline once:
    cd foundry
    python3 layered_walk.py --idea oncall-rotation --budget 80
    python3 report.py --idea oncall-rotation
    python3 sort_and_rank.py --idea oncall-rotation
    python3 monte_carlo.py --idea oncall-rotation
(Note: it's four commands now, not three -- monte_carlo.py is new this session.) Report in a few
lines what's loaded and whether it ran clean before doing anything else.

Then read `foundry/comparisons/jev-monte-carlo-showcase-2026-09-22.md` (real output across all 7
ideas) and skim `probes/lab_decompose.py` + `probes/decompose/build_tree_edge.py` (the
decompose-and-loop system -- real CPM scheduling, hand-authored ground truth, already more mature
than foundry in some ways) before deciding what "learn from foundry, update the demo" actually
means to build. See "The two threads, and how they relate" below for what's already known about
the gap between them.

Constraints, unchanged: no hosted-model spend from any script's own environment (P0/jev requires
the person to source /workspace/.env in THEIR OWN shell first -- never read or relay the key
yourself). Never restart demo/server.py while an experiment runs through it (it's currently
running, has been since before this session -- don't kill it). Timeout on every wait, check `ps`
afterward. Commit locally with the Co-Authored-By trailer -- the environment auto-commits
periodically (harmless, already observed twice more this session) but don't rely on it instead of
committing real milestones yourself.
```

## Infrastructure: kev-4b is down, real, not fixed

An oversized diagnostic batch (40 questions/call, well above anything this pipeline normally
sends) pushed `kev-4b` into a CUDA OOM state this session. A restart attempt then failed to reload
it, because the other 4 loaded models already hold the GPU memory it needs at startup (documented
requirement: it must load first, before the other four). It's stopped cleanly, not crash-looping.
**Recovery needs restarting the full lineup in the documented order** (`demo/lineup.sh`) — a
bigger action than the one service that broke, not done without the user's go-ahead. Every run
this session since has used 2 of 3 default models; `call_all`'s existing per-model error tolerance
handled it gracefully throughout, but any diagnostic needing all 3 (the atomic-gate threshold
question, Sorter risk-tier calibration) is still waiting on this.

## Foundry: the guide

**Four commands now**, always, from `/workspace/foundry`:
```bash
python3 layered_walk.py --idea <id> --budget 80      # Slicer + Grinder -> ledger
python3 report.py --idea <id>                          # renders the ledger as tables
python3 sort_and_rank.py --idea <id>                    # Sorter scoring, now persists to
                                                         #   runs/<id>-sort.jsonl
python3 monte_carlo.py --idea <id>                       # NEW this session -- qualitative
                                                          #   risk-concentration pass
```
`--models` on the first and third: comma-separated P-numbers or backend ids (`--models P0,P1`
etc.), default `P1,P2,P3` (semif/kev-4b/so1).

**The walk mechanism was rewritten this session** — see "This session's major work" below for the
full reasoning. In short: `layered_walk.py` no longer picks a fixed top-4 `gap_categories` from
one pooled ranking and walks each with a fixed top-k of children. It now (a) groups the 21
categories by their `shape` field and guarantees a top pick from every one of the 6 shapes, and
(b) drains the whole tree via one shared priority queue until the real budget runs out, not until
an artificial per-node k is exhausted. Verified: `oncall-rotation` went from 1 requirement / 18-of-80
budget spent to 13 requirements / 80-of-80 spent, all 6 shapes represented.

**Model selection**: default P1/P2/P3, grounded in `probes/report_v2.py`'s validated measurement
(1,437 items). laya (56.9%) and verdict (46.7%) excluded by default — independently re-confirmed
this session by a *completely different* harness: `probes/decompose/`'s live-run results show
laya/verdict stopped at the root of a 31-node reference plan (judged the whole thing "atomic",
avg depth 0.0) while semif/kev-4b/so1 correctly recursed to depth 2.0. Same two weak models,
different task, different codebase — strong convergent evidence.

**Hosted Jev (P0)**: works for `layered_walk.py`, user-run in their own terminal only. **Known bug,
still not fixed**: `sort_and_rank.py --models P0` silently scores nothing (`funnel.bounce_and_weigh`
skips any `hosted` backend, `funnel.py` line ~162) — `layered_walk.py` has no such skip. Blocks a
real P0 Sorter/risk-tier calibration until fixed.

## This session's major work (condensed — full detail in commit messages and PLAN.md)

Picking up from the prior BRIDGE.md (gap-1 retirement, 7-idea run, both already committed):

1. **A real bug found by a second content-review pass, not by testing**: `walk()`'s breadcrumb
   told every recursive call "Established so far: `<gap text>`" — asserting each selected gap was
   *true*, when it was selected precisely because a live call judged it *not* true. Same class of
   bug as the original polarity contradiction, now in state-building code instead of authored
   content, invisible to "read the rendered output" checks since this string never reaches
   `report.py`. Fixed.
2. **The atomic-gate diagnostic ran for real** (`diagnose_atomic_gate.py`, now committed): 90
   known-atomic leaves vs. 21 known-compound categories, reproduced twice. On 2 of 3 models,
   separation is +0.006 — noise-level. `ATOMIC_THRESHOLD=0.18` scores 21.6% accuracy on these
   controls, worse than the 81.1% you'd get by calling everything atomic. **Not yet acted on** —
   the decision (drop the gate vs. re-threshold) is pending kev-4b's data.
3. **An Opus arbitration of a user-proposed "OpenAI loop" design** (`foundry/tools/OPENAI-LOOP.md`,
   committed) against the current mechanism found the real search space is only 113 live calls
   total, and the old walk spent only 18 of an 80 budget (22.5%) — reframed the whole debate. Real,
   adopted findings: a priority-queue walk (built, see below), and — independently, from the
   user pushing back hard on the arbitration being too conservative — the diagnosis that the
   real fix was **shape-guaranteed selection using `gap_categories`' own `shape` field**, which
   existed in the yaml but was never actually read by any code before this session.
4. **The priority-queue + shape-guaranteed rewrite**, built and verified: replaced `GAP_TOPK`/
   `CHILD_TOPK_BOOSTED`/`CHILD_TOPK_NORMAL` (three undiagnosed constants) with shape-guaranteed
   seeding + one shared max-priority queue draining by budget. Also replaced `DOMAIN_AUDIENCE_FLOOR`
   (flat 0.6, confirmed discarding real signal — oncall-rotation's 55% and standup-async's 39%
   domain confidence were both thrown away) with a margin-based trust rule. Added a
   `decomposition_depth` score signal (informational only, not yet load-bearing). Verified across
   all 7 ideas: every run now uses close to its full budget; `oncall-rotation` 1→13 requirements,
   `sleep-coach-wearable` 0→4.
5. **A demo qualitative Monte Carlo risk-concentration pass**, built after checking a specific
   factual claim first: PMBOK draws a real line between *qualitative* risk analysis (ordinal
   scores, relative prioritization, no units — what foundry's data can honestly support) and
   *quantitative* risk analysis (where "Monte Carlo simulation" is a named technique needing real
   time/cost estimates — what this project has already refused to fabricate twice, see
   `tools/monte-carlo.yaml`'s `methodology_note` and `probes/lab_decompose.py`'s own docstring,
   independently making the identical argument). Built the qualitative version only:
   `monte_carlo.py` samples each requirement's live risk/effort score as a distribution, ranks
   categories by contribution to simulated exposure *variance* (real sensitivity analysis, not
   just re-sorting by mean), and translates onto a real, cited illustrative scale (COCOMO Organic
   mode, Boehm 1981, verified against real sources — 10 KLOC → ~27 person-months — explicitly
   never a claim about any idea's real size). `sort_and_rank.py` now persists its scoring
   (`runs/<id>-sort.jsonl`) — previously printed to terminal scrollback only. Verified across all
   7 ideas including 2-requirement edge cases, no failures. Full writeup with real numbers:
   `foundry/comparisons/jev-monte-carlo-showcase-2026-09-22.md`.
6. **A second-review pass on `world-knowledge.yaml`'s content** (separate from the bug in #1 it
   found) identified ~15-18 specific leaf-text edits, 3 confirmed-wrong `profile_probes` boost
   mappings (`offline-capable→nonfunctional-availability` was putting server-uptime requirements
   on two on-device ideas with no server — confirmed in real run data), 5 categories that should
   plausibly get a boost and don't, and 2 `domain_enrichment` errors. **None of this applied yet**
   — full list in `foundry/PLAN.md`.
7. **A user-created idea, `ideas/cf-memory.json`** (a distributed ML-training pitch on Cloudflare
   Edge Workers), turned out to be the *exact same pitch*, verbatim, already used as the reference
   plan in `probes/decompose/build_tree_edge.py` — see next section.

## The two threads, and how they relate

`probes/lab_decompose.py` + `probes/decompose/` (`build_tree.py`, `build_tree_edge.py`) is a
**separate, already-more-mature decomposition system**, live in `demo/scenarios.html`'s Scenario
lab page. Read before assuming foundry is the only or the most advanced thing in this repo. What
it has that foundry doesn't:

- **A hand-authored reference tree with real, planted ground truth** (`atomic_ref`, `covers_ref`,
  `gate`, `phase`, `dependency_ref`, `complexity_ref`) — used to actually *grade* each model
  against a known-correct answer. Foundry has no ground truth anywhere in its pipeline.
- **A real CPM (Critical Path Method) schedule** — forward/backward pass, float, critical path,
  duration sensitivity (1.5x/2.0x) — computed once, deterministically, over hand-estimated
  durations and real finish-to-start/start-to-start predecessor edges, never touched by a model.
  This is the legitimate *quantitative* technique foundry's Monte Carlo explicitly can't do yet
  (see work item #5 above) — done here, because real duration estimates exist (one engineer's
  judgment, explicitly labeled as such) where foundry has none.
- **A deliberately planted, technically real coverage gap** (`sys-train`'s children don't address
  concurrent-writer conflicts) as a genuine test of whether a model catches a real hole.
- **A documented bug fix in the CPM code itself** (an "informs"-edge bound error, per the commit
  "immediately caught a scheduling bug") and 5 prior commits of real iteration, including a
  5-agent adversarial review that rebuilt the whole reference plan.
- Already run live: `data/probe-runs-v2/_decompose/tree_scored_edge.json` has real per-model
  results. laya/verdict stopped at the root (avg depth 0.0, judged the *entire* 31-node plan
  atomic); semif/kev-4b/so1 correctly recursed to depth 2.0 — see "Model selection" above.

What foundry has that this doesn't: a **generic, reusable candidate library** (the 21
`gap_categories`) that works across any idea without hand-authoring a new tree each time. The
decompose-and-loop system's plan is a one-off expert artifact for one pitch — rich, but not a
repeatable mechanism the way foundry's `world-knowledge.yaml` is.

**"Learn from our foundry and update the demo"** — not yet resolved into a concrete task. Two
readings, both legitimate, not yet chosen between:
(a) Port foundry's *generic* discipline (a reusable category library, the shape-guaranteed
selection fix, the honesty patterns) into the decompose-and-loop system, so it stops needing a
fresh hand-authored tree per idea.
(b) Port the decompose-and-loop system's *real* CPM/dependency/phase machinery into foundry, since
`depends_on` has been empty everywhere in foundry all session and `slicer.yaml`'s `by-phase`
variant (spike/decide/build/validate/launch — the exact same taxonomy already live in
`build_tree_edge.py`) has never been wired up.
Next session should read both systems properly (this file's summary is not a substitute) and
decide with the user which direction, or both.

## Gotchas learned the hard way (this session, in addition to the prior list still below)

- **A methodology critique can be right about the specific numbers and wrong about the
  architecture underneath them.** The Opus arbitration correctly refuted OpenAI's specific
  thresholds and formula, but under-credited the structural idea (priority queue, shape-based
  organization) — caught only because the user pushed back hard and insisted on re-examining it,
  not because the review caught its own blind spot.
- **Measure the actual size of the thing before evaluating whether a control structure fits it.**
  The whole "priority queue vs. fixed top-k" debate was decided by one number nobody had checked:
  the real search space is 113 calls, not the hundreds either side's mental model assumed.
- **A real external methodology claim (PMBOK's qualitative/quantitative split, COCOMO's Organic
  mode) is worth 5 minutes of verification before either building on it or rejecting a request
  that turns out to rest on it.** The Monte Carlo conversation only converged once the actual
  distinction was checked against real sources instead of argued about in the abstract.
- **An oversized batch to a memory-constrained local model can cascade**: one oversized diagnostic
  call OOM'd kev-4b, and the *fix attempt* then failed because of an ordering dependency
  (kev-4b must load before the other four) — the failure mode compounded past the original mistake.
- **Two independent systems in the same repo, built for the same underlying task, can go
  unnoticed until someone runs the same pitch through both** — foundry and `probes/decompose/`
  coexisted all session without either being checked against the other, until the user's own
  `cf-memory.json` idea happened to be verbatim identical to an existing reference plan.

## Gotchas learned the hard way (prior sessions, still true)

- **A live, well-formed classifier mechanism over broken content still produces broken output.**
  "The tools ran live" is not the same claim as "the output is coherent."
- **A magic threshold tuned against one model or one small diagnostic does not generalize.**
  Re-diagnose, don't reuse, when the model combination changes.
- **Information already in the data structure beats another round of threshold-tuning.** The
  leaf-vs-category fix (structural) mattered more than any threshold value; the shape-guaranteed
  fix (also structural, this session) mattered more than the priority-queue mechanics around it.
- **Cross-model disagreement can mean one model isn't discriminating at all**, not genuine
  ambiguity — found via controlled diagnostics against known controls, twice now (atomic/compound
  text this session, the original P3 diagnosis before it).
- **A YAML file can silently fail to parse, or silently collapse structured data into a string.**
  Re-parse with the real loader after every edit.
- **Reading whether a credential exists is itself a blocked action**, separate from and prior to
  whether a call using it would be blocked.
- **A one-paragraph idea pitch structurally lacks spec detail**, so spec-completeness categories
  look like gaps for almost any idea regardless of what actually matters — only visible by running
  a genuinely varied idea set, not one idea repeatedly.

## Real gaps, prioritized — see `foundry/PLAN.md` for the actionable version

This file no longer duplicates the full list (it did, and immediately went stale relative to
PLAN.md the moment PLAN.md started tracking real-time status). Headline items still open:
kev-4b recovery; the `ATOMIC_THRESHOLD` drop/re-threshold decision (data in hand, pending kev-4b);
the ~15-18 world-knowledge content edits (identified, not applied); `sort_and_rank.py`'s hosted-skip
bug; a real second review of the 21-category library (one Opus pass only, still); and now, the
foundry/decompose-and-loop cross-pollination direction above.

## Scenario lab

No longer "separate, still paused" — see "The two threads" above. `docs/scenario-lab-plan.md` is
the original plan document if useful context, but read `probes/lab_decompose.py` and
`probes/decompose/build_tree_edge.py` directly before trusting any older summary of what's there.
