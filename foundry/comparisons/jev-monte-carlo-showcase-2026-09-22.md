# Showcase: Jev decomposition + qualitative Monte Carlo risk-concentration, all 7 ideas

Real output, not a mockup. Every number below came from a live run of the current pipeline
(`layered_walk.py` -> `report.py` -> `sort_and_rank.py` -> `monte_carlo.py`) on 2026-09-22, after
this session's priority-queue rewrite and the Monte Carlo demo build. Four ideas' ledgers were
stale (predated the rewrite) and were re-run fresh for this showcase; the other three were already
current. Full detail for each idea is in its own `runs/<idea>-*.jsonl` (gitignored, regenerate with
the commands below); this file is the durable summary.

## The pipeline, four commands

```bash
cd /workspace/foundry
python3 layered_walk.py --idea <id> --budget 80   # Slicer + Grinder: shape-guaranteed,
                                                     # priority-queue walk -> ledger
python3 report.py --idea <id>                       # renders the ledger as tables
python3 sort_and_rank.py --idea <id>                 # Sorter: live risk/effort scoring,
                                                       # persists to runs/<id>-sort.jsonl
python3 monte_carlo.py --idea <id>                    # qualitative risk-concentration pass
                                                       # over the persisted scores
```

## Base-level robustness: all 7 ideas, no failures

| idea | requirements found | top risk-concentration category | shape |
|---|---|---|---|
| oncall-rotation | 13 | nonfunctional-performance | non-functional (30.4%) |
| plumber-crm | 5 | functional-core-capability | functional (85.7%) |
| shift-swap-marketplace | 3 | spec-api-contract | technical-spec (95.2%) |
| sleep-coach-wearable | 4 | nonfunctional-availability | non-functional (93.0%) |
| smart-recycling-bin | 17 | story-first-use | user-story (38.6%) |
| standup-async | 12 | functional-core-capability | functional (87.6%) |
| voice-extension | 2 | nonfunctional-data-protection | non-functional (78.8%) |

Every one of the four commands ran clean on every idea, including the two smallest (2 and 3
requirements) -- no crashes, no NaN, no silent zero. The sensitivity calculation degrades
honestly at small N rather than failing.

**The top risk-concentration category is genuinely idea-dependent** -- 3 different shapes win
across 7 ideas (non-functional x3, functional x2, technical-spec x1, user-story x1). This is a
different, later stage than gap_categories' own selection (which the 7-idea run documented in
`seven-idea-run-2026-09-22.md` found dominated by non-functional almost regardless of domain,
because of how the selection composite score works) -- once you're past selection and looking at
which of the *found* requirements' risk/effort scores actually drive variance in simulated
exposure, the answer varies by idea, not just by which categories got picked.

## Deep dive: oncall-rotation (the richest run, 13 requirements)

**Domain/audience**: workflow-automation (55%), internal-employees (70%) -- trusted under the new
margin-based rule (would have been discarded under the old flat 0.6 floor). Enrichment applied.

**Shape-guaranteed selection**: all 6 shapes represented (previously the old pooled-top-4 design
consistently favored non-functional categories regardless of domain -- confirmed in the earlier
7-idea run).

**Sample requirements found** (of 13, full detail in `report.py`'s output):
- *"The system's required speed is stated as a measurable target. The point in the request path at
  which the response time target is measured is named."* (nonfunctional-performance)
- *"The system performs every action its users need in order to complete the task it exists for...
  Each user action produces one defined outcome in the system."* (functional-core-capability)
- *"Putting a new version into production follows a defined, repeatable procedure..."*
  (ops-release-process)

**Sorter scoring** (live, persisted to `runs/oncall-rotation-sort.jsonl`): risk/effort/confidence
per requirement per model -- e.g. the top-risk piece scored risk=0.60, effort=0.54, disagreement
0.02 (models agreed).

**Monte Carlo risk-concentration** (5000 draws, qualitative -- see `tools/monte-carlo.yaml`'s
`methodology_note` for the real PMBOK distinction this is built against):

| category | shape | sensitivity | illustrative person-months (of a 26.9 PM nominal 10-KLOC project) |
|---|---|---|---|
| nonfunctional-performance | non-functional | 30.4% | 8.17 |
| functional-core-capability | functional | 18.5% | 4.97 |
| ops-release-process | operational | 14.6% | 3.93 |
| story-first-use | user-story | 12.0% | 3.22 |
| spec-data-model | technical-spec | 7.1% | 1.91 |
| story-error-recovery | user-story | 5.6% | 1.50 |
| functional-data-lifecycle | functional | 5.2% | 1.39 |
| nonfunctional-data-protection | non-functional | 4.2% | 1.13 |
| spec-api-contract | technical-spec | 2.6% | 0.69 |

The illustrative-PM column is explicitly scale context (COCOMO Organic mode, Boehm 1981, verified
against real sources this session), never a claim about this specific idea's real size.

## What this is, and isn't -- stated once, plainly, per every run's own output

Every `monte_carlo.py` run prints this itself: *"this ranks WHERE unresolved gaps concentrate
relative to each other. It is not a date, not a dollar figure, and has not been validated against
any real outcome."* The qualitative/quantitative distinction it's built on, and why the
quantitative version (an actual schedule or budget forecast) isn't buildable yet, is in
`foundry/PLAN.md`. This showcase demonstrates the pipeline runs correctly and produces
non-degenerate, idea-varying output at base level -- it does not claim the risk rankings above are
individually validated against real project outcomes; no outcome data exists yet to validate
against (also in `PLAN.md`'s suggested next steps).
