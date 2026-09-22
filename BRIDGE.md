# BRIDGE: where we are, for the next session

Updated 2026-09-22 (foundry session). Read `CLAUDE.md` too. This file is the narrative and the
next task. The active thread is `/workspace/foundry` — a live, tool-driven idea-decomposition
pipeline. The Scenario lab work (`demo/scenarios.html`) is a separate, still-paused thread; see the
bottom of this file. Don't touch it unless asked.

## Starter prompt for the next session (paste this)

```
Read /workspace/BRIDGE.md and /workspace/foundry/README.md first, in that order. The active
thread is /workspace/foundry. Read foundry/README.md's "one rule that matters most" before
touching anything -- you author exactly the idea+customer intake and fixed, generic, reusable
candidate library content, nothing idea-specific, ever. Everything else has to come from live
TypeSafe calls against the loaded local models (or, now, optionally the hosted model -- see
below).

Verify state first: `demo/lineup.sh status` (loaded local models), `cd foundry && git status`
(should be clean -- see "Git state" below), and run the three-command pipeline yourself once to
confirm it still works:
    python3 layered_walk.py --idea oncall-rotation --budget 80
    python3 report.py --idea oncall-rotation
    python3 sort_and_rank.py --idea oncall-rotation
Report in a few lines what's loaded and whether it ran clean before doing anything else.

This session got a Fable-model planning pass against the "Real gaps, prioritized" list below,
acted on its one open decision (gap 1: the user chose to retire the 12 original gap_categories,
not build them out or fold them in -- done), then authored the 6 missing idea customer-intakes and
ran all 7 ideas through the live pipeline for the first time (gap 6) -- see
`foundry/comparisons/seven-idea-run-2026-09-22.md` for what that surfaced, some of it genuinely new
evidence, not just BRIDGE.md's prior summary re-confirmed. Read "Real gaps, prioritized" below
before assuming any threshold or selection number is still right -- several are now better
evidenced than before, none are newly resolved except gap 1.

Constraints, unchanged: no hosted-model spend from any script's own environment (P0/jev requires
the person to `set -a; . /workspace/.env; set +a` in THEIR OWN shell before running a script from
it -- never read or paste the key yourself; see "Hosted Jev" below, including a real bug the Fable
pass found in the Sorter half specifically). Never restart demo/server.py while an experiment runs
through it. Timeout on every wait, check `ps` afterward. Commit locally with the Co-Authored-By
trailer -- note: this environment appears to auto-commit periodically (see "Git state"); don't
assume nothing is saved, but don't rely on it either.
```

## Git state

`/workspace` is a small git repo, local commits only, no remote. `foundry/` is tracked (unlike
`data/`, `models/`, `logs/`, `.env`, `research/`). The environment auto-commits periodically
without an explicit `git commit` being run — reassuring, but don't rely on it as a substitute for
committing real milestones yourself. As of this file being written, git is clean: this session
committed the prior session's pending `--models`/`CHILD_TOPK_*` edits after verifying them, the
gap-1 retirement, the 6 authored customer intakes, and this file. Verify with `cd foundry && git
status` regardless — don't take "clean" as read.

## Foundry: the guide

Three commands, always, from `/workspace/foundry`:
```bash
python3 layered_walk.py --idea <id> --budget 80      # Slicer + Grinder, writes a ledger
python3 report.py --idea <id>                          # renders the ledger as tables
python3 sort_and_rank.py --idea <id>                    # Sorter + Conveyor + Spotlight on it
```
`--models` on either of the first and third: comma-separated P-numbers or backend ids, e.g.
`--models P1` (one local model), `--models P0,P1` (hosted + one local), default `P1,P2,P3`
(semif/kev-4b/so1 — see "Model selection" below for why those three specifically).

**Tool guide** (5 tools; full detail in `tools/README.md`):

