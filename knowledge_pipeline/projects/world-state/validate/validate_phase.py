"""validate_phase (T150): one command for the phase gate. Lists each acceptance criterion of a phase as written in the ledger (the latest task line of its T-id), runs the harness module that tests it if it can run now, and prints PASS, FAIL or NOT RUN (with the reason) per criterion plus the evidence file. It never writes to the ledger; the owner's session records the result. Exit 0 only if every criterion is PASS.
Phases: P0 = T149, P1 = T150, P2 = T151, P3 = T152 (P4 to P6 have no harness yet and are refused).
How a criterion is judged (a phase's code must exist before a before/after test can mean anything, so a check that would pass on unchanged code is NOT RUN, not PASS):
  P0 criterion: needs ledger lines on T149 of kind measure, or notes that start with SCORE or RESULT (not PREDICTION, DEPENDS or launch notes), that mention the whole-article vs 300-character result, the router re-score and ms per element: PASS only if all three are found (their ids are the evidence).
  P1 c1 (replay identical, spans resolve): needs runs/pulse/validate/frozen_230.jsonl (freeze_replay.py freeze, before P1 code) and P1 code (check_literal in facts_lib.py); then freeze_replay.py diff (2-3 min CPU) must show 0 changes and the frozen facts must all resolve (text[s:e] equals the stored text).
  P1 c2 (injected spans held back, none read later): needs P1 code; then inject_spans.py --checker facts_lib:check_literal must flag 100% of >= 200 mutants with 0 false alarms. The clause 'none is read by a later layer' has no test yet, so even then the status stays NOT RUN with the first clause reported.
  P2 c1 (bundles carry exact span and factuality tag, Condition coverage reported): needs P2 code ('bundles' in analyze2.py) and runs/pulse/validate/p2_bundles.jsonl (230 rows of {id, text, bundles}); then p2_bundle_check.py.
  P3 c1 (precision >= 0.90 on stories not trained on, every answer cites a bundle): needs P3 code, runs/pulse/validate/p3_scores.jsonl and p3_scores.meta.json {"label_kind", "label_source", "held_out_excludes_training": true}; then p3_threshold_check.py --require-cites; the domain field must pass. The label source is shown in the evidence line (agreement is not accuracy). Truth sets for P3 are owner-gated.
    /workspace/models/embed-zs/.venv/bin/python validate/validate_phase.py P0|P1|P2|P3 [--no-run]   (from projects/world-state; --no-run lists criteria and prerequisites without running anything)  -> runs/pulse/validate/validate_<phase>.json"""
import os, sys, json, re, subprocess, pathlib, argparse
WS = pathlib.Path(__file__).resolve().parents[1]; os.chdir(WS); OUTD = pathlib.Path("runs/pulse/validate"); LEDGER = WS.parents[1] / ".ledger/ledger.jsonl"; PY = sys.executable
PH = {"P0": "T149", "P1": "T150", "P2": "T151", "P3": "T152"}
def criteria(task):
    last = None
    for l in open(LEDGER, encoding="utf-8"):
        try: r = json.loads(l)
        except Exception: continue
        if r.get("kind") == "task" and r.get("task") == task and r.get("acceptance"): last = r
    return last["acceptance"] if last else []
def has(path, s): return s in open(path, encoding="utf-8").read()
def sh(cmd, timeout=1800):
    p = subprocess.run([PY] + cmd, capture_output=True, text=True, timeout=timeout, env={**os.environ, "CUDA_VISIBLE_DEVICES": ""}); return p.returncode, (p.stdout + p.stderr).strip().splitlines()[-3:]
def p0(i, txt):
    need = {"whole-article vs first 300 characters": re.compile(r"300|first 300|whole.article", re.I), "router re-score under tolerance": re.compile(r"router|tolerance", re.I), "ms per element": re.compile(r"ms per|per element|time per", re.I)}; found = {}
    for l in open(LEDGER, encoding="utf-8"):
        try: r = json.loads(l)
        except Exception: continue
        t = r.get("text") or ""
        if r.get("task") == "T149" and (r.get("kind") == "measure" or re.match(r"\s*(SCORE|RESULT|MEASURED)\b", t, re.I)):   # a scored result, not a prediction, plan or dependency note
            for k, rx in need.items():
                if rx.search(t) and k not in found: found[k] = r.get("id")
    miss = [k for k in need if k not in found]
    return ("PASS", "found: " + json.dumps(found), str(LEDGER)) if not miss else ("NOT RUN", "not yet written to the ledger: " + ", ".join(miss) + " (needs the P0 runs scored)", str(LEDGER))
def p1c1():
    fz = OUTD / "frozen_230.jsonl"
    if not fz.exists(): return "NOT RUN", "no baseline: run freeze_replay.py freeze on unchanged code first", str(fz)
    if not has("facts_lib.py", "check_literal"): return "NOT RUN", "needs P1 code (check_literal absent in facts_lib.py)", str(fz)
    rows = [json.loads(l) for l in open(fz)][1:]; bad = sum(1 for r in rows for f in r["data"]["facts"] if f[1] >= f[2] or f[3] != re.sub(r"\s+", " ", r["title"].strip() + ". " + r["body"])[:12000][f[1]:f[2]]); n = sum(len(r["data"]["facts"]) for r in rows)
    rc, out = sh(["validate/freeze_replay.py", "diff"])
    ok = rc == 0 and bad == 0; return ("PASS" if ok else "FAIL"), "diff exit %d (%s); frozen facts that do not resolve to their text: %d of %d" % (rc, out[-1][:160] if out else "", bad, n), str(OUTD / "replay_diff.json")
