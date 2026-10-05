"""World engine v2: WORLD -> COUNTRY -> REGION (settlement type) nodes with channels; persons and audiences (segments) are lenses over the nodes.
Reuses the rules tables via engine.py. Everything is arithmetic; every strength is a guess until fitted."""
import sys, hashlib
import numpy as np
sys.path.insert(0, "/workspace/probes/persona"); sys.path.insert(0, "/workspace/probes/world-engine")
import engine as E
DIALS = E.DIALS; SETTLES = ["metro", "town", "rural"]
class World2:
    def __init__(self, countries, seed=0, noise=True, sigma=0.05):
        self.countries = countries; self.cid = [c["id"] for c in countries]; self.nodes = ["WORLD:world"] + [f"COUNTRY:{c}" for c in self.cid] + [f"REGION:{c}-{s}" for c in self.cid for s in SETTLES]
        self.rng = np.random.default_rng(seed); self.noise = noise; self.tick = 0; self.queue = []; self.seq = 0; self.log = []
        self.delta = {n: np.zeros(len(DIALS)) for n in self.nodes}; self.edges_from = {n: [] for n in self.nodes}; ag = np.random.default_rng(1234)
        def edge(a, b, gain, lag=1, gate=0.002): self.edges_from[a].append({"from": a, "to": b, "gain": gain, "lag": lag, "gate": gate, "slant": np.zeros(len(DIALS)), "sigma": sigma})
        for c in self.cid: edge("WORLD:world", f"COUNTRY:{c}", np.full(len(DIALS), 0.6), gate=0.003)
        for c in self.cid:
            for s in SETTLES: edge(f"COUNTRY:{c}", f"REGION:{c}-{s}", np.clip(1 + 0.1 * ag.standard_normal(len(DIALS)), 0.7, 1.3))
        self.anchor = {n: np.zeros(len(DIALS)) for n in self.nodes}
        for c in countries:
            a = np.array([float(c.get(f"d_{d}", 0.0)) for d in DIALS]); self.anchor[f"COUNTRY:{c['id']}"] = a
            for e in self.edges_from[f"COUNTRY:{c['id']}"]: self.anchor[e["to"]] = a * e["gain"]
        w = np.array([c["pop_m"] for c in countries], float); w /= w.sum(); self.anchor["WORLD:world"] = sum(wi * self.anchor[f"COUNTRY:{c['id']}"] for wi, c in zip(w, countries))
    def total(self, n): return self.delta[n] + self.anchor[n]
    def add(self, tick, node, dial, amount, event): self.seq += 1; self.queue.append((tick, self.seq, node, DIALS.index(dial), float(amount), event, []))
    def step(self):
        t = self.tick; due = sorted([q for q in self.queue if q[0] <= t], key=lambda q: (q[0], q[1])); self.queue = [q for q in self.queue if q[0] > t]
        for (_, _, node, di, amt, ev, path) in due:
            self.delta[node][di] += amt; self.log.append({"tick": t, "node": node, "dial": DIALS[di], "amount": amt, "event": ev, "path": path + [node]})
            for e in self.edges_from[node]:
                a = amt * e["gain"][di] * (1 + e["slant"][di])
                if abs(a) < e["gate"]: continue
                if self.noise: a += float(self.rng.normal(0, e["sigma"] * abs(a)))
                self.seq += 1; self.queue.append((t + e["lag"], self.seq, e["to"], di, a, ev, path + [node]))
        for n in self.delta: self.delta[n] *= E.DECAY
        self.tick += 1
    def run(self, k):
        for _ in range(k): self.step()
    def totals(self): return {n: self.total(n).copy() for n in self.nodes}
    def digest(self): return hashlib.sha1(np.concatenate([self.total(n) for n in self.nodes]).tobytes()).hexdigest()[:12]
def person_delta(world, pop, seg_gain, at=None, zero=(), extra=None):
    T = at if at is not None else world.totals(); R = np.stack([T[f"REGION:{c}-{s}"] for c in world.cid for s in SETTLES]); d = R[pop.region] * seg_gain[pop.seg]
    for z in zero: d[:, DIALS.index(z)] = 0
    for z, v in (extra or {}).items(): d[:, DIALS.index(z)] += v
    return d
def effective(pop, d): return np.clip(pop.base * np.exp(np.log(np.maximum(1 + pop.sal * d, 0.2)) @ E.GRID.T), 0.5, 5.5)
def propensity(eff): return 1 / (1 + np.exp(-(E.BIAS + ((eff - 3.0) / 1.5) @ E.W.T)))
