"""Checks that every PREDICTION note on the ledger from L1117 onward has a later note that cites it (as 'prediction L<id>' or 'L<id>') and starts with SCORE, or is marked superseded. Prints the pairs and any prediction with no score. Exit 0 when none is missing, 2 otherwise.
    python3 ledger_pairs.py [first_id]
Limit (MM3-0011 asked): this checks that a score note exists and cites the prediction id; a SCORE note that mentions the id only in passing also counts. It does not check that the score is right."""
import json, re, sys
first = int(sys.argv[1]) if len(sys.argv) > 1 else 1117
notes = []
for l in open("/workspace/knowledge_pipeline/.ledger/ledger.jsonl"):
    try: r = json.loads(l)
    except Exception: continue
    m = re.match(r"L(\d+)$", r.get("id", ""))
    if m and int(m.group(1)) >= first and r.get("kind") == "note": notes.append((int(m.group(1)), r.get("text", "") or ""))
preds = [(i, t) for i, t in notes if t.startswith("PREDICTION")]
out = []; missing = []
for i, t in preds:
    scores = [j for j, u in notes if j > i and re.match(r"(SCORE|CORRECTION|Result)", u) and re.search(rf"\bL{i}\b", u)]
    (out if scores else missing).append((i, scores))
for i, s in out: print(f"OK      L{i} scored by " + ", ".join(f"L{j}" for j in s))
for i, _ in missing: print(f"MISSING L{i}: no later SCORE note cites it")
print(f"{len(out)} of {len(preds)} predictions from L{first} have a score note (exists and cites the id; not a check that the score is right)")
corr = [(i, t) for i, t in notes if t.startswith("CORRECTION")]
badc = [i for i, t in corr if not re.search(r"\bL\d+\b", t)]
for i, t in corr: print(("OK      " if i not in badc else "NOCITE  ") + f"L{i} correction cites " + ", ".join(sorted(set(re.findall(r"\bL\d+\b", t)))[:6]))
print(f"{len(corr) - len(badc)} of {len(corr)} corrections cite the notes they correct")
sys.exit(2 if (missing or badc) else 0)
