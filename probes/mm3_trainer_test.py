"""MM3 trainer-mode test: can BitMob learn MM3 class-style questions about a codebase from a local teacher?

Inputs     Python functions (8-80 lines) from this workspace's own code (demo, probes, tools, jevbench, jeff/src, kev/kev),
           seeded sample, one TypeSafe request per function: state = file path + the function's source.
Questions  12 class-style questions shaped like MM3's most repeated ones (QUESTIONS below; 10 yes/no, 1 choice, 1 scale).
Teacher    local Clef Flash Q4 (:8018) through demo/backends.py, never a hosted model. Labels: data/bitmob/mm3-test/labels.jsonl
           (+ .meta.json naming the teacher); resumable.
Learner    per question, LogisticRegression(balanced) on the code mob (code-16m) and on e5-small vectors of the state.
Split      by FILE, 70/30 (seeded): no file has functions on both sides.
Pass       per yes/no question, the intake bar: >= 97% agreement with Clef and yes-F1 >= 0.90 on the answers BitMob keeps,
           with Clef answering <= 25% (gate chosen on out-of-fold training answers, applied to the held-out files).
Run: HF_HOME=/workspace/data/hf models/embed-zs/.venv/bin/python probes/mm3_trainer_test.py label|train
"""
import ast, json, random, sys, pathlib, time
from concurrent.futures import ThreadPoolExecutor
import numpy as np

ROOT = pathlib.Path("/workspace"); OUT = ROOT / "data" / "bitmob" / "mm3-test"; OUT.mkdir(parents=True, exist_ok=True)
LAB = OUT / "labels.jsonl"; SEED = 20261017; TEACHER = "clef-flash-q4km"
sys.path.insert(0, str(ROOT / "demo")); sys.path.insert(0, str(ROOT / "probes"))
YN = {
    "silent":   "Could this code fail silently in production, with an error swallowed or ignored?",
    "rawerr":   "Does this code send a raw error message or internal detail back to its caller or user?",
    "input":    "Does this code take input from outside (a request, file, user or network) without validating it?",
    "alone":    "Can this function be checked by itself, without starting a server or other parts?",
    "single":   "Does this function own one clear responsibility?",
    "hardcode": "Does this code hard-code a value that should come from configuration (a path, port, URL, key or model name)?",
    "helper":   "Does this code reach a file, database or network through a shared helper rather than its own direct call?",
    "onecheck": "Could this code be covered by one automated check?",
    "shell":    "Does this code run an external command or shell?",
    "sidefx":   "Does this code change shared state (a global, a file on disk, a cache) as a side effect?",
}
QUESTIONS = {k: {"type": "noul", "instructions": v} for k, v in YN.items()}
QUESTIONS["scope"] = {"type": "choice", "instructions": "Can this be answered from the code shown?", "criteria": {"enough": None, "partial": None, "missing": None}}
QUESTIONS["risk"] = {"type": "score", "instructions": "How risky is this code to change?", "criteria": ["none", "low", "medium", "high"]}


def functions():
    files = [p for d in ("demo", "probes", "tools", "jevbench/jevbench", "jeff/src", "kev/kev") for p in sorted((ROOT / d).rglob("*.py"))
             if "_retired" not in p.parts and ".venv" not in p.parts]
    out = []
    for f in files:
        try: src = f.read_text(); tree = ast.parse(src)
        except (SyntaxError, UnicodeDecodeError, OSError): continue
        lines = src.splitlines()
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and 8 <= n.end_lineno - n.lineno + 1 <= 80:
                body = "\n".join(lines[n.lineno - 1:n.end_lineno])
                if len(body) <= 4000: out.append({"file": str(f.relative_to(ROOT)), "name": n.name, "lines": [n.lineno, n.end_lineno], "code": body})
    random.Random(SEED).shuffle(out); return out


def state_of(fn): return f"File: {fn['file']} (lines {fn['lines'][0]}-{fn['lines'][1]})\n```python\n{fn['code']}\n```"


