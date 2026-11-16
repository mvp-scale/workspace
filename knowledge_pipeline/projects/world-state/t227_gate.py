"""T227 gate (plan T148 step 28): promote a key-phrase cluster to an Area sub-area candidate when the same phrase is topic-concentrated in the SAME topic in two disjoint halves (publisher halves; random article halves as the comparison; topic-shuffled control).
Reads runs/pulse/t227/pub0|pub1|art0|art1/t227_half.json. A match = same topic and at least one shared surface form among each cluster's top four forms.
    python3 t227_gate.py -> runs/pulse/t227/t227_gate.json, runs/pulse/t227/area_candidates.jsonl"""
import json, random, collections
R = "runs/pulse/t227/"; L = lambda n: json.load(open(R + n + "/t227_half.json"))["lanes"]["B_key_phrases"]["concentrated_all"]
def match(A, B, shuffle=False):
    tb = [x["topic"] for x in B]
    if shuffle: random.Random(3).shuffle(tb)
    idx = collections.defaultdict(list)
    for x, t in zip(B, tb):
        for f in x["forms"]: idx[(t, f)].append(x)
    out = []
    for a in A:
        hit = next((b for f in a["forms"] for b in idx.get((a["topic"], f), [])), None)
        if hit: out.append((a, hit))
    return out
res = {}
for name, (x, y) in {"publisher_halves": ("pub0", "pub1"), "random_article_halves": ("art0", "art1")}.items():
    A, B = L(x), L(y); m = match(A, B); ms = match(A, B, shuffle=True)
    small = min(len(A), len(B)); res[name] = {"clusters": [len(A), len(B)], "matched": len(m), "share_of_smaller": len(m) / max(1, small), "topic_shuffled_control_matched": len(ms), "control_share": len(ms) / max(1, small)}
m = match(L("pub0"), L("pub1")); per = collections.defaultdict(list)
for a, b in m: per[a["topic"]].append({"cluster": a["cluster"], "forms": sorted(set(a["forms"]) | set(b["forms"]))[:5], "events": [a["events"], b["events"]], "publishers": [a["publishers"], b["publishers"]], "top_share": [a["top_share"], b["top_share"]]})
res["promoted"] = len(m); res["promoted_topics"] = len(per); res["topics_with_3plus"] = sum(1 for v in per.values() if len(v) >= 3)
res["largest_five_per_topic"] = {t: [x["cluster"] for x in sorted(v, key=lambda z: -sum(z["events"]))[:5]] for t, v in sorted(per.items(), key=lambda kv: -len(kv[1]))[:14]}
open(R + "area_candidates.jsonl", "w").write("".join(json.dumps({"topic": t, **x, "provenance": "key phrase concentrated in this topic in two disjoint publisher halves; no outside truth"}) + "\n" for t, v in per.items() for x in v))
json.dump(res, open(R + "t227_gate.json", "w"), indent=1); print(json.dumps(res, indent=1))
