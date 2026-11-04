# 08 · Compute and runs

**Goal:** every job runs on the cheapest place that can do it, starts only when its test is ready, and can't
silently burn hours.

## Where the time actually goes

Of ~32 Kaggle GPU-hours in the first project, **students trained in about 1 hour in total** (8–13 minutes each on a
T4). Nearly all the rest went to running open LLM teachers on Kaggle T4s, much of it on failed or superseded runs
(see chapter 10). The student is cheap; the teacher and the plumbing around it are where time is lost.

## Compute tiers

| Tier | Use for | Why |
|---|---|---|
| **Local GPU: RTX 5090 (32 GB), RTX 3090 (24 GB)** | Default for student training, int8 export, open-model teachers (Qwen-class 14–32B quantized), smoke tests | No queue, no weekly cap, fast iteration; a 32B model at 4-bit fits on the 5090 |
| **Local CPU** (target-like box) | Speed benchmarks, ship tests | Speed must be measured on hardware like production |
| **Closed-model API** (Claude Haiku/Sonnet, Batch API) | Teacher labels | $0.75–0.87 per 1,000 articles with CPU candidates; ~22 min per 1,000 |
| **RunPod / Google Cloud credits** | Burst: large teacher runs, parallel sweeps, models over 32 GB | Pay per hour; spin down when done |
| **Kaggle** (CPU free, GPU 30 h/week) | Free fallback, public-reproducible runs | Queues, session limits, T4 quirks; the weekly cap ran out in this project |

## Where it runs: status tags (owner rule 2026-10-30)

Every status line starts with the tag for where the compute happens, then the job, then a state word. Nothing is reported without one.

