#!/bin/bash
# D40 chain: T137-R (1,000 engine stories, hosted Jev) then T142-M (MN-DS gold, call 1 only); each card has its own cap and ledger notes.
cd /workspace/knowledge_pipeline/kit/live
python3 run_round.py round_cards/held/T137-R.json > ../../runs/rounds/T137-R.out 2>&1
python3 run_round.py round_cards/held/T142-M.json > ../../runs/rounds/T142-M.out 2>&1
