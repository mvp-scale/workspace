#!/bin/bash
# T41 round 1 on six REVISE traits: bundle B18 (800 natural items). Clef first, then Gemma and Qwen through run_gq.sh.
cd /workspace/knowledge_pipeline/projects/world-state; X=/workspace/knowledge_pipeline/xtest
F="t_x008r1 t_x001r1 t_x032r1 t_x022r1 t_x023r1 t_x010r1"
python3 $X/run.py --bundle runs/xtest/B18 --variant A --rater $X/raters/clef.json --fields $F --order-seed 0 --workers 8 --cap-usd 1 || echo "FAILED clef"
$X/run_gq.sh runs/xtest/B18 "$F" A 0
