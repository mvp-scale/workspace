# kit/ops: operations toolkit (for agents)

These scripts don't depend on any one project. Each one blocks until its job finishes, so call it once and read
its output folder. Don't poll, retry or check status yourself. Rule IDs (R, S, M) refer to `../../ACCEPTANCE.md`
(`kit/ACCEPTANCE.md` in a scaffolded project).

## Compute tiers (try them in this order)

1. **Local GPU (RTX 5090 / 3090):** `local_gpu_run.sh`. No queue and no cap, so use it for iteration and smoke tests.
2. **API:** use the Claude API for teacher labels (Batches plus a cached prefix). Log every call's cost to `runs/spend.jsonl`.
3. **Burst (RunPod or GCP credits):** use this when both local GPUs are busy or the job needs more than 32 GB of
   VRAM. On a RunPod pod, `local_gpu_run.sh` works over SSH. See `runpod.md`.
4. **Kaggle (free fallback):** `kaggle_run.sh`. GPU quota is about 30 h a week. Inputs go through `kaggle_dataset.sh`.

## Scripts and what they guarantee

| Script | Guarantees |
|---|---|
| `kaggle_run.sh <kernel-dir> <out> [poll=600]` | Push, wait and fetch in one call. Retries the push until the CLI prints "successfully pushed", because the CLI's exit code can't be trusted. Exits 2 if the push dropped an input source. Waits for queued/running before polling. Status match is case-insensitive. Refuses a GPU kernel (exit 3) unless `GPU_CHECKED=1`, which you set only after you have confirmed that no other GPU session is running (R4). Saves `push.log` and `status.txt`. `NO_PUSH=1` waits and fetches only. The token comes from the environment or `secrets/vault.env` and is never printed. |
| `kaggle_dataset.sh <folder> <owner/slug> [msg]` | Stages a copy of the folder, refuses secret-looking files, and writes or enforces `"isPrivate": true`. Runs `datasets create\|version -p .` from inside the staging folder, which avoids the Windows upload-cache bug. Checks the CLI's text for success. |
| `local_gpu_run.sh <host> <remote-base> <out> -- <cmd>` | Refuses (exit 3) if `nvidia-smi` shows a compute process on the GPU or the GPU lock is held (R4). Copies code into a fresh run directory, so a running job never sees later edits. Copies `data/` and `gold/` only when `PRIVATE_TARGET=1`. Runs the job detached and logs to `run.log`. Fetches `run.log`, `run.rc` and `outputs/`. Exits with the job's exit code. `SEND_KEYS` passes secrets to the job process over stdin only. |
| `ledger/ledger.mjs append\|check\|brief` | Append-only JSONL ledger. Assigns `id` (L1, L2, …), `ts` and `who` (from `LEDGER_WHO`). Kinds are `task`, `run`, `result`, `verdict`, `decision` and `note`, each with required fields. Runs, results and verdicts must name an existing task. A `prev` sha256 chain makes `check` catch any edited, deleted or reordered line. `brief <task>` prints the task with its runs, results, verdicts and decisions; read that, not the whole ledger. Test: `node ledger/test_ledger.mjs`. |
| `preflight.mjs [preflight.json] [--kaggle]` | Checks that frozen files match their shas (CRLF-safe, R3), that required keys are in the environment or vault (values never printed, S1), and that the total in `spend.jsonl` is under the cap (R5). Checks Kaggle quota only when asked. Prints one PASS/FAIL row per check; exits 1 on any FAIL. |
| `new_project.sh <dir>` | Idempotent scaffold. Creates `cards/`, `runs/`, and gitignored `data/`, `gold/` and `models/`. Writes `.gitignore`, `secrets.example.env`, an empty `ledger.jsonl` and `preflight.json`. Installs the skill and roles in `.claude/`, adds the PreToolUse launch hook, and copies `kit/`. |

## Rules

- **One job per GPU.** The scripts refuse a busy GPU. Never start a second Kaggle GPU session while one is
  running, because two overlapping sessions used up a week's quota (EVIDENCE L409).
- **Smoke test first.** Before any run over 30 min, finish a run on 3 items or fewer and cite its log on the card (R2).
- **Launch with `CARD=`.** The hook blocks `kaggle_run.sh`, `runpodctl`, `torchrun` and `python …train*.py`
  without a card that passes. Put `CARD=cards/Tn.json` in front of every launch.
- **Scripts block, agents don't poll.** Call the script once, then read the output folder. Don't run Kaggle
  status, output or push commands, or ssh loops, by hand.
- **Never edit a running script.** Change the code, then start a new run. `local_gpu_run.sh` already copies the
  code into a fresh directory for each run. A Kaggle kernel version is fixed once you push it.
- **Private datasets only.** Data, gold and labels can contain publisher text, so they never go into git or a
  public dataset.
- **Secrets per process.** Keys come from the environment or `secrets/vault.env`, and each script exports them to
  its own process only. Never echo a key, put it on a command line or commit it.
- **Record everything.** After each run, append a `run` line, then a `result` line with the numbers. The
  evaluator writes the `verdict`.
