# 16 · The working loop

**Goal:** one repeatable way to ask a question of the pipeline, run it, score it honestly, record it, and get faster and safer each time. Written 2026-11-10 from the first long session in which the loop ran for many hours (ledger T27 to T74). Everything marked *built* exists today; everything marked *to build* is a proposal ("ours", not from a published source) and is listed in section 15 with an order.

## 0. The page in one paragraph

Every piece of work is a **round**: one question, one change, a prediction written before the run, a quick smoke test, the real run under a time cap, an automatic score against the prediction, a record on the ledger, and a pages rebuild. A **health check** tells you every 3 minutes whether the pipeline is working, waiting, idle or broken, and on what. When nothing is running and nothing is waited on, the next ready round starts. Every 10 rounds a **retrospective** looks at how the process itself performed (crashes, idle time, forecast hits) and changes exactly one process setting, with a prediction, and reverts it if the number does not move. The loop may change its own process settings; it may never change the sealed set, the labels, spending, GPU use or the engine without the owner's yes.

## 1. Words

| Word | Means |
|---|---|
| **Round** | One question, one change, one prediction, one score. The unit of work. |
| **Round card** | The JSON file that declares a round (section 3). The numbers on the ledger come from files named in the card, never from typing. |
| **Main loop** | The model-improvement rounds only (owner vocabulary, README): train, score on a clean held-out set, mine the mistakes, change one thing, repeat. |
| **Scheduler** | The timer that wakes the agent (`/loop` wakeups). It is not the main loop. |
| **Health check** | `kit/live/health.py`, every 3 minutes: working, waiting, idle or broken (section 9). |
| **Smoke test** | The round run on 5 items, through to its output file, before the full run (section 4). |
| **Sealed set** | The 1,499 items scored once per head. Scores are agreement with Sonnet, not outside truth. |
| **Prediction** | A range written on the ledger before the run, with the reason (section 5). |
| **Retrospective** | The every-10-rounds look at the process itself (section 11). |
| **Owner yes** | A decision only the owner can give (section 12). |

## 2. The cycle

1. **Sense.** Read the health line and the backlog. The backlog is the list of round cards that are *ready* (their inputs exist and nothing they depend on is open).
2. **Decide.** Start every ready round that fits the free CPU cores, in parallel. If nothing is ready and nothing is running, say so and name what blocks it.
3. **Predict.** Fill the card's prediction. Pass `loop_gate.py`. If it says the round needs a yes, stop and ask once with the reason.
4. **Smoke.** Run the card on 5 items into a scratch folder. If it fails, fix it and smoke again; the full run does not start.
5. **Run.** Full run under the card's time cap. The runner registers a heartbeat, writes the log, and closes the row itself.
6. **Score.** Compare with the predicted range and with the baseline, using the fixed words (section 6). A post-hoc analysis is labelled as such and never replaces the registered result.
7. **Record.** Ledger score note citing the prediction id, step marks, an independent verdict (a different agent, `cp.mjs verdict`, AGENTS.md rule 5; local Clef through `tools/mm3local` is free, and a split is recorded, not resolved), close with evidence, pages rebuilt (gates, solver, bitmobs, state, learned), Training tab data rebuilt.
8. **Learn.** Add the lesson to `LESSONS_LEARNED.md` the same day. Every 10 rounds, run the retrospective.

Between rounds the scheduler wakes the agent. The cadence follows the health line: about every 25 minutes while rounds run, longer only when every round is blocked on the owner.

### 2a. How the loop continues without the clock
- **Queue:** the agent writes a round card (prediction, smoke, cap) into `kit/live/round_cards/queue/` for each planned round. Optional fields: `priority` (lower first), `after` (card ids that must have a SCORE note), `parallel`.
- **Start:** every poll, `backlog.py` starts the next ready card when nothing is running, through `run_round.py` and `loop_gate.py`. A card that needs the owner's yes, has no open ledger task, or fails validation is left in the queue with the reason printed. Remove `backlog.enabled` to switch it off.
- **Finish:** the card moves to `started/`, then `done/` (SCORE note found) or `failed/` (the process ended without one). Either writes `runs/rounds/<id>.done`.
- **Wake:** the agent arms a Monitor that waits for a new `.done` file, so the next step starts when a round ends, not at the next clock tick. The clock wake stays as the fallback.
- **Clean:** `sweep.py` runs in the same poll: it moves finished and dead rows to the history and reports orphans, unscored predictions, stale pages, stuck queues and the share of rounds that missed.

