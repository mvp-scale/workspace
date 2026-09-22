# The Foundry

A live, tool-driven idea-decomposition pipeline. Its own folder, separate from `demo/` and
`probes/` -- not wired into the Scenario lab, and shouldn't be until this is proven out further.

## The one rule that matters most

**Claude authors exactly two things: the idea, and the ideal customer/user. Nothing else.**
Every piece of an actual decomposition -- which categories apply, how deep it goes, what the
final atomic requirements say -- has to come from the tools running live against the loaded local
models, never from Claude writing plausible-sounding content and slotting it in as if the tools
had produced it. This was violated repeatedly before it was understood properly; see "Lessons
learned the hard way" below. If you're extending this and you catch yourself writing something
that looks like decomposition output, stop -- that's the one thing not allowed.

## What's actually validated and working right now

```
Two-question intake (idea, ideal customer) -- Claude writes only this, in ideas/<id>.json
        |
        v
Live Slicer (slicer_live.py) -- checks tools/gap-library.yaml's 12 generic, reusable gap
categories against the idea+customer, live, one noul call per category per model. Categories
clearing the confidence bar (0.6) become the decomposition. Nothing idea-specific is authored;
the library is fixed and reusable, the selection is live and per-idea.
        |
        v
Live recursive Grinder (grinder_live.py) -- for a selected category, recurses into a nested,
still-generic sub-library (e.g. tools/gap-library-single-point-of-failure.yaml), checking a live
"is this already atomic" question at every node before deciding whether to recurse further.
Breadcrumbs accumulate at each level; a finished piece's text is the concatenation of the fixed
library text along the path taken -- never something written for this specific idea. Hard budget
and max-depth caps; when a branch can't resolve, it says so honestly instead of being padded out.
        |
        v
Sorter (funnel.py) -- scores each resulting piece live: is it well-supported (Bouncer), how much
does it hurt if wrong (Weigher), how much resource does it take (a third axis). Grouping by
shared need is designed (tools/sorter.yaml) but not built.
        |
        v
Conveyor / Spotlight (funnel.py) -- dependency order and a "what to check first" ranking.
Duration-aware scheduling is designed (tools/conveyor.yaml) but has no real duration source yet.
```

Models are always referred to as P0 (the hosted reference, JEV113, never called -- the
environment's permission classifier blocks hosted spend from scripts outright) through P5 (the
five local models, in a fixed order by published leaderboard accuracy -- see `MODEL_META` in
`funnel.py`). The mapping is stated once per run and never repeated as a raw model name after
that.

## File map

```
ideas/*.json       Raw two-question intake (idea + customer). Claude's only allowed authorship.
                    "pieces" is either absent or explicitly "not decomposed."
problems/*.json     A finished decomposition -- currently only oncall-rotation.json, and it's the
                    only one produced by the live process end to end. Anything else here should
                    have been produced the same way, not hand-written.
tools/*.yaml        Tool definitions (5 tools, 5 variants each, capped by design) and the generic,
                    reusable candidate libraries (gap-library.yaml and its nested children) that
                    make a live Slicer/Grinder possible without a generative LLM call.
comparisons/*.json  Historical design exploration (how different Slicer variants would carve the
                    same idea) -- honestly labeled as hypothesis comparisons, not decomposition
                    output. Superseded by the gap-library approach but kept for the reasoning.
funnel.py           Sorter/Conveyor/Spotlight -- scores and ranks an already-decomposed problem.
slicer_live.py      The live Slicer: idea+customer -> selected Level 0 categories.
grinder_live.py     The live recursive Grinder: walks a nested library, breadcrumbs, budget-capped.
loop.py             Validator only: checks whether existing pieces are actually atomic, live.
                    Never authors content.
runs/               Gitignored, regenerated per run -- not durable, don't rely on anything here.
```

## The one worked example: oncall-rotation

`ideas/oncall-rotation.json` has the real two-question intake. `problems/oncall-rotation.json` has
the Level 0 decomposition (`slicer_live.py`, 10 of 12 gap categories selected -- `single-point-of-
failure` scored highest, 0.84, sensibly matching the idea's own stated "no real backup plan").
`tools/gap-library-single-point-of-failure.yaml` is the one branch pushed further with a real
recursive Grinder walk: of 8 leaf checks, only 1 bottomed out as genuinely atomic under the current
0.6 threshold; the other 7 stopped honestly at "needs further splitting, no deeper library built."

**Open, unresolved as of this cleanup:** do those 7 stuck branches already read as good, actionable
requirements to an experienced reader, meaning the atomic threshold is too strict -- or do they
genuinely need a Level 3 built under them? That's the first thing to resolve before extending this
further, either by building deeper libraries or by re-examining the threshold.

## Lessons learned the hard way (condensed)

- **Writing idea and pieces together, in one pass, proves nothing about decomposition quality** --
  it's grading your own homework. Caught first on a `plumber-crm` example, but it applies to every
  hand-authored `problems/*.json` file that ever existed here (all moved to `ideas/` during this
  cleanup, pending real live decomposition).
- **Even "neutral, problem-level-only" hand-authored pieces are still cheating.** The fix isn't
  writing more carefully -- it's a front-loaded, generic, reusable candidate library (fine, that's
  not idea-specific) selected live per idea (the actual decomposition), which is what
  `gap-library.yaml` + `slicer_live.py` are.
- **The Bouncer question's exact wording is a real confound, not a minor detail.** A "true today,
  without further verification" bar punishes forward-looking claims by construction; a "reasonable
  assumption to build on" bar doesn't. Always know which one produced a given number.
- **Raw per-model number dumps are not the deliverable.** The audience is business, not technical --
  plain verdicts, breadcrumb-built requirement text, and a P0-P5 legend stated once are the
  contract; decimals and repeated model names are not.
- **Cross-model disagreement on a specific question can be large and consistent** (e.g. P3 vs P4 on
  the atomic check, in the oncall-rotation Grinder run) -- worth tracking as its own finding, not
  averaging away.

## Run it

```bash
python3 foundry/slicer_live.py --idea oncall-rotation                     # Level 0 (already run)
python3 foundry/grinder_live.py --idea oncall-rotation \
    --root single-point-of-failure \
    --library tools/gap-library-single-point-of-failure.yaml \
    --budget 250 --max-depth 2                                            # recursive Grinder
python3 foundry/funnel.py --problem 1                                     # score + present
python3 foundry/loop.py --problem 1                                       # validate atomicity
```

Local, free, loaded models only. The hosted model (`jev`/P0) is not reachable from any script
here -- the environment's own permission classifier blocks it, not just convention.
