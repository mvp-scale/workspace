"""pipeline_check: the executable invariants of the knowledge pipeline. Run at the start of every session and before any bulk read:  python3 pipeline_check.py   (from kit/live). Exit 1 on any FAIL. Writes runs/checks/pipeline_check.json.
Checks: (1) decider replays Lean's vectors; (2) jev label rows have the label-store schema and valid values; (3) no leakage: training rows never include sealed ids or outside-gold (MN-DS) ids; (4) cards: done cards have their result file, failed cards are listed (path faults); (5) hosted spend sums against the cap; (6) canary: the latest full read is inside its expected bounds; (7) ledger replays; (8) health line."""
import json, glob, os, sys, subprocess, pathlib, time
ROOT = pathlib.Path(__file__).resolve().parents[2]; WS = ROOT / "projects/world-state"; os.chdir(WS); sys.path.insert(0, str(WS))
R = []
def rec(name, status, detail): R.append({"check": name, "status": status, "detail": detail}); print(f"{status:5s} {name}: {detail}")
try:
    import decider as D; n = D.check_against_lean(); rec("decider replays Lean vectors", "PASS", f"{n} vectors")
except Exception as e: rec("decider replays Lean vectors", "FAIL", repr(e)[:150])
O = json.load(open("/workspace/exports/world-engine-ontology-rules_v2.json")); topics = {t["id"] for t in O["topics"]}; dials = {c["id"] for c in O["conditions"]}
bad = []; total = 0; jev_ids = set()
for p in sorted(glob.glob("runs/label_store/labels_jev_*.jsonl")):
    for l in open(p):
        r = json.loads(l); total += 1; jev_ids.add(r["item_id"])
        if not all(k in r for k in ("item_id", "family", "model", "version", "topic", "story_type", "n_conditions", "kinds", "max_level", "provenance")): bad.append((p, "keys")); continue
        if r["family"] != "jev" or r["topic"] not in topics or r["story_type"] not in ("fact", "opinion", "forecast") or not set(r["kinds"]) <= dials or r["max_level"] not in (-1, 0, 1, 2, 3, 4): bad.append((p, r["item_id"][:8]))
        for c in r.get("conditions", []):
            o = c.get("evidence_offsets")
            if o and not (0 <= o[0] <= o[1]): bad.append((p, "offsets"))
rec("jev label rows: schema and values", "PASS" if not bad else "FAIL", f"{total} rows checked" if not bad else f"{len(bad)} bad, first {bad[:2]}")
sealed = {json.loads(l)["item_id"] for l in open("runs/pulse/sealed/labels.jsonl")}; gold = set()
for g in ("gold_T28.json", "gold_T28b.json", "gold_fresh.json", "gold_fresh2.json"): gold |= set(json.load(open("/workspace/data/anchors/mn_ds/" + g)))
mn_read = set()
for p in glob.glob("/workspace/data/newsreader/labels/mnds-gold*.jsonl"):
    for l in open(p): mn_read.add(json.loads(l)["id"])
leak = [i for i in jev_ids if i in sealed or i in gold or i in mn_read]
rec("no leakage: training rows vs sealed set and outside gold", "PASS" if not leak else "FAIL", f"{len(jev_ids)} jev training ids, {len(leak)} overlap" )
done_missing = []; failed = []
for st in ("done", "failed"):
    for p in glob.glob(f"../../kit/live/round_cards/{st}/*.json"):
        c = json.load(open(p)); rf = c.get("result", {}).get("file")
        if st == "done" and rf and not os.path.exists(rf): done_missing.append((c["id"], rf))
        if st == "failed": failed.append(c["id"])
rec("cards: done cards have their result file", "PASS" if not done_missing else "FAIL", f"{len(done_missing)} missing {done_missing[:2]}")
rec("cards: failed cards listed", "WARN" if failed else "PASS", f"{len(failed)} failed cards (path faults count here): {failed[:6]}")
spend = 0.0; parts = []
for p in sorted(set(glob.glob("runs/pulse/t1[2-9]*/*.json") + glob.glob("runs/pulse/t13*/*.json") + glob.glob("runs/pulse/t14*/*.json") + ["runs/pulse/t135_run2_merged.json"])):
    if not os.path.exists(p): continue
    try: d = json.load(open(p))
    except Exception: continue
    v = d.get("cost_usd_at_0_042_per_million") if isinstance(d, dict) else None
    if isinstance(v, (int, float)): spend += v; parts.append((p.split("/")[2], v))
rec("hosted spend by printed costs since T129", "PASS" if spend < 8 else "WARN", f"{spend:.2f} USD over {len(parts)} result files since T129 (D38 cap 8 USD for these reads; the 2.29 USD of T111 and T114 came before and is extra)")
E_ = json.load(open(ROOT / "kit/live/canary_expect.json")); d = json.load(open(E_["file"])); out = []
for k, (lo, hi) in E_["bounds"].items():
    v = d.get(k); 
    if v is None or not (lo <= v <= hi): out.append((k, v, [lo, hi]))
rec("canary: latest full read inside its bounds", "PASS" if not out else "FAIL", f"{E_['file']}" if not out else f"outside: {out}")
r = subprocess.run(["node", "cp.mjs", "check"], cwd=ROOT / ".ledger", capture_output=True, text=True); line = (r.stdout.strip().splitlines() or [""])[-1]
rec("ledger replays", "PASS" if r.returncode == 0 and "replays" in line else "FAIL", line[:120])
h = subprocess.run([sys.executable, str(ROOT / "kit/live/health.py")], capture_output=True, text=True).stdout.strip().splitlines(); rec("health line", "INFO", (h[-2] if len(h) > 1 else h[-1] if h else "")[:140])
pathlib.Path(ROOT / "runs/checks").mkdir(parents=True, exist_ok=True); json.dump({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "results": R}, open(ROOT / "runs/checks/pipeline_check.json", "w"), indent=1)
sys.exit(1 if any(x["status"] == "FAIL" for x in R) else 0)
