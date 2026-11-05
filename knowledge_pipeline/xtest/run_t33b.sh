#!/bin/bash
# T33 round 2: eventhappened on 1818 marked MAVEN-FACT events (bundle B11). Clef first, then Gemma and Qwen through run_gq.sh.
cd /workspace/knowledge_pipeline/projects/world-state; X=/workspace/knowledge_pipeline/xtest
python3 $X/run.py --bundle runs/xtest/B11 --variant A --rater $X/raters/clef.json --fields eventhappened --order-seed 0 --workers 8 --cap-usd 1 || echo "FAILED clef"
$X/run_gq.sh runs/xtest/B11 eventhappened A 0
