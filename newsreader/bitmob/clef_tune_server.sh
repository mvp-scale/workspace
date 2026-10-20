#!/usr/bin/env bash
# Sweep llama-server settings for Clef on a TEST instance (:8028), production :8018 untouched. Each variant: start, wait healthy,
# run clef_tune.py (20 stories, 20 questions/call, 8 at a time), read /metrics, stop by verified PID. Log: data/clef-tune/tune.log
set -u; LOG=/workspace/data/clef-tune/tune.log; D=/workspace/models/llama-cpp-b11430/llama-b11430
export LD_LIBRARY_PATH=$D:$D/../cudart-llama-b11430-bin-ubuntu-cuda-12.8-x64
M=/workspace/data/models/clef-flash-q4km/Cloudflare_clef-flash-Q4_K_M.gguf
variant(){ name=$1; shift
  echo "$(date '+%F %T') == $name: $*" >> $LOG
  $D/llama-server -m $M --alias clef-flash-q4km --host 127.0.0.1 --port 8028 -ngl 999 --metrics "$@" > /workspace/data/clef-tune/server-$name.log 2>&1 &
  pid=$!; for i in $(seq 120); do curl -sf 127.0.0.1:8028/health >/dev/null && break; sleep 1; done
  if ! curl -sf 127.0.0.1:8028/health >/dev/null; then echo "   failed to start: $(tail -2 /workspace/data/clef-tune/server-$name.log)" >> $LOG; kill $pid 2>/dev/null; wait $pid 2>/dev/null; return; fi
  (cd /workspace/probes/world-engine && CLEF_URL=http://127.0.0.1:8028 WE_RULES=rules_v2 timeout 900 /workspace/kev/.venv/bin/python -I /workspace/newsreader/bitmob/clef_tune.py srv-$name 20 8 20) | sed 's/^/   /' >> $LOG
  curl -s 127.0.0.1:8028/metrics | grep -E "^llamacpp:(prompt_tokens_total|prompt_seconds_total|prompt_tokens_seconds|requests_processing)" | sed 's/^/   metric /' >> $LOG
  [ "$(cat /proc/$pid/cmdline 2>/dev/null | tr '\0' ' ' | grep -c 'port 8028')" = 1 ] && kill $pid; wait $pid 2>/dev/null
}
variant base-np8-ub16k   -c 131072 -np 8  -b 16384 -ub 16384
variant np2-ub16k        -c 32768  -np 2  -b 16384 -ub 16384
variant np4-ub16k        -c 65536  -np 4  -b 16384 -ub 16384
variant np16-ub16k       -c 262144 -np 16 -b 16384 -ub 16384
variant np8-ub8k         -c 131072 -np 8  -b 8192  -ub 8192
variant np8-ub32k        -c 131072 -np 8  -b 32768 -ub 32768
variant np8-ub16k-faon   -c 131072 -np 8  -b 16384 -ub 16384 -fa on
echo "$(date '+%F %T') sweep done" >> $LOG
