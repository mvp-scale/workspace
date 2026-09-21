#!/bin/bash
# Benchmark every backend on the given jevbench tiers (default: original easy hard).
# Skips runs that already exist. Results go to data/bench/<backend>-<tier>/ for the demo viewer.
#   set -a; . .env; set +a; demo/bench.sh [tier ...]
cd "$(dirname "$0")/../jevbench" || exit 1
B=/workspace/data/bench
TIERS=${@:-original easy hard}
MODELS=${MODELS:-jeff kev-0.5b kev-0.8b kev-4b jev}   # e.g. MODELS=kev-4b demo/bench.sh hard
declare -A EP=( [jeff]=http://127.0.0.1:8000 [kev-0.5b]=http://127.0.0.1:8009 [kev-0.8b]=http://127.0.0.1:8011 [kev-4b]=http://127.0.0.1:8010 )
for tier in $TIERS; do
  for n in $MODELS; do
    out=$B/$n-$tier; [ -e "$out" ] && { echo "skip $n-$tier"; continue; }
    if [ $n = jev ]; then
      [ -n "$TYPESAFE_API_KEY" ] || { echo "skip jev: no key"; continue; }
      args=(--endpoint https://api.typesafe.ai --key-env TYPESAFE_API_KEY --price-in-per-m 0.042 --price-out-per-m 0 --cap-usd 1)
    else
      [ $n = jeff ] && export JEFF_KEY=devkey
      k=''; [ $n = jeff ] && k=JEFF_KEY
      args=(--endpoint ${EP[$n]} --key-env "$k" --cost-basis local_cpu_no_provider_tariff --reserve-usd 0 --cap-usd 1)
    fi
    echo "== $n $tier"
    python3 -m jevbench.cli run --tasks datasets/public/$tier.jsonl --adapter typesafe --model jev-latest "${args[@]}" \
      --results $out/results.jsonl --raw-dir $out/raw --ledger $B/ledger.jsonl --manifest $out/manifest.json 2>&1 | tail -1
    python3 -m jevbench.cli summarize --tasks datasets/public/$tier.jsonl --results $out/results.jsonl --public-export $out/summary.json >/dev/null 2>&1
  done
done