## 3. The round card

*Built:* `kit/live/run_round.py` reads one card, validates it, reads the baseline from its file, runs `note_guard.py` on the prediction text, writes the PREDICTION note, runs the command under the time cap, reads the result file, and writes the SCORE note. Cards live in `kit/live/round_cards/`; `example_ok.json` is the template and the `bad_*.json` cards are the validator's tests.

| Field | What it is for |
|---|---|
| `id`, `task`, `who` | The round, the ledger task it belongs to, and the actor code (for example S2). |
| `part` | Which part of the main loop it moves. |
| `field` | The model or field it is about (topic, story type, presence, kinds, size, Area...). |
| `question` | One sentence, answerable yes or no or with one number. |
| `one_change` | The single thing that differs from the baseline. A round with two changes is two rounds. |
| `baseline` | `{model, file, key}`: the score to beat, read from a file, never typed. |
| `prediction` | `{metric, file_key, low, high, why}`: the range and the reason. |
| `command` | The command. CPU only unless the owner said yes; isolated venv for any install. |
| `result` | `{file, key}`: where the score will be read from. |
| `cap_minutes` | Hard time cap, 60 or less. |
| `smoke` | Required. `{command, cap_minutes}` runs on a few items into a scratch folder before anything is written; if it fails, nothing is launched and no prediction is written. Or `{skip: reason of 20 or more characters}`, which is copied into the prediction note. |
| `noise` | The run-to-run noise to treat as "no change" (default 0.03; ours for topic 0.009, story type 0.007, presence F1 0.019). |
| `smoke` *(to build)* | `{command, items, expected_file}`: the 5-item run that must reach the output file. |
| `needs_yes` *(optional)* | Why this round waits for the owner. |

## 4. The smoke test

Rule: **every new or changed script runs on 5 items to its final output file before the full run.** Give every script two switches: the number of items (for example `NP`) and the output folder (for example `T73DIR`), so the smoke run writes to a scratch folder and cannot overwrite a real result.

The smoke output folder must not exist beforehand (2026-11-10: a smoke into an existing folder hid a missing `os.makedirs`). The runner also lints every `.py` a card names (`kit/live/lint_swallow.py`) and refuses a card when a trailing comment hides code on a `;` line.

What it must prove: the script starts, reaches the last line, writes a file that can be read back, and the numbers have the right shape. The numbers of a smoke run are never evidence and are never quoted. Cost: seconds to a few minutes, against the 22 minutes T73 lost when its save step failed on numpy integers.

## 5. Writing a prediction

1. Write it **before** the run, on the ledger, in plain words, with the file or command it refers to.
2. Give a **range** per claim, not a point, and say why. Treat each range as about an 80% range: it should contain the result four times in five.
3. State what a **miss** would mean. That is the finding.
4. Say what the **judge** is: agreement with Sonnet, with the panel, with human labels (MN-DS), or match rates with nothing judged.
5. If you have already seen a related result, say so: the prediction is *informed*, and the score counts as a repeat check, not a test of the forecast (T70).
6. Predictions pass `note_guard.py`: no absolute statements without scope, and citations as `(src: path#key)`.

## 6. Scoring words (fixed)

| Word | Rule |
|---|---|
| **HIT / MISS** | The result is inside or outside the predicted range. Say per claim. |
| **GAIN** | Above the baseline by more than noise. |
| **NO GAIN** | Within noise of the baseline. |
| **WORSE** | Below the baseline by more than noise. |
| **Finished, not passed** | A task closes with every step done but its acceptance bar not shown met. The close text says so (used for T15 to T19, T49, T56). |
| **Post-hoc** | An analysis added after seeing the result. Labelled, saved in its own file, never counted as the registered test (T73 union rule). |
| **Invalid evidence** | A result produced by a degenerate rule. The output file says so and the note says so; it is not cited (T37 composed row). |

