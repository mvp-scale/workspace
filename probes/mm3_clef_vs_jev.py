"""Can local Clef stand in for hosted Jev on MM3 class calls? Same 50 requests to both, compared answer by answer.

Requests  50 functions (20-80 lines, seeded) from this workspace's code; each gets one MM3 class-shaped question set
          (3 concerns categories x 3 yes/no probes + a severity scale + a route choice), 5 sets rotated: security, errors,
          isolation, config, performance. State = file path + source, as MM3 sends its `where`.
Models    local Clef Flash Q4 and hosted Jev (paid, ~$0.0007 a call: 50 calls, approved), through demo/backends.py.
Report    yes/no agreement at 0.5, category gates (pass rule per category, need: all), decisions (same choice; scale gap).
Writes    data/bitmob/mm3-test/clef_vs_jev.jsonl (both answers per request) and clef_vs_jev.json (summary).
Run: set -a; . ./.env; set +a; HF_HOME=/workspace/data/hf models/embed-zs/.venv/bin/python probes/mm3_clef_vs_jev.py
"""
import json, random, sys, pathlib, time
import numpy as np
sys.path.insert(0, "/workspace/demo"); sys.path.insert(0, "/workspace/probes")
import backends, mm3_trainer_test as mt

OUT = mt.OUT; SEED = 20261017; N = 50
SETS = {
    "security": {"input": ("no", ["Does this code take input from outside without validating it?", "Is outside input passed into a command, query, path or HTML without being made safe?", "Could a caller reach data or actions they should not by changing the input alone?"]),
                 "secrets": ("no", ["Does this code contain or print a key, token or password?", "Does it send a secret to a place it should not go (a log, a URL, a response)?", "Is a secret read from somewhere other than the environment or a secrets file?"]),
                 "exposure": ("no", ["Does this code send a raw error or internal detail to the caller?", "Does it bind or expose a network service beyond this machine?", "Does it skip an access check that similar code performs?"])},
    "errors":   {"swallow": ("no", ["Does this code catch an error and ignore it?", "Could a failure here go unnoticed by the caller?", "Does it return a default value that hides a failure?"]),
                 "report": ("yes", ["Does this code tell the caller clearly when something fails?", "Is the error message something a person can act on?", "Are failures logged or surfaced somewhere?"]),
                 "cleanup": ("yes", ["Are files, sockets or processes closed or released on every path?", "Does a failure halfway leave things in a consistent state?", "Are timeouts set on outside calls?"])},
    "isolation": {"boundary": ("yes", ["Does this function do one job?", "Does it reach outside services only through a shared helper or adapter?", "Could it be tested without starting a server?"]),
                  "coupling": ("no", ["Does it reach into another module's internals?", "Does it depend on global state that other code changes?", "Would changing one caller force changes here?"]),
                  "contract": ("yes", ["Are its inputs and outputs clear from its signature and return values?", "Does it behave the same for the same inputs?", "Is its name an accurate description of what it does?"])},
    "config":   {"hardcode": ("no", ["Does this code hard-code a path, port, URL or host?", "Does it hard-code a model name or id?", "Does it hard-code a limit that should be configurable?"]),
                 "source": ("yes", ["Are settings read from one place (environment, a config file or a settings module)?", "Is there a sensible default when a setting is missing?", "Is the setting's meaning clear where it is read?"]),
                 "drift": ("no", ["Does it duplicate a value that is also defined elsewhere?", "Could two parts of the system disagree about this value?", "Is a copy of shared logic kept here instead of calling it?"])},
    "performance": {"loops": ("no", ["Does this code do slow work (a network call, a file read, a model call) inside a loop?", "Does it repeat work whose result could be reused?", "Does it load a large file or model on every call?"]),
                    "blocking": ("no", ["Does it block while waiting on something slow without a timeout?", "Does it hold a lock longer than it needs to?", "Could one slow caller hold up others?"]),
                    "memory": ("no", ["Does it keep growing a list or cache without a limit?", "Does it read a whole large input into memory at once?", "Does it copy large data unnecessarily?"])},
}
DECISIONS = {"severity": {"type": "score", "instructions": "How severe is the worst issue found?", "criteria": ["none", "low", "medium", "high", "critical"]},
             "route": {"type": "choice", "instructions": "Where should this go?", "criteria": {"ship": None, "fix": None, "block": None}}}


