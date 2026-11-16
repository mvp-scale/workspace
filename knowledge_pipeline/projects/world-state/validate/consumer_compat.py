"""consumer_compat (T150 P1): static scan (ast, read-only) of every importer of facts_lib and analyze2 for sites an add-only change could break. Nothing is executed or imported.
Importers: any .py under knowledge_pipeline that imports facts_lib or analyze2 (import x, import x as y, from x import ..., __import__('x')); plus the definition files facts_lib.py and stated_facts.py (the status loop lives there); plus second-hop files that import a direct importer and have a risky site (pool_build.py imports extract).
Kinds (risk): unpack_read (high): a tuple target assigned from a .read( call, so a 4th return value breaks it. unpack_facts_for (high): a tuple target from facts_for(...), which returns (out, ind, doc). checks_all_values (high): all(<checks>.values()), so a new key inside "checks" flips the status (facts_lib.py status loop, pool_build.py). checks_read (medium): any ["checks"] or .get("checks"). item_rebuild (medium): a dict literal with 3 or more fact/item keys (kind, s, e, text, value, unit, noun, verb, checks, status, span, tool, version, strength) or a dict comprehension picking fixed keys from a tuple of strings: a new key is dropped silently, or breaks a schema built from it. fixed_key_tuple (low): a tuple of 3 or more subscripts with fixed item keys (pure reads, add-only safe). json_roundtrip (medium): json.dump(s) of a value derived from facts_for/analyze/read in the same scope, so a fixed-key reader of the file (or a stored frozen copy) sees the new keys. json.load sites are not listed: they read inputs, not these outputs. Taint is by name assignment, one scope level, so it can miss and over-report; every site lists its source line for a human check.
Output: runs/pulse/validate/consumer_sites.json (importers, sites with file, line, kind, risk, snippet) and a count by kind on stdout. Exit 0 always (it is a survey, not a gate).
    /workspace/models/embed-zs/.venv/bin/python validate/consumer_compat.py [--root /workspace/knowledge_pipeline]   (from projects/world-state)"""
import ast, sys, os, json, pathlib, argparse, collections
WS = pathlib.Path(__file__).resolve().parents[1]; MODS = ("facts_lib", "analyze2")
ITEM_KEYS = {"kind", "s", "e", "text", "value", "unit", "noun", "verb", "checks", "status", "span", "tool", "version", "strength"}
RISK = {"unpack_read": "high", "unpack_facts_for": "high", "checks_all_values": "high", "checks_read": "medium", "item_rebuild": "medium", "json_roundtrip": "medium", "fixed_key_tuple": "low"}
def const(n): return n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) else None
def src_of(lines, n): return lines[n.lineno - 1].strip()[:160]
def importer_aliases(tree):
    al = {}; mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split(".")[-1] in MODS: al[a.asname or a.name] = a.name.split(".")[-1]; mods.add(a.name.split(".")[-1])
        elif isinstance(n, ast.ImportFrom) and n.module and n.module.split(".")[-1] in MODS: mods.add(n.module.split(".")[-1])
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "__import__" and n.args and const(n.args[0]) in MODS: mods.add(const(n.args[0]))
    return al, mods
