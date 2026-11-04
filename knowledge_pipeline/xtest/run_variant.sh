#!/bin/bash
# usage: run_variant.sh <bundle> "<fields>" <variant> [seed]  -- ONE run per local rater (Clef, then Gemma and Qwen on their own servers) for an extra control variant. Same safeguards as run_bundle2.sh: trap restores voice and Clef, servers are registered with the heartbeat, free GPU memory is checked, the last line is honest.
B=$1; F=$2; V=$3; SEED=${4:-0}; cd /workspace/knowledge_pipeline/projects/world-state; X=/workspace/knowledge_pipeline/xtest; PY=/workspace/models/clef-flash-nvfp4/.venv/bin/python; HB=/workspace/knowledge_pipeline/kit/live/hb_cli.py; FAILS=0; SP=""
restore() { [ -n "$SP" ] && { kill -- -$SP 2>/dev/null; sleep 5; }; ( cd /workspace && ./service.sh start clef-flash-q4km; ./service.sh start voice ) >/dev/null 2>&1; }
trap 'restore' EXIT
python3 $X/run.py --bundle $B --variant $V --rater $X/raters/clef.json --fields $F --order-seed $SEED --workers 6 --cap-usd 0.1 || { echo "FAILED clef $V"; FAILS=$((FAILS+1)); }
export OPENAI_COMPAT_API_KEY=local VLLM_USE_FLASHINFER_SAMPLER=0
( cd /workspace && ./service.sh stop voice; ./service.sh stop clef-flash-q4km ) >/dev/null 2>&1; sleep 5
for spec in "gemma 8101 /workspace/models/gemma4-26b-nvfp4 " "qwen 8102 /workspace/models/qwen36-27b-nvfp4 --attention-backend TRITON_ATTN"; do set -- $spec; name=$1; port=$2; model=$3; shift 3
  FREE=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1); if [ "$FREE" -lt 26000 ]; then echo "GPU: only ${FREE} MiB free, $name skipped"; FAILS=$((FAILS+1)); continue; fi
  setsid $PY -I -m vllm.entrypoints.openai.api_server --model $model --served-model-name $name --port $port --max-model-len 12288 --gpu-memory-utilization 0.80 --enable-prefix-caching --max-num-seqs 32 "$@" > $B/server_${name}_$V.log 2>&1 &
  SP=$!; python3 $HB start xtest-server-$name-$V --pid $SP --where "[5090] local model server" --why "vLLM server for the $name rater, variant $V of $B" --success "Server answers and the run finishes" --next "Stopped after its run"
  for i in $(seq 1 90); do curl -s localhost:$port/v1/models >/dev/null 2>&1 && break; sleep 10; done
  if curl -s localhost:$port/v1/models >/dev/null 2>&1; then python3 $X/run.py --bundle $B --variant $V --rater $X/raters/$name.json --fields $F --order-seed $SEED --workers 8 --cap-usd 1 || { echo "FAILED $name $V"; FAILS=$((FAILS+1)); }; S=done; else echo "SERVER $name DID NOT START"; FAILS=$((FAILS+1)); S=failed; fi
  kill -- -$SP 2>/dev/null; wait $SP 2>/dev/null; python3 $HB finish xtest-server-$name-$V $S --last "stopped by the script"; SP=""; sleep 10
done
[ $FAILS -eq 0 ] && echo "VARIANT-DONE: every run succeeded" || { echo "VARIANT-INCOMPLETE: $FAILS step(s) failed or were skipped"; exit 1; }
