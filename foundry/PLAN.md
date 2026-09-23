# Foundry: target improvements, on file

Written 2026-09-22. Consolidates two things that, until now, only existed as chat/agent-report
output and were never saved: the Opus arbitration of OPENAI-LOOP.md vs. this session's own
loop-mechanism analysis, and a second-review pass on `tools/world-knowledge.yaml`'s content. Read
`BRIDGE.md` first for how this session got here; this file is the actionable backlog, not the
narrative.

Status tags: **DONE** (committed), **DECISION NEEDED** (blocks on the user, not engineering),
**READY** (diagnosed, sized, no open decision — next to build), **NEEDS DIAGNOSTIC** (a real
measurement has to happen before this is safe to build).

## Already done (this session)

- Retired the 12 original `gap_categories`; 21 requirement-shaped ones remain, all with a library.
- Authored the 6 missing idea customer-intakes; ran all 7 ideas live (`comparisons/seven-idea-run-2026-09-22.md`).
- Fixed a real polarity-inversion bug in `layered_walk.py`'s `walk()` breadcrumb (asserted each
  selected gap as *true* when it was selected because it's *not* true).
- Added per-model values to the ledger (`gap_check`/`grinder_node` emits) — previously only
  mean/spread, which meant no diagnostic could ever be run against a past ledger.
- Ran the atomic-gate diagnostic (`diagnose_atomic_gate.py`, untracked — worth committing) against
  90 known-atomic leaves vs. 21 known-compound categories. Result, reproduced on a clean rerun: on
  the 2 of 3 default models that answered (kev-4b is currently down), separation between atomic
  and compound scores is +0.006 — noise-level. Current `ATOMIC_THRESHOLD=0.18` scores 21.6%
  accuracy on these controls, worse than the 81.1% you'd get by calling everything atomic.
