"""check-educate: done-check for G6 educate v0 (projects/world-state/educate.py; lean wave 0 item I, L2868). Structural only: no model, no hosted call, nothing written except a temp folder (the tick log and resource state are built there from the v7 trace, as check-consolidate.py does). CPU only.
    python3 simulation/check-educate.py [--trace <trace folder>]
Checks (each prints PASS or FAIL):
  fixture    : 5 questions (a resource, a country, a resource in a country, two entities) each resolve to the expected kind and give all six sections non-empty
  pointers   : 100 percent of statements carry >= 1 pointer (fragment: article id and publisher; the one seed-row statement: the seed row); checked on the fixture and on a sweep of every resource, every country and 60 entities
  templates  : 0 untemplated text paths: every statement's template is in TEMPLATES and its text equals the template rendered from its slots plus the fixed suffix; every string slot value occurs in the stored data; exactly one place in educate.py assigns a statement text; every statement says weights equal PROVISIONAL (T178)
  abstain    : 2 questions that match nothing give the abstain line and 0 statements
  determinism: the same question twice gives the same sha256; the inputs are not changed (sha256 of the consolidated body before and after)
  no models  : educate.py imports no network, model or hosted-client module"""
import sys, os, json, ast, hashlib, subprocess, tempfile, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); WS = os.path.join(ROOT, "projects", "world-state"); sys.path.insert(0, WS)
import consolidate as C, educate as ED
opt = lambda f: sys.argv[sys.argv.index(f) + 1] if f in sys.argv else None
TRACE = opt("--trace") or "/workspace/demo/mockups/structure-live/runs-v7/trace"
bad = []
def ck(name, ok, detail=""):
    print("%s %s %s" % ("PASS" if ok else "FAIL", name, detail)); bad.extend([] if ok else [name])
tmp = tempfile.mkdtemp(prefix="educate-check-"); PYNP = "/workspace/models/embed-zs/.venv/bin/python" if os.path.exists("/workspace/models/embed-zs/.venv/bin/python") else sys.executable
r = subprocess.run([PYNP, os.path.join(WS, "ledger_split.py"), TRACE, "--state", tmp + "/state.json", "--persist", tmp + "/ticks.jsonl", "--state-only"], capture_output=True, text=True, cwd=WS)
if r.returncode: print("state could not be built:", r.stderr[-400:]); sys.exit(1)
import glob
g4 = [os.path.join(ROOT, "runs", "g4", "store.jsonl")] + sorted(glob.glob(os.path.join(ROOT, "runs", "g4", "archive", "store.jsonl-*")))
body = C.seal(C.consolidate(C.load_trace(TRACE), [C.load_g4(p) for p in g4 if os.path.exists(p)], C.load_ticks(tmp + "/ticks.jsonl")))
state = json.load(open(tmp + "/state.json")); seed = ED.load_seed(ED.SEED); sha0 = hashlib.sha256(ED.canon(body).encode()).hexdigest()
IX = ED.Index(body, state, seed)
print("inputs: %d edges (%d assertion, %d resource), %d resource-state rows, %d seed resources, consolidated sha256 %s" % (len(body["edges"]), body["counts"]["assertion_edges"], body["counts"]["resource_edges"], len(state["states"]), len(seed), body["sha256"][:16]))
# ---------- fixture ----------
FIX = [("What is happening with housing_stock?", "resource"), ("What is going on in US?", "country"), ("What is state_capacity in GB?", "resource-country"), ("Who is Tom Kearney?", "entity"), ("What does unemployment rate mean here?", "entity")]
ans = {q: ED.answer(IX, q) for q, _ in FIX}
for q, kind in FIX:
    a = ans[q]; ok = a["resolved"] is not None and a["resolved"]["kind"] == kind and all(a["sections"][s] for s in ED.SECTIONS)
    ck("fixture: %r resolves as %s, six sections non-empty" % (q, kind), ok, "%s, %d statements" % ((a["resolved"] or {}).get("label"), a["statements"]))
# ---------- pointers ----------
def pointer_ok(st):
    if not st["refs"] or st["refs_total"] < 1: return False
    return all(rf["art"] and (rf["pub"] or st.get("pointer_kind") == "seed-row") for rf in st["refs"])
