"""World lab engine service (mock-up). Holds one live session: world state, people, audience. JSON over HTTP on 127.0.0.1:8111; the demo console proxies /api/world-lab/*.
Run:  /workspace/kev/.venv/bin/python world_service.py [--n 50000]
Everything here is a demo: people are simulated, the world's effects are our assumptions, starting conditions come from public indices."""
import sys, json, time, hashlib, threading, copy, datetime, email.utils
import numpy as np
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import engine as E, classify as C
from personas import age_band
L = "/workspace/probes/world-engine/ledger"; N = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 50000
BASE = json.load(open("/workspace/probes/world-engine/baseline.json"))
NAMES = {r["id"]: r["name"] for r in E.D_ROWS}
IQ = list(E.O.IDEA_Q)
AGE_BANDS = ["18-29", "30-44", "45-59", "60-74", "75-90"]; INC_BANDS = ["under $30k", "$30k-60k", "$60k-100k", "over $100k"]
LOCK = threading.Lock()

def anchor_values():
    out = {}
    for a in BASE["anchors"]:
        if not a["dial"]: continue
        dev = a["scale"] * (a["value"] - a["reference"]) if a["mode"] == "per_unit" else a["scale"] * (a["value"] - a["reference"]) / a["reference"]
        a["deviation"] = round(dev, 4); out[a["dial"]] = out.get(a["dial"], 0) + dev
    return out