Agreement is never called accuracy. Each score says what text the reader saw and what it was measured against.

## 7. The sealed set

- Each head reads the sealed set **once**, after the dev split has fixed every choice (checkpoint, threshold, filter).
- Before the sealed read, check on dev that the chosen setting is not degenerate: the threshold is a real value, the number of yes calls is sensible, the recall ceiling of any filter is above the bar.
- Compare `n` with the gold file's count. Duplicate ids inflate `n` and shrink intervals (T71: 1,569 rows against 1,545 labels).
- No other family labelled the sealed items: presence is scored against Sonnet gold only.
- Near-twin check done: 1 of 1,499 sealed items has a cosine 0.95 neighbour in training.

## 8. Running jobs

- **Heartbeat.** Every job has a row in `runs-live/<job>.json` with `why`, `success`, `next`, `need`, and an update promise: `every_s` for a job, or `service: true` for an always-on process. A row is stale after 2.5 times its `every_s` (never under 10 minutes). Idle and waiting rows are never stale.
- **Who closes the row.** Exactly one owner of the end of a row. A script that closes its own row must not put a process id on it: the poller closes any row whose process ends without a finish call, as `failed`, before the script's own watcher runs (T72). A script without its own finish uses `job.py`, which registers the pid and closes the row.
- **A long single stage needs `alive_pid`.** A row that is rewritten only when a stage changes goes overdue after 10 minutes inside a 30-minute stage, and the health check then discounts it (T82: 'nothing running' while a run was healthy). Put the worker's process id in the row as `alive_pid` (not `pid`: the poller closes any row whose `pid` dies without a finish call). The health check counts a row whose `alive_pid` process exists as reporting. `alive_pid` is read only by `health.py`; the row still ends by its own finish call.
- **Watcher.** A job nobody watches is caught only after the overdue grace. Use a watcher that marks the row done (result file exists) or failed (it does not) the moment the process ends.
- **Isolation.** Installs go into a fresh venv under `/workspace/data/venvs/`. Never into the pulse reader's or the engine's venv.
- **Caps.** Every run has a time cap of 60 minutes or less and is started under `timeout`. Kill only by a verified process id; never kill what the owner is running.
- **No GPU, no hosted calls, no legacy models without the owner's yes.** Local Clef is approved. Hosted review runs are small but are not counted in the hardware view's spend line.

## 9. The health check

`kit/live/health.py` runs every poll (3 minutes) through `tick.py`, writes the heartbeat row `health`, and appends a line to `projects/world-state/runs/health_history.jsonl`. It is the first line on every ledger tab and at the top of `tools/hw.py`.

| Verdict | When | Says |
|---|---|---|
| **BROKEN** | The poller, ledger viewer, console, Clef or pulse reader is not answering | which piece |
| **WORKING** | At least one job is running and reporting on time | which jobs |
| **WAITING** | Nothing running, but something queued outside or tasks blocked on the owner | what it waits on, and for how long |
| **IDLE** | Nothing running and nothing waited on | "start the next piece" |

Flags added to the line: a kernel queued over an hour, a running job past its promised update, failed jobs in 24 hours, disk under 50 GB, no ledger write for 30 minutes while nothing runs. If the line itself is missing or marked OVERDUE, the poller or `health.py` is down.

Tested on fake rows for all six paths (queued only, an overdue job not counted as working, a fresh job, empty, a core piece down, idle). Known limit: failed-job counts include false failures until the poller is restarted on the fixed code.

### 9a. Reality check (2026-11-10)
The health line also compares the rows with what the machine is doing, so a row cannot say working while the CPU is idle, and a busy CPU cannot hide behind a quiet Live view. Flags it raises: a running row with the CPU idle (load under 1), a busy CPU (load over 4) with no running job row, load over 1.5 times the core count, memory under 10 percent available, more than 3 unregistered rows. A pool worker or a command run by a round card is part of its parent's job and gets no row of its own (`heartbeat.watch_untracked`). A job that blocks for a long time (a pool map) names its main process in `alive_pid` so the health check can see it is alive. At every wake the agent reads the flags first and fixes what they name before starting anything.

## 10. The model rollout and the trust grid

