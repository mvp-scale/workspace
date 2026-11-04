"""Descriptive tally: how much of the 46.5k pool is already in each confidence tier, from labels we hold (no model runs, no spend). Stdlib only.
Sources: Haiku r1 (runs/p7, 46.5k), Sonnet r1 (runs/p7b, 7.7k), cheap cues (URL section, headline). Tiers per field:
A both families agree; C they disagree; B one family plus a supporting cue; D one family, no support (needs a second voter)."""
import json, glob, re, collections
def lo(p):
    d = {}
    for f in glob.glob(p):
        for l in open(f, encoding="utf-8"):
            r = json.loads(l); d[r["item_id"]] = r["label"]
    return d
H, S = lo("runs/p7/*/labels.jsonl"), lo("runs/p7b/*/labels.jsonl")
pool = {json.loads(l)["id"]: json.loads(l) for l in open("data/pool_train.jsonl", encoding="utf-8")}
OPU = re.compile(r"/(opinions?|comments?|commentary|editorials?|analysis|columns?|columnists?|viewpoints?|views|blogs?|voices|perspectives?|op-?ed|forum|letters?|insight|ideas)(/|-|\.|$)", re.I)
OPH = re.compile(r"^(opinion|analysis|editorial|comment|column|commentary|view|perspective|why|how)\b|\b(should|must|we need|needs to|time to|let's)\b|\?\s*$", re.I)
FCH = re.compile(r"\b(will|expected to|forecast|predict\w*|set to|projected|outlook|likely to|could|to rise|to fall|plans? to|aims? to)\b", re.I)
first = lambda t: re.split(r"(?<=[.!?])\s", t, 1)[0]
def cue_story(i):
    t = first(pool[i]["text"]); op = bool(OPH.search(t)) or (i.startswith("cc:") and bool(OPU.search(i))); fc = bool(FCH.search(t)); return "opinion" if op else ("forecast" if fc else "fact")
res = {}; ids = [i for i in H if i in pool]
for field, g in (("story_type", lambda l: l["story_type"]), ("condition_present", lambda l: bool(l["conditions"])), ("topic", lambda l: l["topic"])):
    c = collections.Counter()
    for i in ids:
        if i in S: c["A_both_families_agree" if g(S[i]) == g(H[i]) else "C_families_disagree"] += 1
        elif field == "story_type": c["B_one_family_plus_cue" if cue_story(i) == g(H[i]) or (g(H[i]) in ("unclear",) and False) else "D_one_family_no_support"] += 1
        else: c["D_one_family_no_support"] += 1
    res[field] = {"items": len(ids), **{k: v for k, v in sorted(c.items())}, **{"share_" + k[0]: round(v / len(ids), 3) for k, v in sorted(c.items())}}
json.dump(res, open("runs/pulse/tier_pool.json", "w"), indent=1); print(json.dumps(res, indent=1))
