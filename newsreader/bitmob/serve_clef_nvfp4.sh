#!/bin/bash
# Serve Clef Flash Fast (CLF9F4) on :8038 for the benchmark. The 5090 holds the regular Clef (:8018) too, so start pauses it (clef_fast_mode.sh pause) and stop ALWAYS resumes it and health-checks.
#   newsreader/bitmob/serve_clef_nvfp4.sh start [UTIL=0.6] | stop | status
# Refuses to start with data/progress/STOP set or while the live feed is on. Kills only the verified PID (cmdline contains serve_clef_nvfp4.py and --port 8038). Log data/progress/clef8038.log, pid file data/progress/clef8038.pid.
W=/workspace; PIDF=$W/data/progress/clef8038.pid; LOGF=$W/data/progress/clef8038.log; FM=$W/newsreader/bitmob/clef_fast_mode.sh; PORT=8038
mypid(){ p=$(cat $PIDF 2>/dev/null); [ -n "$p" ] && tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -q "serve_clef_nvfp4.py" && echo $p; }
case "$1" in
 status) echo "pid8038=$(mypid) health=$(curl -sf -m3 127.0.0.1:$PORT/health >/dev/null && echo ok || echo down)"; bash $FM status ;;
 start)
  [ -e $W/data/progress/STOP ] && { echo STOP; exit 1; }
  [ -n "$(mypid)" ] && { echo "already running"; exit 0; }
  bash $FM pause || { echo "pause failed ($?)"; bash $FM resume; exit 2; }
  nohup $W/models/cygnet-venv/bin/python $W/newsreader/bitmob/serve_clef_nvfp4.py --port $PORT --util ${2:-0.6} > $LOGF 2>&1 & echo $! > $PIDF
  for i in $(seq 300); do curl -sf -m3 127.0.0.1:$PORT/health >/dev/null && break; kill -0 $(cat $PIDF) 2>/dev/null || break; sleep 2; done
  curl -sf -m3 127.0.0.1:$PORT/health >/dev/null || { echo "FAILED to start; see $LOGF"; $0 stop; exit 3; }
  echo "CLF9F4 serving on :$PORT" ;;
 stop)
  p=$(mypid); [ -n "$p" ] && { kill $p; for i in $(seq 40); do kill -0 $p 2>/dev/null || break; sleep 1; done; kill -0 $p 2>/dev/null && echo "pid $p still alive (not forced)"; }
  sleep 3; bash $FM resume; bash $FM status ;;
 *) echo "usage: $0 start [util] | stop | status"; exit 64 ;;
esac
