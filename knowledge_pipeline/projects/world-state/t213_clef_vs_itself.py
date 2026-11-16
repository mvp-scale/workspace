"""T213 (step 20): calibrate the Step 1 noise band. Same 800 held-out state-text stories and the same T35 harness as t211 and t212, no CPU heads. The engine's presence rule averages Clef's two question wordings per attribute; sensitivity.presence(P, wording=0 or 1) reads one wording alone. Replay Clef's single-wording readings against the two-wording reading and report the share of engine outputs within the band (same band as t211: 95th percentile of pairwise replays with engine noise), the median ratio to the band and the fired keys that differ per story. This is Clef against itself: the share a reader that is as good as a re-read of Clef would reach. Prediction in card T148-O.
Run (from projects/world-state): R=800 OUT=runs/pulse/t213 /workspace/kev/.venv/bin/python -u t213_clef_vs_itself.py"""
import os, sys, json, time, pathlib, itertools, numpy as np
os.environ.setdefault("WORLD_GPU", "0"); os.environ.setdefault("WE_RULES", "rules_v2")
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t213")); OUT.mkdir(parents=True, exist_ok=True); R = int(os.environ.get("R", 800)); T0 = time.time()
sys.path.insert(0, "/workspace/probes/world-engine"); import sensitivity as SN, classify as C
rows = []; seen = set()
for f in ("test", "r3", "r5", "c1", "r1_local", "r1b"):
    for l in open("/workspace/data/clef-labels/" + f + ".jsonl"):
        try: r = json.loads(l)
        except Exception: continue
        if "P" in r and len(r["P"]) == 328 and r["id"] not in seen: seen.add(r["id"]); rows.append(r)
n = len(rows); pub = [r.get("day") or "" for r in rows]; order = np.argsort(pub); te = np.zeros(n, bool); te[order[int(0.7 * n):]] = True
rng = np.random.RandomState(5); idx = np.where(te)[0]; idx = np.sort(rng.choice(idx, min(R, len(idx)), replace=False)); print("replay stories", len(idx), flush=True)
def weight(P): rd = C.read(P); w_, _, _ = C.type_weight(rd["gate"]["happened"], rd["gate"]["announced"], rd["gate"]["opinion"], P["g|forecast"]); return w_
stories = [{"id": rows[i]["id"], "w": weight(rows[i]["P"]), "keys": SN.presence(rows[i]["P"])} for i in idx]
SN.G["stories"] = stories; SN.G["med"] = SN.medians(stories); SN.build()
clean = SN.replay(SN.clean_readings(stories)); cr = SN.clean_readings(stories); outs = np.array([SN.replay(cr, seed=s, noise=True) for s in range(10)])
pair = np.array([np.abs(outs[i] - outs[j]) for i, j in itertools.combinations(range(10), 2)]); band = np.percentile(pair, 95, axis=0); print("band median", float(np.median(band)), round(time.time() - T0), flush=True)
res = {"stories_replayed": len(idx), "band_median_points": round(float(np.median(band)), 4), "fired_keys_per_story_two_wording": round(sum(len(s["keys"]) for s in stories) / len(stories), 3)}
for w in (0, 1):
    ks = [SN.presence(rows[i]["P"], wording=w) for i in idx]; o = SN.replay([(SN.readings_of(k), s["w"]) for k, s in zip(ks, stories)]); d = np.abs(o - clean) / band
    diff = sum(len(set(k) ^ set(s["keys"])) for k, s in zip(ks, stories)) / len(stories)
    res[f"wording_{w}_alone"] = {"share_outputs_within_band": round(float((d <= 1).mean()), 3), "ratio_median": round(float(np.median(d)), 3), "ratio_max": round(float(d.max()), 3), "fired_keys_differing_per_story": round(diff, 3), "fired_keys_per_story": round(sum(len(k) for k in ks) / len(ks), 3)}
res["share_within_band_wording0"] = res["wording_0_alone"]["share_outputs_within_band"]; res["seconds"] = round(time.time() - T0)
json.dump(res, open(OUT / "t213_clef_vs_itself.json", "w"), indent=1); print(json.dumps(res, indent=1))
