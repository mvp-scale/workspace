"""Mutation test of the verification layers. F = hand fixtures, O = Lean exact oracle (built from FitChecks.lean). Prediction: ledger L519."""
import re, json, random, subprocess, time, itertools, collections, os
HERE = os.path.dirname(os.path.abspath(__file__)); SRC = open(os.path.join(HERE, "..", "fitness_screen.py")).read()
ALPHA = re.search(r"def alpha\(.*?\n(?=\ndef status)", SRC, re.S).group(0)
STATUS = re.search(r"def status\(.*?\n(?=\ndef screen)", SRC, re.S).group(0)
HDR = "import collections, itertools\n\n"
MUT = {  # name: (function, old, new)
 "alpha_m1": ("alpha", "1 / (m - 1)", "1 / m"),
 "alpha_m2": ("alpha", "(n * (n - 1))", "(n * n)"),
 "alpha_m3": ("alpha", "round(1 - Do / De, 3)", "round(1 + Do / De, 3)"),
 "alpha_m4": ("alpha", "n += m", "n += 1"),
 "alpha_m5": ("alpha", "round(1 - Do / De, 3)", "round(1 - Do / De, 1)"),
 "alpha_m6": ("alpha", "if m < 2: continue", "if m < 3: continue"),
 "alpha_m7": ("alpha", "0 if a == b else 1", "1 if a == b else 0"),
 "status_m1": ("status", "top > len(u) / 2", "top >= len(u) / 2"),
}
code = {"alpha_base": ("alpha", ALPHA), "status_base": ("status", STATUS)}
for k, (fn, old, new) in MUT.items():
    base = ALPHA if fn == "alpha" else STATUS
    assert base.count(old) == 1, (k, base.count(old)); code[k] = (fn, base.replace(old, new))
for k, (fn, txt) in code.items(): open(os.path.join(HERE, "mutants", k + ".py"), "w").write(HDR + txt)
def fn_of(k):
    ns = {}; exec(HDR + code[k][1], ns); return ns[code[k][0]]
# F: hand fixtures (alpha) -- no status fixtures existed
def fixtures(alpha):
    try: return _fixtures(alpha)
    except Exception: return False
def _fixtures(alpha):
    random.seed(1); u = [[random.choice("AB"), random.choice("AB")] for _ in range(20000)]
    chk = [alpha([["A","A"]]*5 + [["B","B"]]*5) == 1.0, alpha([["A","A"]]*4 + [["B","B"]]*4 + [["A","B"]]*2) == 0.62,
           abs(alpha(u)) < 0.02, alpha([["A","A"]]*10) is None, alpha([["A","B"]]*5 + [["B","A"]]*5) == -0.9,
           alpha([[1,1],[2,2],[3,3],[1,2]], True) > alpha([[1,1],[2,2],[3,3],[1,3]], True)]
    return all(chk)
# O: Lean oracle
t0 = time.time(); random.seed(7)
cases = []
while len(cases) < 300:
    a, b, d = random.randint(0, 20), random.randint(0, 20), random.randint(0, 20)
    if a + b + d >= 2 and (2*a + d) > 0 and (2*b + d) > 0: cases.append((a, b, d))
vecs = list(itertools.product(range(4), repeat=4))
lean = open(os.path.join(HERE, "FitChecks.lean")).read()
lean += "\n" + "\n".join(f"#eval s!\"A {a} {b} {d} {num(a,b,d)} {den(a,b,d)}\"" if False else "" for a, b, d in []) 
ev = "\n#eval (" + "[" + ",".join(f"({a},{b},{d})" for a, b, d in cases) + "] : List (Nat × Nat × Nat)).map (fun (a, b, d) => s!\"A {a} {b} {d} {num a b d} {den a b d}\")\n"
ev += "#eval (List.finRange 4).flatMap (fun a => (List.finRange 4).flatMap (fun b => (List.finRange 4).flatMap (fun c => (List.finRange 4).map (fun d => s!\"S {a} {b} {c} {d} {if status [a,b,c,d] = .unanimous then 0 else if status [a,b,c,d] = .majority then 1 else 2}\"))))\n"
p = os.path.join(HERE, "..", "runs", "pulse", "oracle.lean"); open(p, "w").write(lean + ev)
out = subprocess.run(["lean", p], capture_output=True, text=True, timeout=300).stdout
T_lean = time.time() - t0
orc = {"A": [], "S": []}
for line in re.findall(r'"([AS] [^"]+)"', out):
    t = line.split(); orc[t[0]].append(t[1:])
assert len(orc["A"]) == 300 and len(orc["S"]) == 256, (len(orc["A"]), len(orc["S"]))
def oracle(k):
    try: return _oracle(k)
    except Exception: return False
def _oracle(k):
    fn = fn_of(k)
    if code[k][0] == "alpha":
        for a, b, d, n, dn in orc["A"]:
            a, b, d, n, dn = map(int, (a, b, d, n, dn))
            units = [["A","A"]]*a + [["B","B"]]*b + [["A","B"]]*d
            got = fn(units)
            if got is None or abs(got - n/dn) > 0.0006: return False
        return True
    for *v, s in orc["S"]:
        v = list(map(int, v)); want = ["unanimous", "majority", "split"][int(s)]
        if fn(v) != want: return False
    return True
res = {}
for k in code:
    fn = fn_of(k); t1 = time.time()
    f = fixtures(fn) if code[k][0] == "alpha" else None
    o = oracle(k)
    res[k] = {"fixtures_pass": f, "oracle_pass": o}
for k in code:
    if k.endswith("base"): continue
    r = res[k]; r["caught_by_fixtures"] = (r["fixtures_pass"] is False); r["caught_by_oracle"] = (r["oracle_pass"] is False)
res["_timing_s"] = {"lean_oracle_build_and_eval": round(T_lean, 1)}
json.dump(res, open(os.path.join(HERE, "..", "runs", "pulse", "mutation_FO.json"), "w"), indent=1)
for k, r in res.items(): print(k, r)
