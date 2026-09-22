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

Fixed, generic, reusable candidate content (a domain taxonomy, a gap-category library) is the one
exception -- front-loaded once, selected from live per idea. That distinction, and getting the
mechanics of the selection itself actually right, is most of what this file's history is about.

## Tool guide (quick reference)

| Tool | Job | Live today? |
|---|---|---|
| **Slicer** | picks the domain/audience, and which of 21 gap categories apply to the idea | yes |
| **Grinder** | recurses a selected category down to atomic requirements | yes, all 21 categories have a library (see below) |
| **Sorter** | scores each requirement (risk if false, effort) and groups by risk tier | yes, both halves |
| **Conveyor** | sequences requirements into an order | `risk-first` yes; `dependency-order`/`parallel-lanes` blocked (no `depends_on`); duration variants not attempted (no real duration source) |
| **Spotlight** | ranks what to check first | 3 of 5 variants live; `downstream-impact`/`audience-weighted` honestly blocked (no data to support them) |

Two scripts, always run in order:
```bash
python3 foundry/layered_walk.py --idea <id>     # Slicer + Grinder, writes a ledger
python3 foundry/report.py --idea <id>           # renders that ledger as tables
python3 foundry/sort_and_rank.py --idea <id>    # Sorter + Conveyor + Spotlight on the ledger's atomic requirements
```

## The pipeline, at a glance

```
1. Intake (ideas/<id>.json)     idea + customer -- the only thing Claude authors
2. Slicer.by-domain             1 call -> domain + audience (needs 0.6 confidence, both, or skipped)
3. Expand                        world-knowledge.yaml lookup, no call -- folds enrichment into state
4. Slicer.gap_categories        1 call -> scores all 21; top-4 by mean become the decomposition
5. Grinder                      recurse each selected category's library (if it has one) to atomic
6. Ledger + report              layered_walk.py writes runs/<id>-layered-walk.jsonl; report.py reads it
7. Sorter/Conveyor/Spotlight (sort_and_rank.py) score, group and rank the atomic requirements
   steps 1-6 produced -- live, real numbers, run as its own command against the ledger
```

Models: P1 (semif), P2 (kev-4b), P3 (so1) -- three, not five. laya (P4) and verdict (P5) are
excluded, on `probes/report_v2.py`'s already-measured accuracy and calibration (P4 56.9%, P5
46.7%, both with a weak or near-zero confidence signal), not an in-session guess. See "Lessons
learned" for why P3 was wrongly excluded first and this ended up the opposite of the first fix.

## File map

```
ideas/*.json       Raw two-question intake (idea + customer). Claude's only allowed authorship.
                    "pieces" is either absent or explicitly "not decomposed."
problems/*.json     A historical decomposition -- oncall-rotation.json, produced by the now-deleted
                    slicer_live.py. Marked HISTORICAL in its own "source" field: pre-polarity-fix
                    text, single-model threshold selection. The current mechanism doesn't write to
                    problems/*.json at all -- see runs/ below.
tools/*.yaml        Tool definitions (5 tools, up to 5 variants each -- Grinder has 3, by design;
                    see tools/README.md) and world-knowledge.yaml, the one file for everything
                    that isn't a tool -- the generic, reusable gap_categories/gap_category_detail
                    that make a live Slicer/Grinder possible without a generative LLM call, plus
                    domain enrichment.
comparisons/*.json  Historical design exploration (how different Slicer variants would carve the
                    same idea) -- honestly labeled as hypothesis comparisons, not decomposition
                    output. Superseded by the gap_categories approach but kept for the reasoning.
funnel.py           Sorter/Conveyor/Spotlight's core functions (bounce_and_weigh, spotlight,
                    conveyor) -- reused as-is by sort_and_rank.py, not modified.
layered_walk.py     The live pipeline, one recursive loop (`walk`) over one tree with a virtual
                    root (`build_tree`): classify, expand with world-knowledge metadata, recurse
                    into whatever's selected, stop at no-further-level or a real, enforced
                    call-count budget (`--budget`, default 60). Writes
                    runs/<idea>-layered-walk.jsonl.
report.py           Reads that ledger and renders it as tables. Never authors content --
                    formatting only.
sort_and_rank.py     Reads that same ledger's atomic requirements, scores them live with
                    funnel.py's Sorter, groups and ranks with Sorter/Conveyor/Spotlight -- the
                    bridge that didn't exist before: funnel.py only ever read problems/*.json,
                    layered_walk.py never wrote to it.
runs/               Gitignored, regenerated per run -- not durable, don't rely on anything here
                    surviving between sessions, but it IS layered_walk.py's only durable output
                    and both report.py's and sort_and_rank.py's only input for the current idea's
                    most recent run.
```