class Session:
    def __init__(self):
        t0 = time.time(); self.anchors = anchor_values(); self.pop = E.Population(N); self.aud = E.Audience(); self.cache = {}
        D = json.load(open("/workspace/data/persona-lab/offline.json")); self.ref_iv = np.array([[D["idea"][k][q] for q in IQ] for k in D["direct"]])
        d = np.linalg.norm(self.ref_iv[:, None] - self.ref_iv[None], axis=2); np.fill_diagonal(d, 9); self.nn = np.sort(d.min(1))
        a = self.pop.age; self.age_idx = np.select([a < 30, a < 45, a < 60, a < 75], [0, 1, 2, 3], 4); self.cohort = self.age_idx * 4 + self.pop.inc
        self.seglab, self.segs, self.pop_who = segment_setup(self.pop); self.reset(); self.boot = round(time.time() - t0, 1)
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
            evs.append({"event": cid, "title": use[0]["title"], "entry": use[0]["entry"], "count": len(use), "readings": list(best.values()), "published": email.utils.parsedate_to_datetime(ev[use[0]["evidence_id"]]["published_at"]), "source": "feed"})
        evs.sort(key=lambda e: e["published"]); self.w = E.World(0, True, anchors=self.anchors); self.events = []; self.hist = [self.w.snapshot_totals()]
        for e in evs: self.apply(e, settle=1)
        self.w.run(2); self.hist.append(self.w.snapshot_totals()); self.cache = {}
    def apply(self, e, settle=1):
        t = self.w.tick; e = dict(e); e["tick"] = t
        for r in e["readings"]: self.w.add(t, e["entry"], r["dial"], r["amount"], e["event"])
        self.w.add(t, "COUNTRY:usa", "news_overload", 0.01 * e.get("count", 1), e["event"])
        self.events.append({k: (v.isoformat() if isinstance(v, datetime.datetime) else v) for k, v in e.items()})
        for _ in range(settle): self.w.step(); self.hist.append(self.w.snapshot_totals())
        self.cache = {}
    def grid(self, p): return np.array([[p[(self.age_idx == a) & (self.pop.inc == i)].mean() if ((self.age_idx == a) & (self.pop.inc == i)).any() else np.nan for i in range(4)] for a in range(5)])
    def cohort_mean(self, p): s = np.bincount(self.cohort, p, minlength=20); n = np.bincount(self.cohort, minlength=20); return np.where(n > 0, s / np.maximum(n, 1), np.nan)
    # ---------------- endpoints
    def state(self):
        T = self.hist[-1]; c = T["COUNTRY:usa"]; anc = self.w.anchor["COUNTRY:usa"]; dials = []
        for i, d in enumerate(E.DIALS):
            dials.append({"id": d, "name": NAMES[d], "now": round(float(c[i]), 4), "from_indices": round(float(anc[i]), 4), "from_news": round(float(c[i] - anc[i]), 4), "series": [round(float(h["COUNTRY:usa"][i]), 4) for h in self.hist]})
        return {"tick": self.w.tick, "people": N, "digest": self.w.digest(), "dials": dials, "anchors": BASE["anchors"], "events": self.events, "note": BASE["note"], "boot_seconds": self.boot}
    def inject(self, title, description):
        ev = {"evidence_id": "inj" + hashlib.sha1(title.encode()).hexdigest()[:8], "published_at": email.utils.format_datetime(datetime.datetime.now(datetime.timezone.utc)), "title": title, "description": description}
        P = C.ask(ev); r = C.read(P); readings = [dict(x, amount=(0.10 if x["direction"] == "up" else -0.10) * x["strength"]) for x in r["readings"] if x["direction"] != "conflict"]   # typed in now: no recency test or discount
        r["gate_ok"] = bool((r["gate"]["happened"] >= .5 or r["gate"]["announced"] >= .5) and r["gate"]["opinion"] < .5 and P["g|forecast"] < .5)
        out = {"title": title, "counted_as_event": r["gate_ok"], "gate": r["gate"], "entry": r["entry"], "readings": [{"dial": x["dial"], "name": NAMES[x["dial"]], "direction": x["direction"], "strength": x["strength"], "amount": round(x["amount"], 4)} for x in readings]}
        if r["gate_ok"] and readings: self.apply({"event": ev["evidence_id"], "title": title, "entry": r["entry"], "count": 1, "readings": readings, "source": "you"}, settle=3)
        return out
    def item(self, text):
        k = "item:" + hashlib.sha1(text.encode()).hexdigest()[:10]
        if k not in self.cache: self.cache[k] = self.aud.demands(text)
        return self.cache[k]
    def ask(self, text):
        iv = self.item(text); P = lambda eff, v=iv: self.aud.probability(self.pop, eff, v)
        eff = self.pop.effective(self.w); p = P(eff); neutral = P(self.pop.base); cm = self.cohort_mean(p)
        blockers = {}                                                       # per person lift if the blocker were removed (never negative), averaged by cohort
        def lift(pc): return self.cohort_mean(np.maximum(pc - p, 0))
        labels = {"cost_monthly": "It costs money every month", "setup_app": "They have to install an app", "id_photo": "It asks for ID or a face photo", "strangers": "It involves people they don't know", "time_heavy": "It takes a lot of their time"}
        for key, lab in labels.items():
            if iv[IQ.index(key)] >= 0.5: v2 = iv.copy(); v2[IQ.index(key)] = 0; blockers["offer:" + key] = {"bucket": "offer", "label": lab, "lift": lift(P(eff, v2))}
        tr = {"price_attention": "They watch every dollar", "privacy_stance": "They don't like handing over personal details", "social_ease": "They're uneasy with strangers", "time_pressure": "They have no spare time", "novelty_seeking": "They stick to what they know"}
        for key, lab in tr.items():
            e2 = eff.copy(); e2[:, E.ELS.index(key)] = 3.0; blockers["mind:" + key] = {"bucket": "mind", "label": lab, "lift": lift(P(e2))}
        blockers["world"] = {"bucket": "world", "label": "The state of the world right now", "lift": lift(P(self.pop.base))}
        allo = iv.copy(); [allo.__setitem__(IQ.index(k), 0) for k in labels]; e3 = eff.copy(); [e3.__setitem__((slice(None), E.ELS.index(k)), 3.0) for k in tr]
        bucket_lift = {"offer": lift(P(eff, allo)), "mind": lift(P(e3)), "world": lift(P(self.pop.base))}
        indicators = {}
        for d in E.DIALS:
            if d in ("optimism", "news_overload"): continue
            up = self.cohort_mean(P(self.pop.effective(self.w, extra={d: 0.1})) - p); dn = self.cohort_mean(P(self.pop.effective(self.w, extra={d: -0.1})) - p)
            indicators[d] = {"name": NAMES[d], "up": [None if np.isnan(x) else round(float(x), 5) for x in up], "down": [None if np.isnan(x) else round(float(x), 5) for x in dn]}
        timeline = {"all": [], "young": [], "senior": [], "low": [], "high": []}
        for h in self.hist:
            pt = P(self.pop.effective(self.w, at=h)); timeline["all"].append(float(pt.mean())); timeline["young"].append(float(pt[self.pop.age < 35].mean())); timeline["senior"].append(float(pt[self.pop.age >= 60].mean()))
            timeline["low"].append(float(pt[self.pop.inc <= 1].mean())); timeline["high"].append(float(pt[self.pop.inc >= 2].mean()))
        ref = np.array([float(P(eff, v).mean()) for v in self.ref_iv]); dist = float(np.linalg.norm(self.ref_iv - iv, axis=1).min())
        r4 = lambda a: [None if np.isnan(x) else round(float(x), 5) for x in a]
        return {"readings": {k: round(float(v), 3) for k, v in zip(IQ, iv)}, "overall": round(float(p.mean()), 4), "overall_neutral_world": round(float(neutral.mean()), 4), "share_yes": round(float((p >= .5).mean()), 4),
                "reference": {"q25": round(float(np.quantile(ref, .25)), 4), "q50": round(float(np.quantile(ref, .5)), 4), "q75": round(float(np.quantile(ref, .75)), 4), "n": len(ref)},
                "cohort": r4(cm), "cohort_neutral": r4(self.cohort_mean(neutral)), "cohort_n": [int(x) for x in np.bincount(self.cohort, minlength=20)], "age_bands": AGE_BANDS, "income_bands": INC_BANDS,
                "blockers": {k: {**{x: v[x] for x in ("bucket", "label")}, "lift": r4(v["lift"])} for k, v in blockers.items()}, "bucket_lift": {k: r4(v) for k, v in bucket_lift.items()}, "indicators": indicators,
                "timeline": {k: [round(x, 5) for x in v] for k, v in timeline.items()}, "extrapolation": {"distance": round(dist, 3), "typical": round(float(np.median(self.nn)), 3), "unlike_anything_fitted": bool(dist > np.quantile(self.nn, .9))}}

