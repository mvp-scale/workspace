#!/bin/bash
# D33 chain: T126-E2 (engine chunk 2, local GPU, cap 50 min) after T126-E1, then T127-L (CPU curve). Each card is its own run_round.py with its own cap and ledger notes.
cd /workspace/knowledge_pipeline/kit/live
while pgrep -f "run_round.py round_cards/held/T126-E1.json" >/dev/null; do sleep 20; done
python3 run_round.py round_cards/held/T126-E2.json > ../../runs/rounds/T126-E2.out 2>&1
python3 run_round.py round_cards/held/T127-L.json > ../../runs/rounds/T127-L.out 2>&1
