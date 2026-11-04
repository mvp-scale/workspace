"""Replication of the mutation test with MECHANICALLY generated mutants (prediction: ledger L521).
Functions: alpha() (fitness_screen.py) and pair_stats() (sourced_checks_test.py). Methods: F hand fixtures, O Lean oracle."""
import re, io, os, json, random, tokenize, subprocess, collections, itertools, math, time
HERE = os.path.dirname(os.path.abspath(__file__)); W = os.path.join(HERE, "..")
rd = lambda p: open(os.path.join(W, p)).read()
FS, SC = rd("fitness_screen.py"), rd("sourced_checks_test.py")
SRC = {"alpha": re.search(r"def alpha\(.*?\n(?=\ndef status)", FS, re.S).group(0),
       "pair_stats": re.search(r"def pair_stats\(.*?\n(?=out = )", SC, re.S).group(0)}
HDR = "import collections, itertools, math\n\n"
def load(src, name):
    ns = {}; exec(HDR + src, ns); return ns[name]
OPS = {"+": "-", "-": "+", "*": "/", "/": "*", "==": "!=", "!=": "==", "<": "<=", ">": ">=", "<=": "<", ">=": ">"}
def mutants(src):
    out = []; toks = list(tokenize.generate_tokens(io.StringIO(src).readline)); lines = src.split("\n")
    for t in toks:
        if t.start[0] == 1: continue  # signature line
        rep = None
        if t.type == tokenize.OP and t.string in OPS: rep = OPS[t.string]
        elif t.type == tokenize.NUMBER and re.fullmatch(r"\d+", t.string): rep = str(int(t.string) + 1)
        if rep is None: continue
        (r, c), (r2, c2) = t.start, t.end; L = lines[r - 1]
        new = lines[:r - 1] + [L[:c] + rep + L[c2:]] + lines[r:]
        out.append((f"L{r}:{c} {t.string}->{rep}", "\n".join(new)))
    return out
# ---- random inputs for the equivalence screen
def rand_alpha_inputs(rs):
    ins = []
    for _ in range(2500): ins.append(([[rs.choice("ABC") for _ in range(rs.randint(2, 4))] for _ in range(rs.randint(1, 8))], False))
    for _ in range(500): ins.append(([[rs.randint(1, 5) for _ in range(rs.randint(2, 4))] for _ in range(rs.randint(1, 8))], True))
    return ins
def rand_pair_inputs(rs):
    ins = []
    for _ in range(1500):
        k = rs.choice([["yes", "no"], ["yes", "no", "x"]])
        ins.append(([(rs.choice(k), rs.choice(k)) for _ in range(rs.randint(20, 80))],))
    return ins
def run(fn, args):
    try: return ("ok", fn(*args))
    except Exception as e: return ("err", type(e).__name__)
def same(a, b):
    if a[0] != b[0]: return False
    return json.dumps(a[1], sort_keys=True, default=str) == json.dumps(b[1], sort_keys=True, default=str)
# ---- fixtures (hand-made)
def fx_alpha(alpha):
    random.seed(1); u = [[random.choice("AB"), random.choice("AB")] for _ in range(20000)]
    return all([alpha([["A","A"]]*5 + [["B","B"]]*5) == 1.0, alpha([["A","A"]]*4 + [["B","B"]]*4 + [["A","B"]]*2) == 0.62,
                abs(alpha(u)) < 0.02, alpha([["A","A"]]*10) is None, alpha([["A","B"]]*5 + [["B","A"]]*5) == -0.9,
                alpha([[1,1],[2,2],[3,3],[1,2]], True) > alpha([[1,1],[2,2],[3,3],[1,3]], True),
                alpha([["A","B"]]) == 0.0, alpha([["A","A"]]*2 + [["B","B"]] + [["A","B"]]) == 0.533])
def pairs(n11, n22, n12, n21): return [("yes","yes")]*n11 + [("no","no")]*n22 + [("yes","no")]*n12 + [("no","yes")]*n21
def fx_pair(ps):
    a = ps(pairs(40, 40, 10, 10)); b = ps(pairs(85, 5, 5, 5))
    sa, sb = a["specific_by_answer"], b["specific_by_answer"]
    return all([a["raw"] == 0.8, a["kappa"] == 0.6, a["ac1"] == 0.6, a["pabak"] == 0.6, sa == {"no": 0.8, "yes": 0.8},
                b["raw"] == 0.9, b["kappa"] == 0.444, b["ac1"] == 0.878, b["pabak"] == 0.8, sb == {"no": 0.5, "yes": 0.944},
                "x" in ps([("x","x")]*10 + [("yes","yes")]*30)["specific_by_answer"],
                "x" not in ps([("x","x")]*9 + [("x","yes")] + [("yes","yes")]*30)["specific_by_answer"],
                all(math.isnan(ps([("a","a")]*30)[k]) for k in ("kappa", "ac1", "pabak"))])
def fixtures(kind, fn):
    try: return (fx_alpha if kind == "alpha" else fx_pair)(fn)
    except Exception: return False
