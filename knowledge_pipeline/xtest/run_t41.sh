#!/bin/bash
# T41 round 1: the two revised trait wordings on the same 800 natural items (bundle B16). Clef first, then Gemma and Qwen through run_gq.sh.
cd /workspace/knowledge_pipeline/projects/world-state; X=/workspace/knowledge_pipeline/xtest
F="t_x013v1 t_x031v1"
python3 $X/run.py --bundle runs/xtest/B16 --variant A --rater $X/raters/clef.json --fields $F --order-seed 0 --workers 8 --cap-usd 1 || echo "FAILED clef"
$X/run_gq.sh runs/xtest/B16 "$F" A 0
