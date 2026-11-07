#!/bin/bash
# T41 round 2 on four traits: bundle B21 (800 natural items). Clef first, then Gemma and Qwen through run_gq.sh.
cd /workspace/knowledge_pipeline/projects/world-state; X=/workspace/knowledge_pipeline/xtest
F="t_x019r1 t_x012r1 t_x020r1 t_x024r1 t_x026r1 t_x027r1 t_x030r1 t_x028r1"
python3 $X/run.py --bundle runs/xtest/B21 --variant A --rater $X/raters/clef.json --fields $F --order-seed 0 --workers 8 --cap-usd 1 || echo "FAILED clef"
$X/run_gq.sh runs/xtest/B21 "$F" A 0