# ---- Lean oracle
random.seed(7)
A_CASES = []
while len(A_CASES) < 300:
    a, b, d = random.randint(0, 20), random.randint(0, 20), random.randint(0, 20)
    if a + b + d >= 2 and 2*a + d > 0 and 2*b + d > 0: A_CASES.append((a, b, d))
P_CASES = [(random.randint(10, 40), random.randint(10, 40), random.randint(0, 25), random.randint(0, 25)) for _ in range(300)]
lean = open(os.path.join(HERE, "FitChecks.lean")).read() + "\n" + open(os.path.join(HERE, "PairStats.lean")).read()
lean += "\ndef fr (x : Rat) : String := s!\"{x.num}/{x.den}\"\n"
lean += "#eval ([" + ",".join(f"({a},{b},{d})" for a, b, d in A_CASES) + "] : List (Nat × Nat × Nat)).map (fun (a, b, d) => s!\"A {a} {b} {d} {num a b d} {den a b d}\")\n"
lean += "#eval ([" + ",".join(f"({a},{b},{c},{d})" for a, b, c, d in P_CASES) + "] : List (Nat × Nat × Nat × Nat)).map (fun (a, b, c, d) => s!\"P {a} {b} {c} {d} {fr (po a b c d)} {fr (kappa a b c d)} {fr (ac1 a b c d)} {fr (pabak a b c d)} {fr (specA a b c d)} {fr (specB a b c d)}\")\n"
t0 = time.time(); p = os.path.join(W, "runs", "pulse", "oracle_rep.lean"); open(p, "w").write(lean)
r = subprocess.run(["lean", p], capture_output=True, text=True, timeout=400); T_LEAN = time.time() - t0
ORC = {"A": [], "P": []}
for line in re.findall(r'"([AP] [^"]+)"', r.stdout): t = line.split(); ORC[t[0]].append(t[1:])
assert len(ORC["A"]) == 300 and len(ORC["P"]) == 300, (len(ORC["A"]), len(ORC["P"]), r.stderr[:500])
fr = lambda s: Fr(int(s.split("/")[0]), int(s.split("/")[1]))
from fractions import Fraction as Fr
def eq3(g, x):
    """g equals x rounded to 3 digits; at an exact tie (x*1000 ends in .5) either neighbour is accepted."""
    v = x * 1000; fl = v.numerator // v.denominator
    if v - fl == Fr(1, 2): return abs(g - fl / 1000) < 1e-9 or abs(g - (fl + 1) / 1000) < 1e-9
    return g == round(float(x), 3)
def oracle(kind, fn):
    try:
        if kind == "alpha":
            for a, b, d, nn, dn in ORC["A"]:
                a, b, d = int(a), int(b), int(d)
                g = fn([["A","A"]]*a + [["B","B"]]*b + [["A","B"]]*d)
                if g is None or not eq3(g, Fr(int(nn), int(dn))): return False
            return True
        for row in ORC["P"]:
            n11, n22, n12, n21 = map(int, row[:4]); po_, ka, ac, pb, sa, sb = map(fr, row[4:])
            g = fn(pairs(n11, n22, n12, n21)); s = g["specific_by_answer"]
            if any(not eq3(x, y) for x, y in [(g["raw"], po_), (g["kappa"], ka), (g["ac1"], ac), (g["pabak"], pb), (s["yes"], sa), (s["no"], sb)]): return False
        return True
    except Exception: return False

# ---- R: independent reference alpha by direct definition (all value pairs), 2 to 4 coders, nominal and interval
def ref_alpha(units, interval=False):
    d = (lambda a, b: (a - b) ** 2) if interval else (lambda a, b: 0 if a == b else 1)
    U = [u for u in units if len(u) >= 2]; pool = [x for u in U for x in u]; n = len(pool)
    if n < 2: return None
    Do = sum(d(u[i], u[j]) / (len(u) - 1) for u in U for i in range(len(u)) for j in range(len(u)) if i != j) / n
    De = sum(d(pool[i], pool[j]) for i in range(n) for j in range(n) if i != j) / (n * (n - 1))
    return None if De == 0 else 1 - Do / De
random.seed(21); R_CASES = [([[random.choice("ABC") for _ in range(random.randint(2, 4))] for _ in range(random.randint(2, 7))], False) for _ in range(250)]
R_CASES += [([[random.randint(1, 5) for _ in range(random.randint(2, 4))] for _ in range(random.randint(2, 7))], True) for _ in range(100)]
def reference(fn):
    try:
        for u, iv in R_CASES:
            want = ref_alpha(u, iv); got = fn(u, iv)
            if (want is None) != (got is None): return False
            if want is not None and got != round(want, 3): return False
        return True
    except Exception: return False

