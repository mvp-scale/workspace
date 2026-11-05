#!/bin/bash
# T32 round 1: presence under the v4a wording (bundle B7). Clef first (up now), then Gemma and Qwen through run_gq.sh (restores voice and Clef on exit).
cd /workspace/knowledge_pipeline/projects/world-state; X=/workspace/knowledge_pipeline/xtest
python3 $X/run.py --bundle runs/xtest/B7 --variant A --rater $X/raters/clef.json --fields presence --order-seed 0 --workers 8 --cap-usd 1 || echo "FAILED clef"
$X/run_gq.sh runs/xtest/B7 presence A 0
