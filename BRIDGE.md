# BRIDGE: where we are, for the next session

Updated 2026-09-24 (overnight autonomous session, user asleep throughout). Read `CLAUDE.md` too.
This file is the narrative; `docs/scenario-lab-structures-plan.md` is the actionable, per-item
backlog for tonight's work (now all DONE) and `docs/custom-decomposition-design.md` is the full
design the custom-decomposition build was implemented from. `foundry/PLAN.md` is still the
backlog for foundry's own unrelated open items (untouched this session, still open — see below).

## The headline: tonight's whole queue is done

The user asked, before going to bed, for autonomous overnight work on: (1) the 5 missing
Scenario-lab "structures" from `docs/scenario-lab-plan.md`'s old backlog (funnel/Monte Carlo,
incremental state, hierarchy, time, baseline), and (2) a new "Custom decomposition" feature —
freeform text in, decomposed live through the loaded models against a fixed generic library,
rendered as an extremely visual, browser-native experience. **Both are done, shipped, and
verified live** — see `docs/scenario-lab-structures-plan.md` for the per-item detail. In order,
this session also: restarted the kev-4b lineup (it was down from the prior session), re-validated
decompose-and-loop live with the full 5-model lineup, then built all 6 pieces.

**No loose ends.** The real `demo/server.py` process was restarted once `window_study.py` and its
`lab_time.py` follow-up both fully finished (the original follow-up watcher process died silently
for an unclear reason — background jobs launched with `nohup ... & disown` in this container
aren't guaranteed to survive; the original `window_study.py` job did survive the whole session, so
this isn't universal, just something to watch for — re-launched it directly once `window_study.py`
was confirmed done, and it completed in under a minute for `so1`/`laya`/`verdict`). All 5 loaded
local models plus hosted `jev` now have both `data/window-study/*.json` and
`data/probe-runs-v2/_time/*.json`. The real server was restarted cleanly, all five new endpoints
verified with real HTTP 200s, and a full puppeteer regression pass across all 10 Scenario-lab
pages plus a live custom-decomposition run (10/10 calls, zero errors) all passed against the real
production port-8100 process. Everything shipped tonight is live.

## What actually shipped, briefly (full detail in commit messages and the plan doc)

**Baseline (majority class)**: pure client-side, no new live calls — always-guess-the-most-common-
label accuracy per set, compared against each model's stored accuracy. Stronger than the existing
chance line on imbalanced sets.

**Funnel (Monte Carlo)**: honestly scoped to `memsafety` only — the one published set with a real
multi-item grouping (NIST Juliet bad/good CWE pairs). Extends foundry's own `monte_carlo.py`
technique with something foundry can never do: validate the forecast against real ground truth.
Real finding: hosted `jev` came back underconfident, `semif` came back badly overconfident — a
genuine, model-specific calibration result the compound view surfaces.

**Window size** (the honest reframe of "incremental state"): confirmed live that these models are
stateless prefill-only with no KV-cache reuse between calls, so the literal "read only new words
vs. re-read the window" comparison the old plan doc asked for isn't real — reframed around what
`probes/window_study.py` actually measures (AUC by trailing-window definition).

**Hierarchy (gate)**: new `probes/lab_hierarchy.py`, a live binary gate question on
`persuasion_appeals` (the one set with a real "none" class), reusing the existing stored flat
7-way answer as detail only if the gate fires. **Real, honest finding, reported plainly**:
hierarchical accuracy was *lower* than flat for every model tested (deltas -35.0% to +0.0%,
never positive) — splitting the question added a second, often weaker place to be wrong rather
than helping.

**Time (onset and false alarms)**: new `probes/lab_time.py`. No dialogue has a real turn-level
onset label, so this measures something self-referential instead that needs no such label: how
much of a manipulative dialogue plays out before a model's own running score commits to an alarm,
and how often a non-manipulative dialogue's running score false-alarms, per 10 turns (never "per
minute" — no real timestamps exist in this data).