def names_in(n): return {x.id for x in ast.walk(n) if isinstance(x, ast.Name)}
def scan_file(path, root, extra=(), force=False):
    try: tree = ast.parse(open(path, encoding="utf-8").read())
    except Exception as ex: return None, []
    al, mods = importer_aliases(tree)
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for nm in ([a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""] + [a.name for a in n.names]):
                if nm.split(".")[-1] in extra: mods.add("via:" + nm.split(".")[-1])
    if force: mods.add("definition")
    if not mods: return None, []
    lines = open(path, encoding="utf-8").read().split("\n"); sites = []; rel = str(path.relative_to(root))
    def add(kind, n): sites.append({"file": rel, "line": n.lineno, "kind": kind, "risk": RISK[kind], "snippet": src_of(lines, n)})
    src_calls = lambda e: any(isinstance(c, ast.Call) and ((isinstance(c.func, ast.Attribute) and c.func.attr in ("facts_for", "analyze", "read", "read_detail")) or (isinstance(c.func, ast.Name) and c.func.id in ("facts_for",))) for c in ast.walk(e))
    scopes = [tree] + [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]; taint_seen = set(); checks_names = {}
    for sc in scopes:
        tainted = set(); cn = set(); body = list(ast.walk(sc)) if sc is tree else list(ast.walk(sc))
        for n in body:
            if isinstance(n, ast.Assign):
                if src_calls(n.value) or names_in(n.value) & tainted:
                    for t in n.targets: tainted |= names_in(t)
                v = n.value
                if (isinstance(v, ast.Subscript) and const(v.slice) == "checks") or (isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) and v.func.attr == "get" and v.args and const(v.args[0]) == "checks"):
                    for t in n.targets: cn |= names_in(t)
            elif isinstance(n, (ast.For, ast.comprehension)):
                it = n.iter
                if src_calls(it) or names_in(it) & tainted: tainted |= names_in(n.target)
        for n in body:
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("dump", "dumps") or (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("dump", "dumps") and isinstance(n.func.value, ast.Name) and n.func.value.id == "json"):
                if n.args and (names_in(n.args[0]) & tainted or src_calls(n.args[0])) and (n.lineno, "json_roundtrip") not in taint_seen: taint_seen.add((n.lineno, "json_roundtrip")); add("json_roundtrip", n)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "all" and n.args and isinstance(n.args[0], ast.Call) and isinstance(n.args[0].func, ast.Attribute) and n.args[0].func.attr == "values":
                tgt = n.args[0].func.value
                if (isinstance(tgt, ast.Name) and tgt.id in cn) or (isinstance(tgt, ast.Subscript) and const(tgt.slice) == "checks") or (isinstance(tgt, ast.Name) and tgt.id in ("c", "checks")):
                    if (n.lineno, "checks_all_values") not in taint_seen: taint_seen.add((n.lineno, "checks_all_values")); add("checks_all_values", n)
    seen = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], (ast.Tuple, ast.List)) and isinstance(n.value, ast.Call):
            f = n.value.func; nm = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
            if nm == "read" and not any(isinstance(x, ast.Subscript) for x in [n.value]): add("unpack_read", n)
            elif nm == "facts_for": add("unpack_facts_for", n)
        if isinstance(n, ast.Subscript) and const(n.slice) == "checks" and ("checks_read", n.lineno) not in seen: seen.add(("checks_read", n.lineno)); add("checks_read", n)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "get" and n.args and const(n.args[0]) == "checks" and ("checks_read", n.lineno) not in seen: seen.add(("checks_read", n.lineno)); add("checks_read", n)
        if isinstance(n, ast.Dict):
            ks = {const(k) for k in n.keys if k is not None} & ITEM_KEYS
            if len(ks) >= 3 and ("item_rebuild", n.lineno) not in seen: seen.add(("item_rebuild", n.lineno)); add("item_rebuild", n)
        if isinstance(n, ast.DictComp) and any(isinstance(g.iter, (ast.Tuple, ast.List)) and len(g.iter.elts) >= 3 and all(const(x) for x in g.iter.elts) for g in n.generators) and ("item_rebuild", n.lineno) not in seen:
            seen.add(("item_rebuild", n.lineno)); add("item_rebuild", n)
        if isinstance(n, ast.Tuple) and len(n.elts) >= 3 and sum(1 for x in n.elts if isinstance(x, ast.Subscript) and const(x.slice) in ITEM_KEYS) >= 3 and ("fixed_key_tuple", n.lineno) not in seen: seen.add(("fixed_key_tuple", n.lineno)); add("fixed_key_tuple", n)
    return {"file": rel, "imports": sorted(mods)}, sites
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--root", default=str(WS.parents[1])); ap.add_argument("--out", default=str(WS / "runs/pulse/validate/consumer_sites.json")); a = ap.parse_args(); root = pathlib.Path(a.root); imps = []; sites = []
    allp = [p for p in sorted(root.rglob("*.py")) if not any(x in p.parts for x in ("__pycache__", ".venv", "node_modules", "validate"))]; direct = set()
    for p in allp:
        i, s = scan_file(p, root, force=p.name in ("facts_lib.py", "stated_facts.py"))
        if i: imps.append(i); sites += s; direct.add(p.stem)
    for p in allp:   # second hop: files that import a direct importer (pool_build imports extract, which imports facts_lib)
        if p.stem in direct: continue
        i, s = scan_file(p, root, extra=direct)
        if i and s: imps.append(i); sites += s
    cnt = collections.Counter(s["kind"] for s in sites); files = collections.Counter(s["file"] for s in sites)
    rep = {"root": str(root), "importers": imps, "n_importers": len(imps), "importers_of": {m: sum(1 for i in imps if m in i["imports"]) for m in MODS}, "indirect_only": [i["file"] for i in imps if not set(i["imports"]) & set(MODS) and "definition" not in i["imports"]], "definition_files": [i["file"] for i in imps if "definition" in i["imports"]], "count_by_kind": dict(cnt), "risk_of_kind": RISK, "sites": sites, "note": "heuristic ast scan, read-only; the planner's grep counted 13 importers of facts_lib plus analyze2, and 20 of analyze2 (19 here plus server.py)"}
    os.makedirs(os.path.dirname(a.out), exist_ok=True); json.dump(rep, open(a.out, "w"), indent=1)
    print("scanned files with sites or imports: %d (direct importers: facts_lib %d, analyze2 %d; definition files %d; second-hop with sites %d); risky-site rows: %d" % (len(imps), rep["importers_of"]["facts_lib"], rep["importers_of"]["analyze2"], len(rep["definition_files"]), len(rep["indirect_only"]), len(sites)))
    for k, v in sorted(cnt.items(), key=lambda kv: (RISK[kv[0]] != "high", RISK[kv[0]] != "medium", -kv[1])): print("  %-18s %-6s %3d" % (k, RISK[k], v))
    print("high-risk sites:"); [print("  %s:%d  %s  | %s" % (s["file"], s["line"], s["kind"], s["snippet"][:90])) for s in sites if s["risk"] == "high"]; print("wrote", a.out)