def request(setname):
    qs, cats = {}, {}
    n = 1
    for cat, (pas, probes) in SETS[setname].items():
        cats[cat] = {"pass": pas, "qs": []}
        for p in probes: qs[str(n)] = {"type": "noul", "instructions": p}; cats[cat]["qs"].append(str(n)); n += 1
    for k, d in DECISIONS.items(): qs[k] = d
    return qs, cats


def main():
    fns = [f for f in mt.functions() if f["lines"][1] - f["lines"][0] + 1 >= 20][:N]; names = list(SETS)
    done = {json.loads(l)["key"] for l in open(OUT / "clef_vs_jev.jsonl")} if (OUT / "clef_vs_jev.jsonl").exists() else set()
    assert not backends.BACKENDS["clef-flash-q4km"]["hosted"] and backends.BACKENDS["jev"]["hosted"]
    cost = 0.0
    with open(OUT / "clef_vs_jev.jsonl", "a") as fo:
        for i, fn in enumerate(fns):
            key = f"{fn['file']}:{fn['lines'][0]}"
            if key in done: continue
            setname = names[i % len(names)]; qs, cats = request(setname); st = mt.state_of(fn); row = {"key": key, "set": setname, "cats": cats}
            for mid in ("clef-flash-q4km", "jev"):
                t = time.time()
                try: row[mid] = backends.ask(mid, st, qs, timeout=120)
                except Exception as e: row[mid] = {"_error": str(e)[:200]}
                row[mid + "_s"] = round(time.time() - t, 2)
            fo.write(json.dumps(row) + "\n"); fo.flush(); print(f"{i + 1}/{len(fns)} {setname:11} {key}", flush=True)
    summarise()


def summarise():
    rows = [json.loads(l) for l in open(OUT / "clef_vs_jev.jsonl")]
    rows = [r for r in rows if "_error" not in r["clef-flash-q4km"] and "_error" not in r["jev"]]
    C, J = "clef-flash-q4km", "jev"; yn = []; gates = []; route = []; sev = []; per = {}
    for r in rows:
        for cat, c in r["cats"].items():
            cg, jg = [], []
            for q in c["qs"]:
                a, b = r[C][q]["noul"], r[J][q]["noul"]; yn.append((a, b)); per.setdefault(r["set"], []).append((a > 0.5) == (b > 0.5))
                ok = lambda p: (p > 0.5) == (c["pass"] == "yes"); cg.append(ok(a)); jg.append(ok(b))
            gates.append((all(cg), all(jg)))
        route.append((r[C]["route"]["choice"], r[J]["route"]["choice"])); sev.append((r[C]["severity"]["score"], r[J]["severity"]["score"]))
    a = np.array(yn); agree = float(np.mean((a[:, 0] > 0.5) == (a[:, 1] > 0.5))); g = np.array(gates)
    res = {"requests": len(rows), "yes_no": {"n": len(a), "agree": agree, "corr": float(np.corrcoef(a[:, 0], a[:, 1])[0, 1]),
                                            "clef_yes": float(np.mean(a[:, 0] > 0.5)), "jev_yes": float(np.mean(a[:, 1] > 0.5))},
           "gates": {"n": len(g), "agree": float(np.mean(g[:, 0] == g[:, 1])), "clef_pass": float(g[:, 0].mean()), "jev_pass": float(g[:, 1].mean())},
           "route_same": float(np.mean([x == y for x, y in route])), "severity_gap": float(np.mean([abs(x - y) for x, y in sev])),
           "per_set_agree": {k: float(np.mean(v)) for k, v in per.items()},
           "seconds": {"clef": float(np.median([r[C + "_s"] for r in rows])), "jev": float(np.median([r[J + "_s"] for r in rows]))}}
    json.dump(res, open(OUT / "clef_vs_jev.json", "w"), indent=1); print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
