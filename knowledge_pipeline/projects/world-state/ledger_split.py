"""ledger_split: the resource ledger v0 (plan v2 step 5; owner design ledger L2707) computed offline from a trace folder, plus the resource-level split-half (test M4 of the build spec).
The page (simulation/index.html, #s_ledger) runs the same rules in JS; test_ledger_parity.cjs checks that both give the same numbers on one trace. Change a rule in both places.
Decision weight (spec 2.2, owner yes L2744): an article counts talked-about mass and direction steps x its landing decision (ANSWER_L1 1.0, EVIDENCE_ONLY 0.5, ABSTAIN 0.25; no landing = 1.0); an ABSTAIN article never sets a direction (its condition step is dropped, not counted in direction items). The page applies the same.
Rules (constants are also shown on the page): an independent item (copies and republished items add nothing, no tick) is one tick. It reaches resources through the topic route: the landing's level-1 code
-> specs/iptc_condition_v0.json rows -> conditions -> resources (traces without a landing stage: the Area topic, when the decider answered it, through the engine's own topic_condition links).
Talked about: +0.2 x function weight (fact 1.0, forecast 0.5, opinion 0.3, unclear 0.5), split over the resources reached. Condition head answered with a direction: +-1.0 on the resource of each condition it names, x2 when the size is "large" (READINGS 1: the spec says "large"; the engine's size scale is minor, notable, major, severe, extreme, so "large" is read as major or above; the v2 trace only holds minor, notable, major).
Decay per tick k = 0.5^(1/half_life), half-life = mean of the resource's engine conditions. Every link is the engine's guess.
State timing (READINGS 2, not fixed by the spec, which says only "falls to warming, then untouched when under 0.05"): idle over 1 half-life = decaying; over 2 = warming; value under 0.05 = untouched (checked first). Readings are written into ledger.json ("readings") and shown on the page; both await an owner yes.
    /workspace/models/embed-zs/.venv/bin/python ledger_split.py <trace folder> [--route auto|area] [--windows 12] [--shuffles 500] [--write | --json <file>]    |    ledger_split.py --selftest [--dump-synth <file>]    |    ledger_split.py <trace folder> --state <out.json> [--persist <ticks.jsonl>] [--state-only]   (resource state v1)    (--write: <trace>/ledger.json, read by funnel_view.py and the page; --json: any other path)
PREDICTION M4 (written before the first run, 2026-11-19; build spec section 4 M4, pattern of ledger L2709), resource level, publishers split by sha1 parity, raw (undecayed) mass per resource, 26 resources:
  replay set (trace-demo, 2,736 lines, Area route): whole-stream split-half Spearman 0.5 to 0.7 (L2709 measured 0.76 on 282 items); per window (12 windows) median under 0.5; shuffled-publisher baseline mean about 0, 95th percentile under 0.35;
  change between windows (share of attention minus the stream's own mix), median per window under 0.3 and not above the shuffled 95th percentile, so 'trends' at resource level is NOT shown yet; direction events (condition present with a direction) on 2 to 4 percent of items.
  v2 trace (runs-v2/trace, 3,609 lines, IPTC route): same ranges, whole-stream expected a little higher because the landing spreads attention over more resources (0.6 to 0.85)."""
import sys, os, json, hashlib, collections, time
import numpy as np
H = os.path.dirname(os.path.abspath(__file__)); SPEC = H + "/specs/iptc_condition_v0.json"
TALK = 0.2; FW = {"fact": 1.0, "forecast": 0.5, "opinion": 0.3, "unclear": 0.5}; SIGN = 1.0; BIG = 2.0; BIG_SIZES = ("major", "severe", "extreme"); DECAY_AT = 1; WARM_AT = 2; MIN_N = 5; FLOOR = 0.05; CONF = 2 / 3; DW = {"ANSWER_L1": 1.0, "EVIDENCE_ONLY": 0.5, "ABSTAIN": 0.25}   # spec 2.2: weight of an article by its topic_landing decision (no landing decision = full weight)
READINGS = ["Spec 2.4 says condition size \"large\" doubles the step; the engine's size scale is minor, notable, major, severe, extreme (size_exact.py), so \"large\" is read as major or above. The v2 trace only holds minor 25, notable 80, major 4 (on items with a direction), so only 'major' is exercised. Awaiting an owner yes.",
            "Spec 2.4 gives no timing for 'decaying -> warming -> untouched': read as idle over 1 half-life = decaying, over 2 = warming, value under 0.05 = untouched. Awaiting an owner yes. On the v2 trace no resource reaches decaying or conflicted, so the rule is checked on a synthetic stream (--selftest), not on real data."]
