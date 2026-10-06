"""Condition -> condition ties (engine2.World2, rules_v2/dial_ties.csv). Each case runs in a fresh interpreter because WE_RULES is read once at import.
   /workspace/kev/.venv/bin/python tests/test_ties.py"""
import os, sys, json, subprocess, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); WE = os.path.dirname(HERE)
CODE = r'''
import sys, json; sys.path.insert(0, "/workspace/probes/world-engine"); sys.path.insert(0, "/workspace/probes/persona")
import engine2 as W2, numpy as np
cs = [{"id": "aa", "pop_m": 1.0}]; w = W2.World2(cs, 0, noise=False); D = W2.DIALS
out = {"ties": {D[k]: [(D[j], s) for j, s in v] for k, v in W2.TIES.items()}}
if "energy_fuel" in D:
    w.add(0, "COUNTRY:aa", "energy_fuel", 0.1, "t"); trace = []
    for _ in range(6): w.step(); trace.append({d: round(float(w.delta["COUNTRY:aa"][D.index(d)]), 5) for d in ("energy_fuel", "prices")})
    out["trace"] = trace; out["hops"] = max(sum(1 for p in l["path"] if str(p).startswith("~tie:")) for l in w.log)
    w2 = W2.World2(cs, 0, noise=False)
    for t in range(40): w2.add(0, "COUNTRY:aa", "energy_fuel", 0.1, "t") if t == 0 else None; w2.step()
    out["bounded"] = float(np.abs(w2.delta["COUNTRY:aa"]).max()) < 0.2
else: out["trace"] = None
print("JSON" + json.dumps(out))
'''
def run(rules):
    env = dict(os.environ); env.pop("WE_RULES", None)
    if rules: env["WE_RULES"] = rules
    o = subprocess.run([sys.executable, "-c", CODE], env=env, capture_output=True, text=True, timeout=120)
    return json.loads(o.stdout.split("JSON")[-1])
class Ties(unittest.TestCase):
    def test_v1_has_no_ties(self): self.assertEqual(run(None)["ties"], {})
    def test_v2_tie_lands_one_tick_later_and_is_bounded(self):
        o = run("rules_v2"); self.assertIn("prices", [t for ts in o["ties"].values() for t, _ in ts]); tr = o["trace"]
        self.assertGreater(tr[0]["energy_fuel"], 0); self.assertEqual(tr[0]["prices"], 0.0)       # tick 0: the change lands, the tie is queued for one tick later
        self.assertGreater(tr[1]["prices"], 0)                                                     # tick 1: the tie has landed (0.5 x 0.1, decayed)
        self.assertLessEqual(o["hops"], 3); self.assertTrue(o["bounded"])
if __name__ == "__main__": unittest.main()
