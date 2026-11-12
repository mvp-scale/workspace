"""T99: capability candidates under the Area draft. A candidate is the recurring action on a thing: (depth-1 Area, predicate lemma, object key) stated in many independent articles, from triples backed by 2 or more independent publishers (T97) and assigned to ontology terms by the mapping (T99-A). A pair (predicate, object) found under 3 or more Areas is a shared-capability candidate (playbook 00: a Capability may be reused across Areas). Counts only; nothing is judged.
    D=<folder with t76_supported_triples.json and t79_assign.json> /workspace/models/embed-zs/.venv/bin/python -u t99_capability.py -> <D>/t99_capability.json, t99_capability_top.json"""
import os, json, collections
D = os.environ.get("D", "runs/pulse/t99")
SUP = json.load(open(D + "/t76_supported_triples.json")); A = json.load(open(D + "/t79_assign.json")); assert len(SUP) == A["rows"], "assignment rows differ from the triple rows (was NP set?)"
d1 = A["depth1_label"]; asg = A["assign_constrained"]
g = collections.defaultdict(lambda: {"articles": set(), "subjects": set(), "rows": 0}); po = collections.defaultdict(lambda: collections.defaultdict(set))
for s, a in zip(SUP, asg):
    area = d1[a]; subj, pred, obj = s["key"]
    x = g[(area, pred, obj)]; x["articles"].add(s["article"]); x["subjects"].add(subj); x["rows"] += 1; po[(pred, obj)][area].add(s["article"])
res = {"rows": len(SUP), "areas_seen": len({k[0] for k in g}), "groups_total": len(g)}
for n in (5, 10, 20, 50): res[f"groups_ge{n}_articles"] = sum(1 for x in g.values() if len(x["articles"]) >= n)
res["areas_with_a_group_ge10"] = len({k[0] for k, x in g.items() if len(x["articles"]) >= 10})
shared = {k: v for k, v in po.items() if sum(1 for ar in v.values() if len(ar) >= 5) >= 3}
res["shared_po_in_3plus_areas_ge5_articles_each"] = len(shared)
res["note"] = "Counts of (Area at depth 1, predicate lemma, object key) groups by number of distinct articles; shared = the same (predicate, object) holds 5 or more articles in each of 3 or more Areas. Unjudged; subjects vary inside a group."
top = sorted(((len(x["articles"]), k, len(x["subjects"])) for k, x in g.items()), reverse=True)[:60]
json.dump(res, open(D + "/t99_capability.json", "w"), indent=1)
json.dump({"top_groups": [{"area": k[0], "predicate": k[1], "object": k[2], "articles": n, "subjects": sj} for n, k, sj in top], "top_shared": [{"predicate": k[0], "object": k[1], "areas": len(v), "articles": sum(len(a) for a in v.values())} for k, v in sorted(shared.items(), key=lambda kv: -sum(len(a) for a in kv[1].values()))[:40]]}, open(D + "/t99_capability_top.json", "w"), indent=1)
print(json.dumps(res, indent=1))
