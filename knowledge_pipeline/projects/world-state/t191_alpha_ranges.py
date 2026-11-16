"""T191: bootstrap 95% ranges for the Krippendorff alpha of the six Pulse fields of fitness_screen.py, from the same item-level votes. fitness_screen.py runs in memory with its output write disabled and screen() wrapped to capture its inputs. Prediction in the ledger on T21 (L2356, D44).
Run (from projects/world-state): python3 -I t191_alpha_ranges.py -> runs/pulse/fitness_screen_v1_ranges.json"""
import json, random, hashlib
src = open("fitness_screen.py").read()
w = 'json.dump({"voters": names, "n_items": len(ids), "fields": F}, open("runs/pulse/fitness_screen_v1.json", "w"), indent=1)'
assert src.count(w) == 1 and src.count("def screen(units_by_item, interval=False, extra=None):") == 1 and src.count("\nF = {}") == 1
src = src.replace(w, "pass").replace("def screen(units_by_item, interval=False, extra=None):", "def _screen(units_by_item, interval=False, extra=None):")
src = src.replace("\nF = {}", "\ncap = []\ndef screen(u, interval=False, extra=None):\n    cap.append((u, interval)); return _screen(u, interval, extra)\nF = {}", 1)
ns = {"__name__": "fs"}; exec(compile(src, "fitness_screen_inmemory", "exec"), ns)
cap, F, alpha = ns["cap"], ns["F"], ns["alpha"]; FIELDS = ["story_type", "topic", "condition_present", "which_condition", "direction", "size"]
assert len(cap) == 6, len(cap)
stored = json.load(open("runs/pulse/fitness_screen_v1.json"))["fields"]; rng = random.Random(21); out = {}
for name, (units, interval) in zip(FIELDS, cap):
    items = [list(u.values()) for u in units.values() if len(u) >= 2]; point = alpha(items, interval)
    ok = point == stored[name]["alpha"]; boots = []
    for _ in range(2000):
        a = alpha([items[rng.randrange(len(items))] for _ in items], interval)
        if a is not None: boots.append(a)
    boots.sort(); out[name] = {"n": len(items), "alpha_recomputed": point, "alpha_stored": stored[name]["alpha"], "reproduces": ok, "ci95": [round(boots[int(0.025 * len(boots))], 3), round(boots[int(0.975 * len(boots)) - 1], 3)], "bootstrap": "2000 resamples of items, seed 21, percentile"}
    out[name]["width"] = round(out[name]["ci95"][1] - out[name]["ci95"][0], 3); print(name, out[name], flush=True)
res = {"source": "fitness_screen.py run in memory (output write disabled), same votes as runs/pulse/fitness_screen_v1.json", "score_end2end_py_sha256_now": hashlib.sha256(open("score_end2end.py", "rb").read()).hexdigest(), "fields": out}
json.dump(res, open("runs/pulse/fitness_screen_v1_ranges.json", "w"), indent=1)
