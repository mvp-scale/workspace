#!/bin/bash
# Benchmark in-process models one at a time: each loads, runs every tier, exits, and frees the GPU.
#   demo/bench-batch.sh <model ...>      models: laya verdict semif so1 clef-flash   (env from ./dev-bench-setup.sh)
#   TIERS="original easy hard" to change tiers. Existing complete runs are skipped.
cd "$(dirname "$0")/../jevbench" || exit 1
B=${BENCH_OUT:-/workspace/data/bench}; M=/workspace/models
TIERS=${TIERS:-original easy hard}
export HF_HOME=/workspace/data/models/hf-cache JEVBENCH_WARM_LOAD=1 PYTHONPATH=/workspace/jevbench
declare -A ADAPTER=( [laya]=laya_local [verdict]=verdict_local [semif]=semif_direct [so1]=so1_decider [clef-flash]=clef_local )
declare -A ENDPOINT=( [laya]=/workspace/data/models/laya [verdict]=/workspace/data/models/verdict [semif]=Qwen/Qwen3.5-4B [so1]=Qwen/Qwen3.5-4B [clef-flash]=/workspace/data/models/clef-flash )
# Local models cost $0, so each run gets its own small ledger. The shared one grows with every item and is re-read on every
# reserve/settle (1.5 s per item at 180k lines, about 90% of a run); per run it stays in the milliseconds.
# Tasks in flight per model for a batching adapter (needs the adapter's thread_safe micro-batcher). Only for accuracy-only sets:
# the leaderboard tiers stay serial because per-item latency under concurrency includes queue time and is not comparable.
declare -A CONC=( [clef-flash]=64 )
declare -A COST=( [clef-flash]=local_gpu_no_provider_tariff )
snap() { ls $HF_HOME/hub/models--Qwen--Qwen3.5-4B/snapshots | head -1; }   # SemIf requires a pinned commit
for n in "$@"; do
  REV=(); [ $n = semif ] && REV=(--revision "$(snap)")
  [ -x $M/$n/.venv/bin/python ] || { echo "skip $n: run ./dev-bench-setup.sh $n"; continue; }
  for tier in $TIERS; do
    out=$B/$n-$tier; [ -e "$out" ] && { echo "skip $n-$tier"; continue; }
    echo "== $n $tier"
    case $tier in original|easy|hard) C=1;; *) C=${CONCURRENCY:-${CONC[$n]:-1}};; esac
    $M/$n/.venv/bin/python -m jevbench.cli run --tasks ${TASKS_DIR:-datasets/public}/$tier.jsonl --adapter ${ADAPTER[$n]} --endpoint ${ENDPOINT[$n]} \
      --model $n "${REV[@]}" --cost-basis ${COST[$n]:-local_cpu_no_provider_tariff} --reserve-usd 0 --cap-usd 1 --concurrency $C \
      --results $out/results.jsonl --raw-dir $out/raw --ledger $out/ledger.jsonl --manifest $out/manifest.json 2>&1 | grep -E "warm load|done|Error|error" | tail -3
    $M/$n/.venv/bin/python -m jevbench.cli summarize --tasks ${TASKS_DIR:-datasets/public}/$tier.jsonl --results $out/results.jsonl --public-export $out/summary.json >/dev/null 2>&1
  done
done
