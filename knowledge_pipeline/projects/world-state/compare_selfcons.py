"""T20: Sonnet self-consistency. Compares the second Sonnet label (runs/pulse/selfcons/labels.jsonl) with the first (runs/p7b). Agreement, with Wilson 95% intervals; reweighted to the natural stream with the presence strata of the old set (positive share 0.259)."""
import json, glob, math, collections, sys
WHO = sys.argv[1] if len(sys.argv) > 1 else "sonnet"   # which labeller is being compared with itself
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
a = {}; b = {r["item_id"]: r["label"] for r in J("runs/pulse/selfcons/labels.jsonl" if WHO == "sonnet" else "runs/pulse/selfcons_haiku/labels.jsonl")}
for f in glob.glob("runs/p7b/*/labels.jsonl" if WHO == "sonnet" else "runs/p7/*/labels.jsonl"):
    for r in J(f): a[r["item_id"]] = r["label"]
ids = [i for i in b if i in a]; LV = ["minor", "notable", "major", "severe", "extreme"]
def wil(k, m, z=1.96):
    p = k / m; d = 1 + z * z / m; c = (p + z * z / (2 * m)) / d; s = z * math.sqrt(p * (1 - p) / m + z * z / (4 * m * m)) / d; return [round(c - s, 3), round(c + s, 3)]
def rate(xs): k = sum(xs); return {"rate": round(k / len(xs), 3), "ci95": wil(k, len(xs)), "n": len(xs)}
pa = {i: bool(a[i]["conditions"]) for i in ids}; pb = {i: bool(b[i]["conditions"]) for i in ids}
res = {"n": len(ids), "story_type": rate([a[i]["story_type"] == b[i]["story_type"] for i in ids]), "topic": rate([a[i]["topic"] == b[i]["topic"] for i in ids])}
pos = [i for i in ids if pa[i]]; neg = [i for i in ids if not pa[i]]
res["presence_given_first_positive"] = rate([pb[i] for i in pos]); res["presence_given_first_negative"] = rate([not pb[i] for i in neg])
sh = 0.259;  # same strata weights for both labellers: share of items with a condition in the natural stream (Sonnet-based, old set)
pr = sh * res["presence_given_first_positive"]["rate"] + (1 - sh) * res["presence_given_first_negative"]["rate"]; res["presence_agreement_natural_weighted"] = round(pr, 3)
res["presence_agreement_unweighted"] = rate([pa[i] == pb[i] for i in ids])
both = [i for i in pos if pb[i]]; res["items_both_positive"] = len(both)
res["top_condition_same"] = rate([a[i]["conditions"][0]["condition"] == b[i]["conditions"][0]["condition"] for i in both]); res["any_condition_shared"] = rate([bool({c["condition"] for c in a[i]["conditions"]} & {c["condition"] for c in b[i]["conditions"]}) for i in both])
dd, zz = [], []
for i in both:
    ca = {c["condition"]: c for c in a[i]["conditions"]}
    for c in b[i]["conditions"]:
        if c["condition"] in ca: dd.append(ca[c["condition"]]["direction"] == c["direction"]); zz.append(abs(LV.index(ca[c["condition"]]["level"]) - LV.index(c["level"])) <= 1)
res["direction_same_on_shared_condition"] = rate(dd) if dd else None; res["size_within_one_on_shared_condition"] = rate(zz) if zz else None
json.dump(res, open("runs/pulse/selfcons_result_" + WHO + ".json", "w"), indent=1); print(json.dumps(res, indent=1))
