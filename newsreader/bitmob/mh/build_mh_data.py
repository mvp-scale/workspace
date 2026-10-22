"""Build the multi-head training dataset from Clef label files (D-0038). Training rows only: refuses any test file and asserts no id is in the frozen test.
  /workspace/kev/.venv/bin/python newsreader/bitmob/mh/build_mh_data.py OUT_DIR IN.jsonl [IN2.jsonl ...]     (e.g. data/clef-labels/train.jsonl data/clef-labels/country.jsonl)
Writes OUT_DIR/{texts.json, targets.npz, keys.json}. Heads (see mh_common.HEADS):
  gate  g|happened,announced,opinion,forecast + x|recent;  scope  s|national,local,new + x|us_focus,x|foreign_focus
  cond  318 attributes, target = mean of the two wordings (what classify.read() uses); serving sets both wordings to the head value
  topic_c 49-way soft target = place p_choice;  topic_y 48 yes/no = place p_yes
  region softmax over regions + GLOBAL (country step 1 choice); country softmax over 100 + other_here + global (step 2 choice; region GLOBAL -> 'global')
  expected 39 dials x up/down, positive = in expected()'s returned list; LOSS MASKED for dials the engine does not ask about (reported readings, dials not allowed by the story's topics)
  done  p_done soft target, only where expected() returned items
  severity 39 dials x 5 levels, soft target = severity()[dial]['p'], masked to dials with a reading or expected item
LIMITATION (tell the captain): clef_label.py stores expected() output = the FILTERED list (max(p_up,p_down)>=.5, |net|>.05, top 4), not the raw e| answers. So a dial's 'negative' also covers weak and over-the-top-4 cases, 'done' exists only for stories with >=1 expected item, and e| probabilities are 0/1 targets, not Clef's soft values. Re-label with raw e| stored for faithful targets."""
import os, sys, json, argparse, csv
os.environ.setdefault("WE_RULES", "rules_v2"); os.environ.setdefault("WORLD_GPU", "0")
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo"]
import numpy as np, classify as C
ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("inp", nargs="+"); a = ap.parse_args()
test_ids = {json.loads(l)["id"] for l in open("/workspace/data/clef-labels/test.jsonl") if l.strip()} if os.path.exists("/workspace/data/clef-labels/test.jsonl") else set()   # id assertion only
for f in a.inp: assert "test" not in os.path.basename(f), f"refusing a test file: {f}"
rows = [json.loads(l) for f in a.inp for l in open(f) if l.strip()]; seen = set(); R = []
for r in rows:
    if r["id"] in seen: continue
    seen.add(r["id"]); assert r["id"] not in test_ids, "frozen test id in training: " + r["id"]; R.append(r)
GATE = ["g|happened", "g|announced", "g|opinion", "g|forecast", "x|recent"]; SCOPE = ["s|national", "s|local", "s|new", "x|us_focus", "x|foreign_focus"]
ATT = [(d, dr, i) for (d, dr), lst in sorted(C.ATTRS.items()) for i in range(len(lst))]; COND = [f"{d}|{dr}|{i}" for d, dr, i in ATT]
DOM = [d["id"] for d in C.DOMAINS]; DOMY = [d for d in DOM if d != "other"]
rows100 = C._country_rows(); REG = sorted({x["region"] for x in rows100}) + ["GLOBAL"]; CTY = [x["id"] for x in rows100] + ["other_here", "global"]
DIALS = sorted(C.PHRASES); EXP = [f"{d}|{u}" for d in DIALS for u in ("up", "down")]; LV = [l["id"] for l in C.LEVELS]
keys = {"gate": GATE, "scope": SCOPE, "cond": COND, "topic_c": DOM, "topic_y": DOMY, "region": REG, "country": CTY, "expected": EXP, "done": ["done"], "severity": DIALS, "levels": LV}
N = len(R); Z = lambda *s: np.zeros(s, np.float32)
T = {k: Z(N, len(keys[k])) for k in ("gate", "scope", "cond", "topic_c", "topic_y", "region", "country", "expected")} | {"expected_mask": Z(N, len(EXP))} | {"done": Z(N), "done_mask": Z(N), "severity": Z(N, len(DIALS), 5), "sev_mask": Z(N, len(DIALS))}
ci = {k: i for i, k in enumerate(CTY)}; ri = {k: i for i, k in enumerate(REG)}; ei = {k: i for i, k in enumerate(EXP)}; di = {d: i for i, d in enumerate(DIALS)}
for n, r in enumerate(R):
    P = r["P"]
    for j, k in enumerate(GATE): T["gate"][n, j] = P[k]
    for j, k in enumerate(SCOPE): T["scope"][n, j] = P[k]
    for j, (d, dr, i) in enumerate(ATT): T["cond"][n, j] = (P[f"a|{d}|{dr}|{i}|0"] + P[f"a|{d}|{dr}|{i}|1"]) / 2
    pc = {x["id"]: x["p_choice"] for x in r["place"]}; s = sum(pc.values()) or 1.0
    for j, d in enumerate(DOM): T["topic_c"][n, j] = pc.get(d, 0.0) / s
    py = {x["id"]: x["p_yes"] for x in r["place"]}
    for j, d in enumerate(DOMY): T["topic_y"][n, j] = py.get(d, 0.0)
    det = r["country_detail"]; reg = det["region_choice"]
    if reg is None: reg = "GLOBAL" if r["country"] == "global" else next(x["region"] for x in rows100 if x["id"] == r["country"])
    T["region"][n, ri[reg]] = 1.0
    T["country"][n, ci["global" if reg == "GLOBAL" else "other_here" if det.get("chose_other_here") else r["country"]]] = 1.0
    reported = {x["dial"] for x in r["read"]["readings"] if x["direction"] != "conflict"}; allowed = C.allowed_dials(r["place"])
    for d in DIALS:
        if d in reported or d not in allowed: continue
        T["expected_mask"][n, ei[f"{d}|up"]] = T["expected_mask"][n, ei[f"{d}|down"]] = 1.0
    for x in r["expected"]: T["expected"][n, ei[f"{x['dial']}|{x['direction']}"]] = 1.0
    if r["expected"]: T["done"][n] = float(np.mean([x["p_done"] for x in r["expected"]])); T["done_mask"][n] = 1.0
    for d, v in r["severity"].items():
        p = np.array([v["p"].get(l, 0.0) for l in LV], np.float32)
        if p.sum() > 0: T["severity"][n, di[d]] = p / p.sum(); T["sev_mask"][n, di[d]] = 1.0
os.makedirs(a.out, exist_ok=True); np.savez_compressed(f"{a.out}/targets.npz", **T)
json.dump([r["state_text"] for r in R], open(f"{a.out}/texts.json", "w")); json.dump({"ids": [r["id"] for r in R], **keys}, open(f"{a.out}/keys.json", "w"))
print(N, "rows;", {k: T[k].shape[1] for k in ("gate", "scope", "cond", "topic_c", "topic_y", "region", "country", "expected")}, "severity dials", len(DIALS))
