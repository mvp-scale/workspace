"""Step 1 of the Fable method (ledger S-0001): how much reader error the World engine tolerates. CPU only, no model calls.
Replays the 880 Clef-read stories (data/newsreader/labels/clef-q4km.jsonl) through the live engine's feed arithmetic (prepare_feed without the
model call: expected-impact readings omitted, ledger C-0006), entering at WORLD:world (no country in the records, C-0003), one tick per story.
Unit: the engine's 78 condition|direction reading keys. Outputs: decision likelihood change (points) for WORLD and the 8 audiences (9 x 20).

Formulas (fixed before running, ledger C-0007):
  out(run)       = 100 x (weighted mean over a group's sampled people of p_end - p_start), groups = WORLD + 8 audiences, 20 decisions
  noise band_o   = 95th percentile over all seed pairs (i<j) of |out_i,o - out_j,o|, clean readings, engine noise on, seeds 0..9
  drift_o(cell)  = mean over injection seeds of |out_inj,o - out_clean,o|, engine noise off (paired, deterministic)
  ratio(cell)    = max over outputs o of drift_o / band_o;  a cell passes when ratio <= 1
  budget(key)    = the passing cells of the TPR x FPR grid; knee = lowest passing TPR at FPR 0 and highest passing FPR at TPR 1
  rank           = keys ordered by ratio at TPR .4, FPR .01
Run with WORLD_GPU=0 WE_RULES=rules_v2 /workspace/kev/.venv/bin/python sensitivity.py <mode>."""
import os, sys, json, copy, time, argparse, itertools
os.environ.setdefault("WORLD_GPU", "0"); os.environ.setdefault("WE_RULES", "rules_v2")
import numpy as np
sys.path.insert(0, "/workspace/probes/persona"); sys.path.insert(0, "/workspace/probes/world-engine")      # world-engine first: both folders have an engine.py (same order as world_service2.py)
import engine as E, engine2 as W2, classify as C      # engine before classify: classify puts probes/persona (which has its own engine.py) first on the path
assert E.__file__.startswith("/workspace/probes/world-engine/"), E.__file__
assert not W2.GPU, "Step 1 runs on CPU only: set WORLD_GPU=0"
LABELS = "/workspace/data/newsreader/labels/clef-q4km.jsonl"
OUT = "/workspace/data/step1"
FEED_SCALE, FEED_CAP = 0.5, 0.4                       # world_service2.py:459
KEYS = sorted(C.ATTRS)                               # 78 (dial, direction)
TPRS = [1.0, 0.8, 0.6, 0.4, 0.2]; FPRS = [0.0, 0.005, 0.01, 0.02, 0.05]
G = {}                                               # globals shared with forked workers

# ---------------- stories: which keys are present, and with what strength (C.read's rule, kept per direction)
def presence(P, wording=None):
    """wording None = the engine's rule (mean of the two wordings); 0 or 1 = that wording alone (Clef against itself, after-the-fact context)."""
    keys = {}
    for (d, dirn), lst in C.ATTRS.items():
        ms = [(P[f"a|{d}|{dirn}|{i}|0"] + P[f"a|{d}|{dirn}|{i}|1"]) / 2 if wording is None else P[f"a|{d}|{dirn}|{i}|{wording}"] for i in range(len(lst))]
        ms = [m for m in ms if m >= C.ATTR_MIN]
        if ms: keys[(d, dirn)] = round(max(ms), 3)
    return keys
def readings_of(keys):
    """C.read's dial rule: exactly one direction present -> a reading; both -> conflict (no amount)."""
    out = []
    for d in sorted({k[0] for k in keys}):
        dirs = [x for x in ("up", "down") if (d, x) in keys]
        if len(dirs) == 1: out.append((d, dirs[0], keys[(d, dirs[0])]))
    return out
def load_stories():
    st = []
    for l in open(LABELS):
        r = json.loads(l); P = r["P"]; rd = C.read(P)
        w_, _, _ = C.type_weight(rd["gate"]["happened"], rd["gate"]["announced"], rd["gate"]["opinion"], P["g|forecast"])
        keys = presence(P)
        mine = sorted((d, x, s) for d, x, s in readings_of(keys)); theirs = sorted((x["dial"], x["direction"], x["strength"]) for x in rd["readings"] if x["direction"] != "conflict")
        assert mine == theirs, f"reconstruction differs from C.read for {r['id']}"
        st.append({"id": r["id"], "w": w_, "keys": keys})
    return st

