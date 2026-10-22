"""Round 5 pick-mix (bridge/user addition): replace most random slots with free-picked stories for the other weak rows. Keeps the 2,365 condition-aimed picks, 135 random, adds 250 borderline read-or-skip
(top gate_margin) and 250 likely-worldwide (top worldwide score) from data/picker/pool_scores.jsonl. Test ids asserted absent. Rewrites data/clef-labels/r5_in.jsonl (old copy r5_in_v1.jsonl) and adds the split to r5_pick_report.json."""
import json, random, shutil
W = "/workspace/data"; test = {json.loads(l)["id"] for f in ("test_in", "test") for l in open(f"{W}/clef-labels/{f}.jsonl")}
old = [json.loads(l) for l in open(f"{W}/clef-labels/r5_in.jsonl")]; shutil.copy(f"{W}/clef-labels/r5_in.jsonl", f"{W}/clef-labels/r5_in_v1.jsonl")
aimed = [r for r in old if r.get("picked_for") != "random"]; rnd = [r for r in old if r.get("picked_for") == "random"]; random.seed(11); random.shuffle(rnd); rnd = rnd[:135]
have = {r["id"] for r in aimed + rnd}; pool = [json.loads(l) for l in open(f"{W}/picker/pool_scores.jsonl")]; pool = [p for p in pool if p["id"] not in have and p["id"] not in test]
bord = sorted(pool, key=lambda p: -p["gate_margin"])[:250]; have |= {p["id"] for p in bord}
ww = sorted([p for p in pool if p["id"] not in have], key=lambda p: -p["worldwide"])[:250]
def row(p, why, sc): return {"id": p["id"], "title": p["title"], "description": p["description"], "date": p["date"], "picked_for": why, "pick_score": sc}
new = aimed + rnd + [row(p, "borderline_gate", p["gate_margin"]) for p in bord] + [row(p, "worldwide", p["worldwide"]) for p in ww]
assert not ({r["id"] for r in new} & test) and len({r["id"] for r in new}) == len(new); print("no test ids; picks", len(new))
open(f"{W}/clef-labels/r5_in.jsonl", "w").write("\n".join(json.dumps(r) for r in new) + "\n")
rep = json.load(open(f"{W}/clef-labels/r5_pick_report.json")); rep["split"] = {"condition_aimed": len(aimed), "random": len(rnd), "borderline_gate": len(bord), "worldwide": len(ww), "total": len(new)}; rep["n_picked"] = len(new); rep["random"] = len(rnd)
json.dump(rep, open(f"{W}/clef-labels/r5_pick_report.json", "w"), indent=1); print(rep["split"])