| Tag | Where | Pays with |
|---|---|---|
| `[SESS]` | this Claude Code session (Claude reading, writing, deciding) | the owner's plan tokens |
| `[API]` | Anthropic API called from a local script: Batch or Messages | workspace $ (limit in Console) |
| `[CON]` | Console agent session in Anthropic's cloud container | workspace $ |
| `[KAG]` | Kaggle notebook or kernel (T4/P100, CPU) | free weekly quota |
| `[5090]` `[3090]` | local GPU (needs the owner's yes) | nothing, but it blocks other GPU use |
| `[CPU]` | local CPU: scripts, scoring, speed tests, viewers | nothing |
| `[HOST]` | third-party hosted model (Jev) | that vendor's $ |

Live status is shown in the ledger viewer (Story, Live runs): each job writes `runs-live/<job>.json` through `kit/live/heartbeat.py`; `kit/live/poll_live.py` adds Console sessions, batches and Kaggle. A running job silent for 10 min shows NO UPDATE.

State words: `queued`, `running`, `done`, `failed`, `stopped`. Form: `[API] wave 3 Haiku+Sonnet labelling - running, $2.97/$50`. A job that spans places lists each: the local driver is `[CPU]` and the labelling it calls is `[API]`. `waves.py` log lines carry a `where` field with the same tag.

**Kaggle in this project (owner, 2026-10-30):** it is where the CPU classifier is trained (P9). Kaggle's own quota is 30 GPU-hours a week, shared with BitMob. This project's self-imposed caps (PLAN decision 6, an assumed default, not a Kaggle limit): 3 GPU-hours in total and 4 in any one week, so BitMob keeps the rest. Account `coreygorman`, items named `kp-*`, token in `secrets/vault.env` (`KAGGLE_API_TOKEN`). Its resources are tracked like any other: GPU hours (weekly quota), CPU, and TPU (not planned, allowed if a step needs it). Any free daily AI allowance Kaggle offers may be used for validation, and is recorded in the ledger when used.

**Kaggle quotas, as the account page showed on 2026-10-30 (owner paste):**

| Resource | Used / limit | Note |
|---|---|---|
| GPU | 10:20 / 30 h this week | 19 h 40 left; shared with BitMob; resets weekly |
| TPU | 0:00 / 20 h | not planned |
| Daily AI Models | $0.00 / $10.00 | the daily AI allowance: usable for validation calls |
| Monthly AI Models | $0.00 / $100.00 | same allowance, monthly cap |
| Private datasets | 603 MB / 214.75 GB | |
| Private models | 0 B / 214.75 GB | |

## Running-now table (owner rule 2026-10-31)
One row per active job, because several run in parallel. Columns: Job (state, progress, spend against cap, age), Why, Where (in words), Succeeds if, Then, You. Every job that costs money or runs over 5 minutes passes `why`, `success`, `next` and `need` to `beat()`. `why` and `success` fall back to `projects/world-state/phases.json` through the job's `task`. A field with nothing to say stays blank; "You" shows only when the owner has something to do. The same table is on Story (Running now) and on Live (Active).

## Local tool registry (measured, 2026-10-30; one thread unless noted; accuracy against Sonnet labels on dev waves, frozen 300 untouched)

Rule (owner, D5): try cheap local tools as validators and data sources, prove each on a test before use, log the result here. Always print the majority-class baseline and per-class scores next to accuracy.

| Tool | Size | Speed | Needs | Measured | Role |
|---|---|---|---|---|---|
| TF-IDF + logistic regression | a few MB | 0.04 ms/item | scikit-learn | topic .54; story type accuracy .90 but baseline .88 | baseline only |
| potion-base-8M static embeddings + LR (calibrated) | ~30 MB weights | 0.03 ms/item encode | model2vec, scikit-learn | topic .62 overall, calibrated: confidence >= .7 covers 48% of items at 84%, >= .9 covers 26% at 93%; story type macro-F1 .37 (rare classes weak) | cheap first stage of a cascade for topic; router |
| HDBSCAN on PCA(40) of static embeddings | none extra | 1.4 s for 1,945 items | scikit-learn | 21-26% of items in 11 clusters, purity .5-.6; raw 256-d gives 88% outliers | density / novelty support signal, not a classifier |
| Qwen2.5-0.5B-Instruct, next-token A/B/C/D, no text generated | ~1 GB | 1,159 ms/item (1 thread), 341 ms (4 threads) | torch, transformers | story type accuracy .72 (baseline .89) | not a serving candidate; larger model untested |
| e5-small-v2, gliclass-edge, deberta-xsmall-mnli, spaCy, wink-nlp, compromise | 269 MB / 269 MB / n.a. / n.a. | not yet measured | | not yet tested | next |

**Plain-words key (use these, not the short names):** *answer key* = the big AI (Sonnet) standing in for the right answer; it is not truth. *Dumb baseline* = the score you get by always guessing the most common answer; a tool only counts if it beats this. *Right-answer rate* = share of items where the tool matches the answer key. *Precision* = when the tool says yes, how often it is right. *Recall* = of the real yeses, how many the tool finds. *Combined score (F1)* = one number from 0 to 1 that mixes precision and recall. *Ranking quality (AUC)* = how well the tool puts real yeses above real noes: 0.5 is guessing, 1.0 is perfect. *Two big AIs* = Haiku and Sonnet compared with each other, which is the realistic ceiling for now.

### Whole-contract probe (ontology_probe.py, 2026-10-30; test W7+W8, n=1942 items, vs Sonnet; baselines beside every score)

| Output | Cheap local tool | Result | Baselines | Verdict |
|---|---|---|---|---|
| Is any condition moving? (8% of items yes) | static embedding + LR | ranking quality .88 (0.5 = guessing); keeping 90% of true positives clears 66% of the "none" items, so the LLM reads 39% of items (51% at 95% recall) | yes/no majority .918; Haiku vs Sonnet .936 | **best lever so far**: a gate in front of the expensive question |
| Which conditions (30 of 38 have enough examples) | one-vs-rest on static embeddings | combined score .29 (right when it says yes 19% of the time, finds 60% of the real ones) | two big AIs .589 | weak: only ~400 positive training items in 4,900; needs enriched sampling |
| Direction up/down | change-verb lexicon | decides 49% of cases, right 75% of those | majority "up" .829; teachers agree .969 | no use; direction is nearly constant |
| Size level (5) | static embedding + LR | exact .47, within one level .94 | majority "notable" .535; teachers .698 | no use for exact level |
| Place (100 countries) | name / alias lookup | finds a country in 36% of items | no truth labels yet | coverage only; spaCy places + city-to-country mapping next |

### How to ask Clef and Jev (standard, owner rule 2026-10-30; test: ask_better.py on gold-Q, 50 items)

1. Write the question by the rules in `mm3 agent probe` (borrowed guidance; MM3 itself reviews code and process, it does not label). Rules: one narrow judgment per question; the question carries its full meaning on its own; positive wording where "yes" is the thing you mean; at most 160 characters; always include a "cannot tell / none fits" option.
2. Test the wording on the gold set for each model. Report three counts: how often it says yes, how many of the sure cases it finds, how many of its yeses are right.
3. Wording is per model. Measured on "is a condition moving?" (6 sure cases of 50): **Jev** with three narrow questions (a number went up or down; a shortage, harm, disruption or relief affects people; the effect lasts beyond one event) and a 2-of-3 rule says yes on 17, finds 5 of 6, right on 10 of 17. The old long question said yes on 30, found 5 of 6, right on 16 of 30. **Clef** with the same 2-of-3 rule is too strict (yes on 2, finds 1 of 6); with any-of-3 it matches the old question (yes on 23, finds 5, right on 11). So Clef needs its own wording; not yet found.
4. Never send the long compound question (it asked about prices, health, safety, supply and more at once). It over-flags.

### Candidate tools by position (survey from general knowledge, 2026-10-30; speeds are typical, NOT measured here; status says what we have tested)

Position: **IN** = intake, before the reader; **EX** = extraction (structure the reader does not produce); **CL** = classification (the reader itself or a second opinion); **OUT** = output check (validator / voter on the reader's answers).

| # | Tool | Pos | What it gives us | Typical cost | Helps with | Status |
|---|---|---|---|---|---|---|
| 1 | fastText language ID / lingua | IN | drop or route non-English items | ~0.1 ms | pool cleaning, multilingual later | not tested |
| 2 | simhash / minhash (datasketch) | IN | near-duplicate items | microseconds | dedupe (PRD stage 0), no repeated labels | not tested |
| 3 | Presidio / regex PII spotting | IN | flag sensitive text so it stays local | ~ms | local-only routing of private data | not tested |
| 4 | trafilatura / readability | IN | clean article bodies | ~10 ms | bodies test (decision 11) | not tested |
| 5 | spaCy (sm/md: entities, POS, dependencies) | EX | who did what, places, orgs, change-verbs | 5-15 ms | conditions + direction cues, anchors later | installed (embed venv), not tested |
| 6 | compromise (JS) | EX | people, places, dates, numbers by rules | <1 ms | cheap cues, runs in the browser | not tested |
| 7 | wink-nlp (JS) | EX | tokens, entities, sentiment | ~1 ms | cheap cues, browser | not tested |
| 8 | GLiNER (small) | EX | zero-shot entities of any type we name | 20-50 ms | anchors, condition mentions | not tested |
| 9 | dateparser / HeidelTime | EX | time expressions | ms | event time, forecast vs fact | not tested |
| 10 | quantulum3 / regex | EX | numbers with units and direction | ms | size of change, level | not tested |
| 11 | static embeddings (potion) + LR, calibrated | CL | topic, router, confidence | 0.03 ms | topic first stage (cascade) | **measured**: topic .62, confident half 84% |
| 12 | e5-small / bge-small / granite-small + head | CL | stronger topic and intent | ~4 ms int8 | the second stage of the cascade | cached locally, not tested |
| 13 | GLiClass edge / small | CL | zero-shot multi-label from label descriptions, no training | 10-50 ms | topic and story-type second opinion, new labels fast | cached locally, not tested |
| 14 | NLI zero-shot (DeBERTa-xsmall-mnli) | CL | one entailment test per label | N passes | story type, yes/no conditions | cached locally, not tested |
| 15 | SetFit | CL | few-label fine-tune of a sentence encoder | 5-20 ms | rare classes (opinion, forecast) | not tested |
| 16 | fastText supervised | CL | linear text classifier | microseconds | baseline, router | not tested |
| 17 | LightGBM on embedding + cue features | CL | blends many cheap signals | <1 ms | combine layers (owner's layered idea) | not tested |
| 18 | HDBSCAN on PCA of embeddings | OUT | density, outliers, novelty | 1.4 s per 2,000 items | flag "new" items | **measured**: 21-26% clustered, purity .5-.6 |
| 19 | calibration (temperature scaling) / conformal prediction | OUT | honest confidence; accept / defer thresholds | free | cascades, label audit | **measured**: error .04 topic |
| 20 | change-verb and cue lexicons (rules) | OUT | independent vote on condition direction | microseconds | conditions + direction voter | not tested |
| 21 | VADER / lexicon tone | OUT | tone, severity cue | microseconds | size / level cue | not tested |
| 22 | YAKE / KeyBERT keywords | OUT | topic cue words | ms | topic voter | not tested |
| 25 | short-prompt Haiku gate (303-token prompt, one yes/no, spec world_state_gate_v1) | OUT/IN | skips the expensive condition question on items with no change | about $0.02 per 1,000 items (batch) | any-change gate | **measured**: flags 19% of items, finds 25 of 27 of Sonnet's yeses (93%); small sample |
| 24 | local Clef Flash Q4 (already loaded; registry clef-flash-q4km; typed choice questions with probabilities) | CL/OUT | independent third voter, real probabilities | 0.47 s/item for 3 questions, one request at a time (4 in parallel jammed it) | topic, story type | **measured**: topic 74% vs Sonnet (87.5% when >=50% sure); story type 93% (opinion 17/24); any-change as worded poor |
| 23 | tiny LLM, A/B/C/D next-token probabilities | OUT | no-training multiple choice | 340-1,160 ms for 0.5B | offline spot check only | **measured** at 0.5B: story type macro-F1 .22, AUC .61 opinion / .53 forecast: no signal; larger models untested |

Keep data private wherever it runs: no publisher text in public datasets, notebooks or images.

## Rules

1. **Smoke test every new stack for 5 minutes** on 2–3 items before any long run: model loads, one batch completes,
   output parses, output file lands where the evaluator expects.
2. **Iterate prompts and code locally,** not one remote push per patch. A remote run is for a finished script.
3. **Test the cheap teacher before the expensive one.** Haiku via API did 1,000 articles for $0.87 the day after a
   32B Kaggle run spent ~8 GPU-h on 219 articles.
4. **One owner per GPU.** Before any GPU launch, check that nothing else is running there (`nvidia-smi`, `kaggle
   kernels status`, RunPod dashboard). Two overlapping judge runs pushed us 1.87 h over the cap.
5. **Script the run loop** (push → wait → fetch → verify), e.g. `kit/ops/kaggle_run.sh` or `kit/ops/local_gpu_run.sh`. The script
   must fail loudly: require an explicit success string from the push, exit if inputs were dropped, and match status
   text case-insensitively. Agents don't poll inside a turn.
6. **Don't edit a script while it runs.** Bash reads scripts as it goes; editing one mid-run crashed our watcher.
7. **Pin versions that touch the GPU stack** (e.g. vLLM 0.10.2 needed transformers < 4.57; T4 needed
   `VLLM_USE_V1=0`, xformers backend, no prefix caching or chunked prefill). Record them in a lock file.
8. **Guard multiprocess entry points** (`if __name__ == "__main__":`); vLLM workers re-ran our driver without it.
9. **Every run asserts its frozen inputs** (scorer, gold, model shas) at start and prints them in the log.
10. **Budget per task, not per project:** GPU-h, CPU-h, API $ and agent tokens each have a cap on the task card. An
    agent wave once ran to 34M tokens against a 6M cap before the owner stopped it.

## Claude Console and the `ant` CLI (added 2026-10-29)

- One API key belongs to one workspace. Before using it, list agents, environments and vaults and check they are the ones you expect.
- `ant auth login` binds to one workspace (`workspace_id` in `~/.config/anthropic/configs/default.json`). If `ANTHROPIC_API_KEY` is set in the shell it overrides the login. Organisation commands need `ant auth login --admin`.
- In a non-interactive shell `ant` reads piped input as a request body. Pipe `echo '{}'` for list calls, or pass the key with `--api-key-stdin`. Never put a key on the command line.
- Strip carriage returns (`\r`) from any field read from a file before sending it.
- Vault credentials: type `environment_variable`, write-only, one exact host each (no wildcard over a shared cloud domain). Send values on stdin. A credential's hosts and the environment's network allow-list are separate lists; keep them in step.
- Batches wait up to 24 h by default. Pass a wait limit of 1 hour for unattended stages.
- A Console session takes a hard spend ceiling: `--budget '{type: limit, max_list_cost: {amount: "5", currency: USD}}'`, in whole US cents as a string. At the cap the session pauses (idle), with at most one request of overshoot. Always set one.
- Files go in with `ant beta:files upload`, then `--resource '{type: file, file_id: ..., mount_path: ...}'`. They appear under `/mnt/session/uploads/<mount_path>`, so tell the agent that path.
- Results come back as the agent's final message in `ant beta:sessions:events list --session-id ...` (filter on `agent.message`). Ask for JSON only. Files the agent writes inside the container are not fetched this way; keep results small enough for the message.
- Checked 2026-10-30 with synthetic content: a session that reads a mounted file and answers with JSON costs under one cent on Haiku.

## Done when

Each run has: tier chosen with reason, a smoke test result, the run script, frozen-input shas in its log, and its
spend recorded against the cap.

## Footprint rule: what may be installed, and where
- **Runtime stack stays portable:** Python, numpy, scikit-learn, static embeddings, spaCy small models. Nothing that needs Java, Maven, a server or a GPU may sit on the serving path. The deployed reader must run anywhere.
- **Pipeline-only tools** (Java extractors such as MinIE or CoreNLP, big parsers) are allowed for one test, in one folder, with a stated size and a removal line in the ledger note. They produce training data or teacher labels, never a serving dependency.
- **Before installing a runtime or toolchain,** tell the owner the size and why, and record it. Test the idea on the 8-item sample first to see whether it earns the install.
- **Published test outputs hold publisher text:** keep them out of git.

## Where a run goes (owner rule 2026-10-31)
- Short, bursty CPU tests (minutes): run on this machine (i9-10900K, 20 threads). Several can run side by side, about one core each. Free, no upload.
- Hours-long jobs, GPU fine-tuning, or many variants at once: Kaggle, several sessions in parallel. Within the D12 caps (3 GPU-hours total, 4 a week); tell the owner when one starts.
- Every run is registered in the job history (`projects/world-state/log_run.py`, `kit/live/heartbeat.py`) when it starts and when it ends.

## Ops notes from the 2026-11-04 session (ledger L647, L662)
- **GPU is shared.** Clef holds 10.8 GB, the voice server 5.8 GB and the world engine 1.25 GB; Qwen3.6-27B needs about 25 GB free (estimate: it failed to start with 24.0 GB free) and Gemma 4 26B about 23 GB. Run `nvidia-smi` first, size `gpu_memory_utilization` to what is free, and ask before stopping a service other than Clef.
- **Measured speeds.** Qwen3.6-27B (thinking off) 2.9 items/s, so 13,000 items take about 1.3 hours; Gemma 4 26B 29 items/s.
- **Waits.** Never `until ! pgrep -f "<name>"` inside the waiting shell: the shell's own command line matches, so it never exits (four such loops ran for hours to days). Wait on a pid or a file.
- **Smoke first.** Run 20 items before any job longer than 10 minutes (wrong working directory, dtype, missing `no_grad` and a missing multiprocessing guard each cost a full launch).
- **Every script registers with the heartbeat (2026-11-04, ledger L685).** A process that runs over a minute inside `knowledge_pipeline` and has no heartbeat is picked up by the watchdog as `auto-<script>-<pid>`. Before the fix it was then written to the history as *failed* when it ended, so 25 finished xtest runs and servers looked like failures. Now such rows end as *lost* (unknown, not failed), and `xtest/run.py` reports its own start, progress and result. A new starter calls `hb.beat(...)` at the start and `hb.finish(...)` with the real outcome; a server process started from a shell script needs its own beat.
