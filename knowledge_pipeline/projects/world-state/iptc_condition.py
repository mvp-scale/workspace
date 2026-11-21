"""iptc_condition: build specs/iptc_condition_v0.json (plan v2 step 5, resource ledger v0). For each world-engine condition, the IPTC level-1 codes that talk about it.
Derived, not fitted: engine topic_condition (49 legacy topics -> conditions) x topic_to_iptc_v1.json (topic -> IPTC level-1 NAMES) x mnds_name_to_code_v1.json (name -> code). Every row says it is the engine's guess (reference).
Level-2 refinements are add-only rows ("ours, guess", with a changeNote); v0 has none. Also written: the resource table (engine half-lives), a by_topic block (fallback route for traces without a landing stage), and code -> name / level-2 parent for the page.
Read-only on medtop.json and the engine ontology. Run (from projects/world-state):
    /workspace/models/embed-zs/.venv/bin/python iptc_condition.py            # writes specs/iptc_condition_v0.json
    /workspace/models/embed-zs/.venv/bin/python iptc_condition.py --publish  # also copies it to demo/mockups/structure-live/ledger-v0/ (the console serves /mockups/*; the sim page reads it there)"""
import sys, os, json, hashlib, collections, shutil
H = os.path.dirname(os.path.abspath(__file__)); ONT = "/workspace/exports/world-engine-ontology-rules_v2.json"; MED = "/workspace/data/ontology_src/iptc/medtop.json"
OUT = H + "/specs/iptc_condition_v0.json"; PUB = "/workspace/demo/mockups/structure-live/ledger-v0/iptc_condition_v0.json"
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
def build():
    o = json.load(open(ONT)); t2i = json.load(open(H + "/specs/topic_to_iptc_v1.json")); mn = json.load(open(H + "/specs/mnds_name_to_code_v1.json")); L1 = mn["l1"]
    cs = json.load(open(MED))["conceptSet"]; u2q = {c["uri"]: c["qcode"] for c in cs}; node = {c["qcode"]: c for c in cs}
    par = {c["qcode"]: (u2q.get(c["broader"][0]) if c.get("broader") else None) for c in cs}
    def chain(q):
        out = []
        while q and len(out) < 10: out.append(q); q = par.get(q)
        return out[::-1]   # top first: [l1, l2, ...]
    topics = {t["id"]: t["name"] for t in o["topics"]}; t2c = collections.defaultdict(list); [t2c[l["from"]].append(l["to"]) for l in o["links"]["topic_condition"]]
    cond = {c["id"]: c for c in o["conditions"]}; c2r = {l["from"]: l for l in o["links"]["condition_resource"]}; c2t = collections.defaultdict(list); [c2t[l["to"]].append(l["from"]) for l in o["links"]["topic_condition"]]
    miss = []; rows = []
    for c in sorted(cond):
        cr = c2r[c]; per = collections.OrderedDict()   # code -> {name, topics, primary_topics}
        for t in sorted(c2t[c]):
            names = t2i["map"].get(t) or []
            for i, nm in enumerate(names):
                code = L1.get(nm)
                if not code: miss.append([t, nm]); continue
                r = per.setdefault(code, {"code": code, "name": nm, "topics": [], "primary_topics": 0}); r["topics"].append(t); r["primary_topics"] += i == 0
        rows.append({"condition": c, "name": cond[c]["name"], "resource": cr["to"], "up_means": cr["up_means"], "half_life_ticks": cond[c]["half_life_ticks"], "iptc": sorted(per.values(), key=lambda r: (-r["primary_topics"], -len(r["topics"]), r["code"])),
                     "n_topics": len(c2t[c]), "status": "derived from the engine's guess, reference"})
    by_res = collections.defaultdict(list); [by_res[r["resource"]].append(r["half_life_ticks"]) for r in rows]
    res = [{"id": r["id"], "name": r["name"], "group": r["group"], "conditions": sorted(x["condition"] for x in rows if x["resource"] == r["id"]), "half_life_ticks": round(sum(by_res[r["id"]]) / len(by_res[r["id"]]), 1) if by_res.get(r["id"]) else None, "status": "guess (engine half-lives, mean over its conditions)"} for r in o["resources"]]
    used = {x["code"] for r in rows for x in r["iptc"]}; l1codes = sorted({v for v in L1.values()})
    l1n = {}; [l1n.setdefault(v, k) for k, v in L1.items()]; l1n.update({"medtop:11000000": "politics and government", "medtop:12000000": "religion"})
    names = {}; l2of = {}
    for q, c in node.items():
        ch = chain(q)
        if c.get("retired") or any(node[x].get("retired") for x in ch): continue
        if len(ch) <= 2: names[q.split(":")[1]] = c["prefLabel"]["en-GB"].lower()
        l2of[q.split(":")[1]] = ch[1].split(":")[1] if len(ch) > 1 else ch[0].split(":")[1]
    for k, v in l1n.items(): names[k.split(":")[1]] = v
    return {"version": "iptc_condition_v0", "status": "derived from the engine's guess (reference): the engine's topic links were hand-set and never fitted. Not a published crosswalk.",
            "label_version": {"iptc_release": mn["iptc_release"], "table": mn["version"]},
            "derived_from": {"ontology": {"file": ONT, "ruleset": o["meta"]["ruleset"], "git_commit": o["meta"]["git_commit"], "sha256": sha(ONT)}, "topic_to_iptc": {"file": "specs/topic_to_iptc_v1.json", "sha256": sha(H + "/specs/topic_to_iptc_v1.json")}, "name_to_code": {"file": "specs/mnds_name_to_code_v1.json", "sha256": sha(H + "/specs/mnds_name_to_code_v1.json")}},
            "rule": "condition <- engine topic_condition <- topic -> topic_to_iptc_v1 names -> mnds_name_to_code_v1 level-1 codes; every IPTC name the topic lists is used (lenient), primary_topics counts topics where it is the first name",
            "rows": rows, "resources": res, "l2_refinements": [], "l2_refinements_note": "add-only rows ('ours, guess', with a changeNote) go here; none in v0 (ledger Q4 open: nothing is promoted)",
            "by_topic": {t: {"name": topics[t], "conditions": sorted(t2c.get(t, []))} for t in sorted(topics)},
            "unlinked_l1": [{"code": c, "name": l1n[c]} for c in l1codes if c not in used and c in l1n], "unmatched_names": miss, "names": names, "l2_of": l2of}
if __name__ == "__main__":
    d = build(); json.dump(d, open(OUT, "w"), indent=1, ensure_ascii=False); n = len(d["rows"])
    print("conditions", n, "resources", len(d["resources"]), "with half-life", sum(1 for r in d["resources"] if r["half_life_ticks"]), "| level-1 codes linked", len({x["code"] for r in d["rows"] for x in r["iptc"]}), "unlinked", [(u["code"], u["name"]) for u in d["unlinked_l1"]], "unmatched", d["unmatched_names"], "->", OUT)
    if "--publish" in sys.argv: os.makedirs(os.path.dirname(PUB), exist_ok=True); shutil.copyfile(OUT, PUB); print("published ->", PUB)
