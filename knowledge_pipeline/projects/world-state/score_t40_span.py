"""T40 step 2 scorer: gate check 5 (directly in the input). Per trait: share of positives with a valid exact quote AND a majority yes (2 of 3 raters) on the quote alone; share of majority yes on the random same length window of the same item (control). Pass line set before the run: directly-in-the-input rate >= 0.90 and control majority-yes rate <= 0.30.
    /workspace/kev/.venv/bin/python -I score_t40_span.py   (from projects/world-state)"""
import json, collections, sys
R = ["clef", "gemma", "qwen"]; QF = sys.argv[1] if len(sys.argv) > 1 else "runs/xtest/B15_quotes.json"; B = sys.argv[2] if len(sys.argv) > 2 else "runs/xtest/B15"; OUTF = sys.argv[3] if len(sys.argv) > 3 else "runs/pulse/traits_check5_result.json"; Qs = json.load(open(QF))
ans = {r: {} for r in R}
for r in R:
    for l in open(f"{B}/runs/{r}_A_s0/results.jsonl"):
        x = json.loads(l)
        if x["ok"]: ans[r][(x["field"], x["item"])] = 1 if x["label"] == "yes" else 0
def maj(t, iid):
    v = [ans[r].get((t, iid)) for r in R]
    return None if any(x is None for x in v) else int(sum(v) >= 2)
by = collections.defaultdict(list)
for o in Qs: by[o["trait"]].append(o)
res = {}
for t, L in by.items():
    n = len(L); valid = [o for o in L if o["valid"]]
    span = [maj(t, o["item"] + "|span") for o in valid]; ctrl = [maj(t, o["item"] + "|rand") for o in valid]
    sy = sum(1 for x in span if x == 1); cy = sum(1 for x in ctrl if x == 1)
    direct = sy / n; control = (cy / len(valid)) if valid else None
    res[t] = {"positives": n, "valid_quotes": len(valid), "valid_rate": round(len(valid) / n, 3), "span_majority_yes": sy, "directly_in_input_rate": round(direct, 3), "control_majority_yes": cy, "control_rate": None if control is None else round(control, 3), "missing_answers": sum(1 for x in span + ctrl if x is None), "pass_check5": bool(direct >= 0.90 and control is not None and control <= 0.30)}
json.dump(res, open(OUTF, "w"), indent=1); print(json.dumps(res, indent=1))