FEATS = ["tech", "price", "privacy", "social", "time", "novelty", "young", "older", "city", "rural", "retired", "income", "caregiver", "alone", "kids", "housemates"]
PHR = {"tech": ("comfortable with tech", "wary of tech"), "price": ("watches every dollar", "relaxed about money"), "privacy": ("guards personal details", "relaxed about sharing data"), "social": ("at ease with strangers", "uneasy with strangers"),
       "time": ("short of time", "has spare time"), "novelty": ("keen on new things", "prefers the familiar"), "young": ("under 30", "30 or older"), "older": ("60 or over", "under 60"), "city": ("lives in a big city", "lives outside big cities"),
       "rural": ("rural or small-town", "not rural"), "retired": ("retired", "not retired"), "income": ("higher income", "lower income"), "caregiver": ("looks after a relative", "no caring duties"), "alone": ("lives alone", "doesn't live alone"),
       "kids": ("kids at home", "no kids at home"), "housemates": ("shares with housemates", "doesn't share a home")}
SEG_WORD = {"tech": ("tech-comfortable", "tech-wary"), "price": ("cost-watching", None), "privacy": ("privacy-guarded", None), "social": ("sociable", "reserved"), "time": ("short of time", None), "novelty": ("early adopters", "set in their ways"),
            "age": ("older", "young"), "income": ("higher-income", "lower-income"), "city": ("big-city", None), "rural": ("rural", None), "retired": ("retired", None), "caregiver": ("carers", None), "alone": ("living alone", None), "kids": ("with kids", None), "housemates": ("sharing a home", None)}
BANDS = ["strongly against", "leaning against", "on the fence", "leaning for", "strongly for"]
OFFER = {"cost_monthly": "Make it free (no monthly cost)", "setup_app": "Remove the app requirement", "id_photo": "Drop the ID and photo check", "strangers": "Remove contact with strangers", "time_heavy": "Make it quick to use"}
BELIEF = {"price": ("Ease their money worries", "price_attention"), "privacy": ("Ease their privacy worries", "privacy_stance"), "social": ("Make strangers feel safe", "social_ease"), "time": ("Free up their time", "time_pressure"), "novelty": ("Make it feel familiar", "novelty_seeking")}