# ---------------- engine state and output sample
def build(sample_n=30000, sample_seed=7):
    import world_service2 as WS
    S = WS.Session(); w0 = copy.deepcopy(S.w); w0.log = []
    p = S.pop; rng = np.random.default_rng(sample_seed)
    idx = np.arange(p.n) if sample_n >= p.n else np.sort(rng.choice(p.n, sample_n, replace=False))
    G.update(w0=w0, T0=w0.totals(), base=p.base[idx], sal=p.sal[idx], region=p.region[idx], seg=p.seg[idx], wt=p.wt[idx], seg_gain=S.seg_gain, cid=w0.cid, nseg=len(S.segs))
    G["p0"] = person_p(G["T0"])
def person_p(T):
    R = np.stack([T[f"REGION:{c}-{s}"] for c in G["cid"] for s in W2.SETTLES]); d = R[G["region"]] * G["seg_gain"][G["seg"]]
    eff = np.clip(G["base"] * np.exp(np.log(np.maximum(1 + G["sal"] * d, 0.2)) @ E.GRID.T), 0.5, 5.5)
    return 1 / (1 + np.exp(-(E.BIAS + ((eff - 3.0) / 1.5) @ E.W.T)))
def outputs(T):
    dp = (person_p(T) - G["p0"]) * 100; wt = G["wt"]; rows = [np.average(dp, axis=0, weights=wt)]
    for s in range(G["nseg"]): m = G["seg"] == s; rows.append(np.average(dp[m], axis=0, weights=wt[m]))
    return np.array(rows)                           # 9 x 20

# ---------------- replay
def replay(story_readings, seed=0, noise=False, ticks=1):
    w = copy.deepcopy(G["w0"]); w.rng = np.random.default_rng(seed); w.noise = noise
    for i, (rs, wt_) in enumerate(story_readings):
        t = w.tick
        for d, dirn, s in rs: w.add(t, "WORLD:world", d, (0.10 if dirn == "up" else -0.10) * s * wt_ * FEED_SCALE, f"s{i}")
        w.add(t, "WORLD:world", "news_overload", 0.01, f"s{i}")
        for _ in range(ticks): w.step()
        for n in w.delta: np.clip(w.delta[n], -FEED_CAP, FEED_CAP, out=w.delta[n])
        w.log = []
    return outputs(w.totals())
def clean_readings(stories): return [(readings_of(s["keys"]), s["w"]) for s in stories]
def inject(stories, key, tpr, fpr, seed, med):
    rng = np.random.default_rng(seed); out = []
    for s in stories:
        k = dict(s["keys"])
        if key in k:
            if rng.random() >= tpr: del k[key]
        elif rng.random() < fpr: k[key] = med[key]
        out.append((readings_of(k), s["w"]))
    return out
def medians(stories):
    allv = [v for s in stories for v in s["keys"].values()]; g = float(np.median(allv))
    return {k: float(np.median(v)) if (v := [s["keys"][k] for s in stories if k in s["keys"]]) else g for k in KEYS}

def inject_joint(stories, tpr, fpr, seed, med, clustered=False):
    """Every key at once. Independent: each key dropped/added on its own. Clustered (C-0002): a story is 'badly read' with probability 1 - tpr;
    a badly read story loses all its keys and takes all the false positives (each absent key added with probability fpr / (1 - tpr)), so the
    marginal rates match the independent mode but errors pile up in the same stories."""
    rng = np.random.default_rng(seed); out = []; fp_bad = min(1.0, fpr / max(1e-9, 1 - tpr))
    for s in stories:
        if clustered:
            if rng.random() < 1 - tpr: k = {key: med[key] for key in KEYS if rng.random() < fp_bad}
            else: k = dict(s["keys"])
        else:
            k = {key: v for key, v in s["keys"].items() if rng.random() < tpr}
            for key in KEYS:
                if key not in s["keys"] and rng.random() < fpr: k[key] = med[key]
        out.append((readings_of(k), s["w"]))
    return out
JOINT = [(0.8, 0.005), (0.6, 0.01), (0.4, 0.01)]
JOINT_FINE = [(0.95, 0.001), (0.9, 0.001), (0.95, 0.0025), (0.9, 0.0025)]          # ledger R-0022: where all-keys error meets tolerance (d)
LEVELS = [(1.0, 0.0), (0.8, 0.005), (0.6, 0.01), (0.4, 0.01)]         # Morris levels 0..3 per key (clean -> the old plateau)
def inject_levels(stories, lv, U, med):
    """Every key at its own level; U (stories x keys) fixed across runs (common random numbers): a present key is dropped when U < 1 - tpr, an absent one added when U < fpr."""
    out = []
    for i, s in enumerate(stories):
        k = {}
        for j, key in enumerate(KEYS):
            t, f = LEVELS[int(round(lv[j]))]
            if key in s["keys"]:
                if U[i, j] >= 1 - t: k[key] = s["keys"][key]
            elif U[i, j] < f: k[key] = med[key]
        out.append((readings_of(k), s["w"]))
    return out