Every BitMob model (Domain/topic, Function/story type, Condition present, Condition per kind, Area, Capability, Novelty, Understanding, Size level) goes through the same stages. The grid on the Training tab (`http://localhost:18766/#training`, built by `projects/world-state/flow_audit.py` from result files only) shows each cell as ✓ shown by a file, ◐ shown but weak or not independent, ✗ tried and failed, – not started.

| Stage | Pass means |
|---|---|
| Data | Count and source measured from the label store, not remembered |
| In/out defined | Exact input text and output labels written down |
| Trained | A model exists and can be reloaded |
| Curve | Dev score per epoch visible, chosen epoch marked (dev score, not lowest training loss) |
| Beats old head | Above the old sparse head by more than noise |
| Beats live head | Paired against the head that is live, with an interval |
| No leakage | Sealed ids excluded from training; near-twin check done |
| Outside truth | Scored against something other than the labelling models |
| Self-improving loop | The model is inside the main loop and a round gained |
| Repeats | At least 3 seeds within about twice the noise |
| v1 | Declared, with the cells above shown |

State of the grid on 2026-11-10: topic and story type v1 trained and not adopted (no measured gain over the live head, and topic is 1.4 points worse on one human-label set and 1.1 better on the other); Condition present weak but useful at a lowered threshold; per-kind and size are v1 candidates; Size has no sealed or outside labels; Area and Capability have a measured route but not a model; Novelty and Understanding are not trained.

## 11. How the loop improves itself

Two layers, kept apart.

**Layer 1: the models (the main loop).** Pick the items the model is least sure about or where heads disagree, get teacher labels, retrain on CPU, change one thing, score once on the sealed set, keep the change only if it beats noise. *Built* for the sparse heads (`learn_loop.json`). The encoder, per-kind and size heads still have to join it.

**Layer 2: the process itself.** Five numbers, computed from the health history, the heartbeat history and the ledger:

| Number | Definition | Provisional target (ours) |
|---|---|---|
| **Utilisation** | Share of time something runs while a ready round exists | at least 70% |
| **Waste** | Rounds that crashed or were closed falsely failed, per 10 rounds | at most 1 |
| **Forecast hit rate** | Share of predicted claims inside their range, with the direction of the misses (too high or too low) | about 80% for 80% ranges; bias near zero |
| **Launch delay** | Time from a result to the next launch | under 10 minutes while work is ready |
| **Owner wait** | Time spent with every ready round blocked on the owner | reported, not targeted |

*Retrospective, every 10 rounds:* read the five numbers, `LESSONS_LEARNED.md` and the last 10 score notes; pick the single worst number; propose one process change; write a prediction for how far that number moves; apply it; measure over the next 10 rounds; **revert on a miss** (rule 9 of chapter 14: one change per round, prediction first, revert on a miss, never reopen another field because of it).

First baseline, from the 2026-11-09 and 10 session: at least two crashed rounds (T72 run 1, T73 run 1), both from an untested edge case; one false failure from a process id on a self-closing row; about 8 minutes of repeated setup per run; forecast misses ran toward predicting too much gain from a change (T72 triples per pair, T74 partial rates). These are observations, not yet computed numbers.

**What the loop may change by itself (process settings only):** wake cadence, thread counts, caching of embeddings and pair lists, smoke size, which ready rounds run in parallel, the template wording of predictions.

**What it may never change by itself:** the sealed set; labels and the label store; any spending; GPU or legacy model use; the engine or the Engine card's adopted version; the owner's decisions (T48); the rules in this chapter.

### 11a. When a head stalls: the ladder (owner, 2026-11-11)
A stall is a head that misses its bar, a pilot that says no-go, or a result that does not move for two rounds. **The loop does not stop at a stall and does not wait on an owner gate.** It walks these rungs in order, cheapest first, records one measurement per rung on the ledger, and starts the next rung. A rung that needs the owner's yes is written once with the cost of waiting, and the loop goes on down the ladder and to the next head.

