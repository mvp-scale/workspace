"""T20 consensus rescore: score an engine version on the 395 dev2 items against the CONSENSUS of 4 same-spec labels (Sonnet x2, Haiku x2) instead of Sonnet alone.
Items where the top answer has under 3 of 4 votes ('split') are left out and reported as contested. CPU only.
    /workspace/models/embed-zs/.venv/bin/python consensus_rescore.py <version> [--save]"""
import json, glob, math, sys, collections, os
os.environ["CUDA_VISIBLE_DEVICES"] = ""
sys.path.insert(0, "."); from expert1_runtime import Expert, Expert3, ExpertS
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]; LV = ["minor", "notable", "major", "severe", "extreme"]
ver = sys.argv[1]; REG = {r["version"]: r for r in json.load(open("engine_versions.json"))}; reg = REG[ver]
e = {"Expert": Expert, "Expert3": Expert3, "ExpertS": ExpertS}[reg["class"]](reg["path"])
def load(pats):
    d = {}
    for p in pats:
        for f in glob.glob(p):
            for r in J(f): d[r["item_id"]] = r["label"]
    return d
V = [load(["runs/p7b/*/labels.jsonl"]), load(["runs/pulse/selfcons/labels.jsonl"]), load(["runs/p7/*/labels.jsonl"]), load(["runs/pulse/selfcons_haiku/labels.jsonl"])]
items = {r["id"]: r["text"] for r in J("runs/pulse/selfcons/items.jsonl")}
CLEAN = "--clean" in sys.argv   # only items dated after the training cutoff (2026-10-25); the rest sit in the training period
ids = [i for i in json.load(open("runs/pulse/selfcons_clean_ids.json" if CLEAN else "runs/pulse/selfcons/ids.json")) if i in items and all(i in v for v in V)]
def wil(k, m, z=1.96):
    if m <= 0: return [None, None]
    p = k / m; d = 1 + z * z / m; c = (p + z * z / (2 * m)) / d; s = z * math.sqrt(p * (1 - p) / m + z * z / (4 * m * m)) / d; return [round(c - s, 3), round(c + s, 3)]
def rate(xs): xs = list(xs); k = sum(xs); return {"rate": round(k / len(xs), 3) if xs else None, "ci95": wil(k, len(xs)), "n": len(xs)}
def cons(vals, need=3):
    c = collections.Counter(vals).most_common(1)[0]; return c[0] if c[1] >= need else None
R = {i: e.read(items[i]) for i in ids}; ans = lambda r, k: r.get(k, {}).get("status") == "answered"
out = {"version": ver, "n_items": len(ids)}; sonly = lambda i: V[0][i]
# story type and topic
for fld, key in (("story_type", "story_type"), ("topic", "topic")):
    cs = {i: cons([v[i][key] for v in V]) for i in ids}; ok = [i for i in ids if cs[i] is not None]
    def eng(i):
        r = R[i]
        if fld == "story_type": return ans(r, "story_type") and r["story_type"]["answer"] == cs[i]
        return ans(r, "topic_top2") and cs[i] in (r["topic_top2"]["answer"] or [])
    sg = lambda i: (R[i]["story_type"]["answer"] == sonly(i)["story_type"] and ans(R[i], "story_type")) if fld == "story_type" else (ans(R[i], "topic_top2") and sonly(i)["topic"] in R[i]["topic_top2"]["answer"])
    out[fld] = {"contested": round(1 - len(ok) / len(ids), 3), "vs_consensus": rate(eng(i) for i in ok), "vs_sonnet_only_same_items": rate(sg(i) for i in ok), "vs_sonnet_only_all_items": rate(sg(i) for i in ids),
                "answered_share": rate(ans(R[i], "story_type" if fld == "story_type" else "topic_top2") for i in ok)["rate"],
                "always_guess": round(collections.Counter(cs[i] for i in ok).most_common(1)[0][1] / len(ok), 3)}
# presence
pc = {i: cons([bool(v[i]["conditions"]) for v in V]) for i in ids}; ok = [i for i in ids if pc[i] is not None]
yes = lambda i: bool(R[i]["condition_present"].get("answer")) if ans(R[i], "condition_present") else None
out["condition_present"] = {"contested": round(1 - len(ok) / len(ids), 3), "vs_consensus_all_items": rate(yes(i) == pc[i] for i in ok), "consensus_positive_share": round(sum(pc[i] for i in ok) / len(ok), 3),
    "always_guess": round(max(sum(pc[i] for i in ok), sum(not pc[i] for i in ok)) / len(ok), 3), "reach": rate(yes(i) is True for i in ok if pc[i]), "answered_share": rate(yes(i) is not None for i in ok)["rate"],
    "vs_sonnet_only_reach": rate(yes(i) is True for i in ids if sonly(i)["conditions"])}
# which / direction / size on consensus-positive items
pos = [i for i in ok if pc[i]]; wh = []; di = []; sz = []; sz1 = []
for i in pos:
    tops = [v[i]["conditions"][0]["condition"] for v in V if v[i]["conditions"]]; ct = cons(tops, 2)
    if ct is None: continue
    c = R[i].get("condition"); found = yes(i) is True and c and c.get("status") == "answered"
    wh.append(bool(found and c["answer"][0] == ct))
    if not (found and c["answer"][0] == ct): continue
    ds = [x["direction"] for v in V for x in v[i]["conditions"] if x["condition"] == ct]; cd = cons(ds, max(2, math.ceil(len(ds) * 0.75)))
    ls = sorted(LV.index(x["level"]) for v in V for x in v[i]["conditions"] if x["condition"] == ct)
    if cd is not None: di.append(c.get("direction") == cd)
    if "size" in c and ls: m = ls[len(ls) // 2]; sz.append(LV.index(c["size"]) == m); sz1.append(abs(LV.index(c["size"]) - m) <= 1)
out["which_condition_of_real"] = rate(wh); out["direction_given_which"] = rate(di); out["size_exact_given_which"] = rate(sz); out["size_within_one_given_which"] = rate(sz1)
print(json.dumps(out, indent=1))
if "--save" in sys.argv: json.dump(out, open(f"runs/pulse/consensus_{ver}{'_clean' if CLEAN else ''}.json", "w"), indent=1)
