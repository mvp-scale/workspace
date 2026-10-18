#!/bin/bash
# Stops the labeller (by its PID) at a fixed time, then trains once on what was labelled. Log: data/newsreader/bitmob/hardstop.log
PID=$1; UNTIL=$2
while [ "$(date +%s)" -lt "$UNTIL" ] && ps -o args= -p "$PID" | grep -q "bitmob/label.py"; do sleep 15; done
if ps -o args= -p "$PID" | grep -q "bitmob/label.py"; then kill "$PID"; echo "$(date +%H:%M) hard stop: labeller $PID stopped at $(wc -l < /workspace/data/newsreader/labels/clef-q4km.jsonl) stories"
else echo "$(date +%H:%M) labeller finished on its own at $(wc -l < /workspace/data/newsreader/labels/clef-q4km.jsonl) stories"; fi
cd /workspace/probes/world-engine && WE_RULES=rules_v2 HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python -I /workspace/newsreader/bitmob/train.py 2>&1 | grep -v Warning
echo "$(date +%H:%M) final training done"
