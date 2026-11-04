#!/bin/bash
cd /workspace/knowledge_pipeline/projects/world-state
run() { FT_TAG=$1 FT_EPOCHS=$2 FT_LR=$3 FT_ALPHA=$4 HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python -u finetune_distill.py B > runs/pulse/ceiling/finetune$1.log 2>&1; }
run _e6 6 2e-5 1.0
run _lr5 3 5e-5 1.0
run _e6lr5 6 5e-5 1.0
run _a3 3 2e-5 3.0
