#!/bin/bash
cd /workspace/knowledge_pipeline/projects/world-state
run() { FT_TAG=$1 FT_EPOCHS=$2 FT_LR=$3 FT_ALPHA=1.0 HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python -u finetune_distill.py B --tranche > runs/pulse/ceiling/finetune$1.log 2>&1; }
run _t16e16lr5 16 5e-5
run _t16e24lr5 24 5e-5
