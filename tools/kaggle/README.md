# Kaggle toolkit

Run GPU jobs on Kaggle without leaving GPUs burning. Every run is logged to a small ledger you can query, and that ledger is checked against Kaggle's own GPU meter.

The toolkit is self-contained. It needs Python 3 (standard library only), bash and the Kaggle CLI. Copy this folder anywhere.

| File | Runs where | Does |
|---|---|---|
| `guard.py` | Inside the Kaggle notebook | Self-shutdown on idle or overrun; writes start / first-step / end events to the log |
| `watch.sh` | Your machine | Pushes a run (optional), watches it, downloads the output, adds the run to the ledger |
| `runs.py` | Your machine | The run ledger: add, backfill, summary, query, quota check |

## Setup

```bash
pip install kaggle             # the Kaggle CLI
kaggle quota                   # proves you are authenticated
export KAGGLE_RUNS_LEDGER=/path/to/kaggle-runs.jsonl  # optional; default ./kaggle-runs.jsonl
```

## 1. Guard the notebook

Kaggle's CLI cannot cancel a running notebook, so the stop has to live inside it. That also means it works if your machine or watcher dies.

```python
# paste guard.py at the top of the kernel script (or upload it and import it)
from guard import guard, beat
guard(max_min=20, idle_min=5)      # hard stop after 20 min; idle stop after 5 min without a beat
for step in ...:
    ...
    beat(f"step {step}")           # call after every batch / step / saved file
```

- **Idle stop:** no `beat()` for `idle_min` minutes → the process exits and Kaggle frees the GPU.
- **Hard stop:** `max_min` minutes after `guard()` → the process exits whatever is happening.
- A normal script end also frees the GPU at once. Batch kernels never sit idle waiting for more work.
- Pick the numbers from your own history with `runs.py summary`. It suggests about 3× your longest pause between beats and 2× your longest run.

## 2. Push and watch

```bash
./watch.sh <owner/kernel-slug> <output-dir> [max-minutes=60] [poll-seconds=60] [push-dir]
# e.g. push the folder with kernel-metadata.json, watch, fetch, record:
./watch.sh me/my-train-r1 out/r1 30 60 kernels/my-train-r1
```

- Giving `push-dir` lets it time **boot** (push → RUNNING). It polls every 10 s until the run starts.
- The output (including `<slug>.log`) is downloaded to `output-dir`, then one ledger line is added.
- Optional hook: `KAGGLE_ON_EVENT` is a shell command run on each status change, with arguments `job state message pid` (`state` = running | done | failed). For example:
  ```bash
  export KAGGLE_ON_EVENT='notify-send "$1" "$2: $3"'
  ```

## 3. Ask the ledger

```bash
./runs.py summary                                 # median / worst per phase, how runs ended, suggested guard
./runs.py query --kernel topic --since 2026-10-21 # table of matching runs
./runs.py query --ended idle_stop --json          # raw lines, for scripts
./runs.py quota                                   # Kaggle's GPU meter vs the ledger this quota week
./runs.py backfill <dir> --owner <name>           # add runs from old kernel logs (<slug>.log)
```

`quota` is the accuracy check. If the ledger and Kaggle's meter drift apart, something ran that wasn't recorded, or a phase is being missed.

## Ledger line (JSONL)

| Field | Meaning |
|---|---|
| `kernel`, `recorded`, `status` | Which run, when recorded, Kaggle's final status |
| `boot_s` | Push → Kaggle reports RUNNING (accurate to the poll interval) |
| `warmup_s` | `guard()` → first real `beat()` (imports, model and data load) |
| `max_gap_s`, `beats` | Longest pause between beats; number of beats |
| `work_s` | Script's first to last log line |
| `shutdown_s_max` | Script end → COMPLETE seen (upper bound) |
| `ended` | `normal`, `idle_stop`, `hard_stop`, or `killed (...)` when no end event was written |
| `gpu_h_wall` | RUNNING → COMPLETE, in hours |
| `gpu_h_meter` | Change in Kaggle's "used" meter across the run (the meter can lag) |
| `max_min`, `idle_min`, `machine_up_s`, `process_up_s` | Guard settings; how long the machine and process had been up when the guard started |
| `log`, `source`, `note` | The log it was read from; whether guard events or older heartbeat lines were used |

Unknown values are left out, never guessed.

### Example

`examples/kaggle-runs.example.jsonl` has three lines:
- two real runs backfilled from old logs (account renamed); they have no boot, shutdown or GPU fields
- one illustrative line showing everything a watched run records; its numbers are made up and its `note` says so

Try it: `KAGGLE_RUNS_LEDGER=examples/kaggle-runs.example.jsonl ./runs.py summary`. The illustrative watched run looks like this:

```json
{"kernel": "your-user/train-example", "recorded": "2026-10-22T09:12:40-04:00", "status": "complete",
 "pushed_at": 1792674000.0, "boot_s": 58.4, "warmup_s": 43.0, "max_gap_s": 43.0, "beats": 2690,
 "work_s": 470.2, "shutdown_s_max": 52.0, "ended": "normal", "gpu_h_wall": 0.145, "gpu_h_meter": 0.14,
 "max_min": 20, "idle_min": 5, "machine_up_s": 61.3, "process_up_s": 3.8, "source": "guard events",
 "log": "out/train-example/train-example.log"}
```

## Login gaps (learned 2026-10-22)
- A browser login (`kaggle auth login`, stored in `~/.kaggle/credentials.json`) gives an access token that lasts about **3 hours**; it is meant to renew itself but can fail. A classic API key (`~/.kaggle/kaggle.json`, from Kaggle Settings > API) does not expire this way and is the recommended setup for unattended jobs.
- A lapsed login does **not** stop a job: it keeps running on Kaggle. Only launching, status checks and downloads from your machine stop.
- `watch.sh` now: refuses to launch if the logged-in account is not the job's owner (the part of the slug before `/`) or if the login would expire before the job's cap plus 10 minutes; treats "authentication required" while watching as a pause, not a failure, and prints the fix (`kaggle auth login --force`, signed in as the owner).
- If the watcher gives up, the results are still on Kaggle: `kaggle kernels output <owner/slug> -p <dir>`.
