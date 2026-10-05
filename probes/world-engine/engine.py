"""World-state engine v0.1 slice: nodes with state, edges as channels (gain, lag, gate, slant, noise), persons as arrays, decisions from state, audience opinion.
All strengths come from ../persona/rules/*.csv or the dicts below; every one is a guess until backtested. No language model runs inside the engine."""
import sys, json, hashlib, copy
import numpy as np
sys.path.insert(0, "/workspace/probes/persona")
from rules import load
from personas import gen, TRAITS
import offline as O

D_ROWS = load("dials"); DIALS = [r["id"] for r in D_ROWS]; HL = np.array([float(r["half_life_ticks"]) for r in D_ROWS]); DECAY = 0.5 ** (1 / HL)
E_ROWS = load("elements"); ELS = [r["id"] for r in E_ROWS]
GRID = np.zeros((len(ELS), len(DIALS)))
for g in load("grid"): GRID[ELS.index(g["element_id"]), DIALS.index(g["dial_id"])] = float(g["strength"])
DEC_ROWS = load("decisions"); DECS = [r["id"] for r in DEC_ROWS]; OPP = np.array([float(r["opportunity_rate"]) for r in DEC_ROWS]); BIAS = np.array([float(r["bias"]) for r in DEC_ROWS])
W = np.zeros((len(DECS), len(ELS)))
for w in load("decision_weights"): W[DECS.index(w["decision_id"]), ELS.index(w["element_id"])] = float(w["weight"])
REGIONS = ["northeast", "south", "midwest", "west"]; SEGMENTS = ["income_low", "income_high", "age_young", "age_senior"]
NODES = ["WORLD:world", "COUNTRY:usa"] + [f"REGION:{r}" for r in REGIONS] + [f"SEGMENT:{s}" for s in SEGMENTS]
SEG_GAIN = {"income_low": {"prices": 1.5, "housing_cost": 1.5, "energy_fuel": 1.5, "job_security": 1.3, "financial_conditions": 1.2, "health_risk": 1.2},
            "income_high": {"prices": 0.7, "energy_fuel": 0.6, "housing_cost": 0.8, "financial_conditions": 1.3, "job_security": 0.8},
            "age_young": {"tech_pace": 1.4, "job_security": 1.2, "housing_cost": 1.3}, "age_senior": {"health_risk": 1.5, "crime": 1.2, "financial_conditions": 1.2, "tech_pace": 0.8, "prices": 1.1}}

class World:
    def __init__(self, seed=0, noise=True, sigma=0.05, anchors=None):
        self.rng = np.random.default_rng(seed); self.noise = noise; self.tick = 0; self.queue = []; self.seq = 0; self.log = []
        self.delta = {n: np.zeros(len(DIALS)) for n in NODES}; self.edges_from = {n: [] for n in NODES}
        agenda = np.random.default_rng(1234)                            # model definition (regional agendas), independent of the run seed
        def edge(a, b, gain, lag=1, gate=0.002):
            e = {"from": a, "to": b, "gain": gain, "lag": lag, "gate": gate, "slant": np.zeros(len(DIALS)), "sigma": sigma, "origin": "DEFAULT"}; self.edges_from[a].append(e)
        edge("WORLD:world", "COUNTRY:usa", np.full(len(DIALS), 0.3), gate=0.004)                    # events abroad reach the US attenuated
        for r in REGIONS: edge("COUNTRY:usa", f"REGION:{r}", np.clip(1 + 0.1 * agenda.standard_normal(len(DIALS)), 0.7, 1.3))
        for s in SEGMENTS: edge("COUNTRY:usa", f"SEGMENT:{s}", np.array([SEG_GAIN[s].get(d, 1.0) for d in DIALS]))
        self.anchor = {n: np.zeros(len(DIALS)) for n in NODES}          # persistent starting conditions from public indices (they do not decay like news shocks)
        if anchors:
            a = np.zeros(len(DIALS))
            for d, v in anchors.items(): a[DIALS.index(d)] = v
            self.anchor["COUNTRY:usa"] = a
            for e in self.edges_from["COUNTRY:usa"]: self.anchor[e["to"]] = a * e["gain"]
    def total(self, node): return self.delta[node] + self.anchor[node]
    def add(self, tick, node, dial, amount, event, path=()):
        self.seq += 1; self.queue.append((tick, self.seq, node, DIALS.index(dial), float(amount), event, list(path)))
    def step(self):
        t = self.tick; due = sorted([q for q in self.queue if q[0] <= t], key=lambda q: (q[0], q[1])); self.queue = [q for q in self.queue if q[0] > t]
        for (_, _, node, di, amt, ev, path) in due:
            self.delta[node][di] += amt; self.log.append({"tick": t, "node": node, "dial": DIALS[di], "amount": round(amt, 5), "event": ev, "path": path + [node]})
            for e in self.edges_from[node]:
                a = amt * e["gain"][di] * (1 + e["slant"][di])
                if abs(a) < e["gate"]: continue
                if self.noise: a += float(self.rng.normal(0, e["sigma"] * abs(a)))
                self.seq += 1; self.queue.append((t + e["lag"], self.seq, e["to"], di, a, ev, path + [node]))
        for n in self.delta: self.delta[n] *= DECAY
        self.tick += 1
    def run(self, ticks):
        for _ in range(ticks): self.step()
    def digest(self): return hashlib.sha1(np.concatenate([self.total(n) for n in NODES]).tobytes()).hexdigest()[:12]
    def snapshot_totals(self): return {n: self.total(n).copy() for n in NODES}

