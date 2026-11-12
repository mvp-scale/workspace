#!/bin/bash
# D40 proof of the run, CPU only: grade the fields on the new evidence, write jev label rows for 1,000 engine stories, retrain the sparse heads and score on outside truth.
cd /workspace/knowledge_pipeline/projects/world-state
P=/workspace/models/embed-zs/.venv/bin/python
ROWS=/workspace/data/newsreader/labels/full-read-100.jsonl TAG=t135 OUT=runs/pulse/t139 $P jev_wire.py > /tmp/claude-0/-workspace/d4b0cb1c-0a5d-4e2c-8056-bf2674982a64/scratchpad/prove1.out 2>&1
ROWS=/workspace/data/newsreader/labels/calibration-1000.jsonl TAG=t137 OUT=runs/pulse/t139b $P jev_wire.py > /tmp/claude-0/-workspace/d4b0cb1c-0a5d-4e2c-8056-bf2674982a64/scratchpad/prove2.out 2>&1
JEV=runs/label_store/labels_jev_t137.jsonl,runs/label_store/labels_jev_t135.jsonl $P -u t143_jev_retrain.py > /tmp/claude-0/-workspace/d4b0cb1c-0a5d-4e2c-8056-bf2674982a64/scratchpad/prove3.out 2>&1
echo done > /tmp/claude-0/-workspace/d4b0cb1c-0a5d-4e2c-8056-bf2674982a64/scratchpad/prove.done