| Tool | Job | Live? |
|---|---|---|
| Slicer | domain/audience + 10-probe tech-context pre-scan (1 call) → Composite-Scoring-ranked top-k of 21 gap categories (1 call) | yes, `by-domain` variant only — 4 other designed variants never run |
| Grinder | recurse each selected category's library to atomic requirements | yes — top-k child selection (see "Fixed this session"); all 21 categories now have a library (the original 12 were retired, see "Real gaps" gap 1) |
| Sorter | score each requirement (risk/effort), group by risk tier | yes, scoring + `by-risk-tier`; 4 other grouping variants blocked (no per-piece tags exist) |
| Conveyor | sequence groups | `risk-first` only; dependency/duration variants blocked (no data source) |
| Spotlight | rank what to check first | 3 of 5 variants live; 2 blocked (same missing-data reasons) |

Both scripts print `TOOL:` before each real invocation and end with a **TOOLS USED THIS RUN**
block naming anything that didn't run and why — read that before assuming a run was complete.

**Model selection**: default is P1/P2/P3 (semif/kev-4b/so1), grounded in `probes/report_v2.py`'s
already-validated measurement (1,437 real items, 15 published sets) — not a guess. An earlier
version of this session excluded P3 instead, based on a small in-session diagnostic that
generalized too far from one question's wording; that was wrong and got corrected. laya (P4,
56.9% accuracy) and verdict (P5, 46.7%, near-zero calibration gap) are the ones actually excluded
by default.

