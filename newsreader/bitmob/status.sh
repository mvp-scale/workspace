#!/bin/bash
# Where the BitMob training stands: labelling progress, speed, time left, GPU, and the latest test results.
L=/workspace/data/newsreader/labels/clef-q4km.jsonl; R=/workspace/data/newsreader/bitmob/results.json
n=$(wc -l < "$L" 2>/dev/null || echo 0); total=1167
pid=$(pgrep -f "bitmob/label.py" | head -1)
if [ -n "$pid" ]; then el=$(ps -o etimes= -p "$pid" | tr -d ' '); rate=$(awk -v n="$n" -v e="$el" 'BEGIN{printf "%.1f", n/(e/60)}'); left=$(awk -v n="$n" -v t="$total" -v r="$rate" 'BEGIN{ if (r>0) printf "%.0f", (t-n)/r; else print "?" }')
  echo "Labelling (Clef, GPU): $n / $total stories · $rate per min · about $left min left"
else echo "Labelling: not running ($n stories labelled)"; fi
[ -f /workspace/data/newsreader/bitmob/hardstop.log ] && echo "Hard stop: 20:48 · $(tail -1 /workspace/data/newsreader/bitmob/hardstop.log 2>/dev/null)"
echo "GPU: $(nvidia-smi --query-gpu=utilization.gpu,power.draw --format=csv,noheader)"
for c in 300 600 1167; do if [ "$n" -ge $c ]; then echo "Checkpoint at $c: reached"; else echo "Checkpoint at $c: in $(( c - n )) stories"; fi; done
if [ -f "$R" ]; then echo "Latest test ($(date -r "$R" +%H:%M)):"; python3 -c "
import json; d=json.load(open('$R'))
for k, v in d.items(): print(f\"  {k:<22} recall {v['recall']:.2f}  precision {v['precision']:.2f}  questions >=97% agree: {v['questions_ge_97']}/328  {v['cpu_ms_per_story']} ms/story  {'PASS' if v['PASS'] else 'not yet'}\")"
else echo "Latest test: none yet (first one runs at 300 stories)"; fi
