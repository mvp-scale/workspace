#!/bin/bash
# T41 hunt for five sparse traits: bundle B22 (600 tasks). Clef first, then Gemma and Qwen through run_gq.sh.
cd /workspace/knowledge_pipeline/projects/world-state; X=/workspace/knowledge_pipeline/xtest
F="t_x024r1 t_x026r1 t_x027r1 t_x028r1 t_x030r1"
python3 $X/run.py --bundle runs/xtest/B22 --variant A --rater $X/raters/clef.json --fields $F --order-seed 0 --workers 8 --cap-usd 1 || echo "FAILED clef"
$X/run_gq.sh runs/xtest/B22 "$F" A 0