def _morris(args):
    n, lv = args
    return n, replay(inject_levels(G["stories"], lv, G["U"], G["med"]))
def _joint(args):
    tpr, fpr, cl, iseed, order, ticks = args
    st = G["stories"]
    if order: rng = np.random.default_rng(order); st = [st[i] for i in rng.permutation(len(st))]
    rs = inject_joint(st, tpr, fpr, 3000 + iseed, G["med"], cl) if tpr is not None else clean_readings(st)
    return args, replay(rs, ticks=ticks)
def _boot(args):
    b, key = args
    rng = np.random.default_rng(5000 + b); st = [G["stories"][i] for i in rng.integers(0, len(G["stories"]), len(G["stories"]))]
    clean = G["boot_clean"][b] if key else None
    if key is None: return args, replay(clean_readings(st))
    return args, replay(inject(st, key, 0.4, 0.01, 7000 + b, G["med"]))
def _cell(args):
    key, tpr, fpr, iseed = args
    return key, tpr, fpr, iseed, replay(inject(G["stories"], key, tpr, fpr, 1000 + iseed, G["med"]))
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("mode", choices=["check", "sample", "noise", "grid", "joint", "order", "boot", "self", "morris", "self3", "jointfine"]); ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--inj-seeds", type=int, default=3); ap.add_argument("--seeds", type=int, default=10); ap.add_argument("--keys", default=""); ap.add_argument("--boots", type=int, default=20); ap.add_argument("--trajectories", type=int, default=10)
    a = ap.parse_args(); os.makedirs(OUT, exist_ok=True); t0 = time.time()
    stories = load_stories(); G["stories"] = stories; G["med"] = medians(stories)
    if a.mode == "check":
        freq = {f"{d}|{x}": sum((d, x) in s["keys"] for s in stories) for d, x in KEYS}
        json.dump({"stories": len(stories), "keys": len(KEYS), "reconstruction": "matches C.read on every story", "key_freq": freq}, open(f"{OUT}/check.json", "w"), indent=1)
        print(len(stories), "stories,", len(KEYS), "keys; reconstruction matches C.read; keys never present:", sum(v == 0 for v in freq.values())); return
    if a.mode == "sample":
        build(sample_n=10**9); full = replay(clean_readings(stories)); fullp0 = G["p0"]
        build(); samp = replay(clean_readings(stories))
        rel = np.abs(samp - full).sum() / np.abs(full).sum()
        json.dump({"full": full.tolist(), "sample30k": samp.tolist(), "relative_L1_error": rel, "max_abs_diff_points": float(np.abs(samp - full).max())}, open(f"{OUT}/sample-check.json", "w"))
        print("relative L1 error of 30k sample vs full:", round(float(rel), 4), "max abs diff (points):", round(float(np.abs(samp - full).max()), 4), round(time.time() - t0), "s"); return
    build()
    if a.mode == "morris":
        sys.path.insert(0, "/workspace/models/salib-lib"); from SALib.sample import morris as MS
        import multiprocessing as mp
        prob = {"num_vars": len(KEYS), "names": ["|".join(k) for k in KEYS], "bounds": [[0, 3]] * len(KEYS)}
        X = MS.sample(prob, a.trajectories, num_levels=4, seed=11); G["U"] = np.random.default_rng(9000).random((len(stories), len(KEYS)))
        clean = replay(clean_readings(stories)); res = {}
        with mp.get_context("fork").Pool(a.workers) as pool:
            for n, o in pool.imap_unordered(_morris, list(enumerate(X)), chunksize=2):
                res[n] = o
                if len(res) % 100 == 0: print(f"{len(res)}/{len(X)} {round(time.time() - t0)} s", flush=True)
        np.savez(f"{OUT}/morris.npz", X=X, outs=np.array([res[i] for i in range(len(X))]), clean=clean, names=np.array(prob["names"]))
        print("morris done", len(X), "runs", round(time.time() - t0), "s"); return
    if a.mode == "self3":                                            # ledger D-0004: three Clef wordings (0, 1, 2 = the attribute definition)
        W3 = {r["id"]: r["P3"] for r in map(json.loads, open(LABELS.replace(".jsonl", "-w3.jsonl")))}
        clean = replay(clean_readings(stories)); res = {}
        for wd in (0, 1, 2):
            rs = []
            for l, s_ in zip(open(LABELS), stories):
                r = json.loads(l); rs.append((readings_of(presence({**r["P"], **W3[r["id"]]}, wd)), s_["w"]))
            res[wd] = replay(rs)
        np.savez(f"{OUT}/self3.npz", clean=clean, w0=res[0], w1=res[1], w2=res[2]); print("self3 done", round(time.time() - t0), "s"); return
    if a.mode == "self":
        clean = replay(clean_readings(stories)); res = {}
        for wd in (0, 1):
            rs = []
            for l, s_ in zip(open(LABELS), stories): rs.append((readings_of(presence(json.loads(l)["P"], wd)), s_["w"]))
            res[wd] = replay(rs)
        np.savez(f"{OUT}/self.npz", clean=clean, w0=res[0], w1=res[1]); print("self done", round(time.time() - t0), "s"); return
    if a.mode == "noise":
        cr = clean_readings(stories); outs = np.array([replay(cr, seed=s, noise=True) for s in range(a.seeds)]); off = replay(cr, noise=False)
        pair = np.array([np.abs(outs[i] - outs[j]) for i, j in itertools.combinations(range(a.seeds), 2)]); band = np.percentile(pair, 95, axis=0)
        np.savez(f"{OUT}/noise.npz", outs=outs, clean_off=off, band=band)
        print("noise band (points): median", float(np.median(band)), "max", float(band.max()), "| clean effect |median|", float(np.median(np.abs(off))), "max", float(np.abs(off).max()), round(time.time() - t0), "s"); return
    if a.mode in ("joint", "order", "boot", "jointfine"):
        import multiprocessing as mp
        G["clean"] = replay(clean_readings(stories)); res = {}
        if a.mode == "jointfine": jobs = [(t, f, cl, s, 0, 1) for t, f in JOINT_FINE for cl in (False, True) for s in range(a.inj_seeds)]
        if a.mode == "joint": jobs = [(t, f, cl, s, 0, 1) for t, f in JOINT for cl in (False, True) for s in range(a.inj_seeds)]
        if a.mode == "order": jobs = [(t, f, False, 0, o, k) for o in (0, 1, 2, 3) for k in (1, 2) for t, f in [(None, None), (0.4, 0.01)]]
        if a.mode == "boot":
            G["boot_clean"] = {}
            with mp.get_context("fork").Pool(a.workers) as pool:
                for (b, _), o in pool.imap_unordered(_boot, [(b, None) for b in range(a.boots)]): G["boot_clean"][b] = o
            jobs = [(b, k) for b in range(a.boots) for k in KEYS]; fn = _boot
        else: fn = _joint
        with mp.get_context("fork").Pool(a.workers) as pool:
            for n, (args, o) in enumerate(pool.imap_unordered(fn, jobs, chunksize=2)):
                res[args] = o
                if n % 100 == 0: print(f"{n}/{len(jobs)} {round(time.time() - t0)} s", flush=True)
        extra = {"boot_clean": np.array([G["boot_clean"][b] for b in range(a.boots)])} if a.mode == "boot" else {}
        np.savez(f"{OUT}/{a.mode}.npz", args=np.array([json.dumps([x if not isinstance(x, tuple) else "|".join(x) for x in k]) for k in res]), outs=np.array(list(res.values())), clean=G["clean"], **extra)
        print(a.mode, "done", len(res), "runs", round(time.time() - t0), "s"); return
    if a.mode == "grid":
        import multiprocessing as mp
        keys = [tuple(k.split("|")) for k in a.keys.split(",")] if a.keys else KEYS
        G["clean"] = replay(clean_readings(stories))
        jobs = [(k, t, f, s) for k in keys for t in TPRS for f in FPRS if not (t == 1.0 and f == 0.0) for s in range(a.inj_seeds)]
        res = {}
        with mp.get_context("fork").Pool(a.workers) as pool:
            for n, (k, t, f, s, o) in enumerate(pool.imap_unordered(_cell, jobs, chunksize=4)):
                res[(k, t, f, s)] = o
                if n % 200 == 0: print(f"{n}/{len(jobs)} {round(time.time() - t0)} s", flush=True)
        np.savez(f"{OUT}/grid.npz", keys=np.array(["|".join(k) for k, *_ in res]), cells=np.array([[t, f, s] for _, t, f, s in res]), outs=np.array(list(res.values())), clean=G["clean"])
        print("grid done", len(res), "runs", round(time.time() - t0), "s")
if __name__ == "__main__": main()
