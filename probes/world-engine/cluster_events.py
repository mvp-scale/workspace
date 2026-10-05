"""Group evidence into events: items about the same thing count once. Uses the small static embedding model (potion-base-8M) from models/embed-venv. Run with that venv's python."""
import json
import numpy as np
from model2vec import StaticModel
L = "/workspace/probes/world-engine/ledger"
ev = [json.loads(l) for l in open(f"{L}/evidence.jsonl")]
m = StaticModel.from_pretrained("minishlab/potion-base-8M"); X = m.encode([e["title"] + ". " + e["description"] for e in ev]); X /= np.linalg.norm(X, axis=1, keepdims=True)
S = X @ X.T; THRESH = 0.72                                   # fixed in advance; a draft value
parent = list(range(len(ev)))
def find(i):
    while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
    return i
for i in range(len(ev)):
    for j in range(i + 1, len(ev)):
        if S[i, j] >= THRESH: parent[find(j)] = find(i)
groups = {}
for i in range(len(ev)): groups.setdefault(find(i), []).append(i)
out = {}
for gi, (root, members) in enumerate(groups.items()):
    for i in members: out[ev[i]["evidence_id"]] = f"ev{gi:03d}"
json.dump(out, open(f"{L}/clusters.json", "w"))
print(len(ev), "items ->", len(groups), "events; groups with more than one item:")
for root, members in groups.items():
    if len(members) > 1: print("  ", [ev[i]["title"][:55] for i in members], [round(float(S[members[0], k]), 2) for k in members[1:]])
print("closest pairs just under the threshold:", sorted([(round(float(S[i, j]), 2), ev[i]["title"][:30], ev[j]["title"][:30]) for i in range(len(ev)) for j in range(i + 1, len(ev)) if 0.55 <= S[i, j] < THRESH], reverse=True)[:5])
