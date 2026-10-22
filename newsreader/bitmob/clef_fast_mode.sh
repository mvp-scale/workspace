#!/bin/bash
# Fast-mode GPU handling (round 6): pause = stop the regular Clef llama-server on :8018 (verified PID only); resume = start it again with the identical command line; status.
#   newsreader/bitmob/clef_fast_mode.sh pause|resume|status
# The original command line is saved in data/progress/clef8018.cmd the first time (from /proc/<pid>/cmdline); resume uses it. resume is safe to run any time (no-op when :8018 is healthy).
W=/workspace; CMDF=$W/data/progress/clef8018.cmd; LOGF=$W/data/progress/clef8018.log
D=$W/models/llama-cpp-b11430/llama-b11430; export LD_LIBRARY_PATH=$D:$W/models/llama-cpp-b11430/cudart-llama-b11430-bin-ubuntu-cuda-12.8-x64
health(){ curl -sf -m3 127.0.0.1:8018/health >/dev/null; }
pid8018(){ for p in $(pgrep -f "clef-flash-q4km"); do tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -q -- "--port 8018" && grep -q "^$(readlink /proc/$p/exe | xargs basename)$" <(echo clef-flash-q4km) 2>/dev/null; if tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -q -- "--port 8018 "; then echo $p; return; fi; done; }
live(){ curl -s -m3 127.0.0.1:8112/live | python3 -c "import sys,json;print(json.load(sys.stdin).get('on'))" 2>/dev/null; }
case "$1" in
 status) echo "pid8018=$(pid8018) health=$(health && echo ok || echo down) live_feed_on=$(live)"; ;;
 pause)
  [ -e $W/data/progress/STOP ] && { echo STOP; exit 1; }
  p=$(pid8018); [ -z "$p" ] && { echo "no :8018 process"; exit 0; }
  [ -s $CMDF ] || tr '\0' ' ' < /proc/$p/cmdline > $CMDF
  [ "$(live)" = "True" ] && { echo "live feed is ON: turn it off first"; exit 2; }
  kill $p; for i in $(seq 30); do kill -0 $p 2>/dev/null || break; sleep 1; done; kill -0 $p 2>/dev/null && { echo "pid $p still alive"; exit 3; }
  sleep 3; echo "paused (pid $p stopped); GPU used: $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"; ;;
 resume)
  health && { echo "already healthy"; exit 0; }
  [ -s $CMDF ] || { echo "no saved command line"; exit 4; }
  cd $W; nohup bash -c "$(cat $CMDF)" > $LOGF 2>&1 &
  for i in $(seq 180); do health && break; sleep 1; done
  health || { echo "FAILED to come back; see $LOGF"; exit 5; }
  r=$(curl -s -m60 127.0.0.1:8018/v1/systemone -H 'Content-Type: application/json' -d '{"model":"clef-flash-q4km","state":"Test.","questions":{"q":{"type":"noul","instructions":"Is this a test?"}}}'); echo "resumed; systemone: $r" | cut -c1-200; ;;
 *) echo "usage: $0 pause|resume|status"; exit 64;;
esac
