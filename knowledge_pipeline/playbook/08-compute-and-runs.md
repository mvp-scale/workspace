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

## Done when

Each run has: tier chosen with reason, a smoke test result, the run script, frozen-input shas in its log, and its
spend recorded against the cap.
