"""World engine service v2 (mock-up): multi-country world, five stages (collect, identify, propagate, decide, read), attractor/detractor ledgers.
JSON over HTTP on 127.0.0.1:8112; the console proxies /api/world-engine/*.   Run: /workspace/kev/.venv/bin/python world_service2.py
Inputs are simulated at the start (data/*.csv, ledger/); everything else is derived by rules. Every strength is a guess or a fit until backtested."""
import sys, json, time, copy, datetime, email.utils, hashlib, threading, csv
import numpy as np
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, "/workspace/probes/persona"); sys.path.insert(0, "/workspace/probes/world-engine")
import engine as E, engine2 as W2, classify as C
from world_pop import WorldPopulation, D as DATA
from sklearn.cluster import KMeans
L = "/workspace/probes/world-engine/ledger"; LOCK = threading.Lock()
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
            cm = [round(float(p.wt[m & (p.country == ci)].sum() / p.wt[m].sum()), 3) for ci in range(len(self.countries))]
            self.segs.append({"id": c, "name": ", ".join(words).capitalize(), "share": round(p.wmean(m.astype(float)), 3), "country_mix": cm})
            for e in EXPOSURE:
                zf = (p.wmean(fa[e["feature"]], m) - mu[e["feature"]]) / sd[e["feature"]]; gain[c, DIALS.index(e["dial"])] += float(e["weight"]) * zf
        self.seg_gain = np.clip(gain, 0.6, 1.6)
        self.masks = {"WORLD:world": np.ones(p.n, bool)}
        for ci, cc in enumerate(self.cid):
            self.masks[f"COUNTRY:{cc}"] = p.country == ci
            for si, s in enumerate(W2.SETTLES): self.masks[f"REGION:{cc}-{s}"] = p.region == ci * 3 + si
        for c in range(k): self.masks[f"AUDIENCE:{c}"] = lab == c
        self.rows = [{"id": "WORLD:world", "label": "World", "level": "world", "parent": None}]
        for cc in self.cid:
            self.rows.append({"id": f"COUNTRY:{cc}", "label": self.cname[cc], "level": "country", "parent": "WORLD:world"})
            self.rows += [{"id": f"REGION:{cc}-{s}", "label": f"{self.cname[cc]} · {SETTLE_NAME[s]}", "level": "region", "parent": f"COUNTRY:{cc}"} for s in W2.SETTLES]
        self.rows += [{"id": f"AUDIENCE:{s['id']}", "label": s["name"], "level": "audience", "parent": "AUDIENCES"} for s in self.segs]
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
            c = use[0].get("country", "usa"); evs.append({"event": cid, "title": use[0]["title"], "entry": f"COUNTRY:{c}" if c in self.cid else "WORLD:world", "country": c, "count": len(use), "readings": list(best.values()), "published": email.utils.parsedate_to_datetime(ev[use[0]["evidence_id"]]["published_at"]), "source": "feed"})
        evs.sort(key=lambda e: e["published"]); self.w = W2.World2(self.countries, 0, True); self.events = []; self.hist = [self.w.totals()]
        for e in evs: self.apply(e, 1)
        self.w.run(2); self.hist.append(self.w.totals()); self.cache = {}; self.last = None
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
    # ---------------- the request: identify -> propagate -> decide -> read
    def classify_kind(self, text):
        """Typed choice question: is this something that happened (event) or something offered (offer)?"""
        a = E.O.call(f"Text:\n{text}", {"k": {"type": "choice", "instructions": "What kind of thing is this text?", "criteria": {"event": "Something that happened or was announced in the world, like a news item", "offer": "A product, service, programme or message being offered to people", "other": "Neither"}}})["k"]
        return a["choice"], {k: round(float(v), 3) for k, v in a["probabilities"].items()}
    def request(self, text, mode):
        auto = None
        if mode == "auto":
            kind, p = self.classify_kind(text); mode = "offer" if kind == "offer" else "event"; auto = {"kind": mode, "p": p}
        r = self.request_event(text) if mode == "event" else self.request_offer(text)
        if auto: r["identify"]["auto"] = auto
        else: r["identify"]["auto"] = {"kind": mode, "p": None}
        return r
    def request_event(self, text):
        ev = {"evidence_id": "req", "published_at": email.utils.format_datetime(datetime.datetime.now(datetime.timezone.utc)), "title": text, "description": ""}
        P = C.ask(ev); r = C.read(P); country, cp = C.ask_country(ev); entry = f"COUNTRY:{country}" if country in self.cid else "WORLD:world"
        readings = [dict(x, amount=(0.10 if x["direction"] == "up" else -0.10) * x["strength"]) for x in r["readings"] if x["direction"] != "conflict"]
        ok = bool((r["gate"]["happened"] >= .5 or r["gate"]["announced"] >= .5) and r["gate"]["opinion"] < .5 and P["g|forecast"] < .5)
        evid = []
        for x in readings:
            for i, a in enumerate(C.ATTRS.get((x["dial"], x["direction"]), [])):
                m = (P[f"a|{x['dial']}|{x['direction']}|{i}|0"] + P[f"a|{x['dial']}|{x['direction']}|{i}|1"]) / 2
                if m >= .65: evid.append({"dial": x["dial"], "attribute": a["attribute"], "q1": a["question_1"], "q2": a["question_2"], "p": round(m, 3)})
        ident = {"mode": "event", "counted": ok, "gate": r["gate"], "country": country, "country_p": cp.get(country), "entry": entry, "readings": [{"dial": x["dial"], "name": DIAL_NAME[x["dial"]], "direction": x["direction"], "strength": x["strength"], "amount": round(x["amount"], 4)} for x in readings], "evidence": evid}
        w2 = copy.deepcopy(self.w); w0 = copy.deepcopy(self.w); w2.noise = w0.noise = False; t0 = w2.tick                      # control branch (no event) run the same 3 ticks, so only the event differs
        w0.run(3)
        if ok and readings: self.apply({"event": "req", "entry": entry, "count": 1, "readings": readings}, 3, world=w2)
        else: w2.run(3)
        eff0, d0 = self.eff_prop(w0); eff1, d1 = self.eff_prop(w2); p0, p1 = E.Population.propensity(None, eff0), E.Population.propensity(None, eff1)
        first = {}
        for l in w2.log:
            if l["event"] == "req" and l["node"] not in first: first[l["node"]] = l["tick"] - t0
        self.last = {"mode": "event", "w2": w2, "eff0": eff0, "eff1": eff1, "d0": d0, "d1": d1, "p0": p0, "p1": p1, "entry": entry, "readings": readings, "counted": ok and bool(readings), "event": {"event": "req", "title": text, "entry": entry, "country": country, "count": 1, "readings": readings, "source": "you"}}
        tot0, tot1 = w0.totals(), w2.totals(); cols = [{"id": d, "label": DEC_NAME[d], "kind": "decision"} for d in E.DECS]; rows = []
        for rw in self.rows:
            if rw["level"] == "audience" or True:
                m = self.masks[rw["id"]]; rows.append({**rw, "share": round(self.pop.wmean(m.astype(float)), 4), "values": [self.hm(p1[:, j] - p0[:, j], m) * 100 for j in range(len(E.DECS))], "base": [self.hm(p0[:, j], m) * 100 for j in range(len(E.DECS))]})
        prop_rows = [{"id": n, "label": next(x["label"] for x in self.rows if x["id"] == n), "level": n.split(":")[0].lower(), "delta": (tot1[n] - tot0[n]).tolist(), "first_tick": first.get(n)} for n in w2.nodes]
        return jn({"identify": ident, "propagate": {"dials": [{"id": d, "name": DIAL_NAME[d]} for d in DIALS], "rows": prop_rows, "note": "change in each dial at each node versus a control run with no event, after 3 ticks"}, "decide": {"kind": "state decisions", "cols": cols, "matrix": {"rows": [{"id": d, "label": DEC_NAME[d], "kind": "decision"} for d in E.DECS], "cols": [{"id": e, "label": EL_NAME[e]} for e in E.ELS if abs(E.W[:, E.ELS.index(e)]).sum() > 0],
                              "values": [[float(E.W[j, E.ELS.index(e)]) for e in E.ELS if abs(E.W[:, E.ELS.index(e)]).sum() > 0] for j in range(len(E.DECS))], "note": "weight of each person state on each decision (rules/decision_weights.csv, hand-set guesses)"}, "rule": "propensity = sigmoid(bias + sum of weights x standardised person states); weights in rules/decision_weights.csv"},
                   "read": {"mode": "event", "cols": cols, "rows": rows, "value_label": "change in propensity (points)", "total_label": None}})
    def request_offer(self, text):
        iv = self.item(text); p = self.aud
        ident = {"mode": "offer", "counted": True, "readings": [{"id": k, "label": PROP_LABEL[k], "p": round(float(v), 3), "question": E.O.IDEA_Q[k]} for k, v in zip(IQ, iv)]}
        eff, d = self.eff_prop(); tri = [E.ELS.index(e) for e in ("tech_comfort", "price_attention", "privacy_stance", "social_ease", "time_pressure", "novelty_seeking")]
        Pm = np.hstack([np.clip((eff[:, tri] - 1) / 4, 0, 1), self.pop.flags]); pr = p.probability(self.pop, eff, iv); pn = p.probability(self.pop, self.pop.base, iv)
        coef = p.m.coef_; a_, c_ = coef[:16], coef[26:].reshape(16, 10); wi = a_ + c_ @ iv; mu = np.array([self.pop.wmean(Pm[:, i]) for i in range(16)]); sd = Pm.std(0) + 1e-9
        self.last = {"mode": "offer", "iv": iv, "eff": eff, "Pm": Pm, "pr": pr, "pn": pn, "wi": wi, "c": c_, "mu": mu, "sd": sd, "text": text}
        cols = [{"id": f["id"], "label": f["label"], "kind": f["kind"]} for f in FACTORS]; rows = []
        for rw in self.rows:
            m = self.masks[rw["id"]]; sup = self.hm(pr, m); scale = sup * (1 - sup) * 100; Pb = np.array([self.pop.wmean(Pm[:, i], m) for i in range(16)]); push = (Pb - mu) * wi * scale; vals = []
            for f in FACTORS: vals.append(self.hm(pr - pn, m) * 100 if f["id"] == "world" else float(push[f["feats"]].sum()))
            rows.append({**rw, "share": round(self.pop.wmean(m.astype(float)), 4), "values": vals, "total": sup * 100})
        tot = self.w.totals(); prop_rows = [{"id": n, "label": next(x["label"] for x in self.rows if x["id"] == n), "level": n.split(":")[0].lower(), "delta": tot[n].tolist(), "first_tick": None} for n in self.w.nodes]
        return jn({"identify": ident, "propagate": {"dials": [{"id": x, "name": DIAL_NAME[x]} for x in DIALS], "rows": prop_rows, "note": "an offer does not move the world; it is read against today's world (each dial's current value)"},
                   "decide": {"kind": "take-up of the offer", "cols": cols, "matrix": {"rows": [{"id": f["id"], "label": f["label"], "kind": f["kind"]} for f in FACTORS if f["feats"]], "cols": [{"id": "main", "label": "on its own"}] + [{"id": k, "label": PROP_LABEL[k]} for k in IQ],
                              "values": [[float(sum(a_[i] for i in f["feats"]))] + [float(sum(c_[i, k] for i in f["feats"])) for k in range(10)] for f in FACTORS if f["feats"]], "note": "weight of each factor on take-up (logit per unit), on its own and in interaction with each property of the offer; fitted on 39 ideas x 400 people"}, "rule": "logit = intercept + person factors + offer properties + their interaction (ridge fitted on 39 ideas x 400 people); push = (node vs world average on a factor) x (that factor's weight for this offer)"},
                   "read": {"mode": "offer", "cols": cols, "rows": rows, "value_label": "push on support (points vs the average person)", "total_label": "support"}})
    # ---------------- drill: the attractor/detractor ledger for one cell
    def drill(self, node, col):
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
            series = [self.hm(self.aud.probability(self.pop, W2.effective(self.pop, W2.person_delta(self.w, self.pop, self.seg_gain, at=h)), L_["iv"]), m) * 100 for h in self.hist]
            return jn({"mode": "offer", "node": node, "col": col, "support": sup * 100, "ledger": sorted(rows, key=lambda r: -abs(r["push"])), "series": series, "series_label": "support after each story (%)"})
        j = E.DECS.index(col); p0, p1 = L_["p0"][:, j], L_["p1"][:, j]; b = self.hm(p0, m); scale = b * (1 - b) * 100; z0 = (L_["eff0"] - 3) / 1.5; z1 = (L_["eff1"] - 3) / 1.5
        s = float(self.hm(self.pop.sal.mean(1), m)); d0 = np.array([self.hm(L_["d0"][:, k], m) for k in range(len(DIALS))]); d1 = np.array([self.hm(L_["d1"][:, k], m) for k in range(len(DIALS))])
        dl = np.log(np.maximum(1 + s * d1, 0.2)) - np.log(np.maximum(1 + s * d0, 0.2))
        for e_i, e in enumerate(E.ELS):
            w_ = E.W[j, e_i]
            if abs(w_) < 1e-9: continue
            dz = self.hm(z1[:, e_i], m) - self.hm(z0[:, e_i], m); push = w_ * dz * scale; contrib = E.GRID[e_i] * dl; k = int(np.argmax(np.abs(contrib)))
            rows.append({"tag": "A" if push > 0 else "D", "factor": EL_NAME[e], "state": self.hm(z1[:, e_i], m), "state_label": "standardised state now", "weight": float(w_), "rule": (f"moved by {DIAL_NAME[DIALS[k]]} ({dl[k]:+.3f} in log perceived dial)" if abs(contrib[k]) > 1e-6 else "not moved by this event"), "delta": dz, "push": push})
        series = [self.hm(E.Population.propensity(None, W2.effective(self.pop, W2.person_delta(self.w, self.pop, self.seg_gain, at=h)))[:, j], m) * 100 for h in self.hist] + [self.hm(p1, m) * 100]
        return jn({"mode": "event", "node": node, "col": col, "value": (self.hm(p1, m) - b) * 100, "ledger": sorted(rows, key=lambda r: -abs(r["push"])), "series": series, "series_label": "propensity after each story, then after the event (%)"})
    def commit(self):
        if not self.last or self.last["mode"] != "event" or not self.last["counted"]: return {"error": "nothing to commit"}
        self.apply(self.last["event"], 3); self.last = None; return {"ok": True, "events": len(self.events)}
    def state(self):
        base = json.load(open("/workspace/probes/world-engine/baseline.json")); tot = self.w.totals(); dials = []
        for i, d in enumerate(DIALS): dials.append({"id": d, "name": DIAL_NAME[d], "world": float(tot["WORLD:world"][i])})
        return jn({"tick": self.w.tick, "digest": self.w.digest(), "people": self.pop.n, "countries": [{"id": c["id"], "name": c["name"], "pop_m": c["pop_m"], "median_age": c["median_age"], "income_k": c["income_k"], "urban": c["urban"], "source": c["source"]} for c in self.countries],
                   "anchors": base["anchors"], "events": [{"title": e["title"], "entry": e["entry"], "country": e.get("country"), "source": e["source"], "readings": [{"dial": r["dial"], "name": DIAL_NAME[r["dial"]], "amount": r["amount"]} for r in e["readings"]]} for e in self.events],
                   "rules": {"dials": len(DIALS), "elements": len(E.ELS), "grid_cells": int((E.GRID != 0).sum()), "decisions": len(E.DECS), "decision_weights": int((E.W != 0).sum()), "factors": len(FACTORS), "questions": len(C.QS)}, "audiences": len(self.segs), "boot_seconds": self.boot, "dials": dials})
