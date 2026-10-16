#!/usr/bin/env bash
# cf_start.sh -- temporary public share of the console through one Cloudflare quick tunnel.
#   ./cf_start.sh [start|stop|status]      (or ./service.sh start|stop share)
# Voice goes through the console (/voice/ws), so one tunnel to :8100 carries everything. The URL is random and dies
# with the tunnel. No auth: anyone with the link can use the server-side TYPESAFE_API_KEY (service switches refuse them).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
CF=./bin/cloudflared
RUN=/tmp/claude-0/cf; mkdir -p "$RUN"
DEMO_PORT=${DEMO_PORT:-8100}

stop() { for n in demo voice; do [ -f "$RUN/$n.pid" ] && kill "$(cat "$RUN/$n.pid")" 2>/dev/null || true; rm -f "$RUN/$n.pid" "$RUN/$n.log"; done; rm -f demo/static/voice-url.txt; echo stopped; }
tunnel() {  # name port -> prints https URL
  nohup "$CF" tunnel --no-autoupdate --url "http://127.0.0.1:$2" >"$RUN/$1.log" 2>&1 & echo $! >"$RUN/$1.pid"
  for _ in $(seq 60); do u=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$RUN/$1.log" | head -1 || true); [ -n "$u" ] && { echo "$u"; return; }; sleep 1; done
  echo "tunnel $1 did not come up; see $RUN/$1.log" >&2; exit 1
}
show() { [ -f "$RUN/demo.pid" ] && kill -0 "$(cat "$RUN/demo.pid")" 2>/dev/null || { echo "not running"; return 1; }
  d=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$RUN/demo.log" | head -1)
  echo "Console: $d/   (voice: $d/flow)"; }

case "${1:-start}" in
  stop) stop ;;
  status) show ;;
  start)
    curl -sf "http://127.0.0.1:$DEMO_PORT/api/status" >/dev/null || { echo "demo not answering on :$DEMO_PORT (./service.sh up)"; exit 1; }
    stop >/dev/null
    tunnel demo "$DEMO_PORT" >/dev/null; show ;;
esac
