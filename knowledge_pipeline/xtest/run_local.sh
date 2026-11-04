#!/bin/bash
# M4b: Gemma and Qwen on the common structure through local OpenAI-compatible vLLM servers. Waits for the classifier script to end, stops voice and Clef, serves one model at a time, runs main + order + paraphrase, restarts services. Each server run stays under 1 hour (3600 tasks x ~1 s with 8 workers).
WAITPID=$1
while [ -n "$WAITPID" ] && kill -0 "$WAITPID" 2>/dev/null; do sleep 20; done
export OPENAI_COMPAT_API_KEY=local VLLM_USE_FLASHINFER_SAMPLER=0
cd /workspace/knowledge_pipeline/projects/world-state; X=/workspace/knowledge_pipeline/xtest; PY=/workspace/models/clef-flash-nvfp4/.venv/bin/python
( cd /workspace && ./service.sh stop voice; ./service.sh stop clef-flash-q4km ) >/dev/null 2>&1; sleep 5
for spec in "gemma 8101 /workspace/models/gemma4-26b-nvfp4" "qwen 8102 /workspace/models/qwen36-27b-nvfp4"; do set -- $spec
  $PY -I -m vllm.entrypoints.openai.api_server --model $3 --served-model-name $1 --port $2 --max-model-len 12288 --gpu-memory-utilization 0.80 --enable-prefix-caching --max-num-seqs 32 > runs/xtest/B1/server_$1.log 2>&1 &
  SP=$!; for i in $(seq 1 90); do curl -s localhost:$2/v1/models >/dev/null 2>&1 && break; sleep 10; done
  if curl -s localhost:$2/v1/models >/dev/null 2>&1; then
    for cfg in "A 0" "A 1" "P 0"; do set -- $1 $2 $3 $cfg
      python3 $X/run.py --bundle runs/xtest/B1 --variant $4 --rater $X/raters/$1.json --fields presence story topic --order-seed $5 --workers 8 --cap-usd 1 || echo "FAILED $1 $4 $5"
    done
  else echo "SERVER $1 DID NOT START"; fi
  kill $SP; wait $SP 2>/dev/null; sleep 10
done
( cd /workspace && ./service.sh start clef-flash-q4km; ./service.sh start voice ) >/dev/null 2>&1
echo LOCAL-DONE
