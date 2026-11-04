#!/bin/bash
# waits for the encoder embedding job to finish, then runs the head matrix (t6k); registered jobs report themselves on the page
cd /workspace/knowledge_pipeline/projects/world-state
while ps -eo args | awk '/ceiling_embed.py/ && !/awk/ && !/bash/' | grep -q .; do sleep 10; done
HF_HOME=/workspace/data/hf /workspace/models/embed-zs/.venv/bin/python -u ceiling_heads.py > runs/pulse/ceiling/heads_t6k.log 2>&1