## The one worked example: oncall-rotation

`ideas/oncall-rotation.json` has the real two-question intake. `problems/oncall-rotation.json` is
a **historical** snapshot from the deleted `slicer_live.py` -- read its own `source` field before
trusting anything in it. The current, correct way to see a real run is to run `layered_walk.py`
yourself (see "Run it" below) and read `report.py`'s output; nothing static in this repo
substitutes for that anymore.

`tools/world-knowledge.yaml`'s `gap_categories` now holds only the 21 requirement-shaped
categories (functional/non-functional/architectural/user-story/technical-spec/operational) -- the
original 12 generic "is this a gap" audit-checklist categories were retired, including the 4 that
had a hand-built `gap_category_detail` tree (`single-point-of-failure`, `trust-adoption`,
`cost-resource`, `behavior-change`). All 21 remaining categories have a detail tree; see
`gap_categories`' own `RETIRED` comment in the yaml for why. Whether a branch gets walked in a
given run still depends on whether it lands in that run's top-4 by Composite Score -- no longer
guaranteed the way a flat floor used to guarantee it.

**Resolved, not open anymore:** two rounds of this. First, whether the atomic threshold was too
strict or a Level 3 was needed -- neither; a diagnostic found P3 (so1) wasn't discriminating
atomic-vs-compound text at all in one specific run, dragging a 5-model mean down. P3 was then
excluded -- which was *also* wrong: `probes/report_v2.py`'s much larger, already-validated
measurement (1,437 real items) shows P3 performs comparably to P1/P2 and is reasonably calibrated;
laya and verdict are the actually weak pair. Second, once the model set was corrected (P1/P2/P3),
a controlled diagnostic found these three models' atomic-check scores are compressed and shifted
low across the board -- even clean, obviously-atomic control text only scored ~0.30 -- so the
threshold was recalibrated to 0.18 (see `layered_walk.py`'s `ATOMIC_THRESHOLD` comment for the
numbers). A separate, sturdier fix layered on top of that: a node that has children in the library
is a category *by construction* (that's why it was given children) and can never be called atomic
regardless of its score -- only true leaves can terminate the walk. That structural rule matters
more than the exact threshold value.

## Lessons learned the hard way (condensed)

- **Writing idea and pieces together, in one pass, proves nothing about decomposition quality** --
  it's grading your own homework. Caught first on a `plumber-crm` example, but it applies to every
  hand-authored `problems/*.json` file that ever existed here (all moved to `ideas/` during an
  earlier cleanup, pending real live decomposition).
- **Even "neutral, problem-level-only" hand-authored pieces are still cheating.** The fix isn't
  writing more carefully -- it's a front-loaded, generic, reusable candidate library (fine, that's
  not idea-specific) selected live per idea (the actual decomposition), which is what
  `world-knowledge.yaml`'s `gap_categories` + `layered_walk.py` are.
- **A fixed candidate library's own text can be silently self-contradictory, and nothing catches
  that except reading the actual concatenated output.** `gap_categories` was written as problem
  statements ("depends on one person with no backup"); `gap_category_detail` was written as
  solved-state assertions ("a backup already exists"). Breadcrumb concatenation joined them into
  literal contradictions for every single requirement this pipeline ever produced, for three hours,
  before an Opus end-to-end review caught it by actually reading the rendered output rather than
  trusting the mechanism's design. Fixed by rewriting `gap_categories` to the same requirement
  polarity as `gap_category_detail`. The general lesson: a live, well-formed mechanism over broken
  content still produces broken output -- "the tools ran live" is not the same claim as "the
  output is coherent," and only reading the actual rendered text checks the second one.
