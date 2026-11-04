"""Does a third family (Qwen3-14B-AWQ, Kaggle) change the consensus? 395 voted items. Stdlib only. Prediction: ledger L537 (does not resolve split presence items)."""
import json, glob, re, os
H = os.path.dirname(os.path.abspath(__file__)); ns = {}
exec("import collections, itertools\n" + re.search(r"def alpha\(.*?\n(?=\ndef status)", open(os.path.join(H, "fitness_screen.py")).read(), re.S).group(0), ns); alpha = ns["alpha"]
def lo(pats):
    d = {}
    for p in pats:
        for f in glob.glob(os.path.join(H, p)):
            for l in open(f, encoding="utf-8"):
                r = json.loads(l); d[r["item_id"]] = r["label"]
    return d
S1, S2, H1, H2, Q = lo(["runs/p7b/*/labels.jsonl"]), lo(["runs/pulse/selfcons/labels.jsonl"]), lo(["runs/p7/*/labels.jsonl"]), lo(["runs/pulse/selfcons_haiku/labels.jsonl"]), lo(["runs/pulse/selfcons_qwen/labels.jsonl"])
ids = [i for i in json.load(open(os.path.join(H, "runs/pulse/selfcons/ids.json"))) if all(i in v for v in (S1, S2, H1, H2, Q))]
F = {"story_type": lambda l: l["story_type"], "topic": lambda l: l["topic"], "condition_present": lambda l: bool(l["conditions"])}
out = {"items": len(ids), "fields": {}}
for k, g in F.items():
    a2 = alpha([[g(S1[i]), g(H1[i])] for i in ids]); a3 = alpha([[g(S1[i]), g(H1[i]), g(Q[i])] for i in ids])
    C = [i for i in ids if g(S1[i]) != g(H1[i])]
    toS = sum(g(Q[i]) == g(S1[i]) for i in C); toH = sum(g(Q[i]) == g(H1[i]) for i in C); neither = len(C) - toS - toH
    A3 = [i for i in ids if g(S1[i]) == g(H1[i]) == g(Q[i])]; A2 = [i for i in ids if g(S1[i]) == g(H1[i])]
    rep = lambda grp: round(sum(g(S2[i]) == g(S1[i]) for i in grp if g(S2[i]) == g(H2[i])) / max(1, sum(g(S2[i]) == g(H2[i]) for i in grp)), 3)
    out["fields"][k] = {"alpha_two_families": a2, "alpha_three_families": a3, "split_items_S1_vs_H1": len(C), "qwen_sides_with_sonnet": toS, "qwen_sides_with_haiku": toH, "qwen_with_neither": neither,
                        "all_three_agree_share": round(len(A3) / len(ids), 3), "two_families_agree_share": round(len(A2) / len(ids), 3), "reproduced_all_three_agree": rep(A3), "reproduced_two_agree": rep(A2)}
json.dump(out, open(os.path.join(H, "runs/pulse/third_voter_test.json"), "w"), indent=1); print(json.dumps(out, indent=1))
