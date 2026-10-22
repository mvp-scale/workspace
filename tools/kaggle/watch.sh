#!/bin/bash
# Watch one Kaggle run: optionally push it, poll its status, download the output when it ends, add it to the run ledger.
# Usage: watch.sh <owner/kernel-slug> <output-dir> [max-minutes=60] [poll-seconds=60] [push-dir]
#   push-dir     push that kernel folder first, so boot time (push -> RUNNING) is measured; polls every 10 s until RUNNING
# Environment (all optional):
#   KAGGLE_RUNS_LEDGER   run ledger file (default ./kaggle-runs.jsonl)
#   KAGGLE_ON_EVENT      shell command run on every status change with args: job state message pid
#                        state is one of: running, done, failed. Example: KAGGLE_ON_EVENT='notify-send "$1" "$3"'
# The run stops on Kaggle when its script ends (and guard.py stops it if it hangs); this script only watches and fetches.
set -u
K="$1"; OUT="$2"; MAX="${3:-60}"; POLL="${4:-60}"; PUSH="${5:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JOB="kaggle:${K##*/}"
EV() {  # state message
  echo "$(date +%H:%M:%S)  $JOB  $1  $2"
  [ -n "${KAGGLE_ON_EVENT:-}" ] && sh -c "$KAGGLE_ON_EVENT" _ "$JOB" "$1" "$2" "$$" >/dev/null 2>&1
  return 0
}
USED() { kaggle quota 2>/dev/null | awk '$1=="GPU"{sub("h","",$2); print $2}'; }
RECORD() {  # status
  local u1; u1=$(USED)
  python3 "$HERE/runs.py" add --kernel "$K" --status "$1" --done "$(date +%s)" \
    $( [ -f "$OUT/${K##*/}.log" ] && echo "--log $OUT/${K##*/}.log" ) \
    ${PUSHED:+--pushed $PUSHED} ${RUNNING:+--running $RUNNING} \
    ${U0:+--gpu-used-before $U0} ${u1:+${U0:+--gpu-used-after $u1}} >/dev/null \
    && echo "run ledger: recorded $K" || echo "run ledger: could not record $K"
}
U0=$(USED); PUSHED=""; RUNNING=""
if [ -n "$PUSH" ]; then
  PUSHED=$(date +%s)
  kaggle kernels push -p "$PUSH" >/dev/null 2>&1 || { EV failed "push of $PUSH failed"; exit 1; }
fi
end=$(( $(date +%s) + MAX * 60 ))
EV running "watching $K (poll ${POLL}s, max ${MAX} min)"
while [ "$(date +%s)" -lt "$end" ]; do
  s=$(kaggle kernels status "$K" 2>&1 | grep -oE 'KernelWorkerStatus\.[A-Z_]+' | cut -d. -f2)
  if [ "$s" = RUNNING ] && [ -z "$RUNNING" ]; then RUNNING=$(date +%s); fi
  case "$s" in
    COMPLETE)
      mkdir -p "$OUT"
      if kaggle kernels output "$K" -p "$OUT" >/dev/null 2>&1; then
        RECORD complete; EV done "finished; output in $OUT ($(du -sh "$OUT" | cut -f1)); GPU left: $(kaggle quota 2>/dev/null | awk '$1=="GPU"{print $3}')"
      else
        RECORD complete; EV failed "finished on Kaggle but download failed; output is still kept on Kaggle"
      fi
      exit 0 ;;
    ERROR|CANCEL_ACKNOWLEDGED|CANCEL_REQUESTED)
      mkdir -p "$OUT"; kaggle kernels output "$K" -p "$OUT" >/dev/null 2>&1; RECORD "$s"
      EV failed "Kaggle run ended with $s; log in $OUT"; exit 1 ;;
    *) EV running "Kaggle status ${s:-unknown}" ;;
  esac
  if [ -z "$RUNNING" ]; then sleep 10; else sleep "$POLL"; fi
done
EV failed "watcher stopped after ${MAX} min; the run may still be going on Kaggle (check: kaggle kernels status $K)"
exit 2
