"""T102: separate specific capability candidates from reporting boilerplate. Uses the T99 groups (Area at depth 1, predicate lemma, object key, distinct articles). A predicate and object pair is specific when most of its articles sit in few Areas: its top Area holds SHARE or more of its articles (default 0.5) and it appears in at most MAXAREAS Areas with 5 or more articles (default 5). The pairs that spread over many Areas (say statement, tell reporter, take place) are boilerplate. Counts only, nothing judged.
    D=<folder with t76_supported_triples.json and t79_assign.json> SHARE=0.5 MAXAREAS=5 /workspace/models/embed-zs/.venv/bin/python -u t102_specific.py -> <D>/t102_specific.json"""
import os, json, collections
D = os.environ.get("D", "runs/pulse/t99"); SHARE = float(os.environ.get("SHARE", 0.5)); MAXA = int(os.environ.get("MAXAREAS", 5))
SUP = json.load(open(D + "/t76_supported_triples.json")); A = json.load(open(D + "/t79_assign.json")); assert len(SUP) == A["rows"]
d1 = A["depth1_label"]; asg = A["assign_constrained"]
g = collections.defaultdict(set); po = collections.defaultdict(lambda: collections.defaultdict(set))
for s, a in zip(SUP, asg):
    area = d1[a]; _, pred, obj = s["key"]; g[(area, pred, obj)].add(s["article"]); po[(pred, obj)][area].add(s["article"])
spec = set()
for k, ar in po.items():
    tot = sum(len(v) for v in ar.values()); top = max(len(v) for v in ar.values()); wide = sum(1 for v in ar.values() if len(v) >= 5)
    if top / tot >= SHARE and wide <= MAXA: spec.add(k)
res = {"share": SHARE, "max_areas": MAXA, "pairs_total": len(po), "pairs_specific": len(spec)}
for n in (10, 20, 50):
    allg = [k for k, v in g.items() if len(v) >= n]; sp = [k for k in allg if (k[1], k[2]) in spec]
    res[f"groups_ge{n}_all"] = len(allg); res[f"groups_ge{n}_specific"] = len(sp)
res["groups_ge10_specific_share"] = round(res["groups_ge10_specific"] / max(res["groups_ge10_all"], 1), 4)
boiler = sorted(((sum(len(v) for v in ar.values()), k) for k, ar in po.items() if k not in spec and sum(1 for v in ar.values() if len(v) >= 5) >= 3), reverse=True)[:20]
res["largest_boilerplate_pairs"] = [{"predicate": k[0], "object": k[1], "articles": n} for n, k in boiler]
top = sorted(((len(v), k) for k, v in g.items() if (k[1], k[2]) in spec), reverse=True)[:25]
res["largest_specific_groups"] = [{"area": k[0], "predicate": k[1], "object": k[2], "articles": n} for n, k in top]
json.dump(res, open(D + "/t102_specific.json", "w"), indent=1); print(json.dumps({k: v for k, v in res.items() if not k.startswith("largest")}))
