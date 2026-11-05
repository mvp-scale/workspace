#!/bin/bash
# T32 round 2: presence under the v4b wording (bundle B8 = 600 B1 items + 952 MAVEN-FACT items). Clef first, then Gemma and Qwen through run_gq.sh.
cd /workspace/knowledge_pipeline/projects/world-state; X=/workspace/knowledge_pipeline/xtest
python3 $X/run.py --bundle runs/xtest/B8 --variant A --rater $X/raters/clef.json --fields presence --order-seed 0 --workers 8 --cap-usd 1 || echo "FAILED clef"
$X/run_gq.sh runs/xtest/B8 presence A 0
