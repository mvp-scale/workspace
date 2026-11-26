"""check-lexicons: the gate of playbook 00.1 round E (lexicons to data; owner D3 via D55; prediction L3011). Offline, CPU, no model, no service touched.
  X1 data       projects/world-state/lexicons.json loads; every class has pos, means, origin, ledger and one non-empty body (words | map | groups | pairs)
  X2 WordNet    every word is a lemma of its class pos in the local WordNet 3.1 files (exception list + simple suffixes), or sits in not_stated_pos with a reason; a stated other pos (or a phrase head) is checked too
  X3 no words   in claims_v1.py, g4_align.py, concepts_v0.py, developments_v0.py: no moved name is bound to a literal (each comes from lexicons.*), no string literal compared (== / in) is a word of a moved class, NUM_RE holds no amount.units word
  X4 on / off   the modules load the file's words unchanged (on), and every moved name is empty with NUM_RE reading scale units only (KP_LEXICONS=off, separate process)
Run: /workspace/models/embed-zs/.venv/bin/python simulation/check-lexicons.py"""
import sys, os, re, ast, json, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); WS = os.path.join(os.path.dirname(HERE), "projects", "world-state"); sys.path.insert(0, WS); os.chdir(WS)
LEX = os.path.join(WS, "lexicons.json"); WN = "/workspace/data/ontology_src/wordnet/wordnet"
MOVED = {"claims_v1.py": {"HIT_V": "attack.hit_verbs", "ATTACK_V": "attack.attack_verbs", "BLOCK_V": "attack.block_verbs", "BLOCK_PHRASAL": "attack.block_phrasal", "BLOCK_IF_INCOMING": "attack.block_if_incoming_object",
                          "DENY_V": "attack.deny_verbs", "DENIED_N": "attack.denied_object_nouns", "SELF_REPORT_V": "attack.self_report_verbs", "DMG_N": "attack.damage_nouns", "INCOMING_N": "attack.incoming_nouns"},
         "g4_align.py": {"STATUS_VERB": "status.verbs", "CARE_VERB": "status.care_verbs", "CARE_OBJ": "status.care_nouns", "DEAD_OBJ": "status.dead_words", "ALIVE_OBJ": "status.alive_words", "REPORT_PAIRS": "attack.report_pairs"},
         "concepts_v0.py": {"OPPOSE": "relation.oppose_predicates", "KIN": "relation.kinetic_verbs", "STATUS_GROUPS": "change.status_groups", "STATUS_OBJ": "change.status_objects", "UNITS": "amount.units"},
         "developments_v0.py": {"_NOT_FWD": "forward.not_forward_phrases"}}   # round A (L3012): FWD_NOT of developments_v0.py:22
res = []
def ok(name, cond, msg=""): res.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name + (("  " + msg) if msg else ""), flush=True)
def flat(c): return c.get("words") or list(c.get("map", {})) or [w for g in c.get("groups", []) for s in g for w in s] or [w for p in c.get("pairs", []) for w in p[:2]]
J = json.load(open(LEX)); D = J["classes"]; LABELS = {w for k, v in J.get("labels", {}).items() if k != "about" for w in v}   # output class names may appear in code
bad = [k for k, c in D.items() if not all(c.get(f) for f in ("pos", "means", "origin", "ledger")) or sum(1 for b in ("words", "map", "groups", "pairs") if c.get(b)) != 1]
ok("X1 data", not bad, "%d classes, %d words; bad %s" % (len(D), sum(len(flat(c)) for c in D.values()), bad))
idx = {p: {l.split(" ", 1)[0] for l in open("%s/index.%s" % (WN, p)) if not l.startswith(" ")} for p in ("verb", "noun", "adj", "adv")}
exc = {p: dict(l.split()[:2] for l in open("%s/%s.exc" % (WN, p))) for p in ("verb", "noun", "adj")}
def lemma(w, p):
    w = w.replace(" ", "_")
    if w in idx[p] or w in exc.get(p, {}): return True
    return any(w.endswith(s) and w[:-len(s)] + r in idx[p] for s, r in (("s", ""), ("es", ""), ("ed", ""), ("ed", "e"), ("d", ""), ("ing", ""), ("ing", "e")))
miss = []; n = 0
for k, c in D.items():
    if c["pos"] not in idx: continue   # pos 'class' = outcome class names, not words
    ns = c.get("not_stated_pos") or {}
    for w in flat(c):
        n += 1
        if lemma(w, c["pos"]): continue
        x = ns.get(w)
        if not x or not x.get("why"): miss.append("%s:%s (no reason)" % (k, w))
        elif x.get("pos") and not lemma(x.get("head") or w, x["pos"]): miss.append("%s:%s (stated %s not in WordNet)" % (k, w, x["pos"]))
