"""T214 (step 21): the clean version of t213. Clef reads each question in two wordings; the engine averages them. t213 compared one wording with the average (which contains it). Here wording 0 alone is replayed against wording 1 alone: two equally good, independent readings of the same story by the same reader. The share of engine outputs within the Step 1 band is the ceiling for any reader. No new model run. (t213 text follows.) Calibrate the Step 1 noise band. Same 800 held-out state-text stories and the same T35 harness as t211 and t212, no CPU heads. The engine's presence rule averages Clef's two question wordings per attribute; sensitivity.presence(P, wording=0 or 1) reads one wording alone. Replay Clef's single-wording readings against the two-wording reading and report the share of engine outputs within the band (same band as t211: 95th percentile of pairwise replays with engine noise), the median ratio to the band and the fired keys that differ per story. This is Clef against itself: the share a reader that is as good as a re-read of Clef would reach. Prediction in card T148-O.
Run (from projects/world-state): R=800 OUT=runs/pulse/t214 /workspace/kev/.venv/bin/python -u t214_clef_wordings.py"""
import os, sys, json, time, pathlib, itertools, numpy as np
os.environ.setdefault("WORLD_GPU", "0"); os.environ.setdefault("WE_RULES", "rules_v2")
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t214")); OUT.mkdir(parents=True, exist_ok=True); R = int(os.environ.get("R", 800)); T0 = time.time()
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
res = {"stories_replayed": len(idx), "band_median_points": round(float(np.median(band)), 4)}
k0 = [SN.presence(rows[i]["P"], wording=0) for i in idx]; k1 = [SN.presence(rows[i]["P"], wording=1) for i in idx]
o0 = SN.replay([(SN.readings_of(k), s["w"]) for k, s in zip(k0, stories)]); o1 = SN.replay([(SN.readings_of(k), s["w"]) for k, s in zip(k1, stories)]); d = np.abs(o0 - o1) / band
res["wording0_vs_wording1"] = {"share_outputs_within_band": round(float((d <= 1).mean()), 3), "ratio_median": round(float(np.median(d)), 3), "ratio_max": round(float(d.max()), 3), "fired_keys_differing_per_story": round(sum(len(set(a_) ^ set(b_)) for a_, b_ in zip(k0, k1)) / len(k0), 3), "fired_keys_per_story_w0": round(sum(len(k) for k in k0) / len(k0), 3), "fired_keys_per_story_w1": round(sum(len(k) for k in k1) / len(k1), 3)}
rng2 = np.random.RandomState(11); boots = []
for _ in range(200): ii = rng2.randint(0, len(d), len(d)); boots.append(float((d[ii] <= 1).mean()))
res["wording0_vs_wording1"]["share_ci95"] = [round(float(np.percentile(boots, 2.5)), 3), round(float(np.percentile(boots, 97.5)), 3)]
res["share_within_band_w0_vs_w1"] = res["wording0_vs_wording1"]["share_outputs_within_band"]
res["seconds"] = round(time.time() - T0)
json.dump(res, open(OUT / "t214_clef_wordings.json", "w"), indent=1); print(json.dumps(res, indent=1))