class Population:
    def __init__(self, n, seed=1):
        ps = [gen(s) for s in range(1, n + 1)]; r = np.random.default_rng(seed + 99); self.n = n
        inc = np.array([["under $30,000", "$30,000 to $60,000", "$60,000 to $100,000", "over $100,000"].index(p["income"]) for p in ps]); age = np.array([p["age"] for p in ps])
        lat = {t: np.array([p["latent"][t] for p in ps], float) for t in TRAITS}; cl = lambda x: np.clip(x, 1, 5)
        col = {"tech_comfort": lat["tech"], "price_attention": lat["price"], "privacy_stance": lat["privacy"], "social_ease": lat["social"], "time_pressure": lat["time"], "novelty_seeking": lat["novelty"],
               "financial_stress": 1 + 0.5 * (3 - inc), "optimism": cl(3 + .6 * r.standard_normal(n)), "safety_concern": cl(3 + .7 * r.standard_normal(n)), "institutional_trust": cl(3 + .7 * r.standard_normal(n)),
               "liquidity": cl(1 + .9 * inc + (age >= 60) * .5 + .5 * r.standard_normal(n)), "habit_inertia": cl(2.2 + age / 50 + .6 * r.standard_normal(n)), "loss_aversion": cl(3 + .6 * r.standard_normal(n)),
               "tenure": np.full(n, 3.0), "life_stage": 1 + 4 * age / 90}
        self.base = np.column_stack([col[e] for e in ELS]).astype(np.float32); self.area = np.array([p['area'] for p in ps]); self.household = np.array([p['household'] for p in ps]); self.work = np.array([p['work'] for p in ps]); self.caregiver = np.array([p['caregiver'] for p in ps])
        self.region = np.array([["Northeast", "South", "Midwest", "West"].index(p["region"]) for p in ps]); self.seg_inc = (inc >= 2).astype(int)           # 0 low, 1 high
        self.seg_age = np.where(age < 35, 0, np.where(age >= 60, 1, -1)); self.sal = r.uniform(.3, 1.0, (n, len(DIALS))).astype(np.float32); self.age = age; self.inc = inc
        self.flags = np.column_stack([age < 30, age >= 60, [p["area"] == "large city" for p in ps], [p["area"] in ("rural area", "small town") for p in ps], [p["work"] == "retired" for p in ps],
                                      inc / 3, [p["caregiver"] for p in ps], [p["household"] == "lives alone" for p in ps], ["children" in p["household"] for p in ps], [p["household"] == "lives with housemates" for p in ps]]).astype(np.float32)
        self.traits_truth = np.column_stack([lat[t] for t in TRAITS])
    def person_delta(self, w, zero=(), at=None, extra=None):
        T = at if at is not None else {n: w.total(n) for n in NODES}
        c = T["COUNTRY:usa"]; reg = np.stack([T[f"REGION:{r}"] for r in REGIONS])[self.region]
        si = np.stack([T["SEGMENT:income_low"] - c, T["SEGMENT:income_high"] - c])[self.seg_inc]
        sa = np.where((self.seg_age >= 0)[:, None], np.stack([T["SEGMENT:age_young"] - c, T["SEGMENT:age_senior"] - c])[np.maximum(self.seg_age, 0)], 0.0)
        d = reg + 0.5 * (si + sa)
        for z in zero: d[:, DIALS.index(z)] = 0
        for z, v in (extra or {}).items(): d[:, DIALS.index(z)] += v
        return d
    def effective(self, w, zero=(), at=None, extra=None):
        perceived = np.maximum(1 + self.sal * self.person_delta(w, zero, at, extra), 0.2); return np.clip(self.base * np.exp(np.log(perceived) @ GRID.T), 0.5, 5.5)
    def propensity(self, eff): return 1 / (1 + np.exp(-(BIAS + ((eff - 3.0) / 1.5) @ W.T)))
    def groups(self):
        g = {"COUNTRY:usa": np.ones(self.n, bool)}
        for i, r in enumerate(REGIONS): g[f"REGION:{r}"] = self.region == i
        g["SEGMENT:income_low"] = self.seg_inc == 0; g["SEGMENT:income_high"] = self.seg_inc == 1; g["SEGMENT:age_young"] = self.seg_age == 0; g["SEGMENT:age_senior"] = self.seg_age == 1; return g

