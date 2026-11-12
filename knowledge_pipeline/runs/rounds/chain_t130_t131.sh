#!/bin/bash
# D35 chain: T130-J (Jev reads the 1,736 stored engine stories) then T131-J (3,000 new queue stories); hosted Jev, no GPU; each card has its own cap.
cd /workspace/knowledge_pipeline/kit/live
python3 run_round.py round_cards/held/T130-J.json > ../../runs/rounds/T130-J.out 2>&1
python3 run_round.py round_cards/held/T131-J.json > ../../runs/rounds/T131-J.out 2>&1
