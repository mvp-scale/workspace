"""Short probe library: content words only, at most 5 per probe (owner direction: embeddings do not need filler words)."""
import json, yaml, re, pathlib
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
STOP = ENGLISH_STOP_WORDS - {"more", "less", "no", "not", "nor"}      # these carry direction, keep them
H0 = pathlib.Path(__file__).resolve().parent; base = json.load(open(H0 / "specs/world_state_v2_frozen_haiku.json")); lib = {}
keep = lambda t: [w for w in re.findall(r"[a-z][a-z-]+", t.lower()) if w not in STOP][:5]
for l in [l for l in base["guideline"] if " | up = " in l and not l.startswith("CONDITIONS")]:
    cid, rest = l.split(":", 1); p = [x.strip() for x in rest.split("|")]
    M, U, D = keep(p[0]), keep(p[1].replace("up =", "")), keep(p[2].replace("down =", ""))
    j = lambda w: " ".join(w)
    lib[cid] = {"meaning": j(M), "up": [j(U), "sharp " + j(U[:4]), "slight " + j(U[:4])], "down": [j(D), "sharp " + j(D[:4]), "slight " + j(D[:4])], "inverse_up": [j(D)], "inverse_down": [j(U)], "none": [j(M)]}
yaml.safe_dump({"version": "probe-lib-short-v0", "conditions": lib}, open(H0 / "specs/probe_library_short.yaml", "w"), sort_keys=True, width=200)
print(len(lib), sum(len(v[k]) for v in lib.values() for k in ("up", "down", "inverse_up", "inverse_down", "none")), "probes"); print(json.dumps(lib["water_stress"]))
