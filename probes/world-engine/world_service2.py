"""World engine service v2 (mock-up): multi-country world, five stages (collect, identify, propagate, decide, read), attractor/detractor ledgers.
JSON over HTTP on 127.0.0.1:8112; the console proxies /api/world-engine/*.   Run: /workspace/kev/.venv/bin/python world_service2.py
Inputs are simulated at the start (data/*.csv, ledger/); everything else is derived by rules. Every strength is a guess or a fit until backtested."""
import os, sys, json, time, copy, datetime, email.utils, hashlib, threading, csv, random, urllib.parse
import numpy as np
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, "/workspace/probes/persona"); sys.path.insert(0, "/workspace/probes/world-engine")
import engine as E, engine2 as W2, classify as C
from world_pop import WorldPopulation, load_countries, D as DATA
from sklearn.cluster import KMeans
L = "/workspace/probes/world-engine/ledger"; LOCK = threading.RLock()      # re-entrant: the request handler holds it and log_unplaced takes it again
IQ = list(E.O.IDEA_Q); DIALS = E.DIALS; DIAL_NAME = {r["id"]: r["name"] for r in E.D_ROWS}; EL_NAME = {r["id"]: r["name"] for r in E.E_ROWS}; DEC_NAME = {r["id"]: r["name"] for r in E.DEC_ROWS}
FEATS = ["tech", "price", "privacy", "social", "time", "novelty", "young", "older", "city", "rural", "retired", "income", "caregiver", "alone", "kids", "housemates"]
FEAT_LABEL = {"tech": "tech comfort", "price": "price attention", "privacy": "privacy stance", "social": "ease with strangers", "time": "time pressure", "novelty": "novelty appetite", "young": "under 30", "older": "60 or over", "city": "big city", "rural": "rural or small town",
              "retired": "retired", "income": "income", "caregiver": "caring for a relative", "alone": "living alone", "kids": "kids at home", "housemates": "sharing with housemates"}
PROP_LABEL = {"cost_monthly": "costs money monthly", "setup_app": "needs an app", "id_photo": "needs ID or a photo", "strangers": "involves strangers", "time_heavy": "takes a lot of time", "urban_only": "big cities only", "youth_target": "aimed at under 30s", "older_target": "aimed at over 60s", "rural_target": "aimed at rural areas", "novel": "something new"}
SEG_WORD = {"tech": ("tech-comfortable", "tech-wary"), "price": ("cost-watching", None), "privacy": ("privacy-guarded", None), "social": ("sociable", "reserved"), "time": ("short of time", None), "novelty": ("early adopters", "set in their ways"), "age": ("older", "young"),
            "income": ("higher-income", "lower-income"), "city": ("big-city", None), "rural": ("rural", None), "retired": ("retired", None), "caregiver": ("carers", None), "alone": ("living alone", None), "kids": ("with kids", None), "housemates": ("sharing a home", None)}
