#!/bin/bash
# T33: the 'happened' question on 1552 items (bundle B10). Clef first, then Gemma and Qwen through run_gq.sh (restores voice and Clef on exit).
cd /workspace/knowledge_pipeline/projects/world-state; X=/workspace/knowledge_pipeline/xtest
python3 $X/run.py --bundle runs/xtest/B10 --variant A --rater $X/raters/clef.json --fields happened --order-seed 0 --workers 8 --cap-usd 1 || echo "FAILED clef"
$X/run_gq.sh runs/xtest/B10 happened A 0