**Custom decomposition**: the big one. `probes/lab_custom_decompose.py` is a from-scratch reimplementation
of foundry's Slicer+Grinder walk mechanics (shape-guaranteed category selection, one shared
priority queue, a real enforced budget) — read directly from `foundry/tools/world-knowledge.yaml`
and `slicer.yaml`, **not** importing `foundry/layered_walk.py` (which mutates a module-global model
list and writes its own ledger; a hybrid leaf battery from `lab_decompose.py` (gate/phase/risk/
complexity/dependency, dropping `atomic` — measured at noise level in foundry's own diagnostic —
and `parallel` — no real sibling group exists for freeform text). Since there's no ground truth,
it computes lift-over-a-control, cross-model spread, a flat-scoring-model flag, and a scope
warning instead of grading. **Live acceptance check passed exactly**: run on the same intake as
`layered_walk.py --idea oncall-rotation --budget 60`, the new engine visited the identical 58 node
ids in the identical order — byte-for-byte parity. Shipped with a full live-streaming UI: an
animated radial "orbit map" of all 111 library items lighting up as calls resolve (the actual
"extremely visual" ask), an accessible Outline view, a detail panel, a read-out card, spend-more/
download controls. Verified interactively end-to-end with a real headless Chrome (see below).

## New capability this session: real browser verification is now set up

Puppeteer + a real headless Chrome got installed in this container specifically because CLAUDE.md
requires testing frontend changes in an actual browser, not just reviewing code — `unzip` was
missing (installed via apt), then `npx puppeteer browsers install chrome` worked. Location:
`/tmp/pptr-test/node_modules`, Chrome cached at `/root/.cache/puppeteer`. **Use this for any future
Scenario-lab UI work** — screenshot before/after, a `pageerror`/console-error listener, and a full
regression pass across the other Structures pages after every change. This was used for every
piece of UI shipped tonight, including one genuinely interactive test (typing real text, clicking
Run, watching a live decomposition stream and animate, clicking a node, switching views, checking
dark mode).

**The pattern for testing server.py changes without touching the real running process**: since the
real `demo/server.py` (port 8100) must never be restarted while an experiment is running through
it (this session had `window_study.py`/`lab_time.py` doing exactly that for hours), every server.py
change tonight was verified by launching a *second*, temporary instance on another port
(`DEMO_PORT=810X python3 demo/server.py &`, `disown`), testing against it, then killing *only* that
PID (confirmed via `ps`/`curl` each time that the real instance was untouched). Use this pattern
again rather than ever restarting the real one speculatively.

## Infrastructure state

- **kev-4b**: restarted successfully this session (was down from the prior session), full 5-model
  lineup (`kev-4b`, `semif`, `so1`, `laya`, `verdict`) confirmed active, 28196/32607 MiB.
- **`probes/window_study.py`**: ran for `semif`/`so1`/`laya`/`verdict` (only `kev-4b` and hosted
  `jev` had data before tonight) as a detached background job, `logs/window-study/run.log`.
  `verdict` (CPU-bound) is the slow one. A queued follow-up
  (`logs/window-study/lab_time_followup.log`) runs `probes/lab_time.py` for `so1`/`laya`/`verdict`
  once `window_study.py` fully finishes, so the two never compete for the same model's GPU time.
  Check both logs — if either is still running, let it finish before restarting the real server.
- **`demo/server.py`** (port 8100): restarted 2026-09-23 ~02:46, running tonight's code, all new
  endpoints verified live.

## Gotchas learned the hard way, this session

- **A background job launched with `nohup ... & disown` is invisible to the harness's own
  notification system** — it's a detached OS process, not a tracked background task, so nothing
  auto-notifies on completion. Poll it explicitly (log tail, `ps`) on a real timer instead of
  assuming a task-notification will arrive.
- **Never assume a live-testable claim without actually testing it live.** The custom-decomposition
  design doc was extremely thorough on paper; the actual value came from running the CLI parity
  check for real (it could easily have silently diverged from `layered_walk.py` in some subtle way)
  and from an actual interactive puppeteer run, not from the design reading well.
- **A tuple-unpacking bug in freshly written code is exactly the kind of thing unit tests with a
  fake dependency catch before a single real model call is wasted on it** — `test_lab_custom_decompose.py`
  caught a `call_all_models` return-arity mismatch on the very first run, entirely offline.
- **Reframing a plan-doc item honestly, once the data says the literal framing doesn't hold, beats
  forcing the original framing.** Both "incremental state" (stateless models, no real KV-cache
  comparison possible) and the hierarchical-gate result (real, negative finding) were reported as
  what was actually true, not adjusted to match what the backlog assumed going in.
- **Real infrastructure conflicts (two live jobs wanting the same long-running server process) are
  worth designing around rather than serializing on blindly** — the temp-instance-on-another-port
  pattern let UI/server work continue in parallel with the hours-long window_study job instead of
  blocking on it.

## What's still open (unrelated to tonight's queue, from prior sessions, still true)

`foundry/PLAN.md`'s own backlog is untouched tonight: the `ATOMIC_THRESHOLD` drop/re-threshold
decision (kev-4b's data is now available again after tonight's restart — this is now unblocked,
next session could pick it up), the ~15-18 `world-knowledge.yaml` content edits identified but not
applied, `sort_and_rank.py`'s hosted-model-skip bug, and a real second review of the 21-category
library. The "learn from our foundry and update the demo" open question from the prior BRIDGE.md
is, in effect, resolved by tonight's custom-decomposition build — not by picking either of the two
directions that file laid out, but by a third path: a fresh, from-scratch reimplementation of
foundry's walk *mechanics* inside the demo, deliberately not importing foundry's own code or
touching `probes/decompose/`'s separate CPM/reference-plan system at all. Whether to *also* pursue
either original direction (porting CPM/dependency machinery into foundry, or foundry's generic-
library discipline into `probes/decompose/`) is still open, now a fresh question rather than a
continuation.

**Stretch goals explicitly out of v1 scope** (from `docs/custom-decomposition-design.md` §5, in
priority order if picked up later): a Board view (phase columns), a model-subset toggle, a Numbers
view (sortable/exportable table), a compare-two-texts overlay, saved-run replay, leaf-level lift
(21 more cached control calls), and an optional paid hosted-model escalation for "models split"
leaves.

## Scenario lab

`docs/scenario-lab-plan.md`'s original backlog (items 1-18) is now mostly superseded by
`docs/scenario-lab-structures-plan.md` for the structures specifically (items 6-13). Its other
items — overview orientation (item 1), family header labels (item 2), colour normalization (item
3), new probe sets beyond the existing 15 (item 4: PII, support escalation, toxicity, prosocial
safety, negotiation all still unbuilt), blind grading (item 14, still planning-stage only), and the
lineup/benchmark items (15-18: jevbench is still 8+ commits behind upstream v1.3.0, which changes
scoring) — remain genuinely open, not touched tonight.