S = None
class H(BaseHTTPRequestHandler):
    def _send(self, code, obj): b = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path.startswith("/state"):
            with LOCK: return self._send(200, S.state())
        self._send(404, {"error": "not found"})
    def do_POST(self):
        try:
            req = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 20000)))
            with LOCK:
                if self.path == "/request": t = str(req["text"]).strip(); assert 8 <= len(t) <= 1500 and req["mode"] in ("event", "offer", "auto"); return self._send(200, S.request(t, req["mode"]))
                if self.path == "/drill": return self._send(200, S.drill(str(req["node"]), str(req["col"])))
                if self.path == "/commit": return self._send(200, S.commit())
                if self.path == "/reset": S.reset(); return self._send(200, S.state())
            self._send(404, {"error": "not found"})
        except (AssertionError, KeyError, ValueError, StopIteration): self._send(400, {"error": "bad request"})
        except OSError as e: self._send(502, {"error": f"classifier not reachable: {e}"})
    def log_message(self, *a): pass
if __name__ == "__main__":
    S = Session(); print(f"world engine ready: {S.pop.n:,} people, {len(S.countries)} countries, {len(S.segs)} audiences, {len(S.events)} events, boot {S.boot}s", flush=True); ThreadingHTTPServer(("127.0.0.1", 8112), H).serve_forever()