def segment_setup(pop, k=8):
    from sklearn.cluster import KMeans
    F = np.column_stack([pop.traits_truth, pop.age, pop.inc, pop.flags[:, 2], pop.flags[:, 3], pop.flags[:, 4], pop.flags[:, 6], pop.flags[:, 7], pop.flags[:, 8], pop.flags[:, 9]]).astype(float)
    key = ["tech", "price", "privacy", "social", "time", "novelty", "age", "income", "city", "rural", "retired", "caregiver", "alone", "kids", "housemates"]
    Z = (F - F.mean(0)) / F.std(0); lab = KMeans(k, n_init=5, random_state=0).fit(Z[:15000]).predict(Z); segs = []
    for c in range(k):
        m = lab == c; z = (F[m].mean(0) - F.mean(0)) / F.std(0); words = []
        for i in np.argsort(-np.abs(z)):
            w = SEG_WORD[key[i]][0 if z[i] > 0 else 1]
            if w and w not in words: words.append(w)
            if len(words) == 3: break
        pctg = lambda mask: round(float(mask[m].mean()), 3)
        segs.append({"id": c, "name": (", ".join(words)).capitalize(), "share": round(float(m.mean()), 3), "n": int(m.sum()),
                     "who": {"median_age": int(np.median(pop.age[m])), "under_35": pctg(pop.age < 35), "age_60_plus": pctg(pop.age >= 60), "under_60k": pctg(pop.inc <= 1), "over_100k": pctg(pop.inc == 3), "big_city": pctg(pop.area == "large city"),
                             "rural_small_town": pctg(np.isin(pop.area, ["rural area", "small town"])), "lives_alone": pctg(pop.household == "lives alone"), "kids_at_home": pctg(np.char.find(pop.household, "children") >= 0),
                             "shares_home": pctg(pop.household == "lives with housemates"), "retired": pctg(pop.work == "retired"), "caring_for_relative": pctg(pop.caregiver)}})
    allm = np.ones(pop.n, bool); pop_who = {"median_age": int(np.median(pop.age)), "under_35": float((pop.age < 35).mean()), "age_60_plus": float((pop.age >= 60).mean()), "under_60k": float((pop.inc <= 1).mean()), "over_100k": float((pop.inc == 3).mean()), "big_city": float((pop.area == "large city").mean()),
        "rural_small_town": float(np.isin(pop.area, ["rural area", "small town"]).mean()), "lives_alone": float((pop.household == "lives alone").mean()), "kids_at_home": float((np.char.find(pop.household, "children") >= 0).mean()), "shares_home": float((pop.household == "lives with housemates").mean()),
        "retired": float((pop.work == "retired").mean()), "caring_for_relative": float(pop.caregiver.mean())}
    return lab, segs, {k_: round(v, 3) if isinstance(v, float) else v for k_, v in pop_who.items()}