ok("X2 WordNet", not miss, "%d words checked, %d listed with a reason; miss %s" % (n, sum(len(c.get("not_stated_pos") or {}) for c in D.values()), miss))
hits = []
for f, names in MOVED.items():
    t = ast.parse(open(os.path.join(WS, f)).read()); vocab = {w for cls in names.values() if D[cls]["pos"] != "class" for w in flat(D[cls])}
    for nd in ast.walk(t):
        if isinstance(nd, ast.Assign):
            for tg in nd.targets:
                for nm in ([tg] if isinstance(tg, ast.Name) else tg.elts if isinstance(tg, ast.Tuple) else []):
                    if isinstance(nm, ast.Name) and nm.id in names and not (isinstance(nd.value, ast.Call) and ast.unparse(nd.value.func).startswith("LX.")):
                        hits.append("%s:%d %s bound to %s" % (f, nd.lineno, nm.id, type(nd.value).__name__))
        if isinstance(nd, ast.Compare):
            for side in [nd.left] + nd.comparators:
                for s in ([side] if isinstance(side, ast.Constant) else side.elts if isinstance(side, (ast.Tuple, ast.List, ast.Set)) else []):
                    if isinstance(s, ast.Constant) and isinstance(s.value, str) and s.value in vocab - LABELS: hits.append("%s:%d literal %r compared" % (f, nd.lineno, s.value))
src = open(os.path.join(WS, "concepts_v0.py")).read(); m = re.search(r'NUM_RE = re\.compile\((.*)$', src, re.M)
hits += ["concepts_v0.py NUM_RE holds %r" % u for u in D["amount.units"]["words"] if m and re.search(r"\|%s\|" % re.escape(u), m.group(1))]
ok("X3 no words in code", not hits, "%d moved names in 4 files; %s" % (sum(len(v) for v in MOVED.values()), hits or "0 literals"))
PROBE = r"""
import json, sys, lexicons as LX, claims_v1 as A, g4_align as G, concepts_v0 as K, developments_v0 as V
M = json.loads(sys.argv[1]); out = {}
def canon(v):
    if isinstance(v, dict): return sorted([canon(k), canon(x)] for k, x in v.items())
    if isinstance(v, (set, frozenset)): return sorted(canon(x) for x in v)
    if isinstance(v, (list, tuple)): return [canon(x) for x in v]
    return v
for f, mod in (("claims_v1.py", A), ("g4_align.py", G), ("concepts_v0.py", K), ("developments_v0.py", V)):
    for nm in M[f]: out[nm] = canon(getattr(mod, nm))
out["_num"] = sorted(map(str, K._amounts("5 dead, 3 million, 12 ships, 40%"))); out["_state"] = LX.state(); out["_fwdnot"] = [bool(V.FWD_NOT.search(s)) for s in ("They struck without warning.", "the early warning radar", "Warning systems failed.", "Iran will retaliate.")]
print("PROBE " + json.dumps(out))"""
def probe(mode):
    r = subprocess.run([sys.executable, "-c", PROBE, json.dumps(MOVED)], cwd=WS, capture_output=True, text=True, env={**os.environ, "KP_LEXICONS": mode, "PYTHONHASHSEED": "0", "CUDA_VISIBLE_DEVICES": ""})
    ln = [l for l in r.stdout.splitlines() if l.startswith("PROBE ")]
    return json.loads(ln[0][6:]) if ln else {"_err": r.stderr[-400:]}
on, off = probe("on"), probe("off")
def want(cls):
    """the file's body in the probe's canonical form (sets sorted, tuples as lists)"""
    c = D[cls]
    if "map" in c: return sorted([k, v] for k, v in c["map"].items())
    if "groups" in c: return [[sorted(a), sorted(b)] for a, b in c["groups"]]
    if "pairs" in c: return sorted([[p[0], p[1]], p[2]] for p in c["pairs"]) if len(c["pairs"][0]) == 3 else sorted(p for p in c["pairs"])
    return sorted(c["words"])
diff = [nm for f, names in MOVED.items() for nm, cls in names.items() if nm != "UNITS" and on.get(nm) != want(cls)]
ok("X4a lexicons on", on.get("_state") == "on" and not diff and "(5.0, 'dead')" in on.get("_num", []) and on.get("_fwdnot") == [True, True, True, False], "names equal to the file: %s; amounts %s %s" % (diff or "all", on.get("_num"), on.get("_err", "")))
full = [nm for names in MOVED.values() for nm in names if off.get(nm)]
ok("X4b lexicons off", off.get("_state") == "off" and not full and off.get("_fwdnot") == [False] * 4 and off.get("_num") == sorted(map(str, {(5.0, ""), (3000000.0, ""), (12.0, ""), (40.0, "pct")})), "non-empty %s; amounts %s %s" % (full or "none", off.get("_num"), off.get("_err", "")))
print("%d/%d PASS" % (sum(res), len(res))); sys.exit(0 if all(res) else 1)