def stmts(a): return [st for s in ED.SECTIONS for st in a["sections"][s]]
sweep = [r_ for r_ in IX.res] + [c for c in IX.countries] + [k for k in sorted(IX.labels)[:: max(1, len(IX.labels) // 60)]]
qs = [("resource:%s" % x) if x in IX.res else ("country:%s" % x) if x in IX.countries else x for x in sweep]; allst = []; unresolved = []
for q in qs:
    a = ED.answer(IX, q)
    if a["resolved"] is None: unresolved.append(q)
    allst += stmts(a)
allst_f = [st for a in ans.values() for st in stmts(a)]
ck("pointers: 100 percent of fixture statements carry a source pointer", all(pointer_ok(st) for st in allst_f), "%d statements" % len(allst_f))
ck("pointers: 100 percent of sweep statements carry a source pointer", all(pointer_ok(st) for st in allst) and len(allst) > 0, "%d statements over %d questions (%d did not resolve: %s)" % (len(allst), len(qs), len(unresolved), unresolved[:3]))
ck("pointers: every statement states a publisher count", all(isinstance(st["publishers_n"], int) and st["publishers_basis"] for st in allst + allst_f))
# ---------- templates ----------
def strings(o):   # every string in the stored data, unescaped
    if isinstance(o, str): yield o
    elif isinstance(o, dict): yield from (x for k, v in o.items() for x in (strings(k), strings(v)) for x in x)
    elif isinstance(o, (list, tuple)): yield from (x for v in o for x in strings(v))
corpus = "\n".join(strings(body)) + "\n" + "\n".join(strings(state)) + "\n" + "\n".join(strings(seed))
def slot_ok(k, v):
    if not isinstance(v, str) or v == "-": return True
    if k == "label" and " in " in v and v.split(" in ")[0] in IX.res and v.split(" in ")[1] in IX.countries: return v == ED.render("label.pair", {"resource": v.split(" in ")[0], "country": v.split(" in ")[1]})   # a resource-in-country label, built by the label.pair template
    if k == "names": return all(p.strip() in corpus for p in v.split(", ") if not p.startswith("+"))
    return v in corpus
untemp = []
for st in allst + allst_f:
    t = st["tpl"]
    if t not in ED.TEMPLATES or st["text"] != ED.render(t, st["slots"]) + ED.SUFFIX.format(refs_total=st["refs_total"], publishers_n=st["publishers_n"], basis=st["publishers_basis"]): untemp.append(st["text"][:60])
    elif not all(slot_ok(k, v) for k, v in st["slots"].items()): untemp.append("slot %s" % [(k, v) for k, v in st["slots"].items() if not slot_ok(k, v)])
ck("templates: 0 untemplated statements (text = template + slots + suffix; string slots occur in the stored data)", not untemp, "%d checked, %d untemplated %s" % (len(allst) + len(allst_f), len(untemp), untemp[:2]))
src = open(os.path.join(WS, "educate.py"), encoding="utf-8").read(); tree = ast.parse(src)
sets = [n for n in ast.walk(tree) if isinstance(n, ast.Assign) and any(isinstance(t_, ast.Subscript) and isinstance(t_.slice, ast.Constant) and t_.slice.value == "text" for t_ in n.targets)]
ck("templates: one place assigns a statement text, and it goes through render()", len(sets) == 1 and "render(" in ast.unparse(sets[0]), "%d assignment(s)" % len(sets))
ck("templates: every statement names the weights as equal PROVISIONAL (T178)", all("PROVISIONAL" in st["weights"] and "T178" in st["weights"] and "T178" in st["text"] for st in allst + allst_f))
used = {st["tpl"] for st in allst + allst_f}; print("info: templates used %d of %d (unused: %s)" % (len(used), len(ED.TEMPLATES), sorted(set(ED.TEMPLATES) - used - {"abstain"})))
# ---------- abstain ----------
for q in ["What is the capital of Atlantis?", "zzzzzz qqqq"]:
    a = ED.answer(IX, q); ck("abstain: %r gives the abstain line and 0 statements" % q, a["resolved"] is None and a["statements"] == 0 and a["abstain"] == ED.render("abstain", {"question": json.dumps(q)}))
# ---------- determinism, read-only ----------
q0 = FIX[0][0]; h = lambda a: hashlib.sha256(ED.canon(a).encode()).hexdigest()
ck("determinism: same question twice, same sha256", h(ED.answer(IX, q0)) == h(ED.answer(IX, q0)), h(ans[q0])[:16])
ck("read-only: the consolidated body is unchanged after all answers", hashlib.sha256(ED.canon(body).encode()).hexdigest() == sha0)
bad_imp = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for m in ([a_.name for a_ in n.names] if isinstance(n, ast.Import) else [n.module or ""]) if m.split(".")[0] in {"requests", "urllib", "http", "socket", "anthropic", "openai", "torch", "transformers", "httpx", "aiohttp", "numpy"}]
ck("no models: educate.py imports no network, model or hosted-client module", not bad_imp)
# ---------- sample ----------
print("\nSAMPLE ANSWER (%s):\n%s" % (q0, ED.as_text(ans[q0])[:3500]))
print("\n%s: %d check(s) failed %s" % ("FAIL" if bad else "ALL PASS", len(bad), bad)); sys.exit(1 if bad else 0)
