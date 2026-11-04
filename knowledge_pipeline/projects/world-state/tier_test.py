"""Confidence-layer test: does agreement between two independent-family sources (S1 Sonnet, H1 Haiku) predict that the other pair (S2, H2) reproduces the label? Stdlib only."""
import json, glob, collections
def lo(pats):
    d = {}
    for p in pats:
        for f in glob.glob(p):
            for l in open(f, encoding="utf-8"):
                r = json.loads(l); d[r["item_id"]] = r["label"]
    return d
S1, S2, H1, H2 = lo(["runs/p7b/*/labels.jsonl"]), lo(["runs/pulse/selfcons/labels.jsonl"]), lo(["runs/p7/*/labels.jsonl"]), lo(["runs/pulse/selfcons_haiku/labels.jsonl"])
ids = [i for i in json.load(open("runs/pulse/selfcons/ids.json")) if all(i in v for v in (S1, S2, H1, H2))]
F = {"story_type": lambda l: l["story_type"], "topic": lambda l: l["topic"], "condition_present": lambda l: bool(l["conditions"])}
res = {"items": len(ids), "fields": {}}
for k, g in F.items():
    A = [i for i in ids if g(S1[i]) == g(H1[i])]; C = [i for i in ids if g(S1[i]) != g(H1[i])]
    def repro(group, pick):
        ok = tot = 0
        for i in group:
            if g(S2[i]) == g(H2[i]):  # reference exists only when the other pair agrees with itself
                tot += 1; ok += (g(pick[i]) == g(S2[i]))
        return {"reference_items": tot, "reproduced": round(ok / tot, 3) if tot else None}
    res["fields"][k] = {"tier_A_share": round(len(A) / len(ids), 3), "tier_A_items": len(A), "tier_A_label=S1": repro(A, S1), "tier_C_items": len(C), "tier_C_label=S1": repro(C, S1), "tier_C_label=H1": repro(C, H1)}
json.dump(res, open("runs/pulse/tier_test.json", "w"), indent=1); print(json.dumps(res, indent=1))
