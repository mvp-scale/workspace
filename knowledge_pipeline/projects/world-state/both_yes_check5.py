"""Post hoc robustness for gate check 5 (L847 style): require Clef AND Gemma both yes on the quote and on the control window. Not a gate; information for the ship decision.
    /workspace/kev/.venv/bin/python -I both_yes_check5.py <quotes.json> <bundle_dir> <out.json>"""
import json, sys, collections
QF, B, OUT = sys.argv[1:4]; R = ["clef", "gemma"]; ans = {r: {} for r in R}
for r in R:
    for l in open(f"{B}/runs/{r}_A_s0/results.jsonl"):
        x = json.loads(l)
        if x["ok"]: ans[r][(x["field"], x["item"])] = x["label"] == "yes"
by = collections.defaultdict(list)
for o in json.load(open(QF)): by[o["trait"]].append(o)
res = {}
for t, L in by.items():
    v = [o for o in L if o["valid"]]; n = len(L)
    s = sum(1 for o in v if all(ans[r].get((t, o["item"] + "|span")) for r in R)); c = sum(1 for o in v if all(ans[r].get((t, o["item"] + "|rand")) for r in R))
    res[t] = {"positives": n, "both_yes_directly": round(s / n, 3), "both_yes_control": round(c / len(v), 3) if v else None}
json.dump(res, open(OUT, "w"), indent=1); print(json.dumps(res))
