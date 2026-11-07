#!/bin/bash
# T41 check 5 on x008r1 and x032r1 (B18 positives, bundle B19).
cd /workspace/knowledge_pipeline/projects/world-state; X=/workspace/knowledge_pipeline/xtest
export SPAN_BUNDLE=runs/xtest/B18 SPAN_TRAITS="t_x008r1 t_x032r1" SPAN_QFILE=specs/traits_r1_candidates.json SPAN_OUT=runs/xtest/B19_quotes.json SPAN_BUNDLE_ID=B19 SPAN_LOGDIR=runs/xtest/B19
F="t_x008r1 t_x032r1"; mkdir -p runs/xtest/B19
$X/run_quote.sh || { echo "QUOTE STAGE FAILED"; exit 1; }
[ -s runs/xtest/B19_quotes.json ] || { echo "NO QUOTES FILE"; exit 1; }
/workspace/kev/.venv/bin/python -I $X/bundle_span.py || { echo "BUNDLE FAILED"; exit 1; }
sleep 20; curl -s localhost:8018/health >/dev/null || { echo "CLEF NOT BACK"; exit 1; }
python3 $X/run.py --bundle runs/xtest/B19 --variant A --rater $X/raters/clef.json --fields $F --order-seed 0 --workers 8 --cap-usd 1 || echo "FAILED clef"
$X/run_gq.sh runs/xtest/B19 "$F" A 0