- **Rewrote `layered_walk.py`'s selection and walk mechanism** (the "aggressive plan" pass): shape-
  guaranteed + budget-ranked category selection replacing the pooled top-4, a shared priority-queue
  walk replacing fixed top-k depth-first recursion, margin-based domain/audience trust replacing
  `DOMAIN_AUDIENCE_FLOOR`'s flat 0.6, and a new `decomposition_depth` score signal. Verified live:
  `oncall-rotation` went from 1 requirement / 18/80 budget spent to **13 requirements / 80/80
  budget spent**, all 6 shapes represented; `sleep-coach-wearable` (previously 0 requirements) went
  to **4**. `report.py` and `sort_and_rank.py` both stayed compatible, unmodified except one
  additive line in `report.py`. See the commit for full detail. `ATOMIC_THRESHOLD` itself was
  deliberately left untouched this pass (still pending kev-4b's data).
- **Built a demo qualitative Monte Carlo risk-concentration pass** (`monte_carlo.py`,
  `tools/monte-carlo.yaml`): checked the real PMBOK distinction first (qualitative risk analysis =
  ordinal scores for relative prioritization, no units; quantitative Monte Carlo = needs real
  time/cost estimates, which this project has already refused to fabricate twice — see
  `monte-carlo.yaml`'s `methodology_note`) and built only the qualitative version, honestly scoped.
  `sort_and_rank.py` now persists its scoring (`runs/<idea>-sort.jsonl`) — previously printed to
  terminal scrollback only. Samples each requirement's live risk/effort score as a distribution
  (mean + cross-model spread, not a fixed number), ranks categories by contribution to the
  *variance* of simulated exposure (a real sensitivity-analysis technique), and translates the
  ranking onto a real, cited illustrative scale (COCOMO Organic mode, Boehm 1981, verified against
  real sources — 10 KLOC -> ~27 person-months) — explicitly labeled illustrative, never a claim
  about the actual idea's size. Verified at base level across all 7 ideas, including 2- and
  3-requirement edge cases, no failures. Full writeup with real numbers:
  `comparisons/jev-monte-carlo-showcase-2026-09-22.md`.

## Infrastructure blocker

- **kev-4b is down**, stopped cleanly (not crash-looping). Caused by an oversized diagnostic batch
  OOM-ing it; a restart then failed to reload because the other 4 loaded models already hold the
  GPU memory it needs at startup (documented requirement: it must load first). Recovery = restart
  the full lineup in order. **DECISION NEEDED**: say when to do this — it's a bigger action than
  the one service that broke, so it hasn't been done without you. Blocks getting kev-4b's data
  into the atomic-gate diagnostic (currently 2 of 3 models only).

## Loop mechanism (source: Opus arbitration of OPENAI-LOOP.md vs. the current design)

The measurement that decided most of this: the whole reachable search space is 113 live calls (1
domain/audience call + 1 gap-category call + 21 category nodes + 90 leaves). Budget is 60-80. The
7-idea run spent 18/80 (22.5%) per idea. OpenAI's proposal is sized to navigate a frontier you
can't afford to exhaust (`max_nodes: 500`); here you nearly can exhaust the whole thing.

**DONE:** the priority-queue walk and shape-guaranteed selection (see "Already done" above) —
replaces `GAP_TOPK`/`CHILD_TOPK_BOOSTED`/`CHILD_TOPK_NORMAL` entirely. Budget utilization is now the
real, only cutoff, which means the "decision needed" item below about what "selected" means as a
claim is live now, not hypothetical — `report.py`'s table was relabeled "guaranteed" to stay honest
about it.

**READY — no open decision, small, cheap:**
- Standing per-run calibration record: terminal-state counts, score distributions, budget
  utilisation, written alongside the ledger. Zero live calls, pure instrumentation.
- Offline duplicate lint over the fixed 90-leaf library (deterministic script, no calls). Already
  spot-checked by hand: 3 near-duplicate pairs found, none alarming — see content-review section
  below for the actual pairs, which is more specific than the arbitration's own quick check.

**NEEDS DIAGNOSTIC before building — the atomic-gate diagnostic above is step one of this:**
- Whether to drop the leaf atomic gate entirely (a reached leaf becomes the requirement directly,
  using the parent/child relevance score as its confidence) vs. keep it with a re-derived
  threshold. Current evidence (2 of 3 models) points at "drop it" — get kev-4b's data first.
- An escalation rung for the "needs a decision" (cross-model disagreement) bucket, which today just
  reports and stops — 40% of all leaf checks in the 7-idea run landed there. SDE-cascade precedent:
  an any-flag gate, escalate to a stronger check rather than average into silence. Candidate rung:
  hosted P0, once `sort_and_rank.py`'s unrelated `hosted`-skip bug (`funnel.py:162`) is fixed for
  the Sorter half — `layered_walk.py` itself has no such skip already.
- A saturation/plateau stop (the autoresearch cookbook's own stopping rule has this half; foundry
  only has the budget half). Needs one number, best derived by replaying existing ledgers once the
  priority queue is in.

**DECISION NEEDED (yours, not engineering):**
- Once the queue can walk 12-20 of 21 categories instead of a fixed 4, "the model selected the top
  4" stops being literally true — the budget itself becomes the selector unless you deliberately
  cap it below 113. Say which framing you want.
- Whether to spend hosted P0 on escalation (~5 calls/idea, cheap, but real money and a dependency
  the scripts can't reach on their own).

**Rejected, with reasons (from the arbitration, not re-litigated here unless you want to):**
- OpenAI's `max_nodes: 500`/`max_depth: 8` scale (whole space is 113 calls, depth 1).
- The product-of-5-dimensions priority formula (deviates from Composite Scoring's own documented
  weighted-sum guidance; a product means any one weak dimension vetoes the rest).
- Its specific thresholds (`atomicity: 0.90` etc.) — refuted by this project's own measured numbers.
- `information_gain`/`novelty`/runtime duplicate detection (need generation or similarity; neither
  exists here) and cycle detection (impossible today — 0 internal tree nodes below category level).
- Any automated write-path from observed runs back into `world-knowledge.yaml` — violates the
  project's one rule as sketched; the log-then-human-authors-offline shape is fine, auto-promotion
  is not.

## World-knowledge content (source: second-review pass, this session)

**Verdict from the review**: "a reasonable starting point after one targeted pass, not before it."
None of this needs a structural rebuild — it's targeted edits.

**READY — specific text fixes, no open decision:**
- `story-resume-setup`: literal "and" joining an always-true clause to the real fact. Fix:
  "As a new user, I can resume setup where I left off after stopping partway."
- 7 leaves with a hidden second claim (no literal "and"/"or" but two judgments in one): 
  `func-precondition-per-action`, `func-outcome-per-action`, `ops-single-command-deploy`,
  `arch-dependency-isolation`, `story-admin-change-role`, `story-admin-revoke-access`,
  `story-value-in-first-session`. Specific rewrites for each are in the review report (ask if you
  want them reproduced here in full rather than re-fetched).
- 2 wrong-quantifier leaves (`arch-dependency-failure-behavior`, `ops-alert-threshold`) satisfiable
  by a single instance when they should apply to every instance.
- 3 design-prescriptive leaves that assume one implementation choice (`func-record-retention-period`,
  `func-record-change-history`, `nfr-maintenance-window`).
- `ops-incident-response`'s category text is the most oncall-rotation-shaped text in the library
  ("the on-call responder") — doesn't fit non-rotation ideas.
- The word "interface" means two different things in `spec-api-contract` (API) vs.
  `nonfunctional-accessibility` (UI) — a real collision risk.
- 3 categories whose own defining claim no leaf ever checks (`architecture-component-boundaries`,
  `architecture-data-ownership`, `functional-core-capability`) — each needs one added leaf.
- 2 strong near-duplicate pairs worth merging or differentiating:
  `func-record-change-history`/`story-see-what-changed`, `story-resume-setup`/`story-keep-partial-input`.

**READY — profile_probes fixes, confirmed against real run data, not just text review:**
- `offline-capable → nonfunctional-availability` is a real mis-mapping: offline is client-side,
  availability leaves are all server-uptime. Confirmed live: this pushed a 1.44-1.46 boost onto
  sleep-coach-wearable and voice-extension (both on-device, no server) — see
  `comparisons/seven-idea-run-2026-09-22.md`. Proposed replacement:
  `story-error-recovery` + `functional-data-lifecycle`.
- `frequent-change → ops-release-process` confuses runtime reconfigurability with engineering
  deploys; confirmed driving that category into 2 of 7 ideas' top-4 for the wrong reason. Proposed:
  drop both current boosts; no category currently covers "reconfigurable by non-engineers" (a real
  gap, not just a mapping error).
- `mobile-required → story-first-use` has no clear rationale; proposed: `ops-release-process`
  (app-store release lag) + `nonfunctional-performance`.
- 5 of the 9 unboosted categories should plausibly get one: `functional-access-rules`,
  `ops-observability`, `ops-data-recovery`, `spec-api-contract`, `story-administration` — specific
  probe-to-category additions are in the full review report.

**DECISION NEEDED:**
- `domain_enrichment` has 2 confirmed errors (`consumer-hardware-iot` lists a delight that
  contradicts being hardware; `cost-surprise`/`predictable-pricing` never used anywhere despite
  fitting `customer-facing-saas`) plus ~4 of 10 domains reading as near-interchangeable filler.
  Fixable, but is filling in generic vocabulary worth doing now vs. later — your call on priority.
- The review's own structural note: ~62 of 90 leaves are "is this documented/specified/named"
  completeness checks, which are close to guaranteed to read as gaps against any one-paragraph idea
  pitch (this is finding 1 from `comparisons/seven-idea-run-2026-09-22.md`, now traced to a
  specific cause). Whether that's the library working as intended (audit rigor) or a shape problem
  worth addressing is a real judgment call, not a bug — flagged, not resolved here.

## Suggested order if you want one

1. Commit `diagnose_atomic_gate.py` (already working, untracked).
2. Decide kev-4b lineup recovery timing; get its diagnostic data once it's back.
3. Leaf text fixes + probe boost fixes (both READY, no decision blocking them) — these change what
   every future run selects and finds, so doing them before more loop-mechanism work means the loop
   changes get tested against corrected content, not content already known to be wrong in 3 places.
4. Priority-queue rewrite (READY) + the leaf-atomic-gate decision (NEEDS kev-4b data first).
5. Escalation rung, only after its own diagnostic and after the P0 policy decisions above.
