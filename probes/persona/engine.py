"""Toy world-dial engine v0 (see persona-profile-standard.md, 'Engine v0'). Pure numpy, no GPU, no model calls.
    /workspace/kev/.venv/bin/python engine.py
"""
import hashlib, json, time
import numpy as np
from personas import gen, TRAITS

DIALS = ["prices", "job_security", "safety_fear", "health_risk", "trust_institutions", "community", "tech_pace", "disruption", "optimism", "news_overload"]
ELEMS = TRAITS + ["stress", "optimism"]            # 8 elements: tech price privacy social time novelty stress optimism
DECS = ["spend", "buy_new", "subscribe", "travel", "change_work", "move", "switch_brand", "share"]
OPP = np.array([.20, .05, .02, .01, .002, .001, .01, .10])   # base chance a persona meets decision d on a tick
HALF = np.array([150, 200, 100, 150, 300, 300, 50, 80, 200, 20.0])   # dial half-lives in ticks

def table(entries, rows, cols):
    t = np.zeros((len(rows), len(cols)))
    for (r, c), v in entries.items(): t[rows.index(r), cols.index(c)] = v
    return t
# strength of dial -> element (rows = elements, cols = dials). guesses.
GAMMA = table({("price", "prices"): .8, ("stress", "prices"): .6, ("stress", "job_security"): -.8, ("stress", "health_risk"): .3, ("privacy", "trust_institutions"): -.5,
               ("privacy", "safety_fear"): .2, ("social", "community"): .5, ("social", "safety_fear"): -.3, ("time", "disruption"): .6, ("time", "news_overload"): .2,
               ("tech", "tech_pace"): .1, ("novelty", "optimism"): .5, ("novelty", "safety_fear"): -.3, ("optimism", "optimism"): 1.0, ("optimism", "prices"): -.4,
               ("optimism", "job_security"): .5}, ELEMS, DIALS)
# weight of element (standardised level) -> decision, and bias. guesses.
W = table({("spend", "stress"): -1.0, ("spend", "optimism"): .8, ("spend", "price"): -.8, ("buy_new", "novelty"): .8, ("buy_new", "price"): -.9, ("buy_new", "stress"): -.6, ("buy_new", "tech"): .2,
           ("subscribe", "price"): -1.0, ("subscribe", "privacy"): -.3, ("subscribe", "stress"): -.5, ("subscribe", "time"): -.3, ("travel", "stress"): -.8, ("travel", "time"): -.6,
           ("travel", "novelty"): .6, ("travel", "optimism"): .5, ("change_work", "stress"): .4, ("change_work", "optimism"): .4, ("change_work", "novelty"): .5,
           ("move", "novelty"): .5, ("move", "stress"): .2, ("switch_brand", "price"): .9, ("switch_brand", "novelty"): .5, ("share", "social"): .9, ("share", "privacy"): -.7,
           ("share", "time"): -.4}, DECS, ELEMS)
BIAS = np.array([0, -.5, -.8, -.3, -1.5, -2.2, -1.0, -.5])

class Pop:
    def __init__(self, n, seed=1):
        ps = [gen(s) for s in range(1, n + 1)]; inc = np.array([["under $30,000", "$30,000 to $60,000", "$60,000 to $100,000", "over $100,000"].index(p["income"]) for p in ps])
        base = np.column_stack([[p["latent"][t] for p in ps] for t in TRAITS] + [1 + 0.5 * (3 - inc), np.full(n, 3.0)]).astype(np.float32)   # tech..novelty, stress, optimism
        self.n, self.base, self.age, self.inc = n, base, np.array([p["age"] for p in ps]), inc
        self.sal = np.random.default_rng(seed).uniform(.3, 1.0, (n, len(DIALS))).astype(np.float32)   # how strongly each persona perceives each dial

def rates(pop, w, gamma=GAMMA, dials_override=None):
    """expected act rate per persona per decision at dial vector w (10,). returns (n, 8)"""
    perceived = 1 + pop.sal * (w - 1)                                        # (n,10)
    eff = pop.base * np.exp(np.log(perceived) @ gamma.T)                       # (n,8) product of perceived^gamma
    z = (eff - 3.0) / 1.5
    return OPP / 1.0 * (1 / (1 + np.exp(-(z @ W.T + BIAS))))

def run(pop, events, ticks, seed=0, gamma=GAMMA, sample=True, log_every=50):
    rng = np.random.default_rng(seed); w = np.ones(len(DIALS)); decay = 0.5 ** (1 / HALF); out = {"w": [], "exp": [], "acts": []}
    for t in range(ticks):
        w = 1 + (w - 1) * decay
        for (tt, dial, factor) in events:
            if tt == t: w[DIALS.index(dial)] *= factor
        r = rates(pop, w, gamma)
        out["w"].append(w.copy()); out["exp"].append(r.mean(0))
        if sample: out["acts"].append((rng.random(r.shape) < r).sum(0))
    return out

def hash_run(o): return hashlib.sha1(np.array(o["acts"]).tobytes()).hexdigest()[:12]

