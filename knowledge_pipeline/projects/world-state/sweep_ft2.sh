#!/bin/bash
cd /workspace/knowledge_pipeline/projects/world-state
while ps -eo args | awk '/sweep_ft.sh|finetune_distill.py/ && !/awk/ && !/bash -c/' | grep -q .; do sleep 5; done
run() { FT_TAG=$1 FT_EPOCHS=$2 FT_LR=$3 FT_ALPHA=$4 HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python -u finetune_distill.py B > runs/pulse/ceiling/finetune$1.log 2>&1; }
run _e12lr5 12 5e-5 1.0
run _e8lr10 8 1e-4 1.0
run _e6lr5a3 6 5e-5 3.0
run _e16lr5 16 5e-5 1.0