SETTLE_NAME = {"metro": "cities", "town": "towns", "rural": "rural areas"}
FACTORS = list(csv.DictReader(open(f"{DATA}/factors.csv")))
for f in FACTORS: f["feats"] = [FEATS.index(x) for x in f["features"].split("|")] if f["features"] else []
EXPOSURE = list(csv.DictReader(open(f"{DATA}/segment_exposure.csv")))
def jn(o):
    if isinstance(o, dict): return {k: jn(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [jn(v) for v in o]
    if isinstance(o, (np.floating,)): return None if np.isnan(o) else round(float(o), 4)
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, float): return None if o != o else round(o, 4)
    return o

_TR = [E.ELS.index(e) for e in ("tech_comfort", "price_attention", "privacy_stance", "social_ease", "time_pressure", "novelty_seeking")]
_prob_orig = E.Audience.probability
def _prob_fast(self, pop, eff, iv):
    """The audience model is linear (a ridge fit on [traits, idea, traits x idea]), so take-up = sigmoid(intercept + idea.b + traits . (a + C.idea)): the same answer as building the 186-column feature matrix, in a few ms."""
    m = self.m; c = m.coef_; a_, b_, C_ = c[:16], c[16:26], c[26:].reshape(16, 10)
    Pm = np.hstack([np.clip((eff[:, _TR] - 1) / 4, 0, 1), pop.flags]); z = float(np.ravel(m.intercept_)[0]) + float(iv @ b_) + Pm @ (a_ + C_ @ iv)
    return 1 / (1 + np.exp(-z))
if os.environ.get("WORLD_FASTPROB", "1") != "0": E.Audience.probability = _prob_fast
class LazyMasks:
    """Boolean masks of the people in a place or audience, built when asked for."""
    def __init__(self, sess): self.s = sess
    def __getitem__(self, k):
        p = self.s.pop; kind, _, rest = k.partition(":")
        if k == "WORLD:world": return np.ones(p.n, bool)
        if kind == "COUNTRY": return p.country == self.s.cidx[rest]
        if kind == "REGION": c, _, st = rest.rpartition("-"); return p.region == self.s.cidx[c] * 3 + W2.SETTLES.index(st)
        if kind == "AUDIENCE": return p.seg == int(rest)
        raise KeyError(k)
    def __contains__(self, k):
        try: self[k]; return True
        except (KeyError, ValueError): return False
OLD_COUNTRY = {"usa": "usa", "germany": "deu", "japan": "jpn", "brazil": "bra", "india": "ind", "nigeria": "nga", "indonesia": "idn", "mexico": "mex"}      # ids in the saved event ledger
class Session:
    def __init__(self):
        t0 = time.time(); self.pop = WorldPopulation(); self.countries = self.pop.countries; self.cid = [c["id"] for c in self.countries]; self.cname = {c["id"]: c["name"] for c in self.countries}
        self.setup_segments(); self.aud = E.Audience(); self.cache = {}; self.last = None; self.reset(); self.boot = round(time.time() - t0, 1)
    # ---------------- audiences (segments) found from beliefs, habits and life situation together; their exposure to each dial comes from data/segment_exposure.csv
    def setup_segments(self, k=8):
        p = self.pop; F = np.column_stack([p.traits_truth, p.age, p.inc, p.flags[:, 2], p.flags[:, 3], p.flags[:, 4], p.flags[:, 6], p.flags[:, 7], p.flags[:, 8], p.flags[:, 9]]).astype(float)
        key = ["tech", "price", "privacy", "social", "time", "novelty", "age", "income", "city", "rural", "retired", "caregiver", "alone", "kids", "housemates"]; Z = (F - F.mean(0)) / F.std(0)
        lab = KMeans(k, n_init=5, random_state=0).fit(Z[::6]).predict(Z); p.seg = lab; self.segs = []; fa = {"tech": p.tech, "price": p.price, "privacy": p.privacy, "social": p.social, "time": p.time, "novelty": p.novelty, "income": p.inc.astype(float), "young": p.flags[:, 0], "older": p.flags[:, 1], "retired": p.flags[:, 4], "rural": p.flags[:, 3], "caregiver": p.flags[:, 6]}
        mu = {f: p.wmean(v) for f, v in fa.items()}; sd = {f: float(np.sqrt(p.wmean((v - mu[f]) ** 2))) or 1.0 for f, v in fa.items()}; gain = np.ones((k, len(DIALS)))
        for c in range(k):
            m = lab == c; z = (F[m].mean(0) - F.mean(0)) / F.std(0); words = []
            for i in np.argsort(-np.abs(z)):
                w = SEG_WORD[key[i]][0 if z[i] > 0 else 1]
                if w and w not in words: words.append(w)
                if len(words) == 3: break
            cm = np.round(np.bincount(p.country[m], weights=p.wt[m], minlength=len(self.countries)) / p.wt[m].sum(), 4).tolist()
            self.segs.append({"id": c, "name": ", ".join(words).capitalize(), "share": round(p.wmean(m.astype(float)), 3), "country_mix": cm})
            for e in EXPOSURE:
                zf = (p.wmean(fa[e["feature"]], m) - mu[e["feature"]]) / sd[e["feature"]]; gain[c, DIALS.index(e["dial"])] += float(e["weight"]) * zf
        self.seg_gain = np.clip(gain, 0.6, 1.6)
        self.cidx = {c: i for i, c in enumerate(self.cid)}; self.masks = LazyMasks(self)      # a mask is built on demand, so 100 countries do not keep 400 arrays of 300k flags
        self.rows = [{"id": "WORLD:world", "label": "World", "level": "world", "parent": None}]
        for cc in self.cid:
            self.rows.append({"id": f"COUNTRY:{cc}", "label": self.cname[cc], "level": "country", "parent": "WORLD:world"})
            self.rows += [{"id": f"REGION:{cc}-{s}", "label": f"{self.cname[cc]} · {SETTLE_NAME[s]}", "level": "region", "parent": f"COUNTRY:{cc}"} for s in W2.SETTLES]
        self.rows += [{"id": f"AUDIENCE:{s['id']}", "label": s["name"], "level": "audience", "parent": "AUDIENCES"} for s in self.segs]
        # every place and audience as one sparse matrix of normalised person weights, so the mean of any per-person quantity for ALL of them is one product (M @ X), however many places there are
        import scipy.sparse as sp
        nC = len(self.cid); n = p.n; rg = p.region - p.country * 3; rr = np.concatenate([np.zeros(n, int), 1 + p.country * 4, 2 + p.country * 4 + rg, 1 + 4 * nC + p.seg]); cc = np.tile(np.arange(n), 4); dd = np.tile(p.wt, 4)
        tot = np.bincount(rr, weights=dd, minlength=len(self.rows)); self.M = sp.csr_matrix((dd / tot[rr], (rr, cc)), shape=(len(self.rows), n)); self.share = (tot / p.wt.sum()).tolist()
    # ---------------- stage 1: collect (news ledger -> events with entry nodes)
    def reset(self):
        ev = {e["evidence_id"]: e for e in map(json.loads, open(f"{L}/evidence.jsonl"))}; ms = [json.loads(l) for l in open(f"{L}/measurements.jsonl")]; cl = json.load(open(f"{L}/clusters.json")); groups = {}
        for m in ms: groups.setdefault(cl[m["evidence_id"]], []).append(m)
        evs = []
        for cid, mem in groups.items():
            use = [m for m in mem if m["gate_ok"]]
            if not use: continue
            best = {}
            for m in use:
                for r in m["readings"]:
                    if r["direction"] != "conflict" and (r["dial"] not in best or abs(r["amount"]) > abs(best[r["dial"]]["amount"])): best[r["dial"]] = r
            c = OLD_COUNTRY.get(use[0].get("country", "usa"), use[0].get("country", "usa")); evs.append({"event": cid, "title": use[0]["title"], "entry": f"COUNTRY:{c}" if c in self.cid else "WORLD:world", "country": c, "count": len(use), "readings": list(best.values()), "published": email.utils.parsedate_to_datetime(ev[use[0]["evidence_id"]]["published_at"]), "source": "feed"})
        evs.sort(key=lambda e: e["published"]); self.w = W2.World2(self.countries, 0, True); self.events = []; self.hist = [self.w.totals()]
        for e in evs: self.apply(e, 1)
        self.w.run(2); self.hist.append(self.w.totals()); self.cache = {}; self.last = None; self.live_at = len(self.hist) - 1; self.world_cache = None
    def apply(self, e, settle=1, world=None):
        w = world or self.w; t = w.tick; e = dict(e)
        for r in e["readings"]: w.add(t, e["entry"], r["dial"], r["amount"], e["event"])
        w.add(t, e["entry"] if e["entry"] != "WORLD:world" else "WORLD:world", "news_overload", 0.01 * e.get("count", 1), e["event"])
        if world is None:
            self.events.append({k: (v.isoformat() if isinstance(v, datetime.datetime) else v) for k, v in e.items()})
        for _ in range(settle):
            w.step()
            if world is None: self.hist.append(w.totals())
    # ---------------- helpers
    def eff_prop(self, world=None, at=None, **kw):
        d = W2.person_delta(world or self.w, self.pop, self.seg_gain, at=at, **kw); eff = W2.effective(self.pop, d); return eff, d
    def item(self, text):
        k = "item:" + hashlib.sha1(text.encode()).hexdigest()[:10]
        if k not in self.cache: self.cache[k] = self.aud.demands(text)
        return self.cache[k]
    def hm(self, x, mask): return self.pop.wmean(x, mask)
    def gm(self, X): return self.M @ X          # weighted mean of each column of X (n people x k) for every row of self.rows at once
    # ---------------- the request: identify -> propagate -> decide -> read
    def classify_kind(self, text):
        """Typed choice question: is this something that happened (event) or something offered (offer)?"""
        a = E.O.call(f"Text:\n{text}", {"k": {"type": "choice", "instructions": "What kind of thing is this text?", "criteria": {"event": "Something that happened or was announced in the world, like a news item", "offer": "A product, service, programme or message being offered to people", "other": "Neither"}}})["k"]
        return a["choice"], {k: round(float(v), 3) for k, v in a["probabilities"].items()}
    def exposure(self, pl):
        """What a placed story is exposed to, from the domains table (our judgement; no direction is implied)."""
        rows = {d["id"]: d for d in C.DOMAINS}; out = {"state_classes": [], "decisions": [], "resources": []}
        for t in pl:
            if not t["tagged"] or t["id"] == "other": continue
            for key, col in (("state_classes", "state_classes"), ("decisions", "decisions"), ("resources", "resources")):
                for v in rows[t["id"]][col].split("; "):
                    if v and v not in out[key] and v != "depends on the story": out[key].append(v)
        return out
    def log_unplaced(self, text, pl):
        if [t["id"] for t in pl if t["tagged"]] == ["other"]:
            with LOCK, open(L + "/unplaced.jsonl", "a") as f: f.write(json.dumps({"at": datetime.datetime.now().isoformat(), "text": text}) + "\n")
    def request(self, text, mode):
        auto = None
        if mode == "auto":
            kind, p = self.classify_kind(text); mode = "offer" if kind == "offer" else "event"; auto = {"kind": mode, "p": p}
        r = self.request_event(text) if mode == "event" else self.request_offer(text)
        if auto: r["identify"]["auto"] = auto
        else: r["identify"]["auto"] = {"kind": mode, "p": None}
        return r
    def branch(self, readings, entry):
        """A copy of the world, run for 3 ticks with noise off; with readings, the event enters at `entry` first."""
        w = copy.deepcopy(self.w); w.noise = False
        if readings: self.apply({"event": "req", "entry": entry, "count": 1, "readings": readings}, 3, world=w)
        else: w.run(3)
        return w
    def request_event(self, text):
        ev = {"evidence_id": "req", "published_at": datetime.date.today().isoformat(), "title": text, "description": ""}
        P = C.ask(ev); r = C.read(P); country, cp = C.ask_country(ev); entry = f"COUNTRY:{country}" if country in self.cid else "WORLD:world"
        readings = [dict(x, amount=(0.10 if x["direction"] == "up" else -0.10) * x["strength"]) for x in r["readings"] if x["direction"] != "conflict"]
        for x in readings: x["basis"] = "reported"
        pl = C.place(ev); self.log_unplaced(text, pl)
        for x in C.expected(ev, {x["dial"] for x in readings}, C.allowed_dials(pl)): readings.append(dict(x, amount=(0.10 if x["direction"] == "up" else -0.10) * x["strength"] * x["mode_weight"]))     # expected impact, own weight table
        w_, wtype, wwhy = C.type_weight(r["gate"]["happened"], r["gate"]["announced"], r["gate"]["opinion"], P["g|forecast"])      # a weight, not a wall
        for x in readings: x["amount"] = x["amount"] * w_
        ok = bool(readings) and w_ > 0
        evid = []
        for x in readings:
            if x.get("basis") == "expected": continue
            for i, a in enumerate(C.ATTRS.get((x["dial"], x["direction"]), [])):
                m = (P[f"a|{x['dial']}|{x['direction']}|{i}|0"] + P[f"a|{x['dial']}|{x['direction']}|{i}|1"]) / 2
                if m >= .65: evid.append({"dial": x["dial"], "attribute": a["attribute"], "q1": a["question_1"], "q2": a["question_2"], "p": round(m, 3)})
        ident = {"mode": "event", "counted": ok, "status": "moved" if ok else "no_impact_expected", "weight": {"value": w_, "type": wtype, "why": wwhy}, "placement": pl, "exposure": self.exposure(pl), "misses": [dict(m, dial_name=DIAL_NAME[m["dial"]]) for m in C.misses(P)] if not readings else [], "gate": dict(r["gate"], forecast=round(P["g|forecast"], 2)), "country": country, "country_p": cp.get(country), "entry": entry, "readings": [{"dial": x["dial"], "name": DIAL_NAME[x["dial"]], "direction": x["direction"], "strength": x["strength"], "amount": round(x["amount"], 4), "basis": x.get("basis", "reported"), "mode": x.get("mode", "reported"), "mode_weight": x.get("mode_weight", 1.0), "p_up": x.get("p_up"), "p_down": x.get("p_down"), "p_done": x.get("p_done")} for x in readings], "evidence": evid}
        t0 = self.w.tick; w0 = self.branch([], entry); w2 = self.branch(readings if ok else [], entry)      # control run (no event) and event run: same 3 ticks, noise off, so only the event differs
        eff0, d0 = self.eff_prop(w0); eff1, d1 = self.eff_prop(w2); p0, p1 = E.Population.propensity(None, eff0), E.Population.propensity(None, eff1)
        # the event run twice more, with only the reported or only the expected readings: how much of each move comes from which basis (parts need not add up exactly, because effects interact)
        parts = {b: (E.Population.propensity(None, self.eff_prop(self.branch([x for x in readings if x["basis"] == b], entry))[0]) if ok and any(x["basis"] == b for x in readings) else p0) for b in ("reported", "expected")}
        first = {}
        for l in w2.log:
            if l["event"] == "req" and l["node"] not in first: first[l["node"]] = l["tick"] - t0
        self.last = {"mode": "event", "w2": w2, "eff0": eff0, "eff1": eff1, "d0": d0, "d1": d1, "p0": p0, "p1": p1, "parts": parts, "entry": entry, "readings": readings, "counted": ok, "event": {"event": "req", "title": text, "entry": entry, "country": country, "count": 1, "readings": readings, "source": "you"}}
        tot0, tot1 = w0.totals(), w2.totals(); cols = [{"id": d, "label": DEC_NAME[d], "kind": "decision"} for d in E.DECS]; rows = []
        D, Bs = self.gm(p1 - p0) * 100, self.gm(p0) * 100; Pt = {b_: self.gm(parts[b_] - p0) * 100 for b_ in parts}
        for i, rw in enumerate(self.rows): rows.append({**rw, "share": round(self.share[i], 4), "values": D[i].tolist(), "base": Bs[i].tolist(), "parts": {b_: Pt[b_][i].tolist() for b_ in Pt}})
        prop_rows = [{"id": n, "label": next(x["label"] for x in self.rows if x["id"] == n), "level": n.split(":")[0].lower(), "delta": (tot1[n] - tot0[n]).tolist(), "first_tick": first.get(n)} for n in w2.nodes]
        return jn({"identify": ident, "propagate": {"dials": [{"id": d, "name": DIAL_NAME[d]} for d in DIALS], "rows": prop_rows, "note": "change in each dial at each node versus a control run with no event, after 3 ticks"}, "decide": {"kind": "state decisions", "cols": cols, "matrix": {"rows": [{"id": d, "label": DEC_NAME[d], "kind": "decision"} for d in E.DECS], "cols": [{"id": e, "label": EL_NAME[e]} for e in E.ELS if abs(E.W[:, E.ELS.index(e)]).sum() > 0],
                              "values": [[float(E.W[j, E.ELS.index(e)]) for e in E.ELS if abs(E.W[:, E.ELS.index(e)]).sum() > 0] for j in range(len(E.DECS))], "note": "weight of each person state on each decision (rules/decision_weights.csv, hand-set guesses)"}, "rule": "propensity = sigmoid(bias + sum of weights x standardised person states); weights in rules/decision_weights.csv"},
                   "read": {"mode": "event", "cols": cols, "rows": rows, "value_label": "change in propensity (points)", "total_label": None}})
    def request_offer(self, text):
        iv = self.item(text); p = self.aud
        pl = C.place({"published_at": datetime.date.today().isoformat(), "title": text, "description": ""}); self.log_unplaced(text, pl)
        ident = {"mode": "offer", "counted": True, "status": "moved", "placement": pl, "exposure": self.exposure(pl), "readings": [{"id": k, "label": PROP_LABEL[k], "p": round(float(v), 3), "question": E.O.IDEA_Q[k]} for k, v in zip(IQ, iv)]}
        eff, d = self.eff_prop(); tri = [E.ELS.index(e) for e in ("tech_comfort", "price_attention", "privacy_stance", "social_ease", "time_pressure", "novelty_seeking")]
        Pm = np.hstack([np.clip((eff[:, tri] - 1) / 4, 0, 1), self.pop.flags]); pr = p.probability(self.pop, eff, iv); pn = p.probability(self.pop, self.pop.base, iv)
        coef = p.m.coef_; a_, c_ = coef[:16], coef[26:].reshape(16, 10); wi = a_ + c_ @ iv; mu = self.gm(Pm)[0]; sd = Pm.std(0) + 1e-9
        self.last = {"mode": "offer", "iv": iv, "eff": eff, "Pm": Pm, "pr": pr, "pn": pn, "wi": wi, "c": c_, "mu": mu, "sd": sd, "text": text}
        cols = [{"id": f["id"], "label": f["label"], "kind": f["kind"]} for f in FACTORS]; rows = []
        SUP, DPR, PB = self.gm(pr[:, None])[:, 0], self.gm((pr - pn)[:, None])[:, 0], self.gm(Pm)          # every place and audience at once
        for i, rw in enumerate(self.rows):
            sup = SUP[i]; scale = sup * (1 - sup) * 100; push = (PB[i] - mu) * wi * scale
            vals = [DPR[i] * 100 if f["id"] == "world" else float(push[f["feats"]].sum()) for f in FACTORS]
            rows.append({**rw, "share": round(self.share[i], 4), "values": vals, "total": sup * 100})
        tot = self.w.totals(); prop_rows = [{"id": n, "label": next(x["label"] for x in self.rows if x["id"] == n), "level": n.split(":")[0].lower(), "delta": tot[n].tolist(), "first_tick": None} for n in self.w.nodes]
        return jn({"identify": ident, "propagate": {"dials": [{"id": x, "name": DIAL_NAME[x]} for x in DIALS], "rows": prop_rows, "note": "an offer does not move the world; it is read against today's world (each dial's current value)"},
                   "decide": {"kind": "take-up of the offer", "cols": cols, "matrix": {"rows": [{"id": f["id"], "label": f["label"], "kind": f["kind"]} for f in FACTORS if f["feats"]], "cols": [{"id": "main", "label": "on its own"}] + [{"id": k, "label": PROP_LABEL[k]} for k in IQ],
                              "values": [[float(sum(a_[i] for i in f["feats"]))] + [float(sum(c_[i, k] for i in f["feats"])) for k in range(10)] for f in FACTORS if f["feats"]], "note": "weight of each factor on take-up (logit per unit), on its own and in interaction with each property of the offer; fitted on 39 ideas x 400 people"}, "rule": "logit = intercept + person factors + offer properties + their interaction (ridge fitted on 39 ideas x 400 people); push = (node vs world average on a factor) x (that factor's weight for this offer)"},
                   "read": {"mode": "offer", "cols": cols, "rows": rows, "value_label": "push on support (points vs the average person)", "total_label": "support"}})
    # ---------------- drill: the attractor/detractor ledger for one cell
    def drill(self, node, col, want_series=False):
        L_ = self.last; m = self.masks[node]; rows = []
        if not L_: return {"error": "no request yet"}
        if L_["mode"] == "offer":
            f = next(x for x in FACTORS if x["id"] == col); pr, pn = L_["pr"], L_["pn"]; sup = self.hm(pr, m); scale = sup * (1 - sup) * 100
            if f["id"] == "world":
                tot = self.w.totals(); T = tot[node] if node in tot else None
                for dl in DIALS:
                    if dl in ("optimism", "news_overload"): continue
                    d, _ = self.eff_prop(zero=(dl,)); pz = self.aud.probability(self.pop, d, L_["iv"]); push = (self.hm(pr, m) - self.hm(pz, m)) * 100; st = float(self.hm(self.eff_prop()[1][:, DIALS.index(dl)], m))
                    if abs(push) >= 0.02: rows.append({"tag": "A" if push > 0 else "D", "factor": DIAL_NAME[dl], "state": st, "state_label": "dial value here", "weight": None, "rule": "remove this dial and re-ask", "push": push})
            else:
                for i in f["feats"]:
                    Pb = self.pop.wmean(L_["Pm"][:, i], m); z = (Pb - L_["mu"][i]) / L_["sd"][i]; wps = L_["wi"][i] * L_["sd"][i]; push = z * wps * scale
                    top = sorted(enumerate(L_["c"][i] * L_["iv"]), key=lambda t: -abs(t[1]))[:2]; why = "; ".join(f"{PROP_LABEL[IQ[k]]} {v:+.2f}" for k, v in top if abs(v) > 0.01)
                    rows.append({"tag": "A" if push > 0 else "D", "factor": FEAT_LABEL[FEATS[i]], "state": z, "state_label": "sd from world average", "weight": wps, "rule": "main effect + interaction with: " + (why or "nothing"), "push": push})
            series = [] if not want_series else [self.hm(self.aud.probability(self.pop, W2.effective(self.pop, W2.person_delta(self.w, self.pop, self.seg_gain, at=h)), L_["iv"]), m) * 100 for h in self.hist]
            return jn({"mode": "offer", "node": node, "col": col, "support": sup * 100, "ledger": sorted(rows, key=lambda r: -abs(r["push"])), "series": series, "series_label": "support after each story (%)"})
        j = E.DECS.index(col); p0, p1 = L_["p0"][:, j], L_["p1"][:, j]; b = self.hm(p0, m); scale = b * (1 - b) * 100; z0 = (L_["eff0"] - 3) / 1.5; z1 = (L_["eff1"] - 3) / 1.5
        s = float(self.hm(self.pop.sal.mean(1), m)); d0 = np.array([self.hm(L_["d0"][:, k], m) for k in range(len(DIALS))]); d1 = np.array([self.hm(L_["d1"][:, k], m) for k in range(len(DIALS))])
        dl = np.log(np.maximum(1 + s * d1, 0.2)) - np.log(np.maximum(1 + s * d0, 0.2))
        basis = {x["dial"]: x.get("basis", "reported") for x in L_["readings"]}; basis_mode = {x["dial"]: x.get("mode") for x in L_["readings"]}
        for e_i, e in enumerate(E.ELS):
            w_ = E.W[j, e_i]
            if abs(w_) < 1e-9: continue
            dz = self.hm(z1[:, e_i], m) - self.hm(z0[:, e_i], m); push = w_ * dz * scale; contrib = E.GRID[e_i] * dl; k = int(np.argmax(np.abs(contrib))); top = abs(contrib[k])
            via = [{"dial": DIALS[i], "name": DIAL_NAME[DIALS[i]], "direction": "up" if dl[i] > 0 else "down", "basis": basis.get(DIALS[i], "derived"), "mode": basis_mode.get(DIALS[i])} for i in np.argsort(-np.abs(contrib))[:2] if top > 1e-6 and abs(contrib[i]) >= 0.25 * top]
            rows.append({"tag": "A" if push > 0 else "D", "factor": EL_NAME[e], "state": self.hm(z1[:, e_i], m), "state_label": "standardised state now", "weight": float(w_), "via": via, "rule": (f"moved by {DIAL_NAME[DIALS[k]]} ({dl[k]:+.3f} in log perceived dial)" if top > 1e-6 else "not moved by this event"), "delta": dz, "push": push})
        series = [] if not want_series else [self.hm(E.Population.propensity(None, W2.effective(self.pop, W2.person_delta(self.w, self.pop, self.seg_gain, at=h)))[:, j], m) * 100 for h in self.hist] + [self.hm(p1, m) * 100]
        return jn({"mode": "event", "node": node, "col": col, "value": (self.hm(p1, m) - b) * 100, "parts": {k: float(self.hm(v[:, j] - L_["p0"][:, j], m) * 100) for k, v in L_["parts"].items()}, "ledger": sorted(rows, key=lambda r: -abs(r["push"])), "series": series, "series_label": "propensity after each story, then after the event (%)"})
    def world_now(self):
        """The world as it stands now against the world when the feed started (the end of the reset): per place and audience, the change in each decision (points) and in each condition. Cached per tick."""
        if self.world_cache and self.world_cache[0] == self.w.tick: return self.world_cache[1]
        h0 = self.hist[self.live_at]; tot = self.w.totals(); nd = range(len(E.DECS)); rows = []
        if W2.GPU: Nw, Mv, St = W2.world_stats(self.w, self.pop, self.seg_gain, h0, self.M)
        else:
            eff0, p0 = W2.prop_at(self.w, self.pop, self.seg_gain, at=h0); eff1, p1 = W2.prop_at(self.w, self.pop, self.seg_gain); St = self.gm((eff1 - eff0) / 1.5); Nw, Mv = self.gm(p1) * 100, self.gm(p1 - p0) * 100
        for i, rw in enumerate(self.rows):
            n = rw["id"]; dd = (tot[n] - h0[n]) if n in tot else None
            rows.append({"id": n, "label": rw["label"], "level": n.split(":")[0].lower(), "share": round(self.share[i], 4), "now": Nw[i].tolist(), "move": Mv[i].tolist(), "states": St[i].tolist(), "dials": None if dd is None else [float(x) for x in dd]})
        out = jn({"tick": self.w.tick, "since_tick": self.live_at, "decisions": [{"id": d, "label": DEC_NAME[d]} for d in E.DECS], "dials": [{"id": d, "name": DIAL_NAME[d]} for d in DIALS], "state_ids": list(E.ELS), "rows": rows,
                  "note": "change since the live feed started: decision likelihood (points) and each condition's level, from the same rules as an ask"})
        self.world_cache = (self.w.tick, out); return out
    def people_layout(self):
        """Who each modelled person is, for the picture: country, settlement type and audience as three byte arrays (base64), plus names and shares. Static until the engine restarts."""
        import base64
        p = self.pop; b = lambda a: base64.b64encode(np.asarray(a, np.uint8).tobytes()).decode()
        return {"n": int(p.n), "country": b(p.country), "settle": b(p.settle_idx if hasattr(p, "settle_idx") else p.region % 3), "seg": b(p.seg),
                "countries": [{"id": c["id"], "name": c["name"], "pop_m": c["pop_m"], "n": int((p.country == i).sum())} for i, c in enumerate(self.countries)],
                "settles": [{"id": x, "name": SETTLE_NAME[x]} for x in W2.SETTLES], "audiences": [{"id": a["id"], "name": a["name"], "share": a["share"]} for a in self.segs],
                "decisions": [{"id": d, "label": DEC_NAME[d]} for d in E.DECS]}
    def people_values(self, j):
        """Each person's change in likelihood of decision j since the feed started, in thousandths of a point, as int16 (base64). Cached per tick and decision."""
        import base64
        k = ("pv", self.w.tick, j)
        if k in self.cache: return self.cache[k]
        for kk in [x for x in self.cache if isinstance(x, tuple) and x[0] == "pv" and x[1] != self.w.tick]: del self.cache[kk]
        t = time.time(); h0 = self.hist[self.live_at]; p0 = W2.prop_at(self.w, self.pop, self.seg_gain, at=h0)[1]; p1 = W2.prop_at(self.w, self.pop, self.seg_gain)[1]
        v = np.clip(np.round((p1[:, j] - p0[:, j]) * 100 * 1000), -32000, 32000).astype(np.int16)
        out = {"tick": self.w.tick, "d": j, "scale": 1000, "ms": round((time.time() - t) * 1000, 1), "v": base64.b64encode(v.tobytes()).decode()}
        self.cache[k] = out; return out
    def gpu_info(self):
        """What the arithmetic runs on and what each stage costs now: a short timed pass of the real per-person maths, the grouped means and one world step (cached per tick)."""
        k = ("gpu", self.w.tick)
        if k in self.cache: return self.cache[k]
        for kk in [x for x in self.cache if isinstance(x, tuple) and x[0] == "gpu"]: del self.cache[kk]
        d = W2.person_delta(self.w, self.pop, self.seg_gain)
        def tm(f, n=3):
            f(); t0 = time.time(); [f() for _ in range(n)]; return round((time.time() - t0) / n * 1000, 2)
        eff = W2.effective(self.pop, d); pr = E.Population.propensity(None, eff)
        ms = {"state": tm(lambda: W2.person_delta(self.w, self.pop, self.seg_gain)), "effect": tm(lambda: W2.effective(self.pop, d)), "decide": tm(lambda: E.Population.propensity(None, eff)), "group": tm(lambda: self.gm(pr)),
              "spread": tm(lambda: copy.deepcopy(self.w).step(), 1)}
        out = {"gpu": bool(W2.GPU), "device": None, "engine_mb": None, "free_mb": None, "total_mb": None, "people": int(self.pop.n), "places": len(self.rows), "ms": ms}
        if W2.GPU:
            import torch; free, tot = torch.cuda.mem_get_info(); out.update(device=torch.cuda.get_device_name(0), engine_mb=round(torch.cuda.memory_reserved() / 1e6), free_mb=round(free / 1e6), total_mb=round(tot / 1e6))
        self.cache[k] = out; return out
    def graph_info(self):
        """The knowledge graph the engine actually runs on, layer by layer, with every link's strength and sign. Meaning chain: topics -> conditions -> person states -> decisions (+ resources from topics).
        Places chain: world -> countries -> settlement types -> audiences -> people. Static until the engine restarts; live values come from /world."""
        k = ("graph",)
        if k in self.cache: return self.cache[k]
        split = lambda v: [x for x in v.split("; ") if x and x != "none"]; res = C.load("resources"); rname = {r["name"].lower(): r["id"] for r in res}
        topics = [{"id": d["id"], "name": d["name"], "definition": d["definition"], "status": d["status"], "kind": d["kind"]} for d in C.DOMAINS if d["id"] != "other"]
        conds = [{"id": d, "name": DIAL_NAME[d], "definition": next((r.get("definition") or r.get("description") or r.get("meaning") or "" for r in E.D_ROWS if r["id"] == d), "")} for d in DIALS]
        states = [{"id": e, "name": EL_NAME[e], "definition": next((r.get("definition", "") for r in E.E_ROWS if r["id"] == e), "")} for e in E.ELS]
        decs = [{"id": d, "name": DEC_NAME[d]} for d in E.DECS]; resn = [{"id": r["id"], "name": r["name"], "definition": r["definition"]} for r in res]
        t2c = [{"a": d["id"], "b": x, "w": 1.0} for d in C.DOMAINS if d["id"] != "other" for x in split(d.get("dials", ""))]
        t2r = [{"a": d["id"], "b": rname[x.lower()], "w": 1.0} for d in C.DOMAINS if d["id"] != "other" for x in split(d.get("resources", "")) if x.lower() in rname]
        G_, W_ = E.GRID, E.W; gm_, wm_ = float(np.abs(G_).max()) or 1.0, float(np.abs(W_).max()) or 1.0
        c2s = [{"a": DIALS[i], "b": E.ELS[e], "w": round(float(G_[e, i]) / gm_, 3)} for e in range(G_.shape[0]) for i in range(G_.shape[1]) if G_[e, i] != 0]
        s2d = [{"a": E.ELS[e], "b": E.DECS[j], "w": round(float(W_[j, e]) / wm_, 3)} for j in range(W_.shape[0]) for e in range(W_.shape[1]) if W_[j, e] != 0]
        settles = [{"id": x, "name": SETTLE_NAME[x]} for x in W2.SETTLES]
        places = {"countries": [{"id": c["id"], "name": c["name"], "pop_m": c["pop_m"]} for c in self.countries], "settles": settles, "audiences": [{"id": a["id"], "name": a["name"], "share": a["share"]} for a in self.segs],
                  "audience_mix": [{"a": c["id"], "b": a["id"], "w": a["country_mix"][ci]} for a in self.segs for ci, c in enumerate(self.countries)]}
        out = jn({"meaning": {"topics": topics, "conditions": conds, "states": states, "decisions": decs, "resources": resn, "topic_condition": t2c, "condition_state": c2s, "state_decision": s2d, "topic_resource": t2r},
                  "places": places, "people": int(self.pop.n), "topic_of": TICKER_TOPIC, "iso2": {k_: v for k_, v in TICKER_COUNTRY.items() if v},
                  "counts": {"topic_condition": len(t2c), "condition_state": len(c2s), "state_decision": len(s2d), "topic_resource": len(t2r)}})
        self.cache[k] = out; return out
    def prepare_feed(self, it):
        """Read one ticker headline into readings, without touching the world (this calls the model, so it runs outside the engine lock). The headline's own country and topic are used,
        not guessed: the topic limits which conditions may be expected to move, the country decides where it enters. Amounts are scaled down (FEED_SCALE): a headline nudges the world, an ask is measured against it."""
        ev = {"evidence_id": "feed", "published_at": datetime.date.today().isoformat(), "title": it["x"], "description": ""}
        P = C.ask(ev); r = C.read(P); sign = lambda x: 0.10 if x["direction"] == "up" else -0.10
        readings = [dict(x, amount=sign(x) * x["strength"], basis="reported") for x in r["readings"] if x["direction"] != "conflict"]
        dom = TICKER_TOPIC.get(it["t"]); allowed = {v for d in C.DOMAINS if d["id"] == dom for v in d.get("dials", "").split("; ") if v} or None      # no known topic: let every condition be considered
        for x in C.expected(ev, {x["dial"] for x in readings}, allowed, min_p=0.0, min_net=0.0): readings.append(dict(x, amount=sign(x) * x["strength"] * x["mode_weight"]))
        w_, wtype, _ = C.type_weight(r["gate"]["happened"], r["gate"]["announced"], r["gate"]["opinion"], P["g|forecast"])
        for x in readings: x["amount"] *= w_ * FEED_SCALE
        cid = TICKER_COUNTRY.get(it["c"]); return {"it": it, "readings": readings, "entry": f"COUNTRY:{cid}" if cid in self.cid else "WORLD:world", "cid": cid}
    def apply_feed(self, prep):
        """Put a prepared headline into the world: one tick, then clip every node so a long run of headlines cannot push the world to extremes (FEED_CAP)."""
        self.apply({"event": f"feed{LIVE['seq'] + 1}", "entry": prep["entry"], "count": 1, "readings": prep["readings"], "title": prep["it"]["x"], "country": prep["cid"], "source": "ticker"}, 1)
        for n in self.w.delta: np.clip(self.w.delta[n], -FEED_CAP, FEED_CAP, out=self.w.delta[n])
    def commit(self):
        if not self.last or self.last["mode"] != "event" or not self.last["counted"]: return {"error": "nothing to commit"}
        self.apply(self.last["event"], 3); self.last = None; return {"ok": True, "events": len(self.events)}
    def map_info(self):
        """Static picture of how things connect, for the page: topic domains, the conditions (dials) each may move, the decisions, the resource classes, and how strongly
        each condition reaches each decision through the person factors (rules: decision weights x dial-to-factor grid; sign = direction when the condition rises)."""
        split = lambda v: [x for x in v.split("; ") if x and x != "none"]; links = E.W @ E.GRID; mx = float(np.abs(links).max()) or 1.0
        return {"domains": [{"id": d["id"], "name": d["name"], "definition": d["definition"], "cap_topics": split(d["cap_topics"]), "state_classes": split(d["state_classes"]), "dials": split(d["dials"]), "decisions": split(d["decisions"]), "resources": split(d["resources"]), "kind": d["kind"]} for d in C.DOMAINS],
                "dials": [{"id": d, "name": DIAL_NAME[d]} for d in DIALS], "decisions": [{"id": d, "label": DEC_NAME[d]} for d in E.DECS],
                "links": {d: [round(float(links[j, i]) / mx, 3) for j in range(len(E.DECS))] for i, d in enumerate(DIALS)},
                "resources": [{"id": r["id"], "name": r["name"], "definition": r["definition"]} for r in C.load("resources")],
                "phrases": {r["decision_id"]: {"down": r["down"], "up": r["up"]} for r in C.load("decision_phrases")}}
    def state(self):
        base = json.load(open("/workspace/probes/world-engine/baseline.json")); tot = self.w.totals(); dials = []
        for i, d in enumerate(DIALS): dials.append({"id": d, "name": DIAL_NAME[d], "world": float(tot["WORLD:world"][i])})
        return jn({"tick": self.w.tick, "digest": self.w.digest(), "people": self.pop.n, "countries": [{"id": c["id"], "name": c["name"], "pop_m": c["pop_m"], "median_age": c["median_age"], "income_k": c["income_k"], "urban": c["urban"], "region": c.get("region", ""), "iso2": c.get("iso2", ""), "source": c["source"]} for c in self.countries],
                   "map": self.map_info(), "anchors": base["anchors"], "events": [{"title": e["title"], "entry": e["entry"], "country": e.get("country"), "source": e["source"], "readings": [{"dial": r["dial"], "name": DIAL_NAME[r["dial"]], "amount": r["amount"]} for r in e["readings"]]} for e in self.events],
                   "rules": {"domains": len(C.DOMAINS), "dials": len(DIALS), "elements": len(E.ELS), "grid_cells": int((E.GRID != 0).sum()), "decisions": len(E.DECS), "decision_weights": int((E.W != 0).sum()), "factors": len(FACTORS), "questions": len(C.QS)}, "audiences": len(self.segs), "boot_seconds": self.boot, "dials": dials})
# ---------------- live ticker: headlines fed into the world one tick at a time, only while some page is watching
TICKER_FILE = "/workspace/data/news/bank.json" if os.path.exists("/workspace/data/news/bank.json") else "/workspace/demo/ticker.json"; FEED_SCALE, FEED_CAP, FEED_IDLE_S, FEED_EXPECT_MIN = 0.5, 0.4, 25, 0.0     # ticker headlines keep every non-zero reading (asks use a 0.5 bar): each one is only a nudge, and small is not none
TICKER_COUNTRY = {c["iso2"]: c["id"] for c in load_countries() if c["iso2"]}; TICKER_COUNTRY["WORLD"] = None      # ISO2 code of a headline -> engine country
TICKER_TOPIC = {"ECONOMY": "economy_housing", "WORK": "work_labour", "ENERGY": "energy_resources", "CLIMATE": "environment_climate", "HEALTH": "health", "CRIME": "safety_crime", "CONFLICT": "conflict_security",
                "LAW": "government_law", "DIPLOMACY": "international_migration", "SOCIETY": "society_identity", "CULTURE": "culture_leisure", "TECH": "technology_science", "SCHOOL": "education", "BUSINESS": "business_corporate"}
LIVE = {"on": False, "interval": 7.0, "seen": 0.0, "next": 0.0, "seq": 0, "fed": 0, "items": [], "err": None}; LIVE_LOCK = threading.Lock()
ROLL = {"order": [], "pos": 0, "bank": None}
def live_pick(rng, recent):
    """Rolls through the whole bank in a shuffled order and visits every headline once before any repeats (the bank mixes real feeds, tech, satire and our own funny lines)."""
    if ROLL["bank"] is None: ROLL["bank"] = json.load(open(TICKER_FILE))
    if ROLL["pos"] >= len(ROLL["order"]): ROLL["order"] = list(range(len(ROLL["bank"]))); rng.shuffle(ROLL["order"]); ROLL["pos"] = 0
    it = dict(ROLL["bank"][ROLL["order"][ROLL["pos"]]]); ROLL["pos"] += 1; it["x"] = it["x"].replace("{pct}", rng.choice(["8", "12", "15", "20", "30"])).replace("{n}", rng.choice(["3", "12", "40", "120"])); return it
def feeder_loop():
    """Feeds one headline every LIVE['interval'] seconds while it is switched on AND a page has asked for /live in the last FEED_IDLE_S seconds, so closing the page stops the drift."""
    rng, recent = random.Random(), []
    while True:
        time.sleep(0.4)
        with LIVE_LOCK: go = LIVE["on"] and S is not None and time.time() - LIVE["seen"] < FEED_IDLE_S and time.time() >= LIVE["next"]; gap = LIVE["interval"]
        if not go: continue
        try:
            it = live_pick(rng, recent); t0 = time.time(); prep = S.prepare_feed(it); read_ms = round((time.time() - t0) * 1000)
            with LOCK: t1 = time.time(); S.apply_feed(prep); tick = S.w.tick; apply_ms = round((time.time() - t1) * 1000, 1)
            eff = [{"dial": x["dial"], "name": DIAL_NAME[x["dial"]], "dir": "up" if x["amount"] > 0 else "down", "basis": x["basis"]} for x in sorted(prep["readings"], key=lambda x: -abs(x["amount"]))[:3] if abs(x["amount"]) > 0]
            with LIVE_LOCK: LIVE["seq"] += 1; LIVE["fed"] += 1; LIVE["items"].append({"seq": LIVE["seq"], "c": it["c"], "t": it["t"], "x": it["x"], "src": it.get("src"), "kind": it.get("kind"), "effects": eff, "tick": tick, "read_ms": read_ms, "apply_ms": apply_ms}); del LIVE["items"][:-60]; LIVE["err"] = None
        except Exception as e:
            with LIVE_LOCK: LIVE["err"] = f"{type(e).__name__}: {str(e)[:100]}"
        with LIVE_LOCK: LIVE["next"] = time.time() + gap
def live_status(since=0, watching=True):
    with LIVE_LOCK:
        if watching: LIVE["seen"] = time.time()
        out = {"on": LIVE["on"], "interval": LIVE["interval"], "seq": LIVE["seq"], "fed": LIVE["fed"], "err": LIVE["err"], "items": [i for i in LIVE["items"] if i["seq"] > since]}
    out["tick"] = S.w.tick; out["events"] = len(S.events); return out
S = None
class H(BaseHTTPRequestHandler):
    def _send(self, code, obj): b = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path.startswith("/state"):
            with LOCK: return self._send(200, S.state())
        if self.path.startswith("/people_layout"):
            with LOCK: return self._send(200, S.people_layout())
        if self.path.startswith("/people"):
            q = dict(urllib.parse.parse_qsl(self.path.partition("?")[2])); j = max(0, min(len(E.DECS) - 1, int(q.get("d", 0) or 0)))
            with LOCK: return self._send(200, S.people_values(j))
        if self.path.startswith("/graph"):
            with LOCK: return self._send(200, S.graph_info())
        if self.path.startswith("/gpu"):
            with LOCK: return self._send(200, S.gpu_info())
        if self.path.startswith("/world"):
            with LOCK: return self._send(200, S.world_now())
        if self.path.startswith("/live"): return self._send(200, live_status(int(dict(urllib.parse.parse_qsl(self.path.partition("?")[2])).get("since", 0) or 0)))
        self._send(404, {"error": "not found"})
    def do_POST(self):
        try:
            req = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 20000)))
            with LOCK:
                if self.path == "/request": t = str(req["text"]).strip(); assert 8 <= len(t) <= 1500 and req["mode"] in ("event", "offer", "auto"); return self._send(200, S.request(t, req["mode"]))
                if self.path == "/drill": return self._send(200, S.drill(str(req["node"]), str(req["col"]), bool(req.get("series"))))
                if self.path == "/commit": return self._send(200, S.commit())
                if self.path == "/reset":
                    S.reset()
                    with LIVE_LOCK: LIVE["items"].clear(); LIVE["fed"] = 0
                    return self._send(200, S.state())
                if self.path == "/live":
                    with LIVE_LOCK:
                        if "on" in req: LIVE["on"] = bool(req["on"]); LIVE["seen"] = time.time(); LIVE["next"] = 0.0
                        if "interval" in req: LIVE["interval"] = min(60.0, max(3.0, float(req["interval"])))
                    return self._send(200, live_status(1 << 60))
            self._send(404, {"error": "not found"})
        except (AssertionError, KeyError, ValueError, StopIteration): self._send(400, {"error": "bad request"})
        except OSError as e: self._send(502, {"error": f"classifier not reachable: {e}"})
    def log_message(self, *a): pass
if __name__ == "__main__":
    threading.Thread(target=feeder_loop, daemon=True).start()
    S = Session(); print(f"world engine ready: {S.pop.n:,} people, {len(S.countries)} countries, {len(S.segs)} audiences, {len(S.events)} events, boot {S.boot}s", flush=True); ThreadingHTTPServer(("127.0.0.1", 8112), H).serve_forever()
