#!/bin/bash
# T155: five folds in order, hard stop at 55 minutes (one-hour cap)
cd /workspace/knowledge_pipeline/projects/world-state
for F in 0 1 2 3 4; do FOLD=$F EPOCHS=6 OUT=runs/pulse/t155/fold$F /workspace/models/embed-zs/.venv/bin/python -u t155_a08_folds.py > runs/pulse/t155/fold$F.log 2>&1; done