if __name__ == "__main__":
    t0 = time.time(); pop = Pop(100_000); print(f"population of {pop.n:,} built in {time.time()-t0:.1f}s")
    res = {}
    # E1 determinism (20k, 100 ticks, with sampling)
    small = Pop(20_000); ev = [(10, "prices", 1.3)]
    a, b, c = run(small, ev, 100, 5), run(small, ev, 100, 5), run(small, ev, 100, 6)
    res["E1"] = hash_run(a) == hash_run(b) and hash_run(a) != hash_run(c); print("E1 same seed identical, other seed differs:", res["E1"])
    # E2 neutral
    n0 = run(pop, [], 30, sample=False); drift = float(np.abs(np.array(n0["exp"]) - n0["exp"][0]).max()); res["E2"] = drift < 1e-9; print("E2 neutral drift", drift, res["E2"])
    # scenario: prices x1.3 at tick 100, 1000 ticks, timed
    PEAK = 100; t0 = time.time(); base = run(pop, [], 1000, sample=False); base_t = time.time() - t0
    t0 = time.time(); price = run(pop, [(PEAK, "prices", 1.3)], 1000, sample=True); dt = time.time() - t0
    res["E5"] = dt < 120; print(f"E5 100k personas x 1000 ticks (with sampling) {dt:.1f}s = {dt/1000*1000:.0f} ms/tick (no sampling {base_t:.1f}s)", res["E5"])
    E0 = np.array(base["exp"]); E1 = np.array(price["exp"]); rel = (E1[PEAK] - E0[PEAK]) / E0[PEAK]
    print("prices x1.3 peak, relative change in act rate:", {d: f"{x*100:+.1f}%" for d, x in zip(DECS, rel)})
    # E3 direction
    hi = pop.base[:, 1] >= 4; lo = pop.base[:, 1] <= 2
    r_hi = rates(pop, price["w"][PEAK]); r_hi0 = rates(pop, np.ones(10)); drop = lambda m, d: 1 - r_hi[m, d].mean() / r_hi0[m, d].mean()
    sub, buy = DECS.index("subscribe"), DECS.index("buy_new")
    ratio_sub = drop(hi, sub) / drop(lo, sub); ratio_buy = drop(hi, buy) / drop(lo, buy)
    t = run(pop, [(0, "tech_pace", 1.5)], 2, sample=False); tp = np.abs((np.array(t["exp"])[1] - E0[1]) / E0[1])[[buy, sub]].max()
    res["E3"] = rel[sub] < 0 and rel[buy] < 0 and ratio_sub >= 1.25 and ratio_buy >= 1.25 and tp < .01
    print(f"E3 subscribe {rel[sub]*100:+.1f}%, buy_new {rel[buy]*100:+.1f}%; drop high-price/low-price group: subscribe x{ratio_sub:.2f}, buy_new x{ratio_buy:.2f}; tech_pace shock moves them {tp*100:.2f}%", res["E3"])
    # E4 decay
    k = PEAK + int(6 * HALF[0]); ok_dial = abs(price["w"][k][0] - 1) < .02 if k < 1000 else None
    if ok_dial is None: price6 = run(pop, [(0, "prices", 1.3)], int(6 * HALF[0]) + 2, sample=False); wd = price6["w"][-1][0]; gd = float(np.abs((np.array(price6["exp"])[-1] - E0[0]) / E0[0]).max()); ok_dial = abs(wd - 1) < .02; ok_gate = gd < .01
    else: ok_gate = float(np.abs((E1[k] - E0[k]) / E0[k]).max()) < .01
    res["E4"] = bool(ok_dial and ok_gate); print("E4 six half-lives later: dial within 2% of 1:", ok_dial, "; gate rates within 1% of baseline:", ok_gate)
    # E6 explanation by resetting one dial at a time (subscribe, peak)
    w_pk = price["w"][PEAK]; tot = rates(pop, w_pk)[:, sub].mean() - rates(pop, np.ones(10))[:, sub].mean(); parts = {}
    for k_, d in enumerate(DIALS):
        w2 = w_pk.copy(); w2[k_] = 1; parts[d] = tot - (rates(pop, w2)[:, sub].mean() - rates(pop, np.ones(10))[:, sub].mean())
    s = sum(parts.values()); top = max(parts, key=lambda d: abs(parts[d]))
    res["E6"] = abs(s - tot) / abs(tot) <= .15 and top == "prices"; print(f"E6 subscribe total effect {tot:+.5f}, sum of single-dial effects {s:+.5f} ({abs(s-tot)/abs(tot)*100:.1f}% gap); largest dial: {top}", res["E6"])
    # E7 sensitivity: redraw the strengths
    g = np.random.default_rng(1); effs = []
    for _ in range(20):
        G = GAMMA * g.uniform(.5, 1.5, GAMMA.shape); effs.append(rates(pop, w_pk, G)[:, sub].mean() / rates(pop, np.ones(10), G)[:, sub].mean() - 1)
    print(f"E7 subscribe peak effect across 20 redraws of the strengths: min {min(effs)*100:+.1f}%, max {max(effs)*100:+.1f}%, nominal {rel[sub]*100:+.1f}%  (range {abs(max(effs)-min(effs))*100:.1f} points)")
    cohort = {}; bands = ["18-29", "30-44", "45-59", "60-74", "75-90"]
    from personas import age_band
    ab = np.array([age_band(a) for a in pop.age])
    print("peak change in 'subscribe' by age band:", {b_: f"{((r_hi[ab==b_,sub].mean()/r_hi0[ab==b_,sub].mean())-1)*100:+.1f}%" for b_ in bands})
    print("peak change in 'subscribe' by income band:", {i: f"{((r_hi[pop.inc==i,sub].mean()/r_hi0[pop.inc==i,sub].mean())-1)*100:+.1f}%" for i in range(4)})
    print("RESULT", json.dumps({k_: bool(v) for k_, v in res.items()}))