| Rung | Question | How it is measured | If it fails |
|---|---|---|---|
| 0. Was the data run correctly? | Do the numbers describe what we think they describe? | **Data ledger:** rows in and out at every stage, with the count by reason for any filter that drops more than 10 percent; label vocabularies compared programmatically (T93); the head reads the same text view the label was made from (T100, T101); split and leakage check; a sample of 50 items read against the label | Fix and rerun; every figure built on the broken stage is listed as affected |
| 1. Label noise or capacity? | Is the gap to the outside score the student or the labels? | Learning curve and the gap between dev agreement with the teacher and the outside score (T84, T104 pilot: dev 0.65, outside 0.12) | Gap large: go to rung 2. Curve still rising: more data (rung 4) |
| 2. Is the teacher good enough? | Does the teacher beat the student's target on the outside anchor? | Teacher ceiling: score the teacher itself on the anchor (T104-C for local Clef) | Try the next teacher by cost: embedding mapping, zero-shot rerank, local Clef (CLAUDE.md: approved), several teachers with measured agreement, hosted (needs a yes) |
| 3. Is the input view right? | Does the student see enough text? | Same head on headline plus teaser, on sentences and on the first 1200 words (T105) | Change the view, one change per round |
| 4. Where is the next data? | What unused source can add labelled items? | **Source inventory** below, each with yield and cost; pick the highest expected gain per hour; pilot a slice first | Recover filtered rows, label more with the cheapest approved teacher, or find an open dataset |
| 5. Is there an outside reference? | Can the result be scored on something that is not our own agreement? | Anchor search (T96) or the engine's own reading when the goal is agreement with it | Record the written reason and report the head as provisional |
| 6. Report | What did each rung find? | One ledger note listing the rung results | Only now is the head reported as stuck, with the rung evidence, and the loop turns to the next head |

**Source inventory (keep current on the ledger):** the CC-News pool (708,241 rows; 465,374 used, 200,206 dropped for a short description, 77,168 for no date, L1814); the unlabelled queue; the engine's stored Clef readings (1,736 stories); local Clef as a labeller (8 items per second for two typed choices); open anchors (scoring only); the live news queue (service 8140, on demand).
**What counts as improving:** a registered round that moves an outside score or an engine agreement figure with a paired interval, or a recorded finding that removes a rung from the list. Counting and plumbing rounds do not count (L1805).

## 12. Permissions

