#!/usr/bin/env python3
"""Pre-registered check for Clef Flash Fast (CLF9F4, id clef-flash-nvfp4) vs clef-flash-q4km, with full clef-flash for reference (ledger bar sheet on D-0038).
Bars: MMLU overall accuracy (pooled over all 57 sets) within 1.5 points of Q4; each of the 4 MMLU category groups (pooled; standard MMLU categories) within 3 points; each of the non-MMLU sets within 3 points.
Also reports the answer agreement rate with Q4 (same task id, same predicted option/choice) overall, per group and per set.
  python3 newsreader/bitmob/eval_clef_nvfp4.py [OUT.json]   (reads data/probe-runs-v2/<model>-<set>/results.jsonl; writes a table to stdout)"""
import json, os, sys, glob
R = "/workspace/data/probe-runs-v2"; NEW, Q4, FULL = "clef-flash-nvfp4", "clef-flash-q4km", "clef-flash"
G = {"STEM": "abstract_algebra anatomy astronomy college_biology college_chemistry college_computer_science college_mathematics college_physics computer_security conceptual_physics electrical_engineering elementary_mathematics high_school_biology high_school_chemistry high_school_computer_science high_school_mathematics high_school_physics high_school_statistics machine_learning",
     "Humanities": "formal_logic high_school_european_history high_school_us_history high_school_world_history international_law jurisprudence logical_fallacies moral_disputes moral_scenarios philosophy prehistory professional_law world_religions",
     "Social sciences": "econometrics high_school_geography high_school_government_and_politics high_school_macroeconomics high_school_microeconomics high_school_psychology human_sexuality professional_psychology public_relations security_studies sociology us_foreign_policy",
     "Other": "business_ethics clinical_knowledge college_medicine global_facts human_aging management marketing medical_genetics miscellaneous nutrition professional_accounting professional_medicine virology"}
GRP = {f"mmlu_{s}": g for g, v in G.items() for s in v.split()}
def load(model, s):
    p = f"{R}/{model}-{s}/results.jsonl"
    if not os.path.isfile(p): return None
    return {r["task_id"]: r for r in map(json.loads, open(p)) if r.get("valid", True) is not False and r.get("status") == "ok"}
sets = sorted(os.path.basename(d)[len(Q4) + 1:] for d in glob.glob(f"{R}/{Q4}-*"))
def acc(d): return (sum(bool(r["correct"]) for r in d.values()) / len(d)) if d else None
rows = []; pool = {g: {m: [0, 0] for m in (NEW, Q4, FULL)} for g in list(G) + ["ALL MMLU"]}; agree = {g: [0, 0] for g in list(G) + ["ALL MMLU"]}
for s in sets:
    d = {m: load(m, s) for m in (NEW, Q4, FULL)}
    if d[NEW] is None: rows.append({"set": s, "new": None}); continue
    ag = sum(d[NEW][t]["predicted"] == d[Q4][t]["predicted"] for t in d[NEW] if t in d[Q4]) / max(sum(t in d[Q4] for t in d[NEW]), 1)
    row = {"set": s, "n": len(d[NEW]), "new": acc(d[NEW]), "q4": acc(d[Q4]), "full": acc(d[FULL]) if d[FULL] else None, "agree_q4": ag, "complete": len(d[NEW]) == len(d[Q4])}
    rows.append(row)
    if s in GRP:
        for g in (GRP[s], "ALL MMLU"):
            for m in (NEW, Q4, FULL):
                if d[m]: pool[g][m][0] += sum(bool(r["correct"]) for r in d[m].values()); pool[g][m][1] += len(d[m])
            agree[g][0] += sum(d[NEW][t]["predicted"] == d[Q4][t]["predicted"] for t in d[NEW] if t in d[Q4]); agree[g][1] += sum(t in d[Q4] for t in d[NEW])
out = {"groups": {}, "sets": rows, "bars": {}}
for g in pool:
    a = {m: (v[0] / v[1] if v[1] else None) for m, v in pool[g].items()}; out["groups"][g] = {"new": a[NEW], "q4": a[Q4], "full": a[FULL], "n": pool[g][NEW][1], "agree_q4": agree[g][0] / max(agree[g][1], 1)}
ok = lambda x, y, t: x is not None and y is not None and abs(x - y) * 100 <= t
mm = [r for r in rows if r["set"] in GRP]; oth = [r for r in rows if r["set"] not in GRP]
out["bars"]["mmlu_overall_within_1.5"] = ok(out["groups"]["ALL MMLU"]["new"], out["groups"]["ALL MMLU"]["q4"], 1.5)
for g in G: out["bars"][f"mmlu_{g}_within_3"] = ok(out["groups"][g]["new"], out["groups"][g]["q4"], 3)
for r in oth: out["bars"][f"{r['set']}_within_3"] = ok(r.get("new"), r.get("q4"), 3)
out["coverage"] = {"mmlu_sets_run": sum(r.get("new") is not None for r in mm), "mmlu_sets_expected": len(GRP), "other_sets_run": sum(r.get("new") is not None for r in oth), "other_sets_expected": 15, "incomplete_sets": [r["set"] for r in rows if r.get("new") is not None and not r["complete"]]}
out["pass"] = all(out["bars"].values()) and out["coverage"]["mmlu_sets_run"] == len(GRP) and out["coverage"]["other_sets_run"] == 15 and not out["coverage"]["incomplete_sets"]
f = lambda x: "  -  " if x is None else f"{100 * x:5.1f}"
print(f"{'group':<18}{'CLF9F4':>7}{'Q4':>7}{'full':>7}{'agree Q4':>10}{'n':>7}")
for g, v in out["groups"].items(): print(f"{g:<18}{f(v['new']):>7}{f(v['q4']):>7}{f(v['full']):>7}{100 * v['agree_q4']:>9.1f}%{v['n']:>7}")
print(); [print(f"{r['set']:<34}{f(r.get('new')):>7}{f(r.get('q4')):>7}{f(r.get('full')):>7}  agree {100 * r['agree_q4']:.0f}%" if r.get("new") is not None else f"{r['set']:<34}  not run") for r in oth]
print("\nbars:", {k: ("PASS" if v else "FAIL") for k, v in out["bars"].items()}); print("coverage:", out["coverage"]); print("OVERALL:", "PASS" if out["pass"] else "FAIL / incomplete")
if len(sys.argv) > 1: json.dump(out, open(sys.argv[1], "w"), indent=1)
