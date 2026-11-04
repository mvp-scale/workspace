#!/bin/bash
# Jev on B3 (3 runs) and B4 (A seed 0, A seed 1, P seed 0, and the Q frame); the cumulative cap in budget_cap.json applies inside run.py.
set -a; . /workspace/secrets/vault.env 2>/dev/null; set +a
cd /workspace/knowledge_pipeline/projects/world-state; X=/workspace/knowledge_pipeline/xtest; F4=$(python3 -c "import json;print(' '.join(json.load(open('runs/xtest/B4/bundle.json'))['fields']))"); FAILS=0
for cfg in "A 0" "A 1" "P 0"; do set -- $cfg; python3 $X/run.py --bundle runs/xtest/B3 --variant $1 --rater $X/raters/jev.json --fields which_c direction_c size_c --order-seed $2 --workers 6 --cap-usd 0.06 || { echo "FAILED B3 jev $cfg"; FAILS=$((FAILS+1)); }; done
for cfg in "A 0" "A 1" "P 0" "Q 0"; do set -- $cfg; python3 $X/run.py --bundle runs/xtest/B4 --variant $1 --rater $X/raters/jev.json --fields $F4 --order-seed $2 --workers 6 --cap-usd 0.12 || { echo "FAILED B4 jev $cfg"; FAILS=$((FAILS+1)); }; done
[ $FAILS -eq 0 ] && echo "JEV-CATCHUP-DONE: every run succeeded" || echo "JEV-CATCHUP-INCOMPLETE: $FAILS failed"
