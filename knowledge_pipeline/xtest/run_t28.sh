#!/bin/bash
# T28: topic ratings on the MN-DS sample (bundle B6). Clef first (up now), then Gemma and Qwen through run_gq.sh (which restores voice and Clef on exit).
cd /workspace/knowledge_pipeline/projects/world-state; X=/workspace/knowledge_pipeline/xtest
python3 $X/run.py --bundle runs/xtest/B6 --variant A --rater $X/raters/clef.json --fields topic --order-seed 0 --workers 8 --cap-usd 1 || echo "FAILED clef"
$X/run_gq.sh runs/xtest/B6 topic A 0
