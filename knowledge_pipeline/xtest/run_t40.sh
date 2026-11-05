#!/bin/bash
# T40 step 2 controller: Qwen quotes, build B15, Clef verifies, Gemma and Qwen verify. Each stage restores voice and Clef on exit.
cd /workspace/knowledge_pipeline/projects/world-state; X=/workspace/knowledge_pipeline/xtest; mkdir -p runs/xtest/B15
F="t_x025 t_x013 t_x031 t_x034"
$X/run_quote.sh || { echo "QUOTE STAGE FAILED"; exit 1; }
[ -s runs/xtest/B15_quotes.json ] || { echo "NO QUOTES FILE"; exit 1; }
/workspace/kev/.venv/bin/python -I $X/bundle_span.py || { echo "BUNDLE FAILED"; exit 1; }
sleep 20; curl -s localhost:8018/health >/dev/null || { echo "CLEF NOT BACK"; exit 1; }
python3 $X/run.py --bundle runs/xtest/B15 --variant A --rater $X/raters/clef.json --fields $F --order-seed 0 --workers 8 --cap-usd 1 || echo "FAILED clef"
$X/run_gq.sh runs/xtest/B15 "$F" A 0