class Audience:
    """The higher-level classifier: answers 'would this audience take this up' per node, from state, with the same typed answer as the local classifier (a yes/no probability)."""
    def __init__(self):
        from sklearn.linear_model import Ridge
        D = json.load(open("/workspace/data/persona-lab/offline.json")); pers = [gen(s) for s in range(1, 401)]
        trait = np.array([[(p["latent"][t] - 1) / 4 for t in TRAITS] for p in pers]); inc = np.array([["under $30,000", "$30,000 to $60,000", "$60,000 to $100,000", "over $100,000"].index(p["income"]) for p in pers]); age = np.array([p["age"] for p in pers])
        flags = np.column_stack([age < 30, age >= 60, [p["area"] == "large city" for p in pers], [p["area"] in ("rural area", "small town") for p in pers], [p["work"] == "retired" for p in pers], inc / 3,
                                 [p["caregiver"] for p in pers], [p["household"] == "lives alone" for p in pers], ["children" in p["household"] for p in pers], [p["household"] == "lives with housemates" for p in pers]])
        P = np.hstack([trait, flags]); X, y = [], []; lg = lambda p: np.log(np.clip(p, .02, .98) / (1 - np.clip(p, .02, .98)))
        for k in D["direct"]:
            iv = np.array([D["idea"][k][q] for q in O.IDEA_Q]); X.append(self.feat(P, iv)); y.append(lg(np.array(D["direct"][k])))
        self.m = Ridge(alpha=3.0).fit(np.vstack(X), np.concatenate(y)); self.n_ideas = len(D["direct"])
    @staticmethod
    def feat(P, iv): return np.hstack([P, np.tile(iv, (len(P), 1)), (P[:, :, None] * iv[None, None, :]).reshape(len(P), -1)])
    def demands(self, text):
        a = O.call("Product description:\n" + text, {k: {"type": "noul", "instructions": v} for k, v in O.IDEA_Q.items()}); return np.array([a[k]["noul"] for k in O.IDEA_Q])
    def probability(self, pop, eff, iv):
        tr = np.clip((eff[:, [ELS.index(e) for e in ("tech_comfort", "price_attention", "privacy_stance", "social_ease", "time_pressure", "novelty_seeking")]] - 1) / 4, 0, 1)
        return 1 / (1 + np.exp(-self.m.predict(self.feat(np.hstack([tr, pop.flags]), iv))))
    def opinion(self, pop, eff, iv):
        p = self.probability(pop, eff, iv); return {n: {"noul": float(p[m].mean()), "share_yes": float((p[m] >= .5).mean()), "n": int(m.sum())} for n, m in pop.groups().items()}, p
