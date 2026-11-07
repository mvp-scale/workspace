#!/bin/bash
# rebuild the gates mock-up data for the articles in runs/pulse/mockup_articles.json (owner 2026-11-05: three discrete articles)
cd /workspace/knowledge_pipeline/projects/world-state; PY=/workspace/models/embed-zs/.venv/bin/python; HB=/workspace/knowledge_pipeline/kit/live/hb_cli.py; FAIL=0
for s in gates_mockup_data gates_v2 g3_spec agreement wide_net; do
  echo "== $s $(date +%T)" >> runs/pulse/chain.log; $PY $s.py >> runs/pulse/chain_$s.log 2>&1 || { FAIL=1; echo "FAILED $s" >> runs/pulse/chain.log; break; }
done
if [ $FAIL = 0 ]; then python3 $HB finish chain_rebuild done --last "all five stages" ; echo "DONE $(date +%T)" >> runs/pulse/chain.log; else python3 $HB finish chain_rebuild failed --last "see runs/pulse/chain.log"; fi
