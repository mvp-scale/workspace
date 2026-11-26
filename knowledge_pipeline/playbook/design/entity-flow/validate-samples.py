#!/usr/bin/env python3
"""validate-samples.py: validate sample-*.json against entity-flow.schema.json (jsonschema, draft 2020-12) and check referential integrity (every id reference resolves)."""
import json, sys, glob, os
from jsonschema import Draft202012Validator
H = os.path.dirname(os.path.abspath(__file__)); S = json.load(open(os.path.join(H, "entity-flow.schema.json"))); V = Draft202012Validator(S); Draft202012Validator.check_schema(S)
bad = 0
for f in sorted(glob.glob(os.path.join(H, "sample-*.json"))):
    b = json.load(open(f)); errs = sorted(V.iter_errors(b), key=lambda e: list(e.absolute_path))[:5]
    ref = []
    A = {a["id"] for a in b["articles"]}; F = {x["id"] for x in b["facts"]}; E = {e["id"] for e in b["entities"]}; FR = {x["id"] for x in b["fragments"]}; P = {p["id"] for p in b["publishers"]}
    def chk(name, bad_n, total): ref.append("%s: %d unresolved of %d" % (name, bad_n, total))
    chk("articles.publisher", sum(a["publisher"] not in P for a in b["articles"]), len(b["articles"]))
    chk("fragments.article_id", sum(x["article_id"] not in A for x in b["fragments"]), len(b["fragments"]))
    ev = [e for x in b["facts"] for e in x["evidence"]]
    chk("facts.evidence.article_id", sum(e["article_id"] not in A for e in ev), len(ev)); chk("facts.evidence.fragment_id (null allowed)", sum(bool(e["fragment_id"]) and e["fragment_id"] not in FR for e in ev), len(ev))
    chk("links.a/b", sum(l["a"] not in E or l["b"] not in E for l in b["links"]), len(b["links"]))
    isres = lambda i: i.startswith("resource:")
    chk("links.edge_ids (links with no resource end)", sum(i not in F for l in b["links"] if not (isres(l["a"]) or isres(l["b"])) for i in l["edge_ids"]), sum(len(l["edge_ids"]) for l in b["links"] if not (isres(l["a"]) or isres(l["b"]))))
    chk("links.edge_ids (links to a resource row; KNOWN GAP: resource-state edges are not in /api/raw/knowledge edges)", sum(i not in F for l in b["links"] if (isres(l["a"]) or isres(l["b"])) for i in l["edge_ids"]), sum(len(l["edge_ids"]) for l in b["links"] if (isres(l["a"]) or isres(l["b"]))))
    chk("contests.a/b", sum(c["a"] not in F or c["b"] not in F for c in b["contests"]), len(b["contests"]))
    chk("timeline.concept", sum(t["concept"] not in E for t in b["timeline"]), len(b["timeline"])); chk("timeline.edge_id", sum(t["edge_id"] not in F for t in b["timeline"]), len(b["timeline"]))
    chk("changes.article_id", sum(c["article_id"] not in A for c in b["changes"]), len(b["changes"]))
    chk("entities.edge_ids (non-resource)", sum(i not in F for e in b["entities"] if e["kind"] != "resource" for i in e.get("edge_ids", [])), sum(len(e.get("edge_ids", [])) for e in b["entities"] if e["kind"] != "resource"))
    chk("entities.edge_ids (resource rows; KNOWN GAP, same cause)", sum(i not in F for e in b["entities"] if e["kind"] == "resource" for i in e.get("edge_ids", [])), sum(len(e.get("edge_ids", [])) for e in b["entities"] if e["kind"] == "resource"))
    print(os.path.basename(f), "schema errors:", len(list(V.iter_errors(b))), "| size", os.path.getsize(f)); [print("  ERR", list(e.absolute_path), e.message[:160]) for e in errs]
    [print("  ref", r) for r in ref]; bad += len(errs)
sys.exit(1 if bad else 0)