Source of truth: `kit/live/loop_permissions.json`, checked by `kit/live/loop_gate.py` (exit 0 = free to run, exit 2 = needs the owner's yes, with reasons).

The file lists what needs the owner's yes (hosted calls, the GPU, Kaggle, Fable, exposing pulse_reader, a new page, deleting data, commits, services that are not ours, training on anchor data) and what is free. Engine adoption, legacy models and third-party packages are covered by `CLAUDE.md`, not by the file. Read the file, not a summary of it.

**Never, whatever the yes:** human raters or human labels. Truth comes from open datasets and from agreeing model families whose agreement is measured.

A yes is scoped to what was asked. The hosted-review yes on 2026-11-09 covered the two code reviews (T49, T56) and nothing else.

## 13. What went wrong the first time, and the rule it produced

The same table is kept in `LESSONS_LEARNED.md` (section "Working loop, first round"), which is where new lessons are added.

| What happened | Cause | Rule / check |
|---|---|---|
| T73 stage 1 lost 22 minutes | Result save failed on numpy integers | Smoke test to the output file (section 4) |
| Finished T72 recorded as failed | A pid on a row that closes itself | One owner of a row's end (section 8) |
| A crashed job unnoticed for 10 minutes | Nobody watched the process | Watcher plus the health check (sections 8, 9) |
| The T37 composed row predicted every item yes | Threshold search fell back to -1, sealed read spent | Degenerate check on dev before the sealed read (section 7) |
| Interval too tight | Duplicate ids inflated n | Compare n with the gold count (section 7) |
| Two MM3 severity answers above "low" at p 0.34 | A decision field with no defect named | Report as unsure; do not drill; do not claim the gate passed |
| Entity keys scored below text keys | A key that mixed entity and text forms | State what the key mixes; compare with a union rule, labelled post-hoc |
| "running" printed next to queued rows; finished rows flagged stale | Hard-coded word; one flat 10-minute rule | Each row states its own update promise (section 8) |
| A prediction note claimed an audit edit that had not applied | The edit failed silently | After an edit, read back one value before writing the note |
| A 10-arm chain was killed by its own cap and its row stayed 'running' | The cap was a guess (55 min against about 60 needed) and the row was closed only at the script's end | Cap = measured time per arm x arms x 1.5; close the row from an EXIT trap |
| A bigger embedder and richer term text were expected to lift the mapping (T81) and did not | The forecast assumed the embedder was the limit | When a lever is cheap to test, test it before building around it; write the miss-case that names the other limit (ontology granularity) |
| Tasks closed from old work looked like current work | Done without an acceptance check | Close as "finished, not passed" when the bar was not shown met |

## 14. Checklist to start a round

1. Health line read. Is the pipeline idle, and is anything ready?
2. Question is one sentence; one change; baseline read from a file.
3. Prediction written with ranges and the meaning of a miss; informed or blind stated.
4. `loop_gate.py` run; yes requested if it says so.
5. Script has item-count and output-folder switches; smoke run reached the output file.
6. Time cap set and run under `timeout`; installs in an isolated venv.
7. Heartbeat row with `every_s`; one owner of the row's end; watcher attached.
8. Sealed read planned once; degenerate check done on dev.
9. After the run: score with the fixed words; step marks in order; close with evidence ("finished, not passed" if the bar was not shown).
10. Pages and Training tab data rebuilt; lesson added the same day.

## 15. What exists and what to build, in order

| Piece | State | Where |
|---|---|---|
| Round card runner with prediction, cap, score | *built* | `kit/live/run_round.py`, `round_cards/` |
| Permission gate | *built* | `kit/live/loop_gate.py`, `loop_permissions.json` |
| Prediction/score pairing check | *built* | `kit/live/ledger_pairs.py` |
| Note guard on wording and citations | *built* | `kit/live/note_guard.py` |
| Heartbeat, job wrapper, stale rules | *built* | `kit/live/heartbeat.py`, `job.py`, `poll_live.py` |
| Health check and history | *built* | `kit/live/health.py` |
| Training tab, trust grid, bake-off table | *built* | `build_training.py`, `flow_audit.py`, ledger viewer |
| Page monitor with rebuild rules | *built* | `kit/live/monitor_pages.py` |
| Smoke field on every card, enforced by the runner (2026-11-10) | *built* | `run_round.py` |
| Backlog of ready cards and start when idle (2026-11-10) | *built* | `kit/live/backlog.py`, cards in `kit/live/round_cards/queue/`, switch `kit/live/backlog.enabled` |
| 3. Cached pair list and article embeddings (saves about 8 minutes a run) | *to build* | `projects/world-state/` |
| Wake on job completion (2026-11-10) | *built* | a finished round writes `runs/rounds/<id>.done`; the agent arms a Monitor on it (section 2a) |
| Dead-element sweep every poll (2026-11-10) | *built* | `kit/live/sweep.py`, row `sweep` on the Live tab |
| 5. Process numbers and the retrospective | *to build* | from `health_history.jsonl`, heartbeat history, ledger |
| 6. Poller restart on the fixed code (clean Kaggle status line, real uptime, no false failures) | waits on the owner | `kit/live/poll_live.py` |

Expected effect of 1 to 5: fewer crashed rounds, no idle gaps, and about a two to three times shorter time from question to answer for rounds like T72 to T74.

## 16. Open decisions for the owner

- **T48:** answered at ledger L1617 to L1620 (D19 to D22). T39 and T41 stay blocked until their own steps are re-checked.
- **The Area support bar:** what rate of independent support (currently 11% two-of-three, 4.5% exact on pairs) counts as enough to make an Area.
- **The Kaggle kernel** queued since 2026-11-09: leave or cancel.

## 17. Update 2026-11-11: the loop with a teacher read (what changed, written the day it was learned)

**The cycle, ideal form.** (1) Read `GO.md`, `health.py` and the last ledger lines; trust them over any summary. (2) Pick the next card from what the decider itself asks for (its abstain and harvest buckets, `jev_wire.py` output), not from habit. (3) Write the prediction AND the pass or fail tests before the run, name the held-out set and check it does not overlap training. (4) Run through `run_round.py`; gated cards sit in `round_cards/held/` and start by hand only on a recorded owner yes; follow-on cards are chained by a shell script, never by waiting on a question. (5) Score, write the reading note, say corrections as corrections (a superseded figure names the note it replaces). (6) Refresh the `GO.md` state block. (7) Re-arm the wake-up; the loop stays armed until the owner says stop.

**The label loop that is now built and proven (T143, T144).** Jev one-pass reads -> unchanged Lean-checked decider with its own field table (`rust_decider/fields_read.json`, `jev_wire.py`) -> teacher rows (family `jev` in `runs/label_store/labels_jev_*.jsonl`) -> sparse heads retrained (`t143_jev_retrain.py`, `t144_loop.py`, from `lap_retrain.py`) -> scored on outside truth (MN-DS human labels, scoring only, never in training) and on stories no variant trained on. Measured: Jev is a usable, cheaper teacher (paired on 441 stories, topic 0.618 against 0.584 for Sonnet on MN-DS); the abstain share moves little with 1,600 added rows (topic 0.087 to 0.078); Jev story type derived from noul is noisy and raised story-type abstains, so function is held out until validated on CheckThat.

**Rules learned today (each one cost time).**
1. **Never block on a question while the owner sleeps.** Ask every conditional approval up front in one question; chain the follow-ups (the ten-hour stall, L1996).
2. **Scope never shrinks.** A question to the owner must show what each option switches off; a reviewer's "drop X" is shown to the owner, not applied (D39, ledger T136).
3. **Test the real instrument before concluding it fails.** Jev's two-call labeller (0.69) said nothing about the engine's 328 questions (0.78); a small pilot with the real request first, print the cost, then scale. Prefer hosted Jev to the GPU when the owner has allowed it (D34).
4. **Separate the question from the decision rule.** The 39 dial questions rank well per dial (mean AUROC 0.949); the weak part was "any dial at 0.7". Fit thresholds on a calibration set (TypeSafe: set thresholds from data), test wording variants on small samples.
5. **Leakage check is a step, not a hope.** A figure measured on stories that were in training is retracted (the 0.17 abstain share, L2137). Held-out means ids and text, and the outside gold stays scoring only.
6. **Agreement is not accuracy; compare with the majority guess.** Function agreed 0.933 with the label store, which equals its always-fact share, so it said nothing. Paired controls (same stories, two teachers) remove text-mix confounds.
7. **Check the reference and the file names.** Three runner FAILED notes were my own result-path mismatches, and a smoke command with the variables before `cd` wrote into the real file; the card's result key must name the file the script writes, variables go after the `cd`.
8. **Opus as a read-only reviewer at gates** (before a design freezes, before any bulk read), with a self-contained brief that cites ledger ids and files; reviewers are advice, never approval. Haiku is not needed for triggers: `poll_live.py` with `backlog.py` and `ScheduleWakeup` already fire events without a model.
9. **Guard words.** The note guard rejects comparison words without a cited file, hedged figures next to a bar, absolutes, and quoted numbers whose source key does not match; write numbers without thousands separators next to a `(src: ...)`.

**Measured costs for planning.** Hosted Jev about 0.001 USD a story at about 24 thousand input tokens (call 1 alone 14.5 to 15.2 thousand, the engine's 328 questions in one request about 7 thousand), about 13 stories a second, 0.042 USD per million input tokens; local Clef about 12 stories a minute on the GPU.

**Where things are.** State: `GO.md` and the ledger (decisions D30 to D41, tasks T109 to T144, scope list T136). Wiring: `jev_wire.py`, `rust_decider/fields_read.json`, `t135_full_read.py` (the read, `CALL1_ONLY`, `IDS_FILE`), `t136_calibrate.py`, `t143_jev_retrain.py`, `t144_loop.py`. Requests as sent: `data/diag/flow/exact_requests_first_story.json`, question lists and the v2 and v3 drafts beside it.

**The executable check (T146).** `kit/live/pipeline_check.py` runs the invariants that were failing by hand today (decider replay, label-row schema, leakage against the sealed set and the outside gold, result files of done cards, hosted spend, a canary against bounds in `canary_expect.json`, ledger replay). Run it first in every session and before any bulk read; add a check whenever a mistake costs time.