def stage(l, n): return next((s for s in l.get("stages") or [] if s.get("name") == n), None)
def read_chain(folder):
    out = []
    for ln in open(folder + "/chain.jsonl"):
        l = json.loads(json.loads(ln)["line"])
        if l.get("state") == "traced": out.append(l)
    return out
class Ledger:
    def __init__(self, spec, route="auto"):
        self.sp = spec; self.route = route; self.cres = {r["condition"]: r["resource"] for r in spec["rows"]}; self.up = {r["condition"]: r["up_means"] for r in spec["rows"]}
        self.by_code = collections.defaultdict(list); [self.by_code[x["code"]].append(r["condition"]) for r in spec["rows"] for x in r["iptc"]]
        self.res = {r["id"]: {"n": 0, "att": 0.0, "pos": 0.0, "neg": 0.0, "pn": 0, "nn": 0, "last": 0, "t0": 0, "pubs": set(), "feed": collections.Counter(), "seq": None} for r in spec["resources"] if r["half_life_ticks"]}
        self.hl = {r["id"]: r["half_life_ticks"] for r in spec["resources"]}; self.tick = 0; self.seq = None; self.seen = {}; self.kinds = collections.Counter(); self.indep = 0; self.routes = collections.Counter(); self.unlinked = collections.Counter(); self.l2n = collections.Counter(); self.dirs = 0; self.items = 0
    def name(self, c): return self.sp["names"].get(c.split(":")[1], c)
    def independent(self, l):
        d = (l.get("journal") or {}).get("dup")
        if d: return d["kind"] not in ("copy", "republished"), d["kind"]
        w = " ".join((l.get("title") or "").lower().split())
        if len(w.split()) < 5: return True, "no_key"
        S = self.seen.get(w)
        if S is None: self.seen[w] = {l.get("source") or ""}; return True, "first"
        k = "republished" if (l.get("source") or "") in S else "copy"; S.add(l.get("source") or ""); return False, k
    def dec(self, r, T):
        s = self.res[r]; k = 0.5 ** ((T - s["t0"]) / self.hl[r]); s["att"] *= k; s["pos"] *= k; s["neg"] *= k; s["t0"] = T
    def add(self, l):
        """one traced line; returns None for a copy, else a list of (resource, talk, signed) events (signed = +-magnitude in the condition's direction)"""
        if l.get("state") != "traced": return None
        self.items += 1; ind, kind = self.independent(l); self.kinds[kind] += 1; self.last = None; self.last_kind = kind   # last / last_meta: what this item did, read by ResourceState (state v1); no output changes
        if not ind: return None
        self.tick += 1; T = self.tick; self.seq = l.get("seq"); self.indep += 1
        af = stage(l, "area_function"); st = ((af or {}).get("out") or {}).get("story_type") or []; fw = FW.get(st[0][0] if st else "unclear", FW["unclear"])
        ls = stage(l, "topic_landing"); conds = []; feed = None; route = "none"; w = 1.0; dec = None
        if ls and ls.get("state") in ("ran", "abstain") and (ls.get("out") or {}).get("l1_code") and self.route != "area":
            o = ls["out"]; code = o["l1_code"]; route = "iptc"; dec = o.get("decision"); w = DW.get(dec, 1.0); conds = self.by_code.get(code, []); b = ((o.get("rerank") or {}).get("node") or (o.get("best") or {}).get("qcode") or code).split(":")[1]; l2 = self.sp["l2_of"].get(b, b)
            feed = self.sp["names"].get(l2) or self.name(code); self.l2n[l2] += 1
            if not conds: self.unlinked[self.name(code)] += 1
        elif af and (((l.get("decider") or {}).get("topic") or {}).get("outcome") or "").startswith("ANSWER") and (af["out"].get("topic") or []):
            t = af["out"]["topic"][0][0]; route = "area"; bt = self.sp["by_topic"].get(t); conds = (bt or {}).get("conditions", []); feed = (bt or {}).get("name") or t
            if not conds: self.unlinked[feed] += 1
        self.routes[route] += 1
        Rt = sorted({self.cres[c] for c in conds}); ev = {}
        for r in Rt: ev.setdefault(r, [0.0, 0.0, 0.0, set()]); ev[r][0] += TALK * fw * w / len(Rt); ev[r][3].add(feed)
        cs = stage(l, "condition"); co = (cs or {}).get("out") or {}
        if dec != "ABSTAIN" and cs and cs.get("state") == "ran" and co.get("present") is True and co.get("direction") in ("up", "down") and co.get("which"):
            self.dirs += 1; sg = 1 if co["direction"] == "up" else -1; mg = SIGN * w * (BIG if co.get("size") in BIG_SIZES else 1.0)
            for c in co["which"]:
                if c in self.cres and self.cres[c] in self.res:
                    r = self.cres[c]; ev.setdefault(r, [0.0, 0.0, 0.0, set()]); ev[r][1 if sg > 0 else 2] += mg; ev[r][3].add("condition: " + c.replace("_", " "))
        self.last = ev; self.last_meta = {"route": route, "decision": dec, "feed": feed, "l2": (l2 if route == "iptc" else None), "unlinked": not conds and route != "none"}
        out = []
        for r in sorted(ev):
            s = self.res[r]; talk, p, n, fd = ev[r]; self.dec(r, T); s["att"] += talk + p + n; s["pos"] += p; s["neg"] += n; s["pn"] += p > 0; s["nn"] += n > 0; s["n"] += 1; s["last"] = T; s["seq"] = l.get("seq"); s["pubs"].add(l.get("source") or "")
            for x in fd: s["feed"][x] += 1
            out.append((r, talk, p + n))
        return out
    def state(self, r, T):
        s = self.res[r]
        if s["n"] == 0: return "untouched", 0.0, 0.0
        self.dec(r, T); idle = T - s["last"]; h = self.hl[r]; v = s["att"]; sg = s["pos"] + s["neg"]; net = s["pos"] - s["neg"]
        if v < FLOOR: return "untouched", v, net
        if idle > WARM_AT * h: return "warming", v, net
        if idle > DECAY_AT * h: return "decaying", v, net
        if sg > v - sg and sg > 0:
            if s["pos"] > 0 and s["neg"] > 0 and max(s["pos"], s["neg"]) / sg <= CONF: return "conflicted", v, net
            return ("moving up" if net > 0 else "moving down"), v, net
        return ("talked about" if s["n"] >= MIN_N else "warming"), v, net
    def rows(self):
        T = self.tick; rm = {r["id"]: r for r in self.sp["resources"]}; out = []
        for r in self.res:
            s = self.res[r]; stt, v, net = self.state(r, T); lk = [c for c, x in self.cres.items() if x == r]
            out.append({"resource": r, "name": rm[r]["name"], "group": rm[r]["group"], "state": stt, "value": round(v, 6), "net": round(net, 6), "items": s["n"], "publishers": len(s["pubs"]), "up_n": s["pn"], "down_n": s["nn"], "up_means": self.up[lk[0]] if lk else None, "half_life_ticks": self.hl[r],
                        "feeds": s["feed"].most_common(3), "last_seq": s["seq"], "status": "guess"})
        return sorted(out, key=lambda x: (-x["value"], x["resource"]))
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Resource state v1 (plan step 3, add-only; nothing above this block changes an output). State = (resource, country, day): country is place_linker's country (iso2), WORLD when the article has none; tick -> the article's published calendar day.
# Pulse(a,t) = (V, dV, N, C, U) per playbook 00 section 10, one per state: V independent observation volume (independent items that day: copies and republished items add nothing), dV V minus the mean V of the trailing days (TRAIL_DAYS calendar days before, only days from the first day of the stream),
# N novelty = share of the day's items whose topic feed was not seen for that state in the trailing days, C conflict = 2 x min(up, down) / (up + down) over the day's signed steps (0 when none), U unresolved uncertainty = share of the day's items the topic landing abstained on or did not answer.
# Coverage (items, publishers) and freshness (days since the state's last evidence, as of the stream's last day) are reported apart from them. Every state row carries its evidence list: seq, article id, span (the country mention in the text, or null = whole article), publisher, running count of independent publishers.
# The resource list is the engine seed resources.csv (26 rows, all 'guess'): PROVISIONAL until the owner picks a seed list. The IPTC -> condition map is not touched. Durable: ticks are appended to a JSONL log (one line per traced item, with as_of) and ResourceState.load() rebuilds the ledger from it; an id already in the log is never counted twice.
TRAIL_DAYS = 7; SEED_CSV = "/workspace/probes/persona/rules_v2/resources.csv"; STATE_VERSION = "resource-state-v1"
def seed_info():
    import csv
    rows = list(csv.DictReader(open(SEED_CSV, encoding="utf-8")))
    return {"file": SEED_CSV, "sha256": hashlib.sha256(open(SEED_CSV, "rb").read()).hexdigest(), "rows": len(rows), "status": sorted({r["status"] for r in rows}), "provisional": True, "ids": [r["id"] for r in rows]}
