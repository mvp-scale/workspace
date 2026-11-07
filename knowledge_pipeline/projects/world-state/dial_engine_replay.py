"""T35 direct engine-level test (pre-registered L926): replay the 1736 Clef-read stories through the engine feed arithmetic of probes/world-engine/sensitivity.py, once with Clef's readings (clean) and once with the CPU reader's out-of-fold keys (runs/pulse/dial_heads_cv_scores.npz), and compare end-state outputs (9 groups x 20 decisions) against the engine's own noise band (S-0001 definition: ratio = max over outputs of drift / band; pass at 1 or less). Band recomputed on the same stories: 10 seeds, noise on, 95th percentile of seed-pair differences.
    WORLD_GPU=0 WE_RULES=rules_v2 /workspace/kev/.venv/bin/python dial_engine_replay.py   (from projects/world-state)"""
import os, sys, json, time, itertools
os.environ.setdefault("WORLD_GPU", "0"); os.environ.setdefault("WE_RULES", "rules_v2")
import numpy as np
sys.path.insert(0, "/workspace/probes/world-engine"); import sensitivity as SN
t0 = time.time(); stories = SN.load_stories(); SN.G["stories"] = stories; SN.G["med"] = SN.medians(stories); SN.build()
Z = np.load("runs/pulse/dial_heads_cv_scores.npz"); assert list(Z["ids"]) == [s["id"] for s in stories], "story order differs"
S = Z["S"]; hk = [tuple(k.split("|")) for k in Z["keys"]]; med = SN.G["med"]
clean = SN.replay(SN.clean_readings(stories)); print("clean replay", round(time.time() - t0), "s", flush=True)
cr = SN.clean_readings(stories); outs = np.array([SN.replay(cr, seed=s, noise=True) for s in range(10)])
pair = np.array([np.abs(outs[i] - outs[j]) for i, j in itertools.combinations(range(10), 2)]); band = np.percentile(pair, 95, axis=0); print("band median", float(np.median(band)), "max", float(band.max()), round(time.time() - t0), "s", flush=True)
def run(keyfn):
    rs = [(SN.readings_of(keyfn(i, s)), s["w"]) for i, s in enumerate(stories)]; o = SN.replay(rs); d = np.abs(o - clean) / band
    return {"ratio_max": round(float(d.max()), 3), "ratio_median": round(float(np.median(d)), 3), "share_outputs_within_band": round(float((d <= 1).mean()), 3)}
res = {"stories": len(stories), "band_median_points": round(float(np.median(band)), 4), "band_max_points": round(float(band.max()), 4)}
res["empty_reader"] = run(lambda i, s: {})
res["perfect_on_4_dials"] = run(lambda i, s: {k: v for k, v in s["keys"].items() if k[0] in ("air_pollution", "biodiversity_loss", "civil_unrest", "cyber_insecurity")})
res["clef_keys_with_head_only"] = run(lambda i, s: {k: v for k, v in s["keys"].items() if k in set(hk)})
for th in (0.5, 0.7, 0.9, 0.98):
    res[f"reader_th_{th}".replace(".", "_")] = run(lambda i, s, th=th: {hk[j]: med[hk[j]] for j in np.where(S[i] >= th)[0]})
    print(th, res[f"reader_th_{th}".replace(".", "_")], flush=True)
json.dump(res, open("runs/pulse/dial_engine_replay.json", "w"), indent=1); print(json.dumps(res, indent=1), round(time.time() - t0), "s")
