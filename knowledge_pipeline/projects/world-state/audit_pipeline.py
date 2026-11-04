"""Pipeline audit, deterministic part. Does not use the viewer's own code for the independent counts. Run: python3 audit_pipeline.py"""
import sys, json, re, os, glob, time, subprocess, urllib.request, pathlib, calendar
K = pathlib.Path(__file__).resolve().parents[2]; W = K / "projects/world-state"; L = K / ".ledger"; out = {"checks": {}, "defects": []}
lines = [json.loads(l) for l in open(L / "ledger.jsonl", encoding="utf-8") if l.strip()]
# 1 chain
r = subprocess.run(["node", "cp.mjs", "verify"], cwd=L, capture_output=True, text=True); out["checks"]["ledger_chain_verify"] = (r.stdout + r.stderr).strip().splitlines()[-1][:160]
if "refused" in (r.stdout + r.stderr).lower() or r.returncode: out["defects"].append("ledger verify did not pass: " + out["checks"]["ledger_chain_verify"])
# 2 result files named in notes exist
paths = set()
for x in lines:
    for m in re.findall(r"(?:file:)?((?:projects/world-state/)?runs/[A-Za-z0-9_./-]+\.(?:jsonl|json|pkl|npy)(?![A-Za-z]))", x.get("text", "") + " " + " ".join(map(str, x.get("evidence", []) if isinstance(x.get("evidence"), list) else [x.get("evidence", "")]))): paths.add(m)
KNOWN_ERRATA = {"runs/bakeoff/yield.json", "runs/p7b/yield.json"}   # wrong paths in old notes; erratum is ledger L274 (the chain cannot be edited)
miss = sorted(p for p in paths if p not in KNOWN_ERRATA and not ((K / p).exists() or (W / p.replace("projects/world-state/", "")).exists()))
out["checks"]["files_named_in_notes"] = {"named": len(paths), "missing": len(miss)}; out["missing_files"] = miss[:20]
if miss: out["defects"].append(f"{len(miss)} file(s) named in ledger notes do not exist, e.g. {miss[:3]}")
# 3 result files without a job-history record
hist = [json.loads(l) for l in open(K / "runs-history.jsonl") if l.strip()]; ts = lambda s: calendar.timegm(time.strptime(s.split(".")[0].rstrip("Z"), "%Y-%m-%dT%H:%M:%S"))
def safe_ts(x):
    try: return ts(x)
    except Exception: return None   # a record with a missing or odd time is skipped, never fatal
ended = [t for t in (safe_ts(h.get("ended")) for h in hist) if t is not None]; unreg = []
for f in glob.glob(str(W / "runs/snapshots/*.json")) + glob.glob(str(W / "runs/expert1/*report*.json")) + glob.glob(str(W / "runs/structure/t*.json")):
    m = os.path.getmtime(f)
    if time.time() - m < 900: continue
    if not any(abs(m - e) < 900 for e in ended): unreg.append(os.path.relpath(f, W))
out["checks"]["result_files_without_job_record"] = {"count": len(unreg), "examples": unreg[:12]}
if unreg: out["defects"].append(f"{len(unreg)} result file(s) have no job-history record within 15 min, e.g. {unreg[:4]}")
# 4 stale live files
stale = []
for f in glob.glob(str(K / "runs-live/*.json")):
    try: d = json.load(open(f))
    except Exception: stale.append(os.path.basename(f) + " (unreadable)"); continue
    u = safe_ts(d.get("updated"))
    if d.get("state") == "running" and d.get("job") != "poller" and (u is None or time.time() - u > 600): stale.append(d.get("job", os.path.basename(f)))
out["checks"]["stale_live_jobs"] = stale
if stale: out["defects"].append(f"stale running job file(s): {stale}")
# 5 gate counts: independent from raw lines vs the viewer
last = {}
for x in lines:
    for m in x.get("measures", []) or []: last[m["gate"]] = m
ind = {"passing": sum(1 for m in last.values() if m.get("pass")), "failing": sum(1 for m in last.values() if not m.get("pass")), "measured": len(last)}
c = [m for m in last.values() if m.get("n_in")]; roll = 1.0
for m in c: roll *= m["n_pass"] / m["n_in"]
ind["counted"] = len(c); ind["rolled"] = round(roll, 3)
try:
    d = json.load(urllib.request.urlopen("http://127.0.0.1:18766/data", timeout=10)); g = d["gates"]; vc = [x for x in g if x["last"] and x["last"].get("n_in")]; vr = 1.0
    for x in vc: vr *= x["last"]["n_pass"] / x["last"]["n_in"]
    view = {"passing": sum(1 for x in g if x["last"] and x["last"]["pass"]), "failing": sum(1 for x in g if x["last"] and not x["last"]["pass"]), "measured": sum(1 for x in g if x["last"]), "counted": len(vc), "rolled": round(vr, 3)}
except Exception as e: view = {"error": str(e)[:100]}
out["checks"]["gate_counts_independent_vs_page"] = {"independent": ind, "page": view, "match": ind == view}
if ind != view: out["defects"].append(f"page gate counts differ from the raw ledger lines: {ind} vs {view}")
# 6 gates_auto in step
r = subprocess.run(["/workspace/models/embed-zs/.venv/bin/python", "gates_auto.py"], cwd=W, capture_output=True, text=True); out["checks"]["gates_auto"] = r.stdout.strip()[:120]
if "recorded" in r.stdout: out["defects"].append("gates_auto found drift: the page was behind the data (now recorded): " + r.stdout.strip())
# 6b runtime tests (serving contract, embedding equivalence, no torch)
r = subprocess.run(["/workspace/models/embed-zs/.venv/bin/python", "test_runtime.py"], cwd=W, capture_output=True, text=True); out["checks"]["runtime_tests"] = (r.stdout.strip().splitlines() or ["no output"])[-1][:100]
if r.returncode: out["defects"].append("runtime tests failed: " + out["checks"]["runtime_tests"])
# 7 every gate with a value: its sample vs current data is shown? (page has no measured-at): count gates measured more than 24h before the newest data
out["checks"]["gates_never_measured"] = sum(1 for x in (g if isinstance(view, dict) and "error" not in view else []) if not x["last"])
json.dump(out, open(W / "runs/audit_report.json", "w"), indent=1); print(json.dumps(out, indent=1))
sys.exit(1 if out["defects"] else 0)   # fail loudly so a scheduler or a driver can see it
