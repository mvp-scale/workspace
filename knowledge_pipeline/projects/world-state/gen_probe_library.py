"""Builds specs/probe_library.yaml from the guideline text: no hand-written probe sentences. Per condition: up, down, inverse_up, inverse_down, none probes (strengthened and weakened forms included)."""
import json, yaml, pathlib
H0 = pathlib.Path(__file__).resolve().parent; base = json.load(open(H0 / "specs/world_state_v2_frozen_haiku.json")); lib = {}
for l in [l for l in base["guideline"] if " | up = " in l and not l.startswith("CONDITIONS")]:
    cid, rest = l.split(":", 1); p = [x.strip() for x in rest.split("|")]; M, U, D = p[0].rstrip("."), p[1].replace("up =", "").strip().rstrip("."), p[2].replace("down =", "").strip().rstrip(".")
    pos = lambda X: [X, f"The story reports that {X}.", f"Officials said {X}.", f"Sharply: {X}.", f"Slightly: {X}.", f"Many people are affected: {X}."]
    inv = lambda X: [f"There is no sign that {X}.", f"It is not true that {X}.", f"Officials denied that {X}."]
    lib[cid] = {"meaning": M, "up": pos(U), "down": pos(D), "inverse_up": inv(U), "inverse_down": inv(D), "none": [f"Nothing changed: {M}.", f"No change in {M}."]}
yaml.safe_dump({"version": "probe-lib-v0", "generated_from": "specs/world_state_v2_frozen_haiku.json guideline", "conditions": lib}, open(H0 / "specs/probe_library.yaml", "w"), sort_keys=True, width=200, allow_unicode=True)
print(len(lib), "conditions;", sum(len(v[k]) for v in lib.values() for k in ("up", "down", "inverse_up", "inverse_down", "none")), "probes")