def p1c2():
    if not has("facts_lib.py", "check_literal"): return "NOT RUN", "needs P1 code (check_literal absent in facts_lib.py); first clause would run inject_spans.py --checker facts_lib:check_literal; second clause ('none is read by a later layer') has no test yet", str(OUTD / "inject_spans.json")
    rc, out = sh(["validate/inject_spans.py", "--stories", "20", "--checker", "facts_lib:check_literal"]); return "NOT RUN", "first clause %s (%s); second clause ('none is read by a later layer') has no test yet, so the criterion cannot be PASS" % ("PASS" if rc == 0 else "FAIL", out[0][:160] if out else ""), str(OUTD / "inject_spans.json")
def p2c1():
    f = OUTD / "p2_bundles.jsonl"
    if not has("analyze2.py", "bundles"): return "NOT RUN", "needs P2 code (no 'bundles' in analyze2.py)", str(f)
    if not f.exists(): return "NOT RUN", "needs the bundles file (230 rows of {id, text, bundles}) written by the P2 replay", str(f)
    rc, out = sh(["validate/p2_bundle_check.py", "--bundles", str(f)]); n = sum(1 for _ in open(f)); ok = rc == 0 and n >= 230
    return ("PASS" if ok else "FAIL"), (out[-1][:200] if out else "") + ("" if n >= 230 else " | only %d of 230 stories in the file" % n) + " | Condition coverage vs 12 of 230 is reported by P2, not by this module", str(OUTD / "p2_bundle_check.json")
def p3c1():
    f = OUTD / "p3_scores.jsonl"; m = OUTD / "p3_scores.meta.json"
    if not (has("analyze2.py", "bundles") and has("analyze2.py", "basis")): return "NOT RUN", "needs P3 code (no 'bundles' and 'basis' in analyze2.py)", str(f)
    if not f.exists() or not m.exists(): return "NOT RUN", "needs p3_scores.jsonl and p3_scores.meta.json; truth sets (MN-DS, CheckThat) are owner-gated", str(f)
    meta = json.load(open(m))
    if not meta.get("held_out_excludes_training") or meta.get("label_kind") not in ("agreement", "outside"): return "NOT RUN", "meta must state label_kind and held_out_excludes_training true", str(m)
    cmd = ["validate/p3_threshold_check.py", "--scores", str(f), "--label-kind", meta["label_kind"], "--require-cites"] + (["--label-source", meta["label_source"]] if meta.get("label_source") else []); rc, out = sh(cmd); r = json.load(open(OUTD / "p3_threshold_check.json")); d = r["fields"].get("domain")
    if d is None: return "FAIL", "no 'domain' field in the scores file", str(OUTD / "p3_threshold_check.json")
    return ("PASS" if d["pass"] else "FAIL"), "domain [%s]: chosen thr %s, confirm precision %s, answered %s%s" % (r["label"], d["chosen_thr"], (d.get("confirm") or {}).get("precision"), (d.get("confirm") or {}).get("answered"), "" if d["pass"] else " | " + str(d["why"])), str(OUTD / "p3_threshold_check.json")
CHECK = {"P1": [p1c1, p1c2], "P2": [p2c1], "P3": [p3c1]}
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("phase", choices=sorted(PH)); ap.add_argument("--no-run", action="store_true"); a = ap.parse_args(); task = PH[a.phase]; crit = criteria(task); res = []
    print("%s (ledger %s): %d acceptance criteria" % (a.phase, task, len(crit)))
    for i, c in enumerate(crit):
        fn = (lambda: p0(i, c)) if a.phase == "P0" else (CHECK[a.phase][i] if i < len(CHECK[a.phase]) else None)
        if fn is None: st, why, ev = "NOT RUN", "no harness check for this criterion", None
        elif a.no_run: st, why, ev = "NOT RUN", "--no-run: listed only", None
        else:
            try: st, why, ev = fn()
            except Exception as ex: st, why, ev = "FAIL", "harness error: " + repr(ex)[:200], None
        res.append({"n": i + 1, "criterion": c, "status": st, "reason": why, "evidence": ev}); print("[%d] %-7s %s\n      %s\n      evidence: %s" % (i + 1, st, c, why, ev))
    allpass = bool(res) and all(r["status"] == "PASS" for r in res); OUTD.mkdir(parents=True, exist_ok=True); json.dump({"phase": a.phase, "task": task, "criteria": res, "all_pass": allpass, "note": "not written to the ledger; the owner's session records results"}, open(OUTD / ("validate_%s.json" % a.phase), "w"), indent=1)
    print("%s: %d PASS, %d FAIL, %d NOT RUN -> %s" % (a.phase, *(sum(r["status"] == s for r in res) for s in ("PASS", "FAIL", "NOT RUN")), "ALL PASS" if allpass else "NOT PASSED")); sys.exit(0 if allpass else 1)
