"""Contract maintenance check (owner 2026-11-12: the knowledge pipeline contract must always be updated and maintained). Read only. Prints: whether the released contract is intact, how many amendments are pending for the next version, process decisions written after the last review that are NOT yet recorded as amendments, and whether GO.md is older than the last ledger write. Exit 0 when nothing needs attention, 2 otherwise.
Run: python3 kit/live/contract_check.py"""
import json, re, subprocess, pathlib, datetime as dt, sys
L = pathlib.Path("/workspace/knowledge_pipeline/.ledger"); out = []; bad = 0
v = subprocess.run(["node", "cp.mjs", "verify"], cwd=L, capture_output=True, text=True); line = (v.stdout or v.stderr).strip().splitlines()[-1] if (v.stdout or v.stderr).strip() else "no output"
out.append(f"contract: {line}"); bad += 0 if "intact" in line else 1
A = json.load(open(L / "contract/amendments.json")); pend = A["pending_for_v1_1"]
out.append(f"pending amendments for the next version: {len(pend)} ({', '.join(a['id'] for a in pend)}); reviewed through {A['reviewed_through']}")
led = [json.loads(x) for x in open(L / "ledger.jsonl")]; num = lambda i: int(i[1:])
rec = " ".join(a["decision"] + " " + a["change"] for a in pend)
KEY = re.compile(r"\b(rule|process|contract|enforce|closing rule|needs you|session start)\b", re.I)
new = [d for d in led if d["kind"] == "decision" and num(d["id"]) > num(A["reviewed_through"]) and KEY.search(d.get("text") or "") and (d.get("decision") or "") not in rec]
if new: out.append("UNRECORDED process decisions (add to amendments.json or say why not): " + ", ".join(f"{d.get('decision')}({d['id']})" for d in new)); bad += 1
last = dt.datetime.fromisoformat(led[-1]["ts"].replace("Z", "+00:00")); go = dt.datetime.fromtimestamp(pathlib.Path("/workspace/GO.md").stat().st_mtime, dt.timezone.utc); lag = (last - go).total_seconds() / 3600
out.append(f"GO.md is {'older' if lag > 0 else 'newer'} than the last ledger write by {abs(lag):.1f} h" + (" : REFRESH THE HANDOFF" if lag > 3 else "")); bad += 1 if lag > 3 else 0
print("\n".join(out)); sys.exit(2 if bad else 0)
