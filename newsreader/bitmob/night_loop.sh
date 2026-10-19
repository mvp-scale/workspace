#!/bin/bash
# Overnight teaching loop: every hour, label new news-reader arrivals (full text and teasers) with both batteries on local Clef, then retrain
# the potion student and append a progress line. Hard stop at $STOP_AT (default 08:00 today) or when data/mm3-train/STOP exists.
# Each labelling pass is capped at 20 minutes of wall time; Clef is local, MM3 runs are forced local by mm3_label.py.
cd /workspace
STOP_AT=$(date -d "${STOP_AT:-08:00}" +%s); PY=/workspace/models/embed-zs/.venv/bin/python; L=data/mm3-train/night-loop.log
while [ "$(date +%s)" -lt "$STOP_AT" ] && [ ! -e data/mm3-train/STOP ]; do
  echo "== $(date '+%H:%M') pass" >> $L
  python3 newsreader/bitmob/mm3_label.py --workers 4 --minutes 20 >> $L 2>&1
  python3 newsreader/bitmob/mm3_label.py --teasers --workers 4 --minutes 20 >> $L 2>&1
  python3 newsreader/bitmob/mm3_label.py --battery newsreader/bitmob/batteries/evidence-v1.json --workers 4 --minutes 20 >> $L 2>&1
  $PY -I newsreader/bitmob/eval_potion.py >> $L 2>&1
  left=$(( STOP_AT - $(date +%s) )); [ "$left" -le 0 ] && break
  sleep $(( left < 3600 ? left : 3600 ))
done
echo "== $(date '+%H:%M') loop stopped" >> $L
