#!/bin/bash
# usage: run_qwen.sh REPO DIRNAME OUTNAME  (smoke 8 items then full 400; each at most 30 min)
P=/workspace/models/clef-flash-nvfp4/.venv/bin/python; W=/workspace/knowledge_pipeline/projects/world-state
S=/tmp/claude-0/-workspace/2536dad8-e9e4-4b9d-8605-e63d48cb5ead/scratchpad
$P -I -c "
from huggingface_hub import snapshot_download
snapshot_download('$1',local_dir='/workspace/models/$2')" > $S/dl_$3.log 2>&1 || { echo DLFAIL; exit 1; }
VLLM_USE_FLASHINFER_SAMPLER=0 timeout 1800 $P -I $W/local_voter/qwen_voter.py 400 $1 /workspace/models/$2 $3 > $S/q_$3.log 2>&1
echo rc=$? >> $S/q_$3.log