def label(n=600):
    import backends
    assert not backends.BACKENDS[TEACHER]["hosted"], "teacher must be local"
    (OUT / "labels.meta.json").write_text(json.dumps({"teacher": TEACHER, "questions": QUESTIONS}))
    done = {json.loads(l)["key"] for l in open(LAB)} if LAB.exists() else set()
    todo = [f for f in functions()[:n] if f"{f['file']}:{f['lines'][0]}" not in done]
    print(f"{len(done)} labelled, {len(todo)} to go (teacher {TEACHER})", flush=True); t0 = time.time()
    def one(fn):
        for attempt in range(3):
            try: return fn, backends.ask(TEACHER, state_of(fn), QUESTIONS, timeout=180)
            except Exception as e: err = e; time.sleep(2)
        return fn, {"_error": str(err)}
    with ThreadPoolExecutor(4) as ex, open(LAB, "a") as fo:
        for k, (fn, a) in enumerate(ex.map(one, todo), 1):
            if "_error" in a: print("  skip", fn["file"], a["_error"][:120], flush=True); continue
            fo.write(json.dumps({"key": f"{fn['file']}:{fn['lines'][0]}", **fn, "answers": a}) + "\n"); fo.flush()
            if k % 50 == 0: print(f"  {k}/{len(todo)} in {time.time() - t0:.0f} s", flush=True)


def train():
    import bitmob_bench as bb, bitmob_router as br, pocket_test as pt
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold
    from latent_intake import gate, f1
    rows = [json.loads(l) for l in open(LAB)]; states = [state_of(r) for r in rows]
    files = sorted({r["file"] for r in rows}); random.Random(SEED).shuffle(files); test_files = set(files[: int(len(files) * 0.3)])
    te = np.array([r["file"] in test_files for r in rows]); tr = ~te
    X = {m: br.enc(m)(states) for m in ("code-16m", "e5-small")}
    print(f"{len(rows)} functions from {len(files)} files; train {tr.sum()} / held-out {te.sum()} (by file)\n")
    res = {"n": len(rows), "train": int(tr.sum()), "test": int(te.sum()), "teacher": TEACHER, "questions": {}}
    print(f"{'question':10}{'yes rate':>9}{'majority':>9} | {'code-16m agree':>15}{'e5 agree':>9} | {'gate: local share':>18}{'agree kept':>11}{'yes-F1 kept':>12} {'tier':>7}")
    for k in YN:
        y = np.array([float(r["answers"][k]["noul"]) > 0.5 for r in rows]); out = {"yes_rate": float(y.mean()), "majority": float(max(y[te].mean(), 1 - y[te].mean()))}
        if y[tr].sum() < 10 or (~y[tr]).sum() < 10:
            print(f"{k:10}{y.mean():>9.0%}  too few of one answer to learn"); res["questions"][k] = out; continue
        best = None
        for m, V in X.items():
            clf = LogisticRegression(C=1.0, max_iter=5000, class_weight="balanced").fit(V[tr], y[tr]); p = clf.predict_proba(V[te])[:, 1]
            oof = np.zeros(tr.sum())
            for a, b in StratifiedKFold(5, shuffle=True, random_state=0).split(V[tr], y[tr]):
                oof[b] = LogisticRegression(C=1.0, max_iter=5000, class_weight="balanced").fit(V[tr][a], y[tr][a]).predict_proba(V[tr][b])[:, 1]
            share, lo, hi = gate(oof, y[tr]); loc = (p < lo) | (p > hi)
            kept_agree = float(np.mean((p[loc] > hi) == y[te][loc])) if loc.any() else None
            kept_f1 = float(f1((p[loc] > hi), y[te][loc])) if loc.any() and y[te][loc].any() else None
            out[m] = {"agree": float(np.mean((p > 0.5) == y[te])), "local_share": float(loc.mean()), "kept_agree": kept_agree, "kept_f1": kept_f1}
            if best is None or out[m]["local_share"] > out[best]["local_share"]: best = m
        b = out[best]; ok = b["kept_agree"] is not None and b["kept_agree"] >= 0.97 and (b["kept_f1"] or 0) >= 0.90
        tier = "Local" if ok and b["local_share"] >= 0.75 else "Hybrid" if ok and b["local_share"] >= 0.5 else "Clef"
        out["best"] = best; out["tier"] = tier; res["questions"][k] = out
        fmt = lambda v: "-" if v is None else f"{v:.0%}"
        print(f"{k:10}{y.mean():>9.0%}{out['majority']:>9.0%} | {out['code-16m']['agree']:>15.0%}{out['e5-small']['agree']:>9.0%} | "
              f"{fmt(b['local_share']):>12} ({best[:4]}){fmt(b['kept_agree']):>11}{fmt(b['kept_f1']):>12} {tier:>7}")
    json.dump(res, open(OUT / "results.json", "w"), indent=1); print(f"\nwrote {OUT}/results.json")


if __name__ == "__main__":
    {"label": label, "train": train}[sys.argv[1]]()
