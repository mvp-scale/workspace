#!/bin/bash
# T41 round 2 on four traits: bundle B20 (800 natural items). Clef first, then Gemma and Qwen through run_gq.sh.
cd /workspace/knowledge_pipeline/projects/world-state; X=/workspace/knowledge_pipeline/xtest
F="t_x022r2 t_x010r2 t_x023r2 t_x001r2"
python3 $X/run.py --bundle runs/xtest/B20 --variant A --rater $X/raters/clef.json --fields $F --order-seed 0 --workers 8 --cap-usd 1 || echo "FAILED clef"
$X/run_gq.sh runs/xtest/B20 "$F" A 0
