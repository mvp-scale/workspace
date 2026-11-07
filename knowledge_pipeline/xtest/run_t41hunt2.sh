#!/bin/bash
# T41 hunt for x019r2 and x020r2: bundle B25 (240 tasks). Clef first, then Gemma and Qwen through run_gq.sh.
cd /workspace/knowledge_pipeline/projects/world-state; X=/workspace/knowledge_pipeline/xtest
F="t_x019r2 t_x020r2"
python3 $X/run.py --bundle runs/xtest/B25 --variant A --rater $X/raters/clef.json --fields $F --order-seed 0 --workers 8 --cap-usd 1 || echo "FAILED clef"
$X/run_gq.sh runs/xtest/B25 "$F" A 0
