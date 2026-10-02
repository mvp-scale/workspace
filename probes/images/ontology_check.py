"""Validate an ontology file against ONTOLOGY-SCHEMA.md.
    /workspace/kev/.venv/bin/python ontology_check.py bone      # prints PASS or the problems
"""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).parent
BAD = re.compile(r"\b(free of|not|without|absence of|absent|no sign of|suspicious|abnormal-looking|concerning|severe|nice|obviously)\b", re.I)
START = re.compile(r"^(Is|Are|Does|Do|Can|Has|Have|Was|Were)\b")


def walk(fams, depth=1):
    for f in fams:
        yield f, depth
        yield from walk(f.get("children", []), depth + 1)


def check(name):
    errs = []; warn = []
    p = HERE / "cascades" / "v3" / f"{name}.json"
    if not p.is_file(): return [f"missing {p}"], []
    o = json.loads(p.read_text())
    for k in ("task", "title", "status", "pilot", "classes", "state_gate", "state_after_gate", "gate", "families"):
        if k not in o: errs.append(f"missing key {k}")
    if errs: return errs, warn
    if len(o["gate"]) != 10: errs.append(f"gate has {len(o['gate'])} questions, need 10")
    fams = o["families"]
    if not 8 <= len(fams) <= 14: errs.append(f"{len(fams)} root families, need 8 to 14")
    if sum(1 for f in fams if f.get("children")) < 4: errs.append("fewer than 4 root families have children")
    rootq = sum(len(f["probes"]) for f in fams)
    if rootq > 40: errs.append(f"{rootq} root probes, limit 40")
    ids, qs = [], []
    for g in o["gate"]:
        ids.append(g["id"]); qs.append(("gate", g["q"]))
        if g.get("pass") not in ("yes", "no"): errs.append(f"gate {g['id']} needs pass yes or no")
    cl = set(o["classes"])
    if "map" in o and set(o["map"].values()) != cl: errs.append("map values must equal classes")
    for f, d in walk(fams):
        if d > 3: errs.append(f"{f['id']} deeper than 3")
        n = len(f.get("probes", []))
        if d == 1 and n not in (2, 3): errs.append(f"{f['id']} root family has {n} probes, need 2 or 3")
        if d > 1 and not 4 <= n <= 6: errs.append(f"{f['id']} child has {n} probes, need 4 to 6")
        for k in f.get("supports", {}):
            if k not in cl: errs.append(f"{f['id']} supports unknown class {k}")
        for q in f["probes"]:
            ids.append(q["id"]); qs.append((f["id"], q["q"]))
    for where, q in qs:
        if not START.match(q) or not q.endswith("?"): errs.append(f"{where}: must start with Is/Are/Does/Do/Can/Has/Have and end with ?: {q[:60]}")
        if len(q) > 140: errs.append(f"{where}: over 140 characters: {q[:60]}")
        if BAD.search(q): errs.append(f"{where}: negative or subjective wording ({BAD.search(q).group(0)}): {q[:70]}")
        if q.count(" and ") + q.count(" or ") >= 2: warn.append(f"{where}: possibly not atomic: {q[:70]}")
    if len(ids) != len(set(ids)): errs.append("duplicate ids")
    pf = HERE / "pilots" / f"{o['pilot']}.jsonl"
    if not pf.is_file(): errs.append(f"missing pilot file {pf}")
    else:
        items = [json.loads(l) for l in pf.read_text().split("\n") if l.strip()]
        if not 40 <= len(items) <= 100: errs.append(f"pilot has {len(items)} images, need 40 to 100")
        from collections import Counter
        c = Counter(i["expected"] for i in items); top = max(c.values()) / len(items); lim = 0.55 if len(c) == 2 else 0.40
        if top > lim: errs.append(f"pilot class balance {dict(c)}: largest share {top:.2f} over {lim}")
        for i in items[:3]:
            if not Path(i["image"]).is_file(): errs.append(f"image missing {i['image']}")
        for f, _ in walk(fams):
            t = f.get("truth")
            if t:
                miss = sum(t["meta"] not in i.get("meta", {}) for i in items)
                if miss > 0.1 * len(items): errs.append(f"{f['id']} truth meta '{t['meta']}' missing on {miss} items")
        if not any(i.get("meta") for i in items): errs.append("pilot items have no meta")
        if not any(f.get("truth") for f, _ in walk(fams)): warn.append("no family has a truth binding, so detection ability cannot be scored")
    total = sum(len(f["probes"]) for f, _ in walk(fams)) + 10
    warn.append(f"{len(fams)} root families, {rootq} breadth probes, {total} questions in the whole tree")
    return errs, warn


if __name__ == "__main__":
    for n in sys.argv[1:]:
        e, w = check(n)
        print(("PASS " if not e else "FAIL ") + n)
        for x in e: print("  problem:", x)
        for x in w: print("  note:", x)