def audience_view(self, text):
    import numpy as _np
    iv = self.item(text); aud = self.aud; pop = self.pop; K = len(self.segs); lab = self.seglab; tri = [E.ELS.index(e) for e in ("tech_comfort", "price_attention", "privacy_stance", "social_ease", "time_pressure", "novelty_seeking")]
    def Pmat(eff): return _np.hstack([_np.clip((eff[:, tri] - 1) / 4, 0, 1), pop.flags])
    def prob(eff, v=iv): return aud.probability(pop, eff, v)
    def seg_mean(p): return _np.array([p[lab == c].mean() for c in range(K)])
    eff = pop.effective(self.w); p = prob(eff); pn = prob(pop.base); sm = seg_mean(p); smn = seg_mean(pn)
    # drivers: segment deviation on each person feature x that feature's effect on this item (exact on the logit scale, shown in approximate points)
    coef = aud.m.coef_; a_, c_ = coef[:16], coef[26:].reshape(16, 10); wi = a_ + c_ @ iv; P = Pmat(eff); mu = P.mean(0); drivers = []
    for c in range(K):
        d = (P[lab == c].mean(0) - mu) * wi; scale = sm[c] * (1 - sm[c]) * 100; out = []
        for i, f in enumerate(FEATS):
            pts = float(d[i] * scale)
            if abs(pts) >= 0.25: diff = float(P[lab == c, i].mean() - mu[i]); out.append({"feature": f, "kind": "belief" if i < 6 else "situation", "label": PHR[f][0] if diff > 0 else PHR[f][1], "pts": round(pts, 2)})
        wp = float((sm[c] - smn[c]) * 100)
        if abs(wp) >= 0.1: out.append({"feature": "world", "kind": "world", "label": "the state of the world today", "pts": round(wp, 2)})
        drivers.append(sorted(out, key=lambda x: -abs(x["pts"]))[:8])
    # reference: how this audience usually responds to the ideas we have scored
    rng = _np.random.default_rng(5); sub = rng.choice(pop.n, 4000, replace=False); pool = _np.concatenate([aud.m.predict(aud.feat(P[sub], v)) for v in self.ref_iv]); pool = 1 / (1 + _np.exp(-pool)); qs = _np.quantile(pool, [.2, .4, .6, .8])
    band = _np.digitize(p, qs); refm = _np.array([seg_mean(prob(eff, v)) for v in self.ref_iv])
    # levers: per-person lift if removed (never negative), averaged by segment
    levers = []
    def lever(label, kind, pc): levers.append({"label": label, "kind": kind, "lift": [round(float(x) * 100, 2) for x in seg_mean(_np.maximum(pc - p, 0))]})
    for key, lab_ in OFFER.items():
        if iv[IQ.index(key)] >= .5: v2 = iv.copy(); v2[IQ.index(key)] = 0; lever(lab_, "offer", prob(eff, v2))
    for key, (lab_, el_) in BELIEF.items(): e2 = eff.copy(); e2[:, E.ELS.index(el_)] = 3.0; lever(lab_, "belief", prob(e2))
    lever("If the world were calm", "world", pn)
    ind = {}
    for dl in E.DIALS:
        if dl in ("optimism", "news_overload"): continue
        up = seg_mean(prob(pop.effective(self.w, extra={dl: 0.1}))) - sm; dn = seg_mean(prob(pop.effective(self.w, extra={dl: -0.1}))) - sm; ind[dl] = {"name": NAMES[dl], "up": [round(float(x) * 100, 2) for x in up], "down": [round(float(x) * 100, 2) for x in dn]}
    tl = [seg_mean(prob(pop.effective(self.w, at=h))) for h in self.hist]
    segs = []
    for c, s0 in enumerate(self.segs):
        segs.append({**s0, "support": round(float(sm[c]), 4), "support_neutral_world": round(float(smn[c]), 4), "bands": [round(float((band[lab == c] == b).mean()), 3) for b in range(5)], "stronger_than_pct_of_ideas": round(float((refm[:, c] <= sm[c]).mean()), 3),
                     "drivers": drivers[c], "timeline": [round(float(t[c]), 4) for t in tl]})
    allt = [float(prob(pop.effective(self.w, at=h)).mean()) for h in self.hist]
    dist = float(_np.linalg.norm(self.ref_iv - iv, axis=1).min())
    return {"readings": {k: round(float(v), 3) for k, v in zip(IQ, iv)}, "overall": round(float(p.mean()), 4), "overall_neutral_world": round(float(pn.mean()), 4), "bands": BANDS, "segments": segs, "levers": levers, "indicators": ind, "population": self.pop_who,
            "timeline_all": [round(x, 4) for x in allt], "n_ideas": len(self.ref_iv), "extrapolation": {"distance": round(dist, 3), "typical": round(float(_np.median(self.nn)), 3), "unlike_anything_fitted": bool(dist > _np.quantile(self.nn, .9))}}
Session.audience = audience_view

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
                if self.path == "/audience": text = str(req["text"]).strip(); assert 10 <= len(text) <= 1500; return self._send(200, S.audience(text))
                if self.path == "/ask": text = str(req["text"]).strip(); assert 10 <= len(text) <= 1500; return self._send(200, S.ask(text))
                if self.path == "/inject": t = str(req["title"]).strip(); assert 8 <= len(t) <= 300; return self._send(200, {"result": S.inject(t, str(req.get("description", ""))[:300]), "state": S.state()})
                if self.path == "/reset": S.reset(); return self._send(200, S.state())
            self._send(404, {"error": "not found"})
        except (AssertionError, KeyError, ValueError): self._send(400, {"error": "need JSON with a text of 10 to 1500 characters (ask) or a title of 8 to 300 (inject)"})
        except OSError as e: self._send(502, {"error": f"classifier not reachable: {e}"})
    def log_message(self, *a): pass
if __name__ == "__main__":
    S = Session(); print(f"world service ready: {N:,} people, boot {S.boot}s, {len(S.events)} events", flush=True); ThreadingHTTPServer(("127.0.0.1", 8111), H).serve_forever()
