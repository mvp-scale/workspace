#!/usr/bin/env bash
# One blocking call: push a Kaggle kernel -> wait -> fetch its output. The agent runs it once and reads OUT; it never polls.
#   CARD=cards/T7.json kit/ops/kaggle_run.sh <kernel-dir> <out-dir> [poll-sec=600]
#   NO_PUSH=1 kit/ops/kaggle_run.sh ...        wait for / fetch a kernel that is already pushed
# Env: KAGGLE_API_TOKEN (else read from $VAULT, default secrets/vault.env; never printed), KAGGLE_CMD (default
#      "kaggle"; e.g. "python -m kaggle"), PYTHON (default python), GPU_CHECKED=1 (required for GPU kernels, R4),
#      MAX_WAIT_S (0 = no limit).
# Writes OUT/push.log, OUT/status.txt (R4 evidence: what ran, when). Exit: 0 complete, 1 error/cancel/timeout,
#      2 push dropped an input source, 3 GPU push without GPU_CHECKED=1, 4 usage or missing token.
set -euo pipefail
# Card gate (defence in depth with the PreToolUse hook, MM3-0019): no run without a passing task card.
KP_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
if [ "${NO_PUSH:-}" != 1 ]; then
  [ -n "${CARD:-}" ] || { echo "refused: set CARD=<task card> (knowledge_pipeline/agentic/schemas/task-card.schema.json)" >&2; exit 4; }
  node "$KP_ROOT/agentic/scripts/check_card.mjs" "$CARD" >&2 || { echo "refused: task card $CARD fails check_card" >&2; exit 4; }
fi
[ $# -ge 2 ] || { echo "usage: kaggle_run.sh <kernel-dir> <out-dir> [poll-sec]" >&2; exit 4; }
DIR=$1; OUT=$2; POLL=${3:-600}                                   # status checks >= 10 min apart by default
KAGGLE=${KAGGLE_CMD:-kaggle}; PY=${PYTHON:-python}; VAULT=${VAULT:-secrets/vault.env}
[ -f "$DIR/kernel-metadata.json" ] || { echo "no $DIR/kernel-metadata.json" >&2; exit 4; }

if [ -z "${KAGGLE_API_TOKEN:-}" ] && [ -f "$VAULT" ]; then        # secrets per process: exported to this script only
  KAGGLE_API_TOKEN=$(grep '^KAGGLE_API_TOKEN=' "$VAULT" | head -1 | cut -d= -f2- | tr -d '\r' || true)
fi
[ -n "${KAGGLE_API_TOKEN:-}" ] || { echo "KAGGLE_API_TOKEN not set and not in $VAULT" >&2; exit 4; }
export KAGGLE_API_TOKEN

meta() { "$PY" -c "import json,sys;d=json.load(open(sys.argv[1]));print(d.get(sys.argv[2],''))" "$DIR/kernel-metadata.json" "$1"; }
REF=$(meta id); GPU=$(meta enable_gpu)
mkdir -p "$OUT"
stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }

if [ -z "${NO_PUSH:-}" ]; then
  if [ "$GPU" = "True" ] && [ "${GPU_CHECKED:-}" != 1 ]; then    # R4: one job per GPU; the quota is shared
    echo "R4: $REF uses a GPU. First check no other GPU session of yours is running (kaggle.com/me -> active" >&2
    echo "    sessions, or '$KAGGLE kernels list --mine'), and check quota. Then re-run with GPU_CHECKED=1." >&2
    exit 3
  fi
  # The CLI exits 0 on pushes it did not register and on dropped sources: trust its text, not its exit code.
  until P=$($KAGGLE kernels push -p "$DIR" 2>&1) && echo "$P" | grep -qi 'successfully pushed'; do
    echo "$P" | tail -1 >&2; sleep 30                            # session limit or transient error: retry every 30 s
  done
  printf '%s pushed %s gpu=%s\n%s\n' "$(stamp)" "$REF" "$GPU" "$P" > "$OUT/push.log"
  if echo "$P" | grep -i 'not valid' >&2; then echo "push dropped an input source; the run would be wrong" >&2; exit 2; fi
  echo "pushed $REF"
  for _ in $(seq 1 20); do                                       # until queued, status shows the previous version's end
    $KAGGLE kernels status "$REF" 2>/dev/null | grep -qiE 'queued|running' && break; sleep 15
  done
fi

START=$(date +%s)
while :; do
  S=$($KAGGLE kernels status "$REF" 2>/dev/null | grep -ioE 'complete|error|cancel' | head -1 | tr '[:upper:]' '[:lower:]' || true)
  [ -n "$S" ] && break
  if [ "${MAX_WAIT_S:-0}" -gt 0 ] && [ $(( $(date +%s) - START )) -gt "$MAX_WAIT_S" ]; then S=timeout; break; fi
  sleep "$POLL"
done
echo "$(stamp) $REF status=$S" >> "$OUT/status.txt"
[ "$S" = timeout ] || $KAGGLE kernels output "$REF" -p "$OUT" >/dev/null 2>&1 || echo "output fetch failed" >&2
echo "status=$S out=$OUT"; [ "$S" = complete ]
