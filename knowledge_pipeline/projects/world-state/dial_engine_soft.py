"""T35 soft calibrated reader through the engine replay (pre-registered L928). Same stories, clean replay and noise band as dial_engine_replay.py. A reading's amount is calibrated probability x key median strength, for up and down separately (no conflict rule); keys without a head get their base rate; story type weight is Clef's own (an already-Ready field, noted as a caveat).
    WORLD_GPU=0 WE_RULES=rules_v2 /workspace/kev/.venv/bin/python dial_engine_soft.py   (from projects/world-state)"""
import os, sys, json, time, itertools
os.environ.setdefault("WORLD_GPU", "0"); os.environ.setdefault("WE_RULES", "rules_v2")
import numpy as np
sys.path.insert(0, "/workspace/probes/world-engine"); import sensitivity as SN
t0 = time.time(); stories = SN.load_stories(); SN.G["stories"] = stories; SN.G["med"] = SN.medians(stories); SN.build(); med = SN.G["med"]
Z = np.load("runs/pulse/dial_soft_p.npz"); assert list(Z["ids"]) == [s["id"] for s in stories]; P = Z["P"]; hk = [tuple(k.split("|")) for k in Z["keys"]]; hidx = {k: j for j, k in enumerate(hk)}
N = len(stories); base = {k: sum(k in s["keys"] for s in stories) / N for k in SN.KEYS}
clean = SN.replay(SN.clean_readings(stories)); cr = SN.clean_readings(stories)
outs = np.array([SN.replay(cr, seed=s, noise=True) for s in range(10)]); pair = np.array([np.abs(outs[i] - outs[j]) for i, j in itertools.combinations(range(10), 2)]); band = np.percentile(pair, 95, axis=0)
print("band median", float(np.median(band)), round(time.time() - t0), "s", flush=True)
def run(amount):
    rs = [([(k[0], k[1], amount(i, k) * med[k]) for k in SN.KEYS if amount(i, k) > 0], s["w"]) for i, s in enumerate(stories)]; o = SN.replay(rs); d = np.abs(o - clean) / band
    return {"ratio_max": round(float(d.max()), 3), "ratio_median": round(float(np.median(d)), 3), "share_outputs_within_band": round(float((d <= 1).mean()), 3)}
res = {"stories": N, "band_median_points": round(float(np.median(band)), 4)}
res["prior_only"] = run(lambda i, k: base[k]); print("prior_only", res["prior_only"], flush=True)
res["soft_calibrated"] = run(lambda i, k: float(P[i, hidx[k]]) if k in hidx else base[k]); print("soft_calibrated", res["soft_calibrated"], flush=True)
res["soft_head_keys_only_zero_elsewhere"] = run(lambda i, k: float(P[i, hidx[k]]) if k in hidx else 0.0); print("soft_head_only", res["soft_head_keys_only_zero_elsewhere"], flush=True)
json.dump(res, open("runs/pulse/dial_engine_soft.json", "w"), indent=1); print(json.dumps(res, indent=1), round(time.time() - t0), "s")
