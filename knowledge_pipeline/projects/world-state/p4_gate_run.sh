#!/bin/bash
cd /workspace/knowledge_pipeline/projects/world-state
../.venv/bin/python /workspace/knowledge_pipeline/kit/teacher/claude_batch.py --spec specs/world_state_gate_v1.json --items data/pool_train.jsonl --out runs/p4/gate_pool --key-file /workspace/secrets/vault.env --cap-usd 3 > runs/p4/gate_pool.log 2>&1
python3 - <<'PY'
import json, sys
sys.path.insert(0,"/workspace/knowledge_pipeline/kit/live")
from heartbeat import finish
rows=[json.loads(l) for l in open("runs/p4/gate_pool/labels.jsonl")]; pool=sum(1 for _ in open("data/pool_train.jsonl"))
sp=sum(json.loads(l).get("usd",0) for l in open("runs/p4/gate_pool/spend.jsonl"))
if len(rows) < 0.9*pool: finish("p4-gate-pool","failed",last=f"only {len(rows)} of {pool} labelled",spent=round(sp,2)); sys.exit(1)
flag=[r["item_id"] for r in rows if r["label"]["change"]]; open("runs/p4/gate_flagged_ids.txt","w").write("\n".join(flag))
print(f"labelled {len(rows)} of {pool}; flagged {len(flag)} ({len(flag)/len(rows):.1%}); spend ${sp:.2f}")
finish("p4-gate-pool","done",last=f"flagged {len(flag)} of {len(rows)} ({len(flag)/len(rows):.0%})",spent=round(sp,2))
PY
