"""Engine-level ceiling (pre-registered by the plan of 2026-11-05): how much of Clef's (dial, direction) keys can a reader recover if it covers only some dials, on 1736 Clef-read stories not in any Pulse training pool (id and text-prefix overlap 0).
    python3 engine_ceiling.py   (from projects/world-state)"""
import json, collections
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
a = J("/workspace/data/newsreader/labels/clef-q4km.jsonl")
K = lambda r: {(x["dial"], x["direction"]) for x in r["readings"] if x["direction"] != "conflict"}
cov = {"air_pollution", "biodiversity_loss", "civil_unrest", "cyber_insecurity"}
tot = sum(len(K(r)) for r in a); c4 = sum(1 for r in a for k in K(r) if k[0] in cov)
jac = lambda keep: sum((len(K(r) & {k for k in K(r) if keep(k)}) / len(K(r) | {k for k in K(r) if keep(k)}) if (K(r) | {k for k in K(r) if keep(k)}) else 1.0) for r in a) / len(a)
cnt = collections.Counter(k[0] for r in a for k in K(r)); run = 0; need = {}
for n, (d, v) in enumerate(cnt.most_common(), 1):
    run += v; need[n] = round(run / tot, 3)
res = {"stories": len(a), "stories_with_a_key": sum(1 for r in a if K(r)), "clef_keys": tot, "dials_seen": len(cnt), "covered_dials": sorted(cov),
       "ceiling_tpr_4_dials": round(c4 / tot, 3), "ceiling_jaccard_4_dials": round(jac(lambda k: k[0] in cov), 3), "jaccard_empty_reader": round(jac(lambda k: False), 3),
       "ceiling_tpr_by_top_n_dials": {n: need[n] for n in (4, 8, 12, 16, 20, 25, 28, 30, 39) if n in need},
       "dials_needed_for_tpr_0_90": next(n for n, v in need.items() if v >= 0.90), "dials_needed_for_tpr_0_95": next(n for n, v in need.items() if v >= 0.95)}
json.dump(res, open("runs/pulse/engine_ceiling.json", "w"), indent=1); print(json.dumps(res, indent=1))
