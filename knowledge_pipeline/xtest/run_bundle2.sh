#!/bin/bash
# usage: run_bundle2.sh <bundle dir> "<fields>"  -- replaces run_bundle.sh (ledger L686 gaps G1-G5, G7). Differences: a trap restores voice and Clef on ANY exit; each server is registered with the heartbeat; the free GPU memory is checked before a server starts; the whole server process group is stopped; failures are counted and the last line says DONE only if every run succeeded; hosted spend is checked against a CUMULATIVE budget file before any hosted rater.
B=$1; F=$2; set -a; . /workspace/secrets/vault.env 2>/dev/null; set +a
cd /workspace/knowledge_pipeline/projects/world-state; X=/workspace/knowledge_pipeline/xtest; PY=/workspace/models/clef-flash-nvfp4/.venv/bin/python; HB=/workspace/knowledge_pipeline/kit/live/hb_cli.py
FAILS=0; SP=""
restore() { [ -n "$SP" ] && { kill -- -$SP 2>/dev/null; sleep 5; }; ( cd /workspace && ./service.sh start clef-flash-q4km; ./service.sh start voice ) >/dev/null 2>&1; }
trap 'restore' EXIT
runone() { python3 $X/run.py --bundle $B --variant $1 --rater $X/raters/$2.json --fields $F --order-seed $3 --workers $4 --cap-usd $5 || { echo "FAILED $2 $1 $3"; FAILS=$((FAILS+1)); }; }
for r in clef jev; do
  if [ $r = jev ]; then python3 $X/budget.py check --need 0.7 || { echo "BUDGET: jev skipped"; FAILS=$((FAILS+1)); continue; }; fi
  for cfg in "A 0" "A 1" "P 0"; do set -- $cfg; runone $1 $r $2 6 0.3; done
done
export OPENAI_COMPAT_API_KEY=local VLLM_USE_FLASHINFER_SAMPLER=0
( cd /workspace && ./service.sh stop voice; ./service.sh stop clef-flash-q4km ) >/dev/null 2>&1; sleep 5
for spec in "gemma 8101 /workspace/models/gemma4-26b-nvfp4 " "qwen 8102 /workspace/models/qwen36-27b-nvfp4 --attention-backend TRITON_ATTN"; do set -- $spec; name=$1; port=$2; model=$3; shift 3
  FREE=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1); if [ "$FREE" -lt 26000 ]; then echo "GPU: only ${FREE} MiB free, $name skipped"; FAILS=$((FAILS+1)); continue; fi
  setsid $PY -I -m vllm.entrypoints.openai.api_server --model $model --served-model-name $name --port $port --max-model-len 12288 --gpu-memory-utilization 0.80 --enable-prefix-caching --max-num-seqs 32 "$@" > $B/server_$name.log 2>&1 &
  SP=$!; python3 $HB start xtest-server-$name --pid $SP --where "[5090] local model server" --why "vLLM server for the $name rater of $B" --success "Server answers /v1/models and the runs finish" --next "Stopped after its three runs"
  for i in $(seq 1 90); do curl -s localhost:$port/v1/models >/dev/null 2>&1 && break; sleep 10; done
  if curl -s localhost:$port/v1/models >/dev/null 2>&1; then for cfg in "A 0" "A 1" "P 0"; do set -- $cfg; runone $1 $name $2 8 1; done; S=done; else echo "SERVER $name DID NOT START"; FAILS=$((FAILS+1)); S=failed; fi
  kill -- -$SP 2>/dev/null; wait $SP 2>/dev/null; python3 $HB finish xtest-server-$name $S --last "stopped by the script"; SP=""; sleep 10
done
if [ $FAILS -eq 0 ]; then echo "BUNDLE-DONE: every run succeeded"; else echo "BUNDLE-INCOMPLETE: $FAILS step(s) failed or were skipped, see FAILED lines above"; exit 1; fi
