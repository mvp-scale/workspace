"""T21 suite M analysis (pre-registration L672). Per rater and edit type: share saying yes. Expected by the guideline: B yes; F, P, W, N no; S unscored. Writes runs/pulse/suiteM/table.json (rater -> id -> yes) for the Lean checker. python3 suite_m_analyze.py"""
import json, os, collections
J = lambda p: [json.loads(l) for l in open(p)]; D = "runs/pulse/suiteM/"; items = J(D + "items.jsonl"); var = {r["id"]: r["var"] for r in items}; kind = {r["id"]: r["kind"] for r in items}
def lab(d):
    f = D + d + "/labels.jsonl"
    return {r["item_id"]: bool(r["label"]["conditions"]) for r in J(f)} if os.path.exists(f) else None
R = {"Sonnet": lab("sonnet"), "Qwen3.6-27B": lab("qwen"), "Gemma 4 26B": lab("gemma"), "Jev (P>=0.5)": {r["id"]: r["answers"]["presence"]["noul"] >= 0.5 for r in J(D + "jev_same/raw.jsonl") if "answers" in r}}
R = {k: v for k, v in R.items() if v}
print("%-14s" % "rater", *["%-9s" % x for x in ("B yes", "F no", "P no", "W no", "N no", "S yes")], "| follows rule (B yes, F P W N no)")
tab = {}
for k, v in R.items():
    c = collections.defaultdict(lambda: [0, 0])
    for i, y in v.items(): c[var[i]][0] += y; c[var[i]][1] += 1
    exp = {"B": c["B"][0], "F": c["F"][1] - c["F"][0], "P": c["P"][1] - c["P"][0], "W": c["W"][1] - c["W"][0], "N": c["N"][1] - c["N"][0], "S": c["S"][0]}
    n = {x: c[x][1] for x in c}; ok = sum(exp[x] for x in "BFPWN"); tot = sum(n[x] for x in "BFPWN")
    print("%-14s" % k, *["%-9s" % f"{exp[x]}/{n[x]}" for x in ("B", "F", "P", "W", "N", "S")], f"| {ok}/{tot} = {ok / tot:.3f}"); tab[k] = v
json.dump(tab, open(D + "table.json", "w"))
