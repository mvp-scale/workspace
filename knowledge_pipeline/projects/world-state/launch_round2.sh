#!/bin/bash
cd /workspace/knowledge_pipeline/projects/world-state
for f in story_type topic; do
  HF_HOME=/workspace/data/hf nohup /workspace/models/embed-zs/.venv/bin/python -u round2_story_topic.py $f > runs/pulse/round2_$f.log 2>&1 &
done
