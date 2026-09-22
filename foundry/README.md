# The Foundry

Command-line prototype of a factory-line idea-decomposition pipeline. Its own folder on purpose --
not wired into the demo (`demo/`) or the Scenario lab's probe sets (`probes/`) yet, so it can be
iterated on freely without touching either.

## The premise

Given any problem, decompose it the way a developer actually works: cut the problem space (usually
in half or thirds), recurse depth-first into one piece until it stops getting any smaller ("no real
lowering down"), then shift perspective and turn that atomic piece into a requirement. Do this fast
enough and the whole idea maps to a structured requirement list "in seconds," each requirement with
a measured confidence, laid out against a standard development window (phases, dependencies,
schedule). Visualize the tools running live -- the tree filling in on one side, requirements
appearing on the other, as it happens.

Two things are explicitly *not* claimed yet: a live Slicer (see below) and a calibrated schedule-
slip forecast from a Monte Carlo simulation. The latter needs a real reference dataset of past
projects' requirement coverage vs. actual delivery slip to mean anything -- without it, quoting an
"X% schedule expansion" number would be exactly the fabricated-precision mistake the CPM
decompose-and-loop page already made and killed once (see `probes/lab_decompose.py`'s docstring).
What the pipeline *can* honestly compute today is the coverage gap itself and per-requirement
confidence -- both real, neither requiring that dataset.

## The tool vocabulary (factory theme)

**Capped at five tools, five variants each, on purpose** -- "we're not going to create an
exhaustive kit... make it simple, and let's see what we get at the end to figure out what the
gaps are." Registered as YAML in `tools/*.yaml`. The guiding rule for every variant: minimal
agentic reasoning, maximal predefined scaffolding -- only Slicer's initial cut and Grinder's
atomic-check genuinely need a live judgment call; grouping, sequencing and ranking downstream
should all be deterministic rules over data the pieces already carry, never a fresh live call of
their own.

The original seven collapsed into five by reuse, not by cutting capability: Bouncer's one
mechanism (a live yes/no question) is exactly what Grinder's atomic-threshold variant already
needed, so it moved there instead of staying a separate tool. Weigher and Welder merged into
Sorter (score + group, one tool). Conveyor absorbed timing ("how long for this") on top of its
old sequencing job. Spotlight stayed separate from Conveyor on purpose -- "how sure are we" and
"how long will it take" are different questions and merging them would hide one behind the other.

| Tool | Does | Status |
|---|---|---|
| **Slicer** | idea/piece -> first-pass pieces, with dependency edges (+ optional persona/lens tags) | **stubbed, 5 variants** in `tools/slicer.yaml` (binary-halving, by-layer, by-risk, by-phase, by-domain); all manual, no live call. by-domain now reads `tools/customer-lens.yaml`'s fixed pain-point/delight/journey list instead of inventing guesses fresh each run. |
| **Grinder** | re-slice one piece that's still too coarse, recursively, until atomic (also: absorbed Bouncer's old yes/no stopping check) | **3 variants** in `tools/grinder.yaml` (fixed-depth, atomic-threshold, irreducible-fact); none wired to live recursion yet |
| *(unnamed)* | perspective shift at an atomic piece -> a requirement statement | **not designed yet** -- current pieces stop at "atomic claim," not "requirement." Still the real open gap, not a tool-count question. |
| **Sorter** | score each piece live (Weigher's old job) + group pieces by shared need (Welder's old job) | scoring **live** (`funnel.py`'s `bounce_and_weigh`, one noul + one score question per piece per model); **5 grouping variants designed**, none built, in `tools/sorter.yaml` (by-mean-risk, by-persona, by-phase, by-lens, by-risk-tier) -- all deterministic over existing piece metadata |
| **Conveyor** | sequence Sorter's groups + estimate how long each takes | dependency-order **live** (on raw pieces still, not yet groups); **5 variants designed** in `tools/conveyor.yaml` -- duration-weighted and critical-path explicitly **not populated**, no real duration source exists yet |
| **Spotlight** | rank what most needs answering -- risk + cross-model disagreement | risk-plus-disagreement **live**; **5 variants designed** in `tools/spotlight.yaml`, all computable from data Sorter already produces, no new live call for any of them |

`tools/customer-lens.yaml` is not a tool itself -- it's the predefined scaffolding by-domain (and,
downstream, Sorter's by-persona/by-lens) reads from: ~16 pain points, ~10 delights, a 6-stage
generic customer journey, all cross-domain and deliberately not exhaustive.

No Monte Carlo forecast, no confidence interval, no combined "probability of success" number.
Considered and deliberately dropped for the per-idea case: the local models' probabilities aren't
shown to be calibrated (only the hosted model's confidence has ever been shown usable for routing,
per `BRIDGE.md`), there's no ground truth for a novel idea, and the CPM decompose-and-loop page
already killed a fabricated confidence number once for the same reason. The premise's *reframed*
Monte Carlo -- calibrating "requirement-coverage gap" against real historical delivery data, not
sampling this idea's own numbers -- stays aspirational until that reference dataset is found.

## Slicer variant comparison (first finding)

Applied all five original Slicer variants to the same idea (`comparisons/slicer-variants-voice-extension.json`).
All five *can* cut any idea -- that part is settled. What differs is what falls out the other end:
`binary-halving`/`thirds` are coarsest, closest to how a person actually starts, but need the most
Grinder passes before anything is requirement-shaped. `by-risk` front-loads prioritization into the
tree shape itself (Spotlight becomes almost redundant) but produces a lopsided tree, bad for
schedule-mapping. `by-layer` and `by-phase` both produce something requirement-shaped in one pass:
`by-layer` is what every `problems/*.json` file already does by hand and is proven against live
Bouncer/Weigher across 5 problems now; `by-phase` reuses `lab_decompose.py`'s own phase taxonomy and
maps directly onto "a standard development window." **Tentative conclusion: by-layer and by-phase
are the two worth taking further; binary-halving/thirds/by-risk look more like an outer loop that
decides when to switch layers/phases than a primary cut.**

A sixth variant, **by-domain**, was added afterward (domain-driven design: classify domain,
personas and value-per-persona *before* cutting technically, then pull in requirements typical of
that domain+persona combination even if the idea's own wording never states them). Tested against
`shift-swap-marketplace` (`comparisons/by-domain-shift-swap-marketplace.json`), comparing its output
to that same idea's existing by-layer cut: **it surfaced 5 plausible requirements by-layer's
technical framing missed entirely** (swap visibility, a fairness log, manager override-after-the-
fact, a minimum-notice window distinct from the hours threshold, mobile notification given the
persona is rarely at a desk) -- mostly by covering personas (the claimer, compliance) that by-layer
skipped. Real result, but the honesty flag on it is sharper than the other variants': this is
"plausible to an LLM with general domain familiarity," not verified against anything. Shift-swap
software is a well-worn category, which makes the guess easy and hard to fully trust at once --
the next real test is a domain that's less common, where the variant either earns its keep or
reveals it's just generating plausible-sounding filler.

## Problem set

`problems/*.json` -- five ideas across different domains, each hand-decomposed by Claude offline
using the by-layer Slicer variant, tagged with its own `source` field. Shape:

```json
{
  "id": "...",
  "idea": "<=500 chars",
  "source": "how this was produced",
  "pieces": [{"id": "...", "text": "the claim", "depends_on": ["other piece ids"], "lens": "business|technical"}]
}
```

`lens` is now set on all 25 pieces across the 5 files -- it drives the story's two-thread split
(see "Output philosophy" below).

`ideas/*.json` -- raw, **unsliced** problem statements, conversational going forward (however a
real business owner would actually describe their own idea -- a paragraph, a bit loose, vague on
*how* not just *what* -- still under 500 chars). Idea text only. No pieces, no decomposition claim.
This is the honest queue: something lands here first, and only moves to `problems/` once it's been
decomposed by something other than the same author grading their own homework -- see the
correction directly below for why that distinction now matters.

### Slicer honesty correction

An earlier version of this file claimed running `plumber-crm` through the pipeline tested how well
the system handles conversational input -- it didn't. The idea and its pieces were written by the
same author (me), in the same act, with full knowledge of what would make the pieces score well
downstream. That's not a decomposition test; it's grading my own homework, correctly labeled
`source: hand-authored` but framed as evidence about something it never touched. Caught, correctly,
by the person reading the file.

This applies to every `problems/*.json` entry, not just that one: **none of them are evidence that
Slicer can decompose an idea well**, because in every case the same author wrote idea and pieces
together. What *is* real and unaffected: Bouncer/Weigher/Conveyor/Spotlight's live behavior given a
set of atomic claims, whoever supplied them -- those come from real, independent model calls with
no part in authoring the pieces, so every finding about `so1`/`verdict`/agreement patterns/etc.
still stands. What's not tested by any run so far, and won't be until there's a genuinely
independent Slicer step (a live API call, or a human/different process supplying pieces blind to
what "should" be there): decomposition quality, coverage, or faithfulness to the source idea.
`plumber-crm.json` moved to `ideas/`, unsliced, pending that.

A live Slicer (once there's an API key, and a variant is picked) can replace the file loader in
`funnel.py`'s `load_problems()` without touching Bouncer, Weigher, Conveyor or Spotlight.

## Output philosophy (direct user correction -- read before changing rendering code)

Earlier output was backwards: decimal numbers and model codes leading, the decomposition itself as
an afterthought. Corrected per direct instruction -- **the decomposition is the front-facing value,
told as a story anyone can read without explanation.** No model names, no percentages, no legend
leading the output. Concretely:

- **P0-P5, never a model name, in the story.** P0 is always the hosted reference (JEV113, never
  called). P1 through P5 are the five local models, in a *fixed* leaderboard-based order that never
  changes between runs -- so P1 always means the same model. The mapping is stated once, in the
  technical detail section, not repeated per piece.
- **Per piece, one plain verdict, no decimals**: *Confident & aligned*, *Confident, but the models
  disagree*, or *Not confident yet* -- computed from `CONFIDENCE_THRESHOLD` (mean supported-p) and
  `DISAGREEMENT_THRESHOLD` (model spread), both named judgment calls in `funnel.py`, not measured
  constants.
- **Business and technical pieces are shown as two separate threads**, using each piece's `lens`
  tag (now set on all 25 pieces across the 5 problem files), reading in Conveyor's dependency order
  rather than raw file order.
- **Everything numeric still exists** -- in a "TECHNICAL DETAIL" section that comes *after* the
  story, never before it, for verification, not as the lead. `pipeline.json` keeps full detail;
  `story.md` (replacing the old `trace.md`) is the human-facing story alone, no technical section.

**Open problem found on the first run under this design:** every piece on `shift-swap-marketplace`
came back "Confident, but the models disagree" -- none landed on "Confident & aligned." With 5
genuinely different models (one often near 0.2-0.6 while two others sit near 0.9-1.0), spread
above the current 0.3 disagreement bar looks close to inevitable regardless of the piece, which
means "aligned" may never actually trigger as designed. Undecided: raise the bar (e.g. 0.5), or
measure agreement a different way (median-based, so one outlier model can't blow it out alone).

## Run it

```
python3 foundry/funnel.py --list                   # numbered menu of problems/*.json
python3 foundry/funnel.py                          # every problem in problems/
python3 foundry/funnel.py --problem 5               # by number, per --list
python3 foundry/funnel.py --problem standup-async   # or by id
python3 foundry/funnel.py --models kev-4b semif
python3 foundry/funnel.py --bouncer-variant strict  # the old, harder-to-satisfy phrasing (diagnostic only)
```

Local, free, loaded models only (`kev-4b`, `semif`, `so1`, `laya`, `verdict`). The hosted model
(`jev`) is not reachable from this CLI at all -- not just a convention this script follows, the
environment's own permission classifier blocks hosted spend from a script outright. Getting Jev's
own numbers into this comparison means a UI-confirmed run through the demo server, never here.

Every run writes its own folder under `runs/` (gitignored -- regenerated output, not curated
content), named `<problem_id>__<bouncer_variant>__<timestamp>` so nothing ever clobbers a previous
run of the same problem, even under a different phrasing:

```
runs/shift-swap-marketplace__reasonable__20260922-102834/
  pipeline.json   # full structured detail, machine-readable
  story.md        # the human-facing story only -- no model names, no numbers, no technical section
```

## Findings from five problems, 25 claims, 5 models (125 live calls) -- under the strict Bouncer phrasing

Everything in this section was measured under the original `strict` Bouncer phrasing ("well-
supported enough to treat as true today, **without further verification**"). The Bouncer phrasing
check below found that phrasing to be a real confound -- read this section together with that one,
not on its own.

- `verdict` is flat: supported-p sits in a 0.66-0.70 band regardless of subject matter, and stayed
  flat even when the question itself changed (see below) -- the one finding from this section that
  held up under a controlled check, now on firmer ground than before.
- `so1` answered ~0.00 on every claim across all 25 -- **this specific claim is now retracted as
  stated.** Confirmed below: on `shift-swap-marketplace`, `so1` (OAJEV4) moved off flat-zero to
  real, content-tracking variation (0.32-0.62) the moment the question changed. It was very likely
  answering the strict question correctly, not failing to read the claim. Not re-verified across
  the other 4 problems yet -- treat the "always 0.00" claim as probably wrong, not confirmed wrong,
  until that re-run happens.
- Conveyor flattens branching dependency structure (a piece with two independent side-chains) into
  one line; whether that's the right display once a real Grinder makes trees deeper is open.
- The "perspective shift into a requirement" step the premise calls for doesn't exist yet -- every
  problem here stops at "atomic-ish claim," not "requirement." That's the next real gap, not the
  Slicer/Grinder variant question.

## Bouncer phrasing check -- run, and it overturned the leaderboard-mismatch finding

Nearly every piece Slicer produces is a *prediction about future behavior* ("employees will
actually use it"), not a verifiable present fact. The original Bouncer question asked for
something no forward-looking claim can honestly clear ("true today, without further verification").
`funnel.py --bouncer-variant reasonable` asks the same claims a different way -- "is this a
reasonable assumption to build the idea on, even if it hasn't been directly verified?" -- writing to
a separate run folder (`<problem>__reasonable__<timestamp>`) so it sits next to the `strict` run.

Run on `shift-swap-marketplace`, mean shift in supported-p across the 5 pieces, strict -> reasonable:

| Model | Leaderboard rank | Mean shift |
|---|---|---|
| SEMIF4 | #1 (67.5%) | **+0.89** (0.02-0.12 -> 0.90-1.00) |
| KEV4B | #2 (66.8%) | **+0.89** (0.00-0.02 -> 0.70-0.99) |
| OAJEV4 | #3 (64.8%) | **+0.48** (flat 0.00 -> 0.32-0.62, real variation appeared) |
| LAYA4H | #4 (58.4%) | +0.10 (0.09-0.62 -> 0.20-0.70, similar spread both ways) |
| VERD2H | #5 (46.7%) | **-0.01** (0.66-0.69 -> 0.66-0.68, no movement at all) |

**This overturns the earlier "leaderboard order doesn't predict this task's behavior" claim.**
SEMIF4 and KEV4B weren't degenerate under `strict` -- they were reading the question precisely
enough to notice it was nearly unanswerable, and jumped to near-ceiling with real variation the
moment it became satisfiable. The size of the shift itself now looks like a real signal of how
closely a model is parsing the actual question, and it tracks leaderboard rank almost
monotonically: the two best models reacted hardest, the middle model reacted moderately, and the
worst model (`verdict`) didn't react at all -- the same answer regardless of what was actually
asked. Leaderboard rank predicted this reasonably well once the phrasing confound was controlled
for; the earlier conclusion had it backwards because it was measured entirely under a question that
happened to punish precise readers.

**Not yet done:** re-run the other 4 problems under `reasonable` to see if `so1`'s pattern holds as
cleanly outside this one idea, and decide whether `strict` should stay the default anywhere, or be
demoted to its own diagnostic mode now that `reasonable` looks like the better-posed question for
Slicer's typically-predictive pieces.

## Queued (named, not yet built)

- **Depth-of-decomposition experiment** -- goal one from the fuller premise: push a real recursive
  Grinder (the `atomic-threshold` variant, since it reuses `lab_decompose.py`'s proven mechanism)
  as far as it actually goes on one problem, and find the real floor rather than assume one.
- **The requirement-extraction tool** (still unnamed) -- turns a bottomed-out atomic piece into a
  standard requirements-definition entry (id, description, acceptance shape), not just a claim
  sentence.
- **An architecture-rollup tool** (distinct from Welder, which propagates pass/fail down a
  dependency chain) -- clusters the finished, atomic requirement set back up into a proposed
  architecture. Needs its own name.
- **Reference-class Monte Carlo** -- not sampling this idea's own numbers (dead), and not
  necessarily a bespoke historical dataset either: match each atomic, typed piece against known
  industry-standard ranges for that *type* of task (a spike task, a compliance-review task, ...)
  and simulate from those. Real technique (reference-class forecasting), but the reference ranges
  still need to come from a named, real source before any number from this is trustworthy.
- **Cross-model-family framing** -- the `so1`/`verdict` findings above are really the first answer
  to "does this decompositional structure hold up across Jev-like models generally, not just the
  flagship." So far: unevenly. Worth stating explicitly as a tracked result, not just a data quirk.
