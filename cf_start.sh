#!/usr/bin/env bash
# cf_start.sh -- temporary public share of the demo through two Cloudflare quick tunnels.
#   ./cf_start.sh [start|stop|status]
# One tunnel for the console (:8100) and one for the voice server (:8200, websocket), because the
# Conversation flow page opens its own websocket to the voice server. The share link is the console
# URL with ?voice=wss://... so the page's Voice server field is prefilled. URLs are random and die
# with the tunnels. No auth: anyone with the link can use the server-side TYPESAFE_API_KEY.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
CF=./bin/cloudflared
RUN=/tmp/claude-0/cf; mkdir -p "$RUN"
DEMO_PORT=${DEMO_PORT:-8100}; VOICE_PORT=${VOICE_PORT:-8200}

stop() { for n in demo voice; do [ -f "$RUN/$n.pid" ] && kill "$(cat "$RUN/$n.pid")" 2>/dev/null || true; rm -f "$RUN/$n.pid" "$RUN/$n.log"; done; rm -f demo/static/voice-url.txt; echo stopped; }
tunnel() {  # name port -> prints https URL
  nohup "$CF" tunnel --no-autoupdate --url "http://127.0.0.1:$2" >"$RUN/$1.log" 2>&1 & echo $! >"$RUN/$1.pid"
  for _ in $(seq 60); do u=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$RUN/$1.log" | head -1 || true); [ -n "$u" ] && { echo "$u"; return; }; sleep 1; done
  echo "tunnel $1 did not come up; see $RUN/$1.log" >&2; exit 1
}
show() { [ -f "$RUN/demo.log" ] || { echo "not running"; return 1; }
  d=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$RUN/demo.log" | head -1); v=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$RUN/voice.log" | head -1)
  echo "wss://${v#https://}/ws" > demo/static/voice-url.txt   # flow.html reads this when served over https
  echo "Console: $d/"; echo "Flow + voice (share this): $d/flow?voice=wss://${v#https://}/ws"; }

case "${1:-start}" in
  stop) stop ;;
  status) show ;;
  start)
    curl -sf "http://127.0.0.1:$DEMO_PORT/api/status" >/dev/null || { echo "demo not answering on :$DEMO_PORT (./start.sh start)"; exit 1; }
    curl -sf "http://127.0.0.1:$VOICE_PORT/api/status" >/dev/null || echo "warning: voice server not answering on :$VOICE_PORT"
    [ -f "$RUN/demo.pid" ] && stop
    tunnel demo "$DEMO_PORT" >/dev/null; tunnel voice "$VOICE_PORT" >/dev/null; show ;;
esac