**Hosted Jev (P0)**: confirmed working for `layered_walk.py`, run by the user directly in their own
terminal with `.env` sourced first (`set -a; . /workspace/.env; set +a`) — the code has no
special-case exclusion of `jev`, it's just another entry in `ALL_MODELS`. From a Claude-run Bash
tool call, it fails clean with `"TYPESAFE_API_KEY not set"` (no key in that shell's environment) —
this is not a permission block on the call itself, just no credential present; reading whether the
key exists at all (e.g. `cat .env`) **is** a real, harness-level block (hit directly a prior
session) and should not be retried. Never read or relay the key through chat. **Real bug found by
the Fable planning pass, not yet fixed:** `sort_and_rank.py --models P0` (or any `jev`-including
combination) silently scores nothing — `funnel.bounce_and_weigh` (line ~161) does `if
cfg.get("hosted"): continue`, and `demo/server.py` marks `jev` as `hosted: True`. This is a
separate skip from the credential check above; `layered_walk.py` doesn't have it, `sort_and_rank.py`
does. Not fixed this session — flagged in "Real gaps" gap 4.

## Fixed this session (condensed — read before touching any threshold or model list)

- **`slicer.yaml` didn't parse as YAML at all** (a plain multi-line scalar broke mid-file) and
  **`world-knowledge.yaml`'s `domain_enrichment` had silently collapsed into one string** instead
  of staying queryable data (a `>` block scalar swallowed a whole mapping). Both fixed; every yaml
  file in `tools/` should be re-parsed after any edit, not just visually reviewed — this exact
  class of bug happened twice.
- **The pipeline's actual output was self-contradictory for three hours**: `gap_categories` text
  was problem-polarity ("depends on one person, no backup"), `gap_category_detail` text was
  solved-state polarity ("a backup already exists") — breadcrumb concatenation joined them into
  literal contradictions. Fixed by rewriting `gap_categories` to solved-state polarity. Any new
  library content must match this polarity, and must not join two claims with "and"/"or" in a leaf
  (also a real, separately-caught bug).
- **P3 (so1) was wrongly excluded**, based on a 10-statement in-session diagnostic generalized too
  far from one question's wording. `probes/report_v2.py`'s real measurement says the opposite:
  laya and verdict are the weak pair, P1/P2/P3 are comparable and reasonably calibrated. Corrected.
- **`ATOMIC_THRESHOLD` went 0.6 → 0.75 → 0.18** across this session, each a guess before the last
  one — landed on 0.18 via an actual controlled diagnostic (5 known-atomic vs 5 known-compound
  control statements) against the corrected P1/P2/P3 set specifically. **This number is
  model-combination-specific and has not been re-diagnosed for any other `--models` choice**,
  including hosted P0 — a real open item, not a solved one.
- **A node with children was structurally guaranteed to be a category** (that's why it was given
  children when the library was authored) **but a live score alone could still label it "atomic"
  and skip its own children** — the actual root cause of an early false-positive result. Fixed:
  only true leaves (no children) can ever terminate a branch as atomic now, regardless of score.
  This mattered more than any threshold value.
- **`CHILD_RELEVANCE` was a flat 0.6 floor, never actually diagnosed against real data** (unlike
  `ATOMIC_THRESHOLD`). A real run against hosted P0 scored every child across four branches
  0.15–0.45 — nowhere near the floor — so nothing recursed, silently. Replaced with top-k
  selection (`CHILD_TOPK_BOOSTED=3`, `CHILD_TOPK_NORMAL=1`), the same fix already proven at Level 0
  (`GAP_TOPK`) for the identical failure mode. **These top-k numbers are a first attempt, not
  diagnosed** — same open-item caveat as `ATOMIC_THRESHOLD`.
- **`slicer_live.py`, `grinder_live.py`, `loop.py` deleted** (385 lines) — an Opus end-to-end
  review found them fully superseded by `layered_walk.py` and running on the polarity-broken
  content above. `layered_walk.py` is now one recursive loop (`walk`) over one merged tree with a
  virtual root (`build_tree`) — classify → expand (world-knowledge lookup) → recurse into what's
  selected → stop at no-further-level or a real, enforced call budget (`Budget` class, not just a
  depth limit).
- **`funnel.py` (Sorter/Conveyor/Spotlight) was never connected to the new pipeline** — it only
  ever read `problems/*.json`; `layered_walk.py` writes to a ledger instead. `sort_and_rank.py`
  bridges them, reusing `funnel.py`'s scoring code unmodified.
- **Speculative Fan-Out pre-scan + Composite Scoring added**: `tools/world-knowledge.yaml`'s
  `profile_probes` (10 generic, reusable tech-context questions — sensitive data, external
  integration, real-time latency, financial, regulated industry, multi-tenant, offline, mobile,
  scale, change-frequency) are fanned into the same call as domain/audience. Each category's
  selection score is `0.7 * own gap-check score + 0.3 * profile boost` (which probes list that
  category in their `boosts`), not the raw score alone — confirmed live to correctly surface
  `nonfunctional-performance` for the on-call idea's actual 5-minute SLA. **The 10 probes and
  their boost mappings are Claude-authored, generic, never independently validated** — same
  honesty flag as everything else in this file, explicitly unverified.
- **A 21-category / 90-leaf requirement-shaped library was added** (functional, non-functional,
  architectural, user-story, technical-spec, operational — matching real SRS/backlog/arc42
  register, not the original 12's generic "is this a gap" audit-checklist tone). Built via a
  Workflow (6 Sonnet + 6 Haiku + 1 Opus agent) that had a real bug — a JS scoping error meant the
  Sonnet "articulate" stage never ran, so the 6-way consolidation never happened. The final Opus
  "correct" stage caught its own broken (empty) input and disclosed it unprompted, then authored
  the full set solo against the same rules. Read and spot-checked directly before writing to disk;
  held up (consistent polarity, no compound leaves, genuinely shape-appropriate per category) —
  but **it is one reviewer's single pass, not the six-way consolidation originally designed**, and
  hasn't had a second, independent review.

## Real gaps, prioritized

Concentrated in `tools/*.yaml` and `tools/world-knowledge.yaml`, as suspected. A Fable-model
planning pass went through all 8 of the prior version of this list, re-verified each against the
real files (not just this doc's summary), and found several things worth correcting — folded in
below. Gap 1 (below) is resolved this session; the rest are renumbered 1-7 accordingly, roughly in
the sequencing the Fable pass suggested (evidence-gathering first, since gap 6 — now done — turned
out to cheaply inform several of the others at once).

1. **RESOLVED this session.** The 8 of 33 `gap_categories` with no `gap_category_detail` library,
   plus the 4 that had one, were retired — the user's decision, not inferred: one consistent
   21-category requirement-shaped library beats a mixed audit-checklist-plus-SRS one. Caveat the
   Fable pass surfaced before the decision: 7 of the 8 libraryless categories could never be
   boosted by any `profile_probe` anyway, so "they never landed in a top-4" wasn't clean evidence
   of irrelevance on its own — the decision was made on library-shape grounds, with that caveat
   known. See `world-knowledge.yaml`'s `gap_categories` comment for the full reasoning.
2. **4 of Slicer's 5 designed variants have never run live**: `by-layer`, `by-risk`, `by-phase`,
   `binary-halving` exist only as design in `slicer.yaml`. Only `by-domain` (+ the profile
   pre-scan bolted onto it) has ever been exercised. These are whole-idea-level classifications, so
   their natural consumer is Composite Scoring (gap 5 below), not directly gap 3's per-piece
   problem — don't conflate the two when picking this up.
3. **Sorter's 4 non-`by-risk-tier` grouping variants are blocked on missing data**, not missing
   code: `by-domain`/`by-audience`/`by-layer`/`by-phase` grouping need a per-piece tag that nothing
   sets — `by-domain`'s classification is whole-idea-level, not per-requirement. Same root cause
   blocks Conveyor's `dependency-order`/`parallel-lanes` (`depends_on` inference was never built)
   and Spotlight's `downstream-impact`/`audience-weighted`. Cheapest real progress here doesn't
   need new calls: pieces already carry `lens` (business/technical) and `shape` (for the 21
   categories) from their root category — a free grouping by either is unbuilt but needs zero live
   calls, unlike the five designed variants.
4. **`ATOMIC_THRESHOLD`, `CHILD_TOPK_*`, and (newly identified) Sorter's risk-tier bins are all
   calibrated or guessed for the local P1/P2/P3 ensemble only, and now have much stronger evidence
   they're marginal.** The 7-idea run (gap 6, done this session — see
   `foundry/comparisons/seven-idea-run-2026-09-22.md`) found `sleep-coach-wearable` produced
   **zero** requirements at all — every leaf either needed a decision (cross-model spread >= 0.3)
   or had no library — and across all 7 ideas, 13 of 14 requirements ever found landed in Sorter's
   `low-stakes` risk tier, `must-resolve-first` (>= 0.6) was never reached once. The risk-tier bins
   were never diagnosed against real data the way `ATOMIC_THRESHOLD` was — same open-item class.
   Hosted P0 is reachable (user-driven, own terminal) for `layered_walk.py`, but not yet for
   `sort_and_rank.py` — see "Hosted Jev (P0)" above for the `hosted`-skip bug the Fable pass found
   in `funnel.bounce_and_weigh`; fix that before a P0 Sorter calibration is even possible.
5. **`domain_enrichment`/`profile_probes` never narrow which of the 21 `gap_categories` even get
   checked** — every idea still gets all 21 checked unconditionally (the long-standing
   `open_question` in `world-knowledge.yaml`, still unresolved). New evidence this session
   complicates it further, not just confirms it: `nonfunctional-performance` was selected in the
   top-4 for **all 7** ideas run, `nonfunctional-availability` for 6 of 7, regardless of domain —
   and checking the *own* gap-check score (not just the boost) shows it's consistently high
   (0.36-0.81) across every idea, likely because a one-paragraph idea pitch essentially never
   states a measurable performance/availability target, so the honest answer to "is this stated as
   a number" is "no" almost by construction. This means Composite Scoring's boost term is doing
   less differentiating work than assumed, and narrowing-by-domain may not even be the fix — see
   the comparisons file for the full writeup before touching `W_GAP`/`W_PROFILE` or this open
   question.
6. **DONE this session.** All 7 ideas in `ideas/*.json` have now been run through the live
   pipeline (`plumber-crm`, `shift-swap-marketplace`, `sleep-coach-wearable`,
   `smart-recycling-bin`, `standup-async`, `voice-extension`, plus `oncall-rotation` re-run
   post-retirement) — all ran clean, no crashes, no stray processes, polarity read clean on every
   rendered requirement. The 6 previously-untested ideas needed real `customer` intake authorship
   first (`plumber-crm.json` had no `customer` key at all — would have crashed; the other five
   carried a placeholder string) — authored this session, the one authorship the project's own
   rule allows. Full findings, not just "it ran": `foundry/comparisons/seven-idea-run-2026-09-22.md`
   — feeds directly into gaps 4 and 5 above.
7. **The 21-category requirement-shaped library is one Opus pass, not the six-way consolidation
   originally designed** (see "Fixed this session" above) — a real second review, or an actual
   working re-run of the intended research→gap-find→articulate→correct pipeline, is still owed.
   Now the *only* gap_category_detail library (the 12 original's four trees were retired with the
   rest) — a review matters more than before, not less.
8. **Doc drift, broader than one file.** The Fable pass found `foundry/tools/grinder.yaml`'s
   `patterns_applied` still describes the wrongly-excluded-P3 diagnosis and a 0.75 atomic threshold
   (both since corrected elsewhere), and `problems/oncall-rotation.json` is fully historical
   (pre-polarity-fix text, produced by a deleted script, kept only as a labeled artifact). This
   session fixed the doc drift its own gap-1 retirement directly caused (`README.md`,
   `tools/README.md`, two `layered_walk.py` comments) but did not do a full sweep — `grinder.yaml`
   and `problems/oncall-rotation.json` are still stale.

## Scenario lab (separate, still paused)

Untouched this session. Full plan: `docs/scenario-lab-plan.md`. Summary unchanged from before:
build out `/scenarios` (accuracy/calibration on 15 published labelled sets) with an offline runner
and a live `/api/batch` path, keeping the existing template (decomposition, model comparison,
graphs, worked example, item explorer) consistent across sets. Do not pick this up unless asked.

## Gotchas learned the hard way (foundry-specific, this session)

- **A live, well-formed classifier mechanism over broken content still produces broken output.**
  "The tools ran live" is not the same claim as "the output is coherent" — only reading the actual
  rendered text (not trusting the mechanism's design) catches a polarity contradiction.
- **A magic threshold tuned against one model or one small diagnostic does not generalize.**
  Re-diagnose, don't reuse, when the model combination changes — `ATOMIC_THRESHOLD` and
  `CHILD_TOPK_*` are both known-untested outside the P1/P2/P3 default right now.
- **Information already in the data structure beats another round of threshold-tuning.** The
  leaf-vs-category fix (structural, not numeric) mattered more than any of the three threshold
  values tried before it.
- **Cross-model disagreement can mean one model isn't discriminating at all**, not that the
  content is genuinely ambiguous — found via a controlled diagnostic against known-atomic/
  known-compound text, not by staring harder at the disagreement itself.
- **A YAML file can silently fail to parse, or silently collapse structured data into a string** —
  happened twice. Re-parse with the real loader after every edit to `tools/*.yaml`.
- **Reading whether a credential exists is itself a blocked action**, separate from and prior to
  whether a call using it would be blocked. Don't retry it; don't paste secrets into chat either
  direction.
- **A one-paragraph idea pitch structurally lacks spec detail, so spec-completeness categories
  (measurable performance/availability targets, named component boundaries) will look like gaps
  for almost any idea, independent of what actually matters for it.** Found by running 7 genuinely
  different ideas, not visible from one: `nonfunctional-performance`/`nonfunctional-availability`
  dominated the top-4 across all 7, own gap-check score high (0.36-0.81) even without a profile
  boost. A single worked example can't surface this kind of generalization failure — running the
  full idea set is cheap and catches it; running one idea repeatedly doesn't.