from fractions import Fraction as Fr
def ref_pair(pr):
    n = len(pr); cats = sorted({x for p in pr for x in p}); q = len(cats)
    ma = {c: sum(a == c for a, _ in pr) for c in cats}; mb = {c: sum(b == c for _, b in pr) for c in cats}
    po = Fr(sum(a == b for a, b in pr), n); pe = sum(Fr(ma[c] * mb[c], n * n) for c in cats)
    nan = float("nan"); out = {"n": n, "raw": round(float(po), 3)}
    out["kappa"] = round(float((po - pe) / (1 - pe)), 3) if pe < 1 else nan
    S = sum(Fr(ma[c] + mb[c], 2 * n) * (1 - Fr(ma[c] + mb[c], 2 * n)) for c in cats)
    out["pabak"] = round(float((q * po - 1) / (q - 1)), 3) if q > 1 else nan
    out["ac1"] = round(float((po - S / (q - 1)) / (1 - S / (q - 1))), 3) if q > 1 else nan
    out["specific_by_answer"] = {c: round(float(Fr(2 * sum(a == c and b == c for a, b in pr), ma[c] + mb[c])), 3) for c in cats if ma[c] + mb[c] >= 20}
    return out
random.seed(33); RP = []
for _ in range(200):
    k = random.choice([2, 3, 4]); labs = ["yes", "no", "x", "y"][:k]; w = [random.random() ** 2 + 0.05 for _ in labs]
    one = lambda: random.choices(labs, w)[0]
    pr = []
    for _ in range(random.randint(30, 100)):
        a = one(); pr.append((a, a if random.random() < 0.7 else one()))
    RP.append(pr)
def reference_pair(fn):
    try:
        for pr in RP:
            want, got = ref_pair(pr), fn(pr)
            if set(want) != set(got): return False
            for key in want:
                a, b = want[key], got[key]
                if isinstance(a, float) and math.isnan(a):
                    if not (isinstance(b, float) and math.isnan(b)): return False
                elif a != b: return False
        return True
    except Exception: return False
res = {"lean_seconds": round(T_LEAN, 1)}; os.makedirs(os.path.join(HERE, "mutants_rep"), exist_ok=True); sample_pool = []
for kind in ["alpha", "pair_stats"]:
    base = load(SRC[kind], kind); k0 = "alpha" if kind == "alpha" else "pair_stats"
    rs = random.Random(11); ins = rand_alpha_inputs(rs) if kind == "alpha" else rand_pair_inputs(rs)
    base_out = [run(base, a) for a in ins]
    R = {"base_fixtures_pass": fixtures(kind, base), "base_oracle_pass": oracle(kind, base), "base_reference_pass": (reference(base) if kind == "alpha" else reference_pair(base)), "mutants": []}
    for desc, src in mutants(SRC[kind]):
        try: fn = load(src, kind)
        except Exception: continue
        eq = all(same(run(fn, a), b) for a, b in zip(ins, base_out))
        m = {"site": desc, "equivalent": eq}
        if not eq:
            m["killed_by_fixtures"] = not fixtures(kind, fn); m["killed_by_oracle"] = not oracle(kind, fn)
            m["killed_by_reference"] = not (reference(fn) if kind == "alpha" else reference_pair(fn))
            if kind == "pair_stats": sample_pool.append((desc, src))
        R["mutants"].append(m)
    ne = [m for m in R["mutants"] if not m["equivalent"]]
    R["summary"] = {"generated": len(R["mutants"]), "equivalent": len(R["mutants"]) - len(ne), "non_equivalent": len(ne),
                    "killed_by_fixtures": sum(m["killed_by_fixtures"] for m in ne), "killed_by_oracle": sum(m["killed_by_oracle"] for m in ne),
                    "oracle_survivors": [m["site"] for m in ne if not m["killed_by_oracle"]], "fixture_survivors": [m["site"] for m in ne if not m["killed_by_fixtures"]]}
    if True:
        R["summary"]["killed_by_reference"] = sum(m["killed_by_reference"] for m in ne)
        R["summary"]["reference_survivors"] = [m["site"] for m in ne if not m["killed_by_reference"]]
        R["summary"]["union_all_three_killed"] = sum(m["killed_by_fixtures"] or m["killed_by_oracle"] or m["killed_by_reference"] for m in ne)
    assert R["base_fixtures_pass"] and R["base_oracle_pass"] and R["base_reference_pass"], (kind, R["base_fixtures_pass"], R["base_oracle_pass"], R["base_reference_pass"])
    res[kind] = R
random.Random(3).shuffle(sample_pool); res["mm3_sample"] = []
for i, (desc, src) in enumerate(sample_pool[:10]):
    f = f"ps_{i:02d}.py"; open(os.path.join(HERE, "mutants_rep", f), "w").write(HDR + src); res["mm3_sample"].append({"file": f, "site": desc})
open(os.path.join(HERE, "mutants_rep", "ps_base.py"), "w").write(HDR + SRC["pair_stats"])
json.dump(res, open(os.path.join(W, "runs", "pulse", "replication_FO.json"), "w"), indent=1)
for kind in ["alpha", "pair_stats"]: print(kind, res[kind]["base_fixtures_pass"], res[kind]["base_oracle_pass"], res[kind]["summary"])
print("lean s", res["lean_seconds"]); print(res["mm3_sample"])
