#!/usr/bin/env bash
# One blocking call: run a job on a local/LAN GPU box or a RunPod pod over ssh -> wait -> fetch outputs.
#   CARD=cards/T7.json kit/ops/local_gpu_run.sh <ssh-host> <remote-base> <out-dir> -- <command...>
#   e.g. kit/ops/local_gpu_run.sh gpu5090 jobs runs/T7/local -- python train.py --config cfg.json
# Guarantees:
#   R4  refuses (exit 3) if nvidia-smi on the target GPU shows any compute process, or another run of this script
#       holds the GPU lock (<remote-base>/.lock-gpu<N>). The nvidia-smi listing is saved to OUT/gpu_status.txt.
#   Code is copied (tar over ssh; rsync not needed) into a fresh <remote-base>/<RUN_ID>/, so a running job never
#   sees later edits. data/ and gold/ (publisher text) are NOT copied unless PRIVATE_TARGET=1 (your own box or a
#   private pod volume). secrets/, *.env, .git, models/, runs/, venvs are never copied.
#   The job runs detached (nohup) with its log in run.log; this script waits (POLL s between checks) so the agent
#   does not poll, then fetches run.log, run.rc and REMOTE_OUT into OUT. Exit = the job's exit code.
# Env: GPU (index, default 0), SSH_PORT, SSH_KEY, SSH_OPTS, CODE_DIR (default .), REMOTE_OUT (default outputs),
#      POLL (default 60), MAX_WAIT_S (0 = none; job keeps running remotely on timeout), RUN_ID (default UTC stamp),
#      SEND_KEYS="HF_TOKEN WANDB_API_KEY" (values from env or $VAULT, default secrets/vault.env; sent over ssh stdin
#      to the job process only, never on a command line, never printed), PRIVATE_TARGET=1.
set -euo pipefail
# Card gate (defence in depth with the PreToolUse hook, MM3-0019): no run without a passing task card.
KP_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
[ -n "${CARD:-}" ] || { echo "refused: set CARD=<task card> (knowledge_pipeline/agentic/schemas/task-card.schema.json)" >&2; exit 4; }
node "$KP_ROOT/agentic/scripts/check_card.mjs" "$CARD" >&2 || { echo "refused: task card $CARD fails check_card" >&2; exit 4; }
usage() { echo "usage: local_gpu_run.sh <ssh-host> <remote-base> <out-dir> -- <command...>" >&2; exit 4; }
[ $# -ge 5 ] && [ "$4" = "--" ] || usage
HOST=$1; RB=${2#\~/}; OUT=$3; shift 4   # remote-base: absolute, or relative to the remote home ("~/x" -> "x")
if [ $# -eq 1 ]; then CMD=$1; else CMD=$(printf '%q ' "$@"); fi   # one arg = a shell string; several = argv, quoting kept
GPU=${GPU:-0}; POLL=${POLL:-60}; RO=${REMOTE_OUT:-outputs}; CODE=${CODE_DIR:-.}; VAULT=${VAULT:-secrets/vault.env}
RUN_ID=${RUN_ID:-run-$(date -u +%Y%m%dT%H%M%SZ)}; RD="$RB/$RUN_ID"
SSH=(ssh -o BatchMode=yes -o ServerAliveInterval=30 ${SSH_PORT:+-p "$SSH_PORT"} ${SSH_KEY:+-i "$SSH_KEY"} ${SSH_OPTS:-} "$HOST")
mkdir -p "$OUT"; OUT_ABS=$(cd "$OUT" && pwd)
q() { printf '%q' "$1"; }

# R4: one job per GPU.
STATUS=$("${SSH[@]}" "U=\$(nvidia-smi -i $(q "$GPU") --query-gpu=uuid --format=csv,noheader) || exit 9
  echo \"gpu $(q "$GPU") \$U\"; nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_memory --format=csv,noheader | grep \"\$U\" || true
  ls -d $(q "$RB")/.lock-gpu$(q "$GPU") 2>/dev/null && cat $(q "$RB")/.lock-gpu$(q "$GPU")/run 2>/dev/null || true") \
  || { echo "cannot query nvidia-smi on $HOST (exit $?)" >&2; exit 4; }
printf '%s %s\n%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$HOST" "$STATUS" > "$OUT_ABS/gpu_status.txt"
if [ "$(echo "$STATUS" | wc -l)" -gt 1 ]; then
  echo "R4: GPU $GPU on $HOST is busy; refusing. See $OUT/gpu_status.txt:" >&2; echo "$STATUS" >&2; exit 3
fi

# Copy code to a fresh run dir.
EXC=(--exclude=.git --exclude=secrets --exclude='*.env' --exclude=models --exclude=runs --exclude=.venv
     --exclude=venv --exclude=node_modules --exclude=__pycache__ --exclude=.kaggle_stage --exclude='*.lock')
[ "${PRIVATE_TARGET:-}" = 1 ] || EXC+=(--exclude=data --exclude=gold)
(cd "$CODE" && tar -czf - "${EXC[@]}" .) | "${SSH[@]}" "mkdir -p $(q "$RD") && tar -xzf - -C $(q "$RD")"
echo "copied $CODE -> $HOST:$RD (data/gold $( [ "${PRIVATE_TARGET:-}" = 1 ] && echo included || echo excluded ))"

# Secrets for the job process only.
ENVS=""
for k in ${SEND_KEYS:-}; do
  v=${!k:-}; [ -n "$v" ] || { [ -f "$VAULT" ] && v=$(grep "^$k=" "$VAULT" | head -1 | cut -d= -f2- | tr -d '\r' || true); }
  [ -n "$v" ] || { echo "SEND_KEYS: $k not in env or $VAULT" >&2; exit 4; }
  ENVS+="export $k=$(q "$v")"$'\n'
done

# Launch detached; the GPU lock is taken atomically (mkdir) and released when the job ends. The command is written
# to run.cmd so no shell re-quoting is needed.
"${SSH[@]}" bash -s <<EOF >/dev/null
set -e
export LOCKD="\$(cd $(q "$RB") && pwd)/.lock-gpu$(q "$GPU")"
mkdir "\$LOCKD" || { echo "R4: lock \$LOCKD held by \$(cat "\$LOCKD/run" 2>/dev/null)" >&2; exit 3; }
echo $(q "$RUN_ID") > "\$LOCKD/run"
cd $(q "$RD")
printf '%s\n' $(q "$CMD") > run.cmd
$ENVS
export CUDA_VISIBLE_DEVICES=$(q "$GPU")
nohup bash -c 'bash run.cmd > run.log 2>&1; echo \$? > run.rc; rm -rf "\$LOCKD"' >/dev/null 2>&1 < /dev/null &
EOF
echo "started $RUN_ID on $HOST gpu $GPU: $CMD"

START=$(date +%s); RC=""
while :; do
  RC=$("${SSH[@]}" "cat $(q "$RD")/run.rc 2>/dev/null" || true)
  [ -n "$RC" ] && break
  if [ "${MAX_WAIT_S:-0}" -gt 0 ] && [ $(( $(date +%s) - START )) -gt "$MAX_WAIT_S" ]; then
    echo "timeout after ${MAX_WAIT_S}s; job still running at $HOST:$RD (fetch later with the same RUN_ID)" >&2; RC=124; break
  fi
  sleep "$POLL"
done

"${SSH[@]}" "cd $(q "$RD") && tar -czf - run.log \$(ls -d run.rc $(q "$RO") 2>/dev/null)" | (cd "$OUT_ABS" && tar -xzf -) \
  || echo "fetch failed" >&2
echo "rc=$RC out=$OUT"; tail -5 "$OUT_ABS/run.log" 2>/dev/null || true
exit "$RC"
