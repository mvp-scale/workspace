#!/usr/bin/env bash
# start.sh -- pinned-port start/stop/status/restart for demo/server.py.
#
# The demo has been drifting onto whatever port a given session happened to nohup it on, which
# makes it hard to know what's actually running or reachable. This script fixes that: it always
# uses the same port (8100 by default), tracks the process by a pidfile instead of grepping ss
# output by hand, and cleans up anything squatting on that port even if it wasn't started by this
# script (e.g. a stray manual nohup from a previous session).
#
#   ./start.sh start     # start it (no-op if already running)
#   ./start.sh stop      # stop it, and anything else on the same port
#   ./start.sh restart   # stop + start -- use this after editing demo/ code
#   ./start.sh status    # is it running, and where
#
# Sources .env automatically if present (TYPESAFE_API_KEY etc.), matching CLAUDE.md's documented
# `set -a; . ./.env; set +a; python3 demo/server.py` startup. Override the port with DEMO_PORT=...
# for a one-off temporary instance (e.g. while testing a change without touching the real one) --
# but the real, canonical instance should always just be ./start.sh with no overrides.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

PORT="${DEMO_PORT:-8100}"
PIDFILE="logs/demo.pid"
LOGFILE="logs/demo.log"

mkdir -p logs

is_running() {
  [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null
}

pid_on_port() {
  ss -ltnpH 2>/dev/null | grep ":$PORT " | grep -oP 'pid=\K[0-9]+' | head -1 || true
}

wait_for_death() {
  local pid="$1"
  for _ in $(seq 1 25); do
    kill -0 "$pid" 2>/dev/null || return 0
    sleep 0.2
  done
  kill -9 "$pid" 2>/dev/null || true
}

start() {
  if is_running; then
    echo "Already running: pid $(cat "$PIDFILE"), http://127.0.0.1:$PORT (use ./start.sh restart to reload code)"
    return 0
  fi
  local squatter
  squatter="$(pid_on_port)"
  if [ -n "$squatter" ]; then
    echo "Port $PORT is already in use by pid $squatter (not tracked by this script -- stopping it first)."
    kill "$squatter" 2>/dev/null || true
    wait_for_death "$squatter"
  fi
  if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
  fi
  : > "$LOGFILE"
  DEMO_PORT="$PORT" nohup python3 demo/server.py >> "$LOGFILE" 2>&1 &
  echo $! > "$PIDFILE"
  disown
  sleep 1
  if is_running; then
    echo "Started: pid $(cat "$PIDFILE"), http://127.0.0.1:$PORT (log: $LOGFILE)"
  else
    echo "Failed to start -- see $LOGFILE"
    rm -f "$PIDFILE"
    exit 1
  fi
}

stop() {
  local stopped=false
  if is_running; then
    local pid
    pid="$(cat "$PIDFILE")"
    kill "$pid" 2>/dev/null || true
    wait_for_death "$pid"
    stopped=true
  fi
  rm -f "$PIDFILE"
  local squatter
  squatter="$(pid_on_port)"
  if [ -n "$squatter" ]; then
    kill "$squatter" 2>/dev/null || true
    wait_for_death "$squatter"
    stopped=true
  fi
  if $stopped; then echo "Stopped."; else echo "Not running."; fi
}

status() {
  if is_running; then
    echo "Running: pid $(cat "$PIDFILE"), http://127.0.0.1:$PORT"
  else
    local squatter
    squatter="$(pid_on_port)"
    if [ -n "$squatter" ]; then
      echo "Not tracked, but something is listening on port $PORT (pid $squatter, started outside this script)."
    else
      echo "Not running."
    fi
  fi
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) status ;;
  *) echo "Usage: $0 {start|stop|restart|status}"; exit 1 ;;
esac
