#!/bin/bash
# M4c: Qwen3.6-27B (hybrid model) needs the TRITON_ATTN backend, as in the offline runs; the first server attempt failed in CUDA-graph capture without it (run_local.sh, L679). Same bundle, same run.py, same adapters.
export OPENAI_COMPAT_API_KEY=local VLLM_USE_FLASHINFER_SAMPLER=0
cd /workspace/knowledge_pipeline/projects/world-state; X=/workspace/knowledge_pipeline/xtest; PY=/workspace/models/clef-flash-nvfp4/.venv/bin/python
$PY -I -m vllm.entrypoints.openai.api_server --model /workspace/models/qwen36-27b-nvfp4 --served-model-name qwen --port 8102 --max-model-len 12288 --gpu-memory-utilization 0.80 --enable-prefix-caching --max-num-seqs 32 --attention-backend TRITON_ATTN > runs/xtest/B1/server_qwen.log 2>&1 &
SP=$!; for i in $(seq 1 90); do curl -s localhost:8102/v1/models >/dev/null 2>&1 && break; sleep 10; done
if curl -s localhost:8102/v1/models >/dev/null 2>&1; then
  for cfg in "A 0" "A 1" "P 0"; do set -- $cfg
    python3 $X/run.py --bundle runs/xtest/B1 --variant $1 --rater $X/raters/qwen.json --fields presence story topic --order-seed $2 --workers 8 --cap-usd 1 || echo "FAILED qwen $1 $2"
  done
else echo "SERVER qwen DID NOT START"; fi
kill $SP; wait $SP 2>/dev/null; sleep 10
( cd /workspace && ./service.sh start clef-flash-q4km; ./service.sh start voice ) >/dev/null 2>&1
echo QWEN-DONE