- **A confidence floor near 1.0 for almost everything is a rubber stamp, not a decision.** Level 0
  selection at a flat 0.6 floor selected 12 of 12 gap categories in an early run. Switched to
  top-k selection.
- **One universal threshold for every decision contradicts Confidence-Gated Routing's actual
  point.** The pattern's own worked example uses different bars for different-stakes actions.
  This repo had written the opposite down as a deliberate, cited design choice ("chosen for
  consistency with the 0.6 threshold already used everywhere else") -- codifying the anti-pattern
  instead of applying it. Fixed with named, stakes-appropriate thresholds in `layered_walk.py`.
- **A magic-number threshold tuned against a small diagnostic doesn't necessarily generalize, even
  when the diagnostic was real and the direction it found was correct.** A 10-statement atomic-vs-
  compound diagnostic correctly showed these three models discriminate in the right direction, but
  scores compressed low across the board (atomic-mean 0.28, compound-mean 0.085) -- a threshold of
  0.75, then 0.6, then a recalibrated 0.18 were each tried against real runs before landing on a
  value the data actually supports. Multiple rounds of "tune the number, run it, still wrong" was
  the actual sign to stop tuning and look for structure already available instead (next bullet).
- **Information already sitting in the data beats another round of threshold-tuning.** The
  specific bug an 0.18 threshold alone still produced: a category node (one with children in the
  library, specifically because it represents more than one fact) scored just above the line and
  got labeled a final atomic requirement, skipping its own children entirely. The fix wasn't a
  better number -- a node with children was already known, structurally, to be a category, not a
  fact, the moment it was authored. Only true leaves (no children) can terminate the walk now,
  regardless of score. Numeric thresholds still decide *among* leaves; they no longer get to
  override structure that's already known.
- **The Bouncer question's exact wording is a real confound, not a minor detail.** A "true today,
  without further verification" bar punishes forward-looking claims by construction; a "reasonable
  assumption to build on" bar doesn't. Always know which one produced a given number.
- **Raw per-model number dumps are not the deliverable, and neither is a live debug trace.** The
  audience is business, not technical -- plain verdicts, breadcrumb-built requirement text, and a
  P0-P5 legend stated once are the contract. This is why `layered_walk.py` only records to a JSONL
  ledger and `report.py` does the actual rendering, as two separate jobs.
- **Cross-model disagreement can mean one model isn't discriminating at all, not that the content
  is genuinely ambiguous.** Averaging through that (a flat 5-model mean) hides it; a follow-up
  diagnostic that tested each model against known-atomic and known-compound control statements is
  what actually found it, not staring harder at the disagreement itself.
- **A wire-format YAML file can silently fail to parse, or silently collapse structured data into
  a string, and nothing but actually parsing it with the real loader catches that.** Happened
  twice in `tools/`: a multi-line plain scalar broke `slicer.yaml`'s parse entirely; a `>` block
  scalar swallowed `world-knowledge.yaml`'s `domain_enrichment` mapping into one string. Every
  yaml file in `tools/` should be loaded and its structure checked, not just visually reviewed,
  after any edit.

## Run it

```bash
python3 foundry/layered_walk.py --idea oncall-rotation      # Slicer + Grinder -> ledger
python3 foundry/report.py --idea oncall-rotation             # render the ledger as tables
python3 foundry/sort_and_rank.py --idea oncall-rotation       # Sorter + Conveyor + Spotlight on it
```

Local, free, loaded models only (P1/P2/P3 -- laya/P4 and verdict/P5 excluded, see the tool guide
above). The hosted model (`jev`/P0) is not reachable from any script here -- the environment's own
permission classifier blocks it, not just convention.
