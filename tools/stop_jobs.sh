#!/bin/bash
# Stop all of our long-running work now, and block relaunches.
# - writes data/progress/STOP: the captain and crews check it before every launch or relaunch and do nothing while it exists
# - kills local labelling/training jobs by verified PID (command line must match), never Clef, the engine or other services
# - lists Kaggle runs still going (Kaggle's CLI cannot cancel them; each stops itself within its guard limit, <= 45 min)
# Resume: rm data/progress/STOP
set -u
cd /workspace
date -Iseconds > data/progress/STOP && echo "STOP file written: data/progress/STOP (relaunches blocked)"
for pat in "newsreader/bitmob/clef_label.py" "newsreader/bitmob/suite.py" "tools/kaggle/watch.sh"; do
  for pid in $(pgrep -f "$pat"); do
    cmd=$(tr '\0' ' ' < /proc/$pid/cmdline 2>/dev/null)
    case "$cmd" in *"$pat"*) kill "$pid" && echo "stopped $pid: ${cmd:0:110}";; esac
  done
done
echo "Kaggle runs not yet finished (they stop themselves within their guard limit):"
for k in $(kaggle kernels list --mine --page-size 10 2>/dev/null | awk 'NR>2{print $1}'); do
  s=$(kaggle kernels status "$k" 2>&1 | grep -oE 'KernelWorkerStatus\.[A-Z_]+' | cut -d. -f2)
  case "$s" in RUNNING|QUEUED) echo "  $k $s";; esac
done
kaggle quota 2>/dev/null | awk '$1=="GPU"{print "Kaggle GPU this week: "$2" used, "$3" left"}'
