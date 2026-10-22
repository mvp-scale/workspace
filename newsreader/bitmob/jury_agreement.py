"""M1 (criteria rev 3): Jev vs Clef agreement on J, in the engine's units, per area. Writes data/jury/J/agreement.json.
  python3 -I newsreader/bitmob/jury_agreement.py   (Jev labels: night1 / testA records; Clef labels: data/trainset/jclef.jsonl)
Units: type = weight class after the 0.5 cut (fact / forecast / opinion / unclear, classify.type_weight) + the 4 labels at 0.5 for alpha; topic = chosen topic; country = entry country;
recent = P['x|recent'] >= 0.3; condition = per dial: up / down / conflict / none from target_keys (a reading is exactly one direction with majority >= 0.65 over 3 wordings, build_trainset.target)."""
import json, collections, itertools, sys
W = "/workspace/data"; L = lambda f: [json.loads(l) for l in open(f)]
J = json.load(open(f"{W}/jury/J/ids.json"))["ids"]
jev = {r["id"]: r for f in ("night1", "testA") for r in L(f"{W}/trainset/{f}.jsonl") if r["id"] in set(J)}; clef = {r["id"]: r for r in L(f"{W}/trainset/jclef.jsonl")}
ids = [i for i in J if i in clef and i in jev]
def tclass(P):
    h, a, o, f = (P[f"g|{k}"] for k in ("happened", "announced", "opinion", "forecast"))
    return "fact" if (h >= .5 or a >= .5) and o < .5 and f < .5 else "forecast" if f >= .5 else "opinion" if o >= .5 else "unclear"
def dial(r, d):
    k, c = set(r["target_keys"]), set(r["conflicts"]); u, dn = f"{d}|up", f"{d}|down"
    return "conflict" if (u in c or dn in c) else "up" if u in k else "down" if dn in k else "none"
def alpha(pairs):      # Krippendorff's alpha, nominal, 2 coders, no missing
    if not pairs: return None
    co = collections.Counter()
    for a, b in pairs: co[(a, b)] += 1; co[(b, a)] += 1
    n = sum(co.values()); nc = collections.Counter()
    for (a, b), v in co.items(): nc[a] += v
    do = sum(v for (a, b), v in co.items() if a != b) / n; de = sum(nc[a] * nc[b] for a in nc for b in nc if a != b) / (n * (n - 1))
    return None if de == 0 else round(1 - do / de, 4)
def area(name, fn):
    pairs = [(fn(jev[i]), fn(clef[i])) for i in ids]; dis = [i for i, (a, b) in zip(ids, pairs) if a != b]
    return {"n": len(ids), "agree": round(1 - len(dis) / len(ids), 4), "alpha": alpha(pairs), "disagreeing_stories": len(dis)}, set(dis)
out, dis_sets, units = {}, {}, {}
out["type_class"], dis_sets["type"] = area("type", lambda r: tclass(r["P"]))
for k in ("happened", "announced", "opinion", "forecast"):
    out[f"type_label_{k}"], s = area(k, lambda r, k=k: r["P"][f"g|{k}"] >= .5); units[f"type_label_{k}"] = len(s)
out["type_alpha_lowest_label"] = min(v["alpha"] for k, v in out.items() if k.startswith("type_label_") and v["alpha"] is not None)
out["topic"], dis_sets["topic"] = area("topic", lambda r: r["topic"])
out["country_entry"], dis_sets["country"] = area("country", lambda r: r["country"])
out["recent_ge_0.3"], dis_sets["recent"] = area("recent", lambda r: r["P"]["x|recent"] >= .3)
dials = sorted({k.split("|")[0] for r in list(jev.values()) + list(clef.values()) for k in r["target_keys"] + r["conflicts"]})
per, cd = {}, set(); allpairs = []
for d in dials:
    pairs = [(dial(jev[i], d), dial(clef[i], d)) for i in ids]; allpairs += pairs; bad = [i for i, (a, b) in zip(ids, pairs) if a != b]; cd |= set(bad)
    per[d] = {"agree": round(1 - len(bad) / len(ids), 4), "alpha": alpha(pairs), "jev_readings": sum(a != "none" for a, _ in pairs), "clef_readings": sum(b != "none" for _, b in pairs), "disagreements": len(bad)}
dis_sets["conditions"] = cd; units["conditions_dial_story_cells"] = sum(v["disagreements"] for v in per.values())
out["conditions"] = {"n_dials": len(dials), "pooled_cell_agree": round(sum(a == b for a, b in allpairs) / len(allpairs), 4), "pooled_alpha": alpha(allpairs),
                     "pooled_reading_present_agree": round(sum((a != "none") == (b != "none") for a, b in allpairs) / len(allpairs), 4),
                     "disagreeing_stories": len(cd), "dials_with_agree_ge_0.97": sum(v["agree"] >= .97 for v in per.values()), "per_dial": per}
anyd = set().union(*dis_sets.values())
units |= {"type_class": len(dis_sets["type"]), "topic": len(dis_sets["topic"]), "country": len(dis_sets["country"]), "recent": len(dis_sets["recent"])}
tot_units = units["type_class"] + units["topic"] + units["country"] + units["recent"] + units["conditions_dial_story_cells"]
out["summary"] = {"n_labelled_both": len(ids), "n_J": len(J), "stories_with_any_disagreement": len(anyd), "share": round(len(anyd) / max(1, len(ids)), 4),
                  "stories_without_conditions": len(set().union(*(v for k, v in dis_sets.items() if k != "conditions"))), "disagreement_units": units, "total_units": tot_units,
                  "opus_batches_assumption": {"items_per_batch": 25, "batches": -(-tot_units // 25), "items_per_batch_50": 50, "batches_50": -(-tot_units // 50)},
                  "note": "Jev test-retest (rev 3 M1) not run: needs hosted Jev calls, not approved in this task"}
json.dump(out, open(f"{W}/jury/J/agreement.json", "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k not in ("conditions",)}, indent=0)[:1500]); print({k: v for k, v in out["conditions"].items() if k != "per_dial"})