def country_of(l):
    o = ((stage(l, "place_linker") or {}).get("out") or {}); c = o.get("country")
    if c and c.get("iso2"): return c["iso2"], (c.get("spans") or [None])[0]
    if o.get("top_countries"): return o["top_countries"][0][0], None   # traces made before the country field: the linker's top country
    return "WORLD", None
class ResourceState:
    def __init__(self, spec, route="auto", log=None, run_id=None, label_version=None):
        self.L = Ledger(spec, route); self.spec = spec; self.log = log; self.run_id = run_id; self.lv = label_version; self.ids = set(); self.ticks = []; self.cells = {}   # cells: (resource, country, day) -> accumulators
        if log and os.path.exists(log): self.load()
    def _apply(self, t):
        """one logged tick (a dict as written by add) into the cells; shared by add() and load() so both build the same state"""
        if t["ind"]:
            for r, talk, p, n, fd in t["events"]:
                c = self.cells.setdefault((r, t["country"], t["day"]), {"items": 0, "mass": 0.0, "up": 0, "down": 0, "pos": 0.0, "neg": 0.0, "pubs": [], "feeds": collections.Counter(), "abst": 0, "ev": []})
                c["items"] += 1; c["mass"] += talk + p + n; c["up"] += p > 0; c["down"] += n > 0; c["pos"] += p; c["neg"] += n; c["abst"] += t["route"] == "iptc" and t["decision"] != "ANSWER_L1"   # area route is only taken when the decider answered
                for f in fd: c["feeds"][f] += 1
                if t["source"] not in c["pubs"]: c["pubs"].append(t["source"])
                c["ev"].append({"seq": t["seq"], "id": t["id"], "span": t["span"], "publisher": t["source"], "independent_n": len(c["pubs"])})
    def add(self, l):
        """one traced line -> the ledger (as before) and the state cells; returns False when the id was already counted (idempotent replay)"""
        if l.get("state") != "traced" or l["id"] in self.ids: return False
        self.ids.add(l["id"]); d0 = self.L.dirs; ev = self.L.add(l); ind = ev is not None; m = getattr(self.L, "last_meta", None) or {}; country, span = country_of(l)
        day = (l.get("published") or "")[:10] or "undated"
        t = {"id": l["id"], "seq": l.get("seq"), "source": l.get("source") or "", "day": day, "country": country, "span": span, "kind": self.L.last_kind, "ind": ind, "route": m.get("route") if ind else None, "decision": m.get("decision") if ind else None,
             "feed": m.get("feed") if ind else None, "l2": m.get("l2") if ind else None, "unlinked": bool(m.get("unlinked")) if ind else False, "tick": self.L.tick, "dir": self.L.dirs > d0,
             "events": [[r, self.L.last[r][0], self.L.last[r][1], self.L.last[r][2], sorted(x for x in self.L.last[r][3] if x)] for r in sorted(self.L.last)] if ind and self.L.last else []}
        self.ticks.append(t); self._apply(t)
        if self.log:
            os.makedirs(os.path.dirname(os.path.abspath(self.log)), exist_ok=True)
            with open(self.log, "a", encoding="utf-8") as f: f.write(json.dumps({**t, "as_of": {"run_id": self.run_id, "seq": t["seq"], "tick": t["tick"], "label_version": self.lv}}, sort_keys=True, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())
        return True
    def load(self):
        """rebuild the ledger and cells from the log: the Ledger's own counters are re-derived by feeding the logged events through the same update the live path uses"""
        L = self.L
        for ln in open(self.log, encoding="utf-8"):
            if not ln.strip(): continue
            t = json.loads(ln)
            if t["id"] in self.ids: continue
            self.ids.add(t["id"]); L.items += 1; L.kinds[t["kind"]] += 1; self.ticks.append(t)
            if t["ind"]:
                L.tick += 1; T = L.tick; L.seq = t["seq"]; L.indep += 1; L.routes[t["route"]] += 1
                if t["unlinked"]: L.unlinked[t["feed"]] += 1
                if t["l2"]: L.l2n[t["l2"]] += 1
                for r, talk, p, n, fd in t["events"]:
                    s = L.res[r]; L.dec(r, T); s["att"] += talk + p + n; s["pos"] += p; s["neg"] += n; s["pn"] += p > 0; s["nn"] += n > 0; s["n"] += 1; s["last"] = T; s["seq"] = t["seq"]; s["pubs"].add(t["source"])
                    for x in fd: s["feed"][x] += 1
                if t["dir"] and t["decision"] != "ABSTAIN": L.dirs += 1
            else: pass
            self._apply(t)
    @staticmethod
    def _day_add(d, n): return (__import__("datetime").date.fromisoformat(d) + __import__("datetime").timedelta(days=n)).isoformat()
    def states(self):
        days = sorted({k[2] for k in self.cells if k[2] != "undated"}); first = days[0] if days else None; last = days[-1] if days else None
        tot = collections.defaultdict(float)
        for (r, c, d), x in self.cells.items(): tot[(c, d)] += x["mass"]
        out = []
        for (r, c, d), x in sorted(self.cells.items()):
            base = bd = nov = None
            if d != "undated":
                prev = [self._day_add(d, -k) for k in range(TRAIL_DAYS, 0, -1)]; prev = [p for p in prev if first <= p < d]; bd = len(prev)
                if prev: base = sum((self.cells.get((r, c, p)) or {"items": 0})["items"] for p in prev) / len(prev)
                seen = set(); [seen.update((self.cells.get((r, c, p)) or {"feeds": {}})["feeds"]) for p in prev]
                tf = sum(x["feeds"].values()); nov = round(sum(v for f, v in x["feeds"].items() if f not in seen) / tf, 4) if tf else None
            sg = x["pos"] + x["neg"]
            out.append({"resource": r, "country": c, "day": d, "V": x["items"], "baseline_V": None if base is None else round(base, 4), "baseline_days": bd, "dV": None if base is None else round(x["items"] - base, 4), "N": nov,
                        "C": round(2 * min(x["pos"], x["neg"]) / sg, 4) if sg else 0.0, "U": round(x["abst"] / x["items"], 4), "items": x["items"], "publishers": len(x["pubs"]), "up_n": x["up"], "down_n": x["down"], "mass": round(x["mass"], 6),
                        "share": round(x["mass"] / tot[(c, d)], 6) if tot[(c, d)] else 0.0, "freshness_days": None if d == "undated" or not last else (__import__("datetime").date.fromisoformat(last) - __import__("datetime").date.fromisoformat(d)).days, "evidence": x["ev"], "status": "PROVISIONAL (seed resources.csv, guess)"})
        return out
    def day_shares(self):
        by = collections.defaultdict(lambda: collections.defaultdict(dict))
        for st in self.states(): by[st["day"]][st["country"]][st["resource"]] = st["share"]
        return {d: {c: dict(sorted(v.items())) for c, v in sorted(cs.items())} for d, cs in sorted(by.items())}
    def result(self):
        st = self.states(); body = {"version": STATE_VERSION, "seed": seed_info(), "trail_days": TRAIL_DAYS, "key": "(resource, country iso2 or WORLD, day)", "items": self.L.items, "independent": self.L.indep, "kinds": dict(self.L.kinds), "states": st, "day_shares": self.day_shares(),
                                    "counts": {"states": len(st), "with_evidence": sum(1 for x in st if x["evidence"]), "days": len({x["day"] for x in st}), "countries": len({x["country"] for x in st}), "resources": len({x["resource"] for x in st}), "evidence_pointers": sum(len(x["evidence"]) for x in st)},
                                    "pulse_fields": "V, dV, N, C, U (playbook 00 section 10); coverage = items, publishers; freshness = freshness_days", "as_of": {"run_id": self.run_id, "tick": self.L.tick, "label_version": self.lv}}
        body["sha256"] = hashlib.sha256(json.dumps({k: v for k, v in body.items() if k != "sha256"}, sort_keys=True).encode()).hexdigest(); return body
# --- end resource state v1 ---
def spearman(a, b):
    def rk(x):
        o = np.argsort(x, kind="stable"); r = np.empty(len(x)); r[o] = np.arange(len(x)); x = np.asarray(x)
        for v in np.unique(x): m = x == v; r[m] = r[m].mean()
        return r
    ra, rb = rk(a), rk(b)
    if ra.std() == 0 or rb.std() == 0: return float("nan")
    return float(np.corrcoef(ra, rb)[0, 1])
def m4_checks(d):
    """the pre-registered ranges of PREDICTION M4 (docstring) against the measured split-half; every check says PASS or FAIL, nothing is rounded into a pass"""
    iptc = "iptc" in d["route"]; lo, hi = (0.6, 0.85) if iptc else (0.5, 0.7); c = []
    ck = lambda k, pred, got, ok: c.append({"check": k, "predicted": pred, "measured": got, "result": "PASS" if ok else "FAIL"})
    ck("whole-stream rank agreement between publisher halves", "%.2f to %.2f" % (lo, hi), d["whole_stream"], lo <= d["whole_stream"] <= hi)
    ck("per-window median rank agreement", "under 0.5", d["per_window_median"], d["per_window_median"] < 0.5)
    ck("label-shuffle baseline, 95th percentile", "under 0.35", d["whole_label_shuffle_mean_p95"][1], d["whole_label_shuffle_mean_p95"][1] < 0.35)
    ck("change between windows, median", "under 0.3 and not above the random split's 95th percentile (%s)" % d["change_random_split_mean_p95"][1], d["change_median"], d["change_median"] < 0.3 and d["change_median"] <= d["change_random_split_mean_p95"][1])
    ck("direction events, share of items", "2 to 4 percent", round(100 * d["direction_share"], 2), 0.02 <= d["direction_share"] <= 0.04)
    return c
def split_half(lines, spec, route, W=12, S=500, seed=7):
    L = Ledger(spec, route); ev = []   # (window order index, source, resource, mass)
    for l in lines:
        o = L.add(l)
        if o is not None:
            for r, tk, sg in o: ev.append((L.tick, l.get("source") or "", r, tk + sg))
    N = L.tick; R = sorted(L.res); ri = {r: i for i, r in enumerate(R)}; pubs = sorted({e[1] for e in ev}); pi = {p: i for i, p in enumerate(pubs)}
    M = np.zeros((len(pubs), W, len(R)))
    for t, p, r, m in ev: M[pi[p], min(W - 1, (t - 1) * W // N), ri[r]] += m
    par = np.array([int(hashlib.sha1(p.encode()).hexdigest(), 16) % 2 for p in pubs]); rng = np.random.default_rng(seed)
    def stats(h):
        A = M[h == 0].sum(0); B = M[h == 1].sum(0); whole = spearman(A.sum(0), B.sum(0)); win = [spearman(A[w], B[w]) for w in range(W)]
        sa = A / np.maximum(A.sum(1, keepdims=True), 1e-12); sb = B / np.maximum(B.sum(1, keepdims=True), 1e-12)
        mix = [spearman(sa[w] - sa.mean(0), sb[w] - sb.mean(0)) for w in range(W)]; chg = [spearman(sa[w] - sa[w - 1], sb[w] - sb[w - 1]) for w in range(1, W)]
        return whole, win, mix, chg
    whole, win, mix, chg = stats(par); med = lambda x: float(np.nanmedian(x)); sh = []
    for _ in range(S):
        h = rng.permutation(par); w, wi, mx, cg = stats(h); sh.append((w, med(wi), med(mx), med(cg)))
    sh = np.array(sh); q = lambda i: [round(float(np.nanmean(sh[:, i])), 3), round(float(np.nanpercentile(sh[:, i], 95)), 3)]
    A = M[par == 0].sum(0); B = M[par == 1].sum(0); ls = []   # null of L2709: one half's resource labels shuffled (no relationship at all), the other null above is a random publisher split (how much the split itself moves the number)
    for _ in range(S): pm = rng.permutation(len(R)); ls.append((spearman(A.sum(0), B.sum(0)[pm]), med([spearman(A[w], B[w][pm]) for w in range(W)])))
    ls = np.array(ls); ql = lambda i: [round(float(np.nanmean(ls[:, i])), 3), round(float(np.nanpercentile(ls[:, i], 95)), 3)]
    d = {"route": dict(L.routes), "windows": W, "items": N, "publishers": len(pubs), "half_sizes": [int((par == 0).sum()), int((par == 1).sum())], "resources": len(R), "direction_items": L.dirs, "direction_share": round(L.dirs / max(1, N), 4),
            "whole_stream": round(whole, 3), "whole_label_shuffle_mean_p95": ql(0), "whole_random_publisher_split_mean_p95": q(0), "per_window": [round(x, 3) for x in win], "per_window_median": round(med(win), 3), "per_window_label_shuffle_median_mean_p95": ql(1), "per_window_random_split_median_mean_p95": q(1),
            "mix_removed_median": round(med(mix), 3), "mix_removed_random_split_mean_p95": q(2), "change_median": round(med(chg), 3), "change_random_split_mean_p95": q(3), "shuffles": S,
            "note": "raw (undecayed) mass per resource; halves = publishers split by sha1 parity; agreement between halves shows consistency, not truth"}
    d["m4_checks"] = m4_checks(d); d["m4_failed"] = sum(x["result"] == "FAIL" for x in d["m4_checks"]); return d
def synth_cases():
    """synthetic streams for the rules the v2 trace never reaches (no resource there is decaying or conflicted; only 'major' among the large sizes). Each case: fresh ledger, lines, and the state / value expected for a resource at the end. Shared with test_ledger_page.cjs T5 (--dump-synth)."""
    n = [0]
    def ln(cond=None, d="up", size="minor"):
        n[0] += 1; l = {"state": "traced", "seq": n[0], "title": "synthetic story number %d about nothing real" % n[0], "source": "p%d" % (n[0] % 3), "stages": []}
        if cond: l["stages"].append({"name": "condition", "state": "ran", "out": {"present": True, "direction": d, "which": [cond], "size": size}})
        return l
    C = []
    for idle, want in [(19, "moving up"), (20, "moving up"), (21, "decaying"), (40, "decaying"), (41, "warming"), (86, "warming"), (87, "untouched")]:   # attention: half-life 20, one +1.0 step, then idle filler ticks; 0.5^(86/20) = 0.0508, 0.5^(87/20) = 0.0492
        C.append({"name": "attention, %d idle ticks after one stated rise" % idle, "lines": [ln("news_overload")] + [ln() for _ in range(idle)], "resource": "attention", "state": want})
    C.append({"name": "water, one rise and one fall (neither above two thirds)", "lines": [ln("water_stress", "up"), ln("water_stress", "down")], "resource": "water", "state": "conflicted"})
    C.append({"name": "water, three rises and one fall (0.75 of the signed step is up)", "lines": [ln("water_stress", "up") for _ in range(3)] + [ln("water_stress", "down")], "resource": "water", "state": "moving up"})
    C.append({"name": "water, one fall", "lines": [ln("water_stress", "down")], "resource": "water", "state": "moving down"})
    for sz, v in [("minor", 1.0), ("notable", 1.0), (None, 1.0), ("major", 2.0), ("severe", 2.0), ("extreme", 2.0)]:
        C.append({"name": "size %s: one stated rise adds %.1f" % (sz, v), "lines": [ln("water_stress", "up", sz)], "resource": "water", "value": v})
    return C
def run_synth(spec):
    out = []
    for c in synth_cases():
        L = Ledger(spec); [L.add(l) for l in c["lines"]]; r = next(x for x in L.rows() if x["resource"] == c["resource"])
        out.append((c["name"], c.get("state", c.get("value")), r["state"] if "state" in c else r["value"]))
    return out
def selftest(a):
    if "--dump-synth" in a: json.dump(synth_cases(), open(a[a.index("--dump-synth") + 1], "w")); print("wrote", a[a.index("--dump-synth") + 1])
    res = run_synth(json.load(open(SPEC))); bad = 0
    for k, want, got in res:
        ok = want == got or (isinstance(want, float) and abs(want - got) < 1e-9); bad += not ok; print("%s %s: want %s, got %s" % ("PASS" if ok else "FAIL", k, want, got))
    print("%s (%d)" % ("ALL PASS" if not bad else "%d FAILED" % bad, len(res))); sys.exit(1 if bad else 0)
def main():
    a = sys.argv[1:]
    if "--selftest" in a: selftest(a)
    folder = next(x for x in a if not x.startswith("--")); opt = lambda k, d: a[a.index(k) + 1] if k in a else d
    route = opt("--route", "auto"); W = int(opt("--windows", 12)); S = int(opt("--shuffles", 500)); spec = json.load(open(SPEC)); run = json.load(open(folder + "/run.json")); lines = read_chain(folder)
    if "--state" in a:   # resource state v1 (see ResourceState): --state <json out> [--persist <ticks.jsonl>] [--state-only]
        lv0 = {"iptc_release": spec["label_version"]["iptc_release"], "table": spec["label_version"]["table"], "spec": spec["version"], "cards": (run.get("label_version") or {}).get("cards")}
        RS = ResourceState(spec, route, log=opt("--persist", None), run_id=run.get("run_id"), label_version=lv0); new = sum(RS.add(l) for l in lines); res = RS.result(); json.dump(res, open(opt("--state", None), "w"), indent=1, sort_keys=True)
        print("resource state v1 (PROVISIONAL seed): %d lines, %d new this run, %s, sha256 %s, wrote %s" % (len(lines), new, res["counts"], res["sha256"], opt("--state", None)))
        if "--state-only" in a: return
    t0 = time.time(); L = Ledger(spec, route); [L.add(l) for l in lines]; rows = L.rows(); sp = split_half(lines, spec, route, W, S)
    lv = {"iptc_release": spec["label_version"]["iptc_release"], "table": spec["label_version"]["table"], "spec": spec["version"], "cards": (run.get("label_version") or {}).get("cards")}
    stale = bool((run.get("label_version") or {}).get("iptc_release")) and run["label_version"]["iptc_release"] != lv["iptc_release"]
    as_of = {"run_id": run.get("run_id"), "seq": L.seq, "tick": L.tick, "label_version": lv}
    for r in rows: r["as_of"] = as_of; r["label_version"] = lv; r["stale"] = stale
    out = {"version": "ledger-v0", "as_of": as_of, "built_at": time.strftime("%Y-%m-%d %H:%M:%S"), "route": route, "items": L.items, "independent": L.indep, "kinds": dict(L.kinds), "routes": dict(L.routes), "direction_items": L.dirs, "rows": rows,
           "not_linked": [[k, v] for k, v in L.unlinked.most_common()], "split_half": sp, "constants": {"decision_weight": DW, "talk": TALK, "function_weight": FW, "signed": SIGN, "major_multiplier": BIG, "min_items": MIN_N, "floor": FLOOR, "conflict": CONF, "big_sizes": list(BIG_SIZES), "decay_after_half_lives": DECAY_AT, "warm_after_half_lives": WARM_AT}, "readings": READINGS}
    print("%s: %d lines, %d independent (%s), routes %s, direction items %d, %.1fs" % (folder, L.items, L.indep, dict(L.kinds), dict(L.routes), L.dirs, time.time() - t0))
    for r in rows[:26]: print("  %-22s %-13s value %7.3f net %+7.3f items %4d pubs %2d up/down %d/%d" % (r["resource"], r["state"], r["value"], r["net"], r["items"], r["publishers"], r["up_n"], r["down_n"]))
    print("states:", dict(collections.Counter(r["state"] for r in rows))); print("M4 split-half:", json.dumps(sp))
    for x in sp["m4_checks"]: print("  M4 %s: %s, predicted %s, measured %s" % (x["result"], x["check"], x["predicted"], x["measured"]))
    if "--write" in a: json.dump(out, open(folder + "/ledger.json", "w"), indent=1); print("wrote", folder + "/ledger.json")
    if "--json" in a: json.dump(out, open(opt("--json", None), "w"), indent=1); print("wrote", opt("--json", None))   # anywhere else (never into trace-demo/)
if __name__ == "__main__": main()
