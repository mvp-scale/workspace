#!/bin/bash
# Benchmark in-process models one at a time: each loads, runs every tier, exits, and frees the GPU.
#   demo/bench-batch.sh <model ...>      models: laya verdict semif so1   (env from ./dev-bench-setup.sh)
#   TIERS="original easy hard" to change tiers. Existing complete runs are skipped.
cd "$(dirname "$0")/../jevbench" || exit 1
B=/workspace/data/bench; M=/workspace/models
TIERS=${TIERS:-original easy hard}
export HF_HOME=/workspace/data/models/hf-cache JEVBENCH_WARM_LOAD=1 PYTHONPATH=/workspace/jevbench
declare -A ADAPTER=( [laya]=laya_local [verdict]=verdict_local [semif]=semif_direct [so1]=so1_decider )
declare -A ENDPOINT=( [laya]=/workspace/data/models/laya [verdict]=/workspace/data/models/verdict [semif]=Qwen/Qwen3.5-4B [so1]=Qwen/Qwen3.5-4B )
snap() { ls $HF_HOME/hub/models--Qwen--Qwen3.5-4B/snapshots | head -1; }   # SemIf requires a pinned commit
for n in "$@"; do
  REV=(); [ $n = semif ] && REV=(--revision "$(snap)")
  [ -x $M/$n/.venv/bin/python ] || { echo "skip $n: run ./dev-bench-setup.sh $n"; continue; }
  for tier in $TIERS; do
    out=$B/$n-$tier; [ -e "$out" ] && { echo "skip $n-$tier"; continue; }
    echo "== $n $tier"
    $M/$n/.venv/bin/python -m jevbench.cli run --tasks datasets/public/$tier.jsonl --adapter ${ADAPTER[$n]} --endpoint ${ENDPOINT[$n]} \
      --model $n "${REV[@]}" --cost-basis local_cpu_no_provider_tariff --reserve-usd 0 --cap-usd 1 \
      --results $out/results.jsonl --raw-dir $out/raw --ledger $B/ledger.jsonl --manifest $out/manifest.json 2>&1 | grep -E "warm load|done|Error|error" | tail -3
    $M/$n/.venv/bin/python -m jevbench.cli summarize --tasks datasets/public/$tier.jsonl --results $out/results.jsonl --public-export $out/summary.json >/dev/null 2>&1
  done
done
