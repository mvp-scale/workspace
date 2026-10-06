"""World engine v2: WORLD -> COUNTRY -> REGION (settlement type) nodes with channels; persons and audiences (segments) are lenses over the nodes.
Reuses the rules tables via engine.py. Everything is arithmetic; every strength is a guess until fitted."""
import sys, hashlib
import numpy as np
sys.path.insert(0, "/workspace/probes/persona"); sys.path.insert(0, "/workspace/probes/world-engine")
import engine as E
from rules import load_opt
DIALS = E.DIALS; SETTLES = ["metro", "town", "rural"]
MAX_TIE_HOPS = 3        # a change that came from a tie may start at most this many further ties in a row (ties have |strength| < 1 and pass the same gate, so this is a second guard against loops)
def load_ties():
    """condition -> condition ties from the active ruleset's dial_ties.csv: {source condition index: [(target index, strength)]}. No file = no ties = the old behaviour exactly."""
    t = {}
    for r in load_opt("dial_ties"):
        if r["from_dial"] in DIALS and r["to_dial"] in DIALS: t.setdefault(DIALS.index(r["from_dial"]), []).append((DIALS.index(r["to_dial"]), float(r["strength"])))
    return t
TIES = load_ties()
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
            hops = sum(1 for p in path if isinstance(p, str) and p.startswith("~tie:"))
            for dj, s_ in TIES.get(di, ()):          # condition -> condition tie: strength x amount lands on the target at the SAME node one tick later; no noise, no edge channels (the source change already travels along the edges and each place applies its own tie); same gate as the edges
                a = amt * s_
                if hops < MAX_TIE_HOPS and abs(a) >= 0.002: self.seq += 1; self.queue.append((t + 1, self.seq, node, dj, a, ev, path + [f"~tie:{DIALS[di]}"]))
            if path and isinstance(path[-1], str) and path[-1].startswith("~tie:"): continue       # a tie-made change is not sent along the edges again
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
# ---- per-person arithmetic: numpy on the CPU, or torch on the GPU (same maths in float32; WORLD_GPU=0 turns it off). Answers agree to about 1e-6.
import os
try:
    import torch; GPU = os.environ.get("WORLD_GPU", "1") != "0" and torch.cuda.is_available()
except Exception: GPU = False
if GPU:
    _dev = "cuda"; _t = lambda x: torch.as_tensor(np.asarray(x), dtype=torch.float32, device=_dev); _G, _W, _B = _t(E.GRID), _t(E.W), _t(E.BIAS); _pc = {}
    def _pt(pop):
        k = id(pop)
        if k not in _pc: _pc[k] = (_t(pop.base), _t(pop.sal))
        return _pc[k]
    def effective(pop, d):
        base, sal = _pt(pop); return torch.clamp(base * torch.exp(torch.log(torch.clamp(1 + sal * _t(d), min=0.2)) @ _G.T), 0.5, 5.5).cpu().numpy()
    def propensity(eff): return torch.sigmoid(_B + ((_t(eff) - 3.0) / 1.5) @ _W.T).cpu().numpy()
    E.Population.propensity = lambda self, eff: propensity(eff)         # the engine's own method, redirected so every caller gets the fast path
    _ic = {}
    def _idx(pop, sg):
        k = (id(pop), id(sg))
        if k not in _ic: _ic[k] = (torch.as_tensor(pop.region, device=_dev, dtype=torch.long), torch.as_tensor(pop.seg, device=_dev, dtype=torch.long), _t(sg), pop, sg)       # keeps pop and sg alive so the ids stay valid
        return _ic[k]
    def _region_table(world, at):
        T = at if at is not None else world.totals(); return np.stack([T[f"REGION:{c}-{s}"] for c in world.cid for s in SETTLES])
    def person_delta(world, pop, seg_gain, at=None, zero=(), extra=None):
        reg, seg, G, _, _ = _idx(pop, seg_gain); d = _t(_region_table(world, at))[reg] * G[seg]
        for z in zero: d[:, DIALS.index(z)] = 0
        for z, v in (extra or {}).items(): d[:, DIALS.index(z)] += v
        return d.cpu().numpy()
    _mc = {}
    def world_stats(world, pop, seg_gain, at0, M):
        """The live read in one pass on the card: likelihood now, its change since `at0`, and each person state's change, averaged for every place and audience (M is the sparse membership matrix).
        Returns (now R x 8 in points, move R x 8 in points, states R x 15 in std units) as numpy."""
        k = id(M)
        if k not in _mc:
            c = M.tocsr(); _mc[k] = (torch.sparse_csr_tensor(torch.as_tensor(c.indptr, dtype=torch.int64), torch.as_tensor(c.indices, dtype=torch.int64), torch.as_tensor(c.data, dtype=torch.float32), size=c.shape).to(_dev), M)
        Mt = _mc[k][0]; reg, seg, G, _, _ = _idx(pop, seg_gain); base, sal = _pt(pop)
        def run(at):
            d = _t(_region_table(world, at))[reg] * G[seg]; eff = torch.clamp(base * torch.exp(torch.log(torch.clamp(1 + sal * d, min=0.2)) @ _G.T), 0.5, 5.5); return eff, torch.sigmoid(_B + ((eff - 3.0) / 1.5) @ _W.T)
        e0, p0 = run(at0); e1, p1 = run(None); X = torch.cat([p1, p1 - p0, (e1 - e0) / 1.5], dim=1); Y = (Mt @ X).cpu().numpy(); nd = p1.shape[1]
        return Y[:, :nd] * 100, Y[:, nd:2 * nd] * 100, Y[:, 2 * nd:]
    def prop_at(world, pop, seg_gain, at=None):
        """Everything per person in one go on the card: region change -> person state -> decision likelihood. Returns (state n x 15, likelihood n x 8) as numpy."""
        reg, seg, G, _, _ = _idx(pop, seg_gain); d = _t(_region_table(world, at))[reg] * G[seg]; base, sal = _pt(pop)
        eff = torch.clamp(base * torch.exp(torch.log(torch.clamp(1 + sal * d, min=0.2)) @ _G.T), 0.5, 5.5); p = torch.sigmoid(_B + ((eff - 3.0) / 1.5) @ _W.T)
        return eff.cpu().numpy(), p.cpu().numpy()
else:
    def effective(pop, d): return np.clip(pop.base * np.exp(np.log(np.maximum(1 + pop.sal * d, 0.2)) @ E.GRID.T), 0.5, 5.5)
    def propensity(eff): return 1 / (1 + np.exp(-(E.BIAS + ((eff - 3.0) / 1.5) @ E.W.T)))
if not GPU:
    def prop_at(world, pop, seg_gain, at=None):
        eff = effective(pop, person_delta(world, pop, seg_gain, at=at)); return eff, propensity(eff)
