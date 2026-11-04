#!/bin/bash
# usage: run_bundle.sh <bundle dir> "<fields>"   classifiers (Clef, Jev) then local Gemma and Qwen servers, each with main + order + paraphrase control; services restored at the end.
B=$1; F=$2; set -a; . /workspace/secrets/vault.env 2>/dev/null; set +a
cd /workspace/knowledge_pipeline/projects/world-state; X=/workspace/knowledge_pipeline/xtest; PY=/workspace/models/clef-flash-nvfp4/.venv/bin/python
for r in clef jev; do for cfg in "A 0" "A 1" "P 0"; do set -- $cfg; python3 $X/run.py --bundle $B --variant $1 --rater $X/raters/$r.json --fields $F --order-seed $2 --workers 6 --cap-usd 0.6 || echo "FAILED $r $cfg"; done; done
export OPENAI_COMPAT_API_KEY=local VLLM_USE_FLASHINFER_SAMPLER=0
( cd /workspace && ./service.sh stop voice; ./service.sh stop clef-flash-q4km ) >/dev/null 2>&1; sleep 5
for spec in "gemma 8101 /workspace/models/gemma4-26b-nvfp4 " "qwen 8102 /workspace/models/qwen36-27b-nvfp4 --attention-backend TRITON_ATTN"; do set -- $spec; name=$1; port=$2; model=$3; shift 3
  $PY -I -m vllm.entrypoints.openai.api_server --model $model --served-model-name $name --port $port --max-model-len 12288 --gpu-memory-utilization 0.80 --enable-prefix-caching --max-num-seqs 32 "$@" > $B/server_$name.log 2>&1 &
  SP=$!; for i in $(seq 1 90); do curl -s localhost:$port/v1/models >/dev/null 2>&1 && break; sleep 10; done
  if curl -s localhost:$port/v1/models >/dev/null 2>&1; then for cfg in "A 0" "A 1" "P 0"; do set -- $cfg; python3 $X/run.py --bundle $B --variant $1 --rater $X/raters/$name.json --fields $F --order-seed $2 --workers 8 --cap-usd 1 || echo "FAILED $name $cfg"; done; else echo "SERVER $name DID NOT START"; fi
  kill $SP; wait $SP 2>/dev/null; sleep 10
done
( cd /workspace && ./service.sh start clef-flash-q4km; ./service.sh start voice ) >/dev/null 2>&1
echo BUNDLE-DONE
