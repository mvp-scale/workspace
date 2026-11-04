"""Differential test: qualify.consensus_verdict vs the Lean-evaluated verdict (Verdict.lean) on alpha -1.000..1.000, plus mechanical mutants. Prediction: ledger L526."""
import os, re, io, json, subprocess, tokenize
HERE = os.path.dirname(os.path.abspath(__file__)); W = os.path.join(HERE, "..")
src = open(os.path.join(W, "qualify.py")).read(); fn_src = re.search(r"def consensus_verdict\(.*", src, re.S).group(0)
lean = open(os.path.join(HERE, "Verdict.lean")).read() + "\n#eval show IO Unit from do\n  for i in List.range 2001 do\n    IO.println s!\"T {(i : Int) - 1000} {verdict ((i : Int) - 1000)}\"\n"
p = os.path.join(W, "runs", "pulse", "verdict_oracle.lean"); open(p, "w").write(lean)
out = subprocess.run(["lean", p], capture_output=True, text=True, timeout=200)
table = {int(a): int(b) for a, b in re.findall(r'^T (-?\d+) (\d)$', out.stdout, re.M)}; assert len(table) == 2001, (len(table), out.stderr[:300])
NAME = {2: "Clear", 1: "Tentative", 0: "Reject"}
def agrees(code):
    ns = {}
    try:
        exec(code, ns); f = ns["consensus_verdict"]
        return all(f(a / 1000) == NAME[v] for a, v in table.items()) and f(None) == "Not measured"
    except Exception: return False
res = {"base_agrees": agrees(fn_src), "mutants": []}
toks = list(tokenize.generate_tokens(io.StringIO(fn_src).readline)); lines = fn_src.split("\n")
OPS = {">=": ">", ">": ">=", "<": "<=", "<=": "<", "==": "!=", "*": "/"}
for t in toks:
    if t.start[0] == 1: continue
    rep = OPS.get(t.string) if t.type == tokenize.OP else (str(int(t.string) + 1) if t.type == tokenize.NUMBER and t.string.isdigit() else None)
    if rep is None: continue
    (r, c), (_, c2) = t.start, t.end; L = lines[r - 1]
    code = "\n".join(lines[:r - 1] + [L[:c] + rep + L[c2:]] + lines[r:])
    res["mutants"].append({"site": f"L{r}:{c} {t.string}->{rep}", "survives": agrees(code)})
res["summary"] = {"table_points": len(table), "mutants": len(res["mutants"]), "killed": sum(not m["survives"] for m in res["mutants"]), "survivors": [m["site"] for m in res["mutants"] if m["survives"]]}
json.dump(res, open(os.path.join(W, "runs", "pulse", "verdict_test.json"), "w"), indent=1); print(res["base_agrees"], res["summary"])
