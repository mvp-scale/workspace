#!/bin/bash
# M4: Jev and Clef on the common structure: main run (A, seed 0), order control (A, seed 1), paraphrase control (P, seed 0). Fields: presence story topic.
set -a; . /workspace/secrets/vault.env 2>/dev/null; set +a
cd /workspace/knowledge_pipeline/projects/world-state; X=/workspace/knowledge_pipeline/xtest
for r in clef jev; do
  for cfg in "A 0" "A 1" "P 0"; do set -- $cfg
    python3 $X/run.py --bundle runs/xtest/B1 --variant $1 --rater $X/raters/$r.json --fields presence story topic --order-seed $2 --workers 6 --cap-usd 0.40 || echo "FAILED $r $cfg"
  done
done
