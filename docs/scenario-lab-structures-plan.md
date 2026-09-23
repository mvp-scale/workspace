# Scenario lab: structures 8/10-13 + custom decomposition — build plan

Written 2026-09-24, by Claude, autonomously overnight per the user's go-ahead. Supersedes the
"Structures that make sets harder" backlog in `docs/scenario-lab-plan.md` (items 6-13) for items
7-13 specifically -- those are now **verified against real code** by three parallel audits this
session, not assumed from the (partly stale) plan doc. See the chat transcript for the full audit
results if needed; this file is the actionable version.

## Ground truth on current state (verified 2026-09-24)

- **Built and live**: batch performance (item 6), cascade/routing (item 7), decompose-and-loop
  (item 9). `demo/scenarios.html`'s `STRUCTURES` array lists exactly these three:
  `["batch", ...], ["decompose", ...], ["cascade", ...]`.
- **Never started**: funnel/Monte Carlo (8), incremental state (10), hierarchy (11), time (12),
  baseline (13). No `lab_*.py`, no `/api/*` endpoint, no UI section for any of the five.
- **Important find**: `probes/window_study.py` + the still-live `/api/window-study` endpoint
  (confirmed in `demo/server.py`) already measures which trailing window (last N words/sentences/
  turns) best flags manipulation over the 200 labelled dialogues in `probes/v2/manipulation_windows.json`
  -- this is most of the *substance* of "incremental state" (item 10) already computed. Its UI page
  was removed (CLAUDE.md: "the Text windows and Call monitor pages were removed, their
  `/api/speeches` and `/api/window-study` endpoints remain"), so item 10 is mostly a re-surfacing
  job, not new measurement, **if** the stored data actually supports the "read only new words vs.
  re-read the window" comparison the plan doc asks for -- confirm this by reading
  `probes/window_study.py`'s actual output shape before assuming it fits; if it only supports
  "which window size wins," that's a different (still useful, differently-framed) structure.
- **Run principle** (from `docs/scenario-lab-plan.md`, restated): every structure needs an offline
  runner (one model at a time, full GPU, per-item records, resumable, output outside
  `data/bench/`) AND a live path through `demo/server.py` for tests that belong in the page itself
  (batch size, cascade threshold, decompose). The existing three structures both compute from
  **already-stored** `data/probe-runs-v2/*/results.jsonl` (cascade, no new calls at all) or from a
  dedicated offline runner's own JSON (batch, decompose). Prefer the "compute from what's already
  stored" shape wherever the structure's definition allows it -- it's free, it's already correct
  data, and it's the same trick cascade already used.
- **Styling contract** (from `demo/scenarios.html` + `demo/static/app.css`): design tokens only,
  no page-local colours; `STRUCTURES` array + `RAIL_ICONS` glyph convention (add one glyph per new
  structure, in the same `"pathd|pathd|..."` mini-language); `srcNote()` — every claim on the page
  traces to a real file path, shown on hover, exactly as decompose-and-loop and batch already do;
  DOM built with `Jev.el`/`S` (svg) and `textContent`, never `innerHTML` with data; per-model
  display always via `mtagShort`/`Jev.tag`/`Jev.codeOf`, never a raw id.

## Per-structure design

### 13. Baseline — build first, purely offline, no live calls

"Every claim gets a baseline (generative LLM or single-question classifier) on the same items."
The honest, buildable version: a **majority-class baseline** (predict the most common label in each
set) and, where classes are balanced, a **fixed-answer baseline** — both computed entirely from
`expected` labels already in `probes/v2/*.jsonl` and `data/probe-runs-v2/*/results.jsonl`. Zero live
calls, deterministic, a few minutes of Python. Purpose: shows whether a typed decision model beats
the trivial floor, not just chance-adjusted accuracy (which the lab already shows) — a majority
baseline can beat "chance" on an imbalanced set even though it knows nothing. Ship as a column/row
addition to the existing overview heat table (`table.heat`) plus its own Structures page, reusing
`wilson()` and `stepBg`/`heatBg` exactly as batch/cascade do. No new offline runner script needed —
compute in `demo/server.py`'s existing `probe_detail`/`probe_sets` machinery or a tiny new function
next to them.

### 10. Incremental state — CONFIRMED: the literal framing doesn't fit; reframe honestly

Read `probes/window_study.py` in full (done). Verdict: **the "read only new words vs. re-read the
window" comparison from the plan doc is not buildable as a real architectural difference.** These
models are stateless, prefill-only, one call per verdict (see `kev/model.py`'s own description via
CLAUDE.md: "runs a causal LM prefill-only... no generation") — there is no KV-cache or session state
that persists between `/v1/systemone` calls, so *every* window spec re-reads its whole trailing
window from scratch on every call, always. There is no "incremental" path to compare against a
"full re-read" path — they're the same thing here. Fabricating that comparison would violate this
project's own rule against inventing what the data/architecture doesn't support (see
`foundry/README.md`'s "one rule that matters most").

**What's real and worth shipping instead**: `window_study.py` already measures, per window
definition (`w5,w10,w20,w40,s1,s2,s3,t1,t2,t3,full`), AUC of flagging manipulation over 200 labelled
dialogues — a genuine "how much context does a verdict need" question, just not an incremental-cost
one. Stored results exist today for only 2 of the current lineup: `data/window-study/kev-4b.json`
and `jev-typesafe.json` (hosted). **Not yet run for `semif`/`so1`/`laya`/`verdict`** — run
`python3 probes/window_study.py --backend <name>` for each (needs `demo/server.py` up, which it
already is — do NOT restart it) once the kev-4b lineup restart lands, so all current models get
comparable fresh data. This is a live batch job (thousands of `/api/batch` calls per model at
default settings — check `--limit` to size it reasonably for an overnight run) and should be
kicked off early since it's the longest-running piece of the five structures. Ship as: a Structures
rail entry, render function following the batch/cascade pattern (AUC by window size, with the
already-good `boot_ci` 95% interval), `srcNote` pointing at `probes/window_study.py`, reusing the
already-live `/api/window-study` endpoint verbatim (it needs no changes — it already returns
per-backend stored JSON).

### 8. Funnel (Monte Carlo) — DONE, 2026-09-24

Shipped as designed below. Verified live with puppeteer across two very different models: hosted
`jev` came back **underconfident** (forecast 40.6 of 77, actual 51, outside the 90% interval on the
high side) while `semif` came back **overconfident** (forecast 18.6, actual only 4, outside on the
low side) — a genuinely interesting, real finding the compound-calibration view surfaces that a
flat accuracy number wouldn't. CWE-family sensitivity ranking also produces real, varying
per-model weak spots (e.g. semif: 0% actual on 8 of 10 CWE families; jev: a real spread from 25% to
100%). No console/page errors, no regressions on the other four structures + overview + a per-set
page, all re-checked after this change.

### 8. Funnel (Monte Carlo) — original scoping notes: memsafety only, real pairs, real ground truth

Checked every `build_*.py` in `probes/v2/`: only `build_memsafety.py` populates a real `group`
value (`memsafety_cwe{N}_{seq}`, one per NIST Juliet CWE test case) — every other set's builder
writes `"group": None`. Don't fabricate groupings on sets that don't have them (this project's own
rule). Ship Funnel scoped honestly to `memsafety`'s real structure: each group is a **bad/good
pair** — two items testing the same CWE pattern, one genuinely vulnerable, one fixed.

Design (extends foundry's proven `monte_carlo.py` mechanism — sample each item's live probability
as a distribution, combine by a rule, rank drivers by correlation² contribution to variance — but
**with real ground truth to validate against, which foundry explicitly cannot do**): for each pair,
Monte Carlo-sample "model correctly discriminates this pattern" = P(bad item scored vulnerable) ×
P(good item scored not-vulnerable), using each item's own live probability as the sampling mean
(same triangular-draw technique as foundry, no new cross-model spread source needed since these are
single-model runs already in `results.jsonl`). This gives a **forecast probability per pair**, not
just a point prediction. Then — the part foundry can't do — bucket pairs by forecast probability and
plot **actual empirical rate of both-items-correct within each bucket**: a real reliability diagram
for a *compound* event, genuinely harder than and different from any single-item calibration curve
already in the app (see the existing `.rc` reliability-curve CSS class — confirm during build
whether report.html/models.html already has a single-item version, so this can point at it as "here,
extended to a compound event" rather than duplicate it). Rank CWE families by their contribution to
the variance of the total correctly-discriminated-pair count, exactly as foundry's sensitivity
technique already does. Zero new live calls — all from stored `results.jsonl` `probs` per item,
grouped by the already-stored `group` field. Pure post-processing, like cascade and baseline.

### 12. Time — builds on the same dialogue data as manipulation_windows / Conversation flow

"Onset, escalation, detection lag, false alarms per minute" needs turn-by-turn, time-indexed
verdicts over a dialogue, not single-item classification — check whether
`probes/v2/manipulation_windows.json`'s 200 labelled dialogues carry a labelled onset turn/time (a
point where manipulation starts, if the dialogue is manipulative) or whether that has to be newly
authored (small, honest addition — a handful of dialogues with a hand-labelled onset point, in the
same spirit as `probes/decompose/`'s planted coverage gap, clearly marked hand-authored). If an
onset label doesn't exist, this structure needs a small new offline runner: run each model over
growing turn-prefixes of N dialogues (reusing `flow.html`'s existing `buildTimeline`/`runner.feed`
scoring shape if it fits, per CLAUDE.md's note that the transcript source is designed to be reused
this way) and derive onset/lag/false-alarm-rate per model from the per-turn verdict stream.

### 11. Hierarchy — most novel, build last of the five, needs a real new offline runner

"Cheap gate questions, fine questions only when the gate opens" — distinct from cascade (which
escalates across *models*), this escalates across *questions* within one model: a cheap yes/no gate
question, then a fuller battery only if the gate fires. No existing probe set has this two-stage
battery shape today. Design it against a set that already has natural sub-structure — e.g.
`checklist_contractnli` (gate: "does this contract need review at all?"; detail: the existing
checklist items) or `manipulation_dialogue` (gate: "any manipulation at all?"; detail: technique
sub-type, if MentalManip's raw labels carry one — check `probes/v2/build_manipulation_dialogue.py`
for what the source dataset actually labels before inventing sub-categories that aren't in the real
data). Needs a genuine new offline runner (`probes/lab_hierarchy.py`, one call for the gate + one
call for the detail battery per item, same shape as `lab_batch.py`/`lab_decompose.py`), reporting
accuracy and cost (calls made) against the always-ask-everything baseline.

## Validate decompose-and-loop (item 9) — DONE, clean, 2026-09-24

Read `probes/lab_decompose.py` and `probes/decompose/build_tree_edge.py` end to end looking
specifically for the two bug classes foundry found in itself this week: a polarity inversion
(asserting something as true when it was selected/graded because it's *false*) and a structural
gate bug (a score threshold overriding known structure). None found: `grade()`'s
`(p >= 0.5) == ref` comparisons for atomic/covers/gate/parallel/dependency are all directionally
consistent; `simulate_loop()`'s premature-stop detection correctly only fires for non-leaf nodes
scoring above threshold; `cpm()` already documents and fixes its own historical informs-edge bug in
a comment.

**Re-ran it live** with the full restored 5-model lineup (kev-4b was down, now back —
see "Infrastructure" below): `python3 probes/lab_decompose.py --models semif kev-4b so1 laya
verdict --tree decompose/tree_ref_edge.json --out
../data/probe-runs-v2/_decompose/tree_scored_edge.json`. Clean: 155/155 calls answered, 0 errors,
0 NaN. Spot-checked the planted `sys-train` coverage gap by hand against the raw JSON: semif
(covers_p=0.35) and so1 (covers_p=0.02) correctly flag it as not covered; kev-4b (0.93), laya
(0.62) and verdict (0.62) miss it — consistent with, and a fresh independent re-confirmation of,
the semif/kev-4b/so1-recurse-vs-laya/verdict-stop-at-root pattern documented in
`foundry/README.md`. New data point this run: kev-4b recurses correctly (depth 2.0, matching
semif/so1) but still misses the planted gap — a real model-capability finding, not a harness bug.
Item 9 is validated; safe to build on top of.

## Infrastructure: kev-4b restart — DONE, 2026-09-24

Per the user's earlier go-ahead, restarted the full lineup in the documented order
(`demo/lineup.sh down` then `up`, kev-4b first) to recover kev-4b from its stopped state. All five
models (`kev-4b`, `semif`, `so1`, `laya`, `verdict`) confirmed active afterward, 28196/32607 MiB.
`demo/server.py` was never touched/restarted (per its own rule) — only the backend model services.

## Custom decomposition (freeform, visual) — design delegated separately

The one genuinely new, undefined piece: freeform text in, live decomposition through the loaded
models following this project's own methodology, rendered as a highly visual, delightful,
browser-native tree. This needs a real design pass (methodology choice, visual language, live API
shape) before any code — delegated to a separate design pass this session; see
`docs/custom-decomposition-design.md` once it lands.

## Build order — progress as of 2026-09-24, late session

1. ~~Validate decompose-and-loop~~ DONE.
2. ~~Baseline (13)~~ DONE, shipped and verified.
3. ~~Incremental state (10)~~ DONE, shipped as "Window size" (the honestly-reframed version — see
   above). Verified live with 2 of the eventual 6 models (kev-4b, jev — the two that already had
   data); the page reads `/api/window-study` live, so it will pick up semif/so1/laya/verdict
   automatically as `logs/window-study/run.log`'s background job finishes writing their JSON, no
   further UI change needed. Handled the `jev-typesafe` legacy filename/backend-string correctly
   (maps to canonical id `jev`, never displays the raw legacy string, per CLAUDE.md's own callout).
4. ~~Funnel/Monte Carlo (8)~~ DONE, shipped and verified.
5. ~~Time (12)~~ DONE, shipped. Confirmed no dialogue carries a turn-level onset label (checked
   the actual keys: id/source_id/turns/n_turns/manipulative/technique/vulnerability/label_scope,
   dialogue-level only) -- didn't fabricate one. Built `probes/lab_time.py` instead around a
   self-referential measure that needs no onset ground truth: onset lag = how much of a
   manipulative dialogue plays out before the model's own running "everything so far" score
   crosses 0.5 and stays there for good (a committed alarm, not a one-turn blip); false-alarm rate
   = how often a non-manipulative dialogue's running score crosses 0.5 at all, reported per 10
   turns (not "per minute" -- there's no wall-clock time in this dataset, and claiming one would
   be fabricating a unit). Ran live for semif and kev-4b (both free of the window_study.py job);
   so1/laya/verdict queued as a detached follow-up job
   (`logs/window-study/lab_time_followup.log`) that waits for window_study to fully finish before
   running, so the two jobs never compete for the same model's GPU time. Verified UI against a
   third temporary server instance (port 8102, killed after -- confirmed via `ps` that only the
   temp instance died). `demo/server.py` needs one restart to serve both `/api/hierarchy` and
   `/api/time-study` in production -- still deferred until `window_study.py` (and now its
   `lab_time.py` follow-up) fully finish.
6. ~~Hierarchy (11)~~ DONE, shipped. Built on `persuasion_appeals` -- the one published set with a
   genuine "none" class alongside real technique labels. New `probes/lab_hierarchy.py`: one live
   gate call per item (binary "any technique at all?"), reusing the existing stored flat 7-way
   answer as the "detail" prediction only when the gate fires. Ran live for all 5 loaded models.
   **Real, honest finding**: hierarchical accuracy was LOWER than the flat baseline for every
   single model (deltas from -35.0% to +0.0%, never positive) -- splitting the question adds a
   second place to be wrong (the gate itself, sometimes badly anti-correlated, e.g. one model's
   gate scored 31% against an 85.7% majority-class floor) rather than replacing one hard call with
   two easier ones. Reported plainly, not reframed to look better.
   **Verification note**: `demo/server.py`'s new `/api/hierarchy` endpoint could not be tested
   against the real running server (port 8100) because `probes/window_study.py` was mid-run
   against it in the background and restarting would have broken that job (BRIDGE.md's own rule:
   never restart demo/server.py while an experiment runs through it). Verified instead against a
   temporary second instance on port 8101 (`DEMO_PORT=8101 python3 demo/server.py`), then killed
   that instance -- confirmed via `ps`/`curl` that only the temp instance died and the real server
   (PID logged at start, running since 2026-09-22) was untouched. **The real port-8100 server still
   needs a restart** to actually serve `/api/hierarchy` in production -- do this once
   `logs/window-study/run.log` shows all four remaining models finished, not before.
7. ~~Custom decomposition~~ DONE, shipped as designed, full v1. `probes/lab_custom_decompose.py`
   (core walk engine, hybrid of foundry's Slicer+Grinder mechanics + lab_decompose.py's leaf
   battery minus atomic/parallel), `probes/test_lab_custom_decompose.py` (10 unit tests, no
   models, all passing), `demo/server.py` (3 endpoints incl. a streaming NDJSON POST), and the
   full `scenarios.html` UI (input card, live run controls, an animated radial "orbit map" of all
   111 library items lighting up as calls resolve, an accessible Outline view, a detail panel, a
   read-out card, provenance card, spend-more/download controls). **Live acceptance check passed
   exactly**: the CLI run on oncall-rotation (same intake/models/budget as
   `layered_walk.py --idea oncall-rotation --budget 60`) visited the identical 58 node ids in the
   identical order -- byte-for-byte match, strong evidence the port is faithful. Verified live,
   interactively, end-to-end with puppeteer against a fifth temporary server instance (port 8105,
   killed after): typed real text, ran a live 15-20 call decomposition against loaded models,
   watched the map fill in, clicked a node to open the detail panel, switched to Outline view,
   checked dark mode -- zero console/page errors throughout, zero errors in any live run, full
   regression pass across all 9 Structures entries clean. `foundry/README.md` updated per the
   design's own default decision (open question 1): its library is now read, read-only, by this
   module.

**Everything is shipped, live, and committed.** `STRUCTURES` in `scenarios.html` has 9 entries:
batch, decompose, cascade, baseline, funnel, window, hierarchy, time, custom. The background
window_study/lab_time jobs finished (all 5 local models + hosted jev have complete data in
`data/window-study/` and `data/probe-runs-v2/_time/`); the real `demo/server.py` (port 8100) was
restarted cleanly afterward and all five new endpoints (`/api/hierarchy`, `/api/time-study`,
`/api/decompose-library`, `/api/decompose-examples`, `/api/decompose-live`) verified with real
HTTP 200s and a full puppeteer regression pass, including one live custom-decomposition run
against the real production process. Nothing left from tonight's queue.

**Tooling note for whoever continues this**: puppeteer + Chrome are now installed in this
container (`/tmp/pptr-test/node_modules`, `/root/.cache/puppeteer`) specifically so UI changes here
can be visually verified with a real headless browser before committing, per CLAUDE.md's rule to
test frontend changes in a browser, not just review the code. Use it for every remaining structure
and for the custom-decomposition build — screenshot before/after, check `pageerror`/console-error
listeners, and do a quick regression pass across the existing structures after each change (see the
git log for the exact puppeteer invocation used for Baseline/Funnel).

Each ships as: offline computation (new runner only where truly needed, per above) → `/api/*`
endpoint in `demo/server.py` → `STRUCTURES` rail entry + render function in `scenarios.html`,
same shape as batch/cascade/decompose → commit.
