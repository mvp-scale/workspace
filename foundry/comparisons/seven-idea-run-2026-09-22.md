# All 7 ideas through the live pipeline, 2026-09-22

Real run, not a hypothesis comparison (unlike the other files in this directory). Default models
(P1/P2/P3), default budget (80), immediately after retiring the 12 original `gap_categories` (see
`world-knowledge.yaml`'s `gap_categories` comment and BRIDGE.md). Six of these ideas had never been
run before this session -- `plumber-crm.json` had no `customer` key at all, the other five carried
a placeholder string. Customer intakes authored this session (the one authorship the project's own
rule allows), committed separately. Raw rendered `report.py`/`sort_and_rank.py` output for all 7
lives only in this session's scratchpad, not committed -- this file is the durable summary.

## Per-idea summary

| idea | domain (conf) | audience (conf) | enrichment | requirements found | needs-decision | no-library | risk tier |
|---|---|---|---|---|---|---|---|
| oncall-rotation | workflow-automation (55%) | internal-employees (70%) | skipped | 1 | 2 | 9 | worth-checking (0.37) |
| plumber-crm | internal-ops-tooling (97%) | smb-owner-operator (94%) | applied | 3 | 4 | 5 | low-stakes (all 3) |
| shift-swap-marketplace | internal-ops-tooling (62%) | internal-employees (79%) | applied | 3 | 6 | 3 | low-stakes (all 3) |
| sleep-coach-wearable | consumer-hardware-iot (90%) | individual-consumer (100%) | applied | **0** | 7 | 5 | n/a |
| smart-recycling-bin | consumer-hardware-iot (81%) | two-sided-mixed (79%) | applied | 3 | 5 | 4 | low-stakes (all 3) |
| standup-async | internal-ops-tooling (39%) | internal-employees (89%) | skipped | 2 | 4 | 6 | low-stakes (both) |
| voice-extension | customer-facing-saas (99%) | individual-consumer (99%) | applied | 2 | 6 | 4 | low-stakes (both) |

All 7 ran clean end to end (`layered_walk.py` -> `report.py` -> `sort_and_rank.py`), 18/80 budget
spent each, 16 node classifications across 4 branches each, no crashes, no stray processes
afterward. Polarity read clean on every rendered requirement -- no contradictions found.

## Three findings that generalize past the single oncall-rotation example

**1. `nonfunctional-performance` and `nonfunctional-availability` top-4 in nearly every idea,
regardless of content -- and it's not just the boost.** `nonfunctional-performance` was selected
in all 7 runs; `nonfunctional-availability` in 6 of 7 (all but oncall-rotation, where
`nonfunctional-performance` alone still took the #1 slot). Checked the *own* gap-check score (the
0.7-weighted term), not just the profile boost, for each: it sits high (0.36-0.81) on every single
idea, including ones with no boost at all on that category -- `plumber-crm`'s
`nonfunctional-availability` scored composite 0.64 with only a 0.30 boost (own score 0.79 did the
real work). The likely mechanism: every idea intake here is a one-paragraph product pitch, and the
gap-check question is literally "is the required speed/availability stated as a measurable
target" -- a two-sentence pitch essentially never states a number, so the honest answer is "no,
not yet true" (a real gap) almost by construction, independent of whether performance is actually
the idea's biggest risk. This is a property of checking spec-completeness categories against an
intake-stage idea, not obviously a bug in the mechanism -- but it means Composite Scoring's boost
term is doing less differentiating work than `world-knowledge.yaml`'s own comments assume, and the
category *selection* is closer to "which categories are structurally under-specified at pitch
stage" than "which categories matter most for this specific idea." Worth having in hand before
gap 4/5's threshold and boost-coverage work.

**2. The atomic threshold (0.18) is marginal across ideas, not just for oncall-rotation --
`sleep-coach-wearable` produced zero requirements.** All 7 of `sleep-coach-wearable`'s leaf checks
landed in "needs a decision" (cross-model disagreement, spread >= 0.3) or "not yet checkable" --
none cleared 0.18 cleanly. Across all 7 ideas combined: 14 requirements found out of roughly 90-100
leaf checks total (16 node classifications x 7, most of which are leaves). This is the strongest
evidence yet for BRIDGE.md gap 4's open item -- the threshold isn't just marginal on one idea's
control statements, it's marginal on real leaf content across a genuinely varied idea set (an
internal tool, a consumer wearable, a two-sided marketplace, a browser extension).

**3. Every scored requirement across all 7 ideas landed in Sorter's `low-stakes` tier except one.**
13 of 14 requirements scored `low-stakes` (risk-if-false < 0.3); the one exception
(`oncall-rotation`'s single requirement) landed `worth-checking` at 0.37, just over the line.
`must-resolve-first` (>= 0.6) was never reached once, across 7 ideas and 14 scored requirements.
This wasn't flagged as an open item in BRIDGE.md's "Real gaps" list -- it's new: either these three
fixed risk-tier bins (never diagnosed against real data, unlike `ATOMIC_THRESHOLD`) sit too high
for this model combination's score scale, or spec-completeness requirements genuinely are
low-stakes relative to what "risk if false" is really asking. Worth a same-shape diagnostic to
`ATOMIC_THRESHOLD`'s, not assumed either way.

## What this settles vs. still leaves open

Settles (real evidence now, not a one-idea guess): the retirement decision on the original 12
categories is not costing anything observable -- none of them would plausibly have outscored the
performance/availability/data-protection/data-ownership cluster that's dominating every run anyway.
Does not settle: whether that dominance is itself a problem worth fixing (finding 1 above), what
the right atomic threshold or risk-tier bins actually are for P1/P2/P3 (findings 2-3), or anything
about hosted P0 (still user-run only, and `sort_and_rank.py --models P0` needs its `hosted` skip
in `funnel.bounce_and_weigh` lifted first -- unrelated bug, not touched this session).
