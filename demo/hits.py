"""Hit counter for the World engine: does the live reader spread its answers the way the reference does, or fixate on a few?
GET /api/world-engine/hits?n=200[&reader=<id>] (wired in server.py).

How it collects (no engine change, no extra polling): every /api/world-engine/live response the console proxies to a page is passed to ingest_bytes().
Items are kept per reader id in a ring and deduplicated by seq. A GET /live keeps the engine's feed awake, so this module never polls /live by itself
(only when /hits is asked and nothing has been seen for 20 s). It does read /world and /graph (these do not keep the feed awake) to follow the forecast chain.
Reference: data/bitmob-integration/hit_reference.json, made by tools/hit_reference.py.
Flag rules (also printed on the page):
  over-call : live share >= 2x reference share, >= 5 hits, and the Wilson 95% lower bound of the live share is above the reference share.
  under-call: the reference expects >= 5 hits in N, live share <= half the reference share, and the Wilson 95% upper bound is below the reference share."""
import csv, json, math, os, threading, time, urllib.request, collections

ROOT = "/workspace"
REF_PATH = f"{ROOT}/data/bitmob-integration/hit_reference.json"
STATE_PATH = f"{ROOT}/data/world-engine/hits_state.json"
DIALS_CSV = f"{ROOT}/probes/persona/rules_v2/dials.csv"
ENGINE = "http://127.0.0.1:8112"
RING, TICKS, HIST, FLAT, UNIT_COND, WEEK = 1000, 2000, 40, 0.5, 0.04, 7      # the last three mirror grForecast in worldengine2-how.html (history length, 'flat' band, condition scale, week horizon)
LOCK = threading.RLock()
ST = {"readers": {}, "last_seq": 0, "last_tick": -1, "ticks": [], "hist": {}, "current": None, "seen_at": 0.0, "world_at": 0.0, "saved_at": 0.0, "graph": None}
_ref = {"mtime": 0, "data": None}

def configure(engine_url):
    global ENGINE; ENGINE = engine_url; _load()
    def boot():      # once at start: take the engine's last 60 items (a page that is already open would only send newer ones)
        try:
            d = _get("/live?since=0", 15)
            ingest(d)
        except Exception: pass
    threading.Thread(target=boot, daemon=True).start()

def _get(path, timeout=20):
    with urllib.request.urlopen(ENGINE + path, timeout=timeout) as r: return json.loads(r.read())

def _load():
    try:
        d = json.load(open(STATE_PATH))
        with LOCK:
            ST["readers"] = {k: {"label": v.get("label"), "kind": v.get("kind"), "items": v["items"][-RING:]} for k, v in d["readers"].items()}
            for k in ("last_seq", "last_tick", "ticks", "hist", "current"): ST[k] = d.get(k, ST[k])
    except Exception: pass

def _save(force=False):
    if not force and time.time() - ST["saved_at"] < 30: return
    ST["saved_at"] = time.time()
    try:
        with LOCK: d = {k: ST[k] for k in ("readers", "last_seq", "last_tick", "ticks", "hist", "current")}
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        json.dump(d, open(STATE_PATH + ".tmp", "w")); os.replace(STATE_PATH + ".tmp", STATE_PATH)
    except Exception: pass

def reference():
    try:
        m = os.path.getmtime(REF_PATH)
        if m != _ref["mtime"]: _ref["data"] = json.load(open(REF_PATH)); _ref["mtime"] = m
    except Exception: _ref["data"] = None
    return _ref["data"]

def _dial_names():
    r = reference(); return (r or {}).get("dial_names") or {}

def _type_of(t):
    h, a, o, f = (t.get(k, 0) for k in ("happened", "announced", "opinion", "forecast"))      # same rule as the engine's type_weight
    return "fact" if (h >= .5 or a >= .5) and o < .5 and f < .5 else "forecast" if f >= .5 else "opinion" if o >= .5 else "unclear"

def _compact(it):
    fl = it.get("flow") or {}; an = fl.get("answers")
    if not an: return None
    dn = _dial_names(); nm = lambda x: f"{dn.get(x['dial'], x['dial'])} {x['direction']}"
    return {"seq": it["seq"], "tick": it.get("tick"), "by": it.get("by") or fl.get("reader_id") or "unknown", "label": fl.get("reader"), "kind": fl.get("kind"),
            "topic": an.get("topic") or [], "country": an.get("country") or "global", "cond": [nm(x) for x in an.get("conditions") or []],
            "expected": [nm(x) for x in fl.get("expected") or []], "gate_ok": bool(an.get("gate_ok", True)), "type": _type_of(an.get("type") or {}), "entry": (fl.get("engine") or {}).get("entry")}

def ingest(d):
    """d: a /live response. Safe to call with repeated or overlapping responses."""
    items = d.get("items") or []; new_tick = False
    with LOCK:
        if d.get("seq", 0) < ST["last_seq"]:      # the engine was reset: the world and its numbers start again
            ST.update(readers={}, last_seq=0, last_tick=-1, ticks=[], hist={})
        have = {x["seq"] for r in ST["readers"].values() for x in r["items"]}      # dedup by seq
        for it in sorted(items, key=lambda i: i["seq"]):
            if it["seq"] in have: continue
            have.add(it["seq"]); ST["last_seq"] = max(ST["last_seq"], it["seq"]); c = _compact(it)
            if not c: continue
            r = ST["readers"].setdefault(c["by"], {"label": c["label"], "kind": c["kind"], "items": []})
            r["label"] = c["label"] or r["label"]; r["kind"] = c["kind"] or r["kind"]; r["items"].append(c); r["items"].sort(key=lambda x: x["seq"])
            if len(r["items"]) > RING: del r["items"][:len(r["items"]) - RING]
        rd = d.get("reader") or {}; ST["current"] = rd.get("current") or rd.get("last_read_by") or ST["current"]
        ST["seen_at"] = time.time(); tk = d.get("tick"); new_tick = tk is not None and tk != ST["last_tick"] and time.time() - ST["world_at"] > 6
        if new_tick: ST["world_at"] = time.time()
    if new_tick: threading.Thread(target=_follow_forecast, args=(tk,), daemon=True).start()
    _save()

def ingest_bytes(raw):
    try: ingest(json.loads(raw))
    except Exception: pass

# ---------- the forecast chain: which resource is the top mover at each sampled tick (same arithmetic as grResHeat / grForecast on the How page) ----------
def _graph():
    if ST["graph"] is None:
        g = _get("/graph", 30); rl = g["resource_links"]["condition_resource"]; by = collections.defaultdict(list)
        for l in rl: by[l["b"]].append(l)
        hl = {r["id"]: float(r["half_life_ticks"]) for r in csv.DictReader(open(DIALS_CSV))}
        ST["graph"] = {"res": {r["id"]: r["name"] for r in g["meaning"]["resources"]}, "links": by, "half_life": hl}
    return ST["graph"]

def _follow_forecast(tk):
    try:
        G = _graph(); w = _get("/world", 30); W0 = next(r for r in w["rows"] if r["id"] == "WORLD:world"); di = {x["id"]: i for i, x in enumerate(w["dials"])}
        if w["tick"] < ST["last_tick"]: ST["hist"] = {}; ST["ticks"] = []
        ch = {c: math.tanh(W0["dials"][i] / UNIT_COND) for c, i in di.items()}
        pred = {}
        with LOCK:
            for rid, ls in G["links"].items():
                parts = [{"id": l["a"], "c": (-1 if l["up_means"] == "strain" else 1) * ch.get(l["a"], 0.0)} for l in ls]
                v = 100 * sum(p["c"] for p in parts) / len(parts); h = ST["hist"].setdefault(rid, [])
                if h and h[-1][0] == w["tick"]: h[-1][1] = v
                else: h.append([w["tick"], v])
                del h[:-HIST]
                if len(h) >= 3 and h[-1][0] - h[0][0] >= 3:
                    dp = max(-100 - v, min(100 - v, (h[-1][1] - h[0][1]) / (h[-1][0] - h[0][0]) * WEEK)); pred[rid] = (dp, parts)
            ranked = sorted(((abs(dp), rid, dp, parts) for rid, (dp, parts) in pred.items() if abs(dp) >= FLAT), reverse=True)
            ST["last_tick"] = w["tick"]
            if pred:
                top = ranked[0] if ranked else None
                ST["ticks"].append({"tick": w["tick"], "at": time.time(), "top": top[1] if top else None, "dp": round(top[2], 2) if top else 0, "parts": [{"id": p["id"], "c": round(p["c"], 3)} for p in top[3]] if top else [],
                                    "next": [r[1] for r in ranked[1:3]]})
                del ST["ticks"][:-TICKS]
    except Exception: pass
    _save()

# ---------- statistics ----------
def wilson(c, n, z=1.96):
    if n <= 0: return 0.0, 1.0
    p = c / n; d = 1 + z * z / n; m = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, m - h), min(1.0, m + h)

def flag(c, n, ref_c, ref_n):
    """'over', 'under' or None, by the rules in the module docstring. Share = hits / stories read."""
    if not n or not ref_n: return None
    p, q = c / n, ref_c / ref_n; lo, hi = wilson(c, n)
    if c >= 5 and p >= 2 * q and lo > q: return "over"
    if n * q >= 5 and p <= q / 2 and hi < q: return "under"
    return None

def _row(name, c, n, refs):
    row = {"name": name, "count": c, "share": round(c / n, 4) if n else 0.0}
    for key, (counts, rn) in refs.items():
        if counts is None or not rn: continue
        rc = counts.get(name, 0); row[key] = {"count": rc, "share": round(rc / rn, 4), "flag": flag(c, n, rc, rn)}
    return row

def _rows(counter, n, refs, ref_keys, show_all=False):
    names = list(counter)
    for rs in refs.values():
        if rs[0]:
            for k, v in rs[0].items():
                if (v >= 5 or show_all) and k not in counter: names.append(k)      # in the reference, never seen live: needed to find under-calls
    rows = [_row(k, counter.get(k, 0), n, refs) for k in dict.fromkeys(names)]
    rows.sort(key=lambda r: (-max(r["share"], r.get("labels", {}).get("share", 0)), r["name"]))
    return rows

def summarize(items, n_req):
    win = items[-n_req:]; n = len(win); ref = reference() or {}; sets = ref.get("sets") or {}
    J, C = sets.get("clef_test") or sets.get("jev_testA"), sets.get("clef_reads")   # the Clef labels of the frozen test replace the Jev one-tag set once built (newsreader/bitmob/hit_ref_clef.py)
    def refs(cat): return {k: ((s.get(cat) if s else None), (s["stories_with_topic"] if cat == "topic" else s["n"]) if s else 0) for k, s in (("labels", J), ("reads", C))}
    cnt = lambda f: collections.Counter(x for it in win for x in f(it))
    out = {"n": n, "seq_from": win[0]["seq"] if win else None, "seq_to": win[-1]["seq"] if win else None, "categories": {}}
    tp = collections.Counter(t for it in win for t in set(it["topic"]))      # every topic tag counts once per story (a story can sit in several domains)
    ntp = sum(1 for it in win if it["topic"]); tags = sum(len(set(it["topic"])) for it in win)
    out["categories"]["topic"] = {"title": "Topic (every tag per story)", "n": n, "rows": _rows(tp, n, refs("topic"), None)}
    out["topic_all"] = {"tags": tags, "stories": ntp, "counts": dict(cnt(lambda i: i["topic"]).most_common())}
    def ref_tps(s):      # mean topic tags per story in a reference set: only if it carries tag totals
        if not s or not s.get("topic") or not s.get("n"): return None
        return round(sum(s["topic"].values()) / s["n"], 3)
    out["topics_per_story"] = {"live": round(tags / n, 3) if n else None, "labels": ref_tps(J), "reads": ref_tps(C),
                               "note": "Mean topic tags per story. A reference shows a value only if it has tag totals; the Jev test labels hold one topic per story by construction, the Clef reads set holds no topic totals."}
    out["categories"]["country"] = {"title": "Entry place (country)", "n": n, "rows": _rows(cnt(lambda i: [i["country"]]), n, refs("country"), None)}
    out["categories"]["cond"] = {"title": "Condition readings (dial and direction)", "n": n, "rows": _rows(cnt(lambda i: i["cond"]), n, refs("cond"), None)}
    ex = cnt(lambda i: i["expected"]); out["categories"]["expected"] = {"title": "Expected-impact readings", "n": n, "no_reference": True, "stories_with": sum(1 for i in win if i["expected"]),
                                                                          "rows": _rows(ex, n, {}, None)}
    nr = sum(1 for i in win if not i["cond"]); gc = sum(1 for i in win if not i["gate_ok"])
    both = lambda key, c: {k: ({"count": s[key], "share": round(s[key] / s["n"], 4), "flag": flag(c, n, s[key], s["n"])} if s and s["n"] else None) for k, s in (("labels", J), ("reads", C))}
    out["categories"]["health"] = {"title": "Stories with no reading, gate closed", "n": n, "rows": [dict(name="No condition read", count=nr, share=round(nr / n, 4) if n else 0, **{k: v for k, v in both("no_reading", nr).items() if v}),
                                                                                                    dict(name="Gate closed", count=gc, share=round(gc / n, 4) if n else 0, **{k: v for k, v in both("gate_closed", gc).items() if v})]}
    out["categories"]["type"] = {"title": "Story type", "n": n, "rows": _rows(cnt(lambda i: [i["type"]]), n, refs("type"), None, True)}
    return out

def _forecast(n_req, live_items):
    G = ST["graph"]; ref = (reference() or {}).get("sets") or {}; J = ref.get("clef_test") or ref.get("jev_testA")
    with LOCK: tl = ST["ticks"][-n_req:]
    out = {"samples": len(tl), "asked": n_req, "tick_from": tl[0]["tick"] if tl else None, "tick_to": tl[-1]["tick"] if tl else None, "resources": [], "top": None,
           "how": "At each sampled tick the forecast chain's top mover (week outlook, same arithmetic as the Forecast view) is recorded. Samples are every tick or two, not every story."}
    if not tl or not G: return out
    cnt = collections.Counter(t["top"] for t in tl); N = len(tl)
    out["resources"] = [{"id": r, "name": G["res"].get(r, r) if r else "(none moving)", "count": c, "share": round(c / N, 3)} for r, c in cnt.most_common()]
    out["distinct_tops"] = len([r for r in cnt if r]); out["n_resources"] = len(G["res"])
    top = next((r for r, _ in cnt.most_common() if r), None)
    if not top: return out
    mine = [t for t in tl if t["top"] == top]; heat = collections.defaultdict(list)
    for t in mine:
        for p in t["parts"]: heat[p["id"]].append(p["c"])
    dn = _dial_names(); n_live = len(live_items); feeders = []
    for l in G["links"][top]:
        cid = l["a"]; reads = {}
        for dr in ("up", "down"):
            name = f"{dn.get(cid, cid)} {dr}"; c = sum(1 for i in live_items if name in i["cond"]); rc = (J or {}).get("cond", {}).get(name, 0); rn = (J or {}).get("n", 0)
            reads[dr] = {"name": name, "live_count": c, "live_share": round(c / n_live, 4) if n_live else 0, "ref_share": round(rc / rn, 4) if rn else None, "flag": flag(c, n_live, rc, rn)}
        feeders.append({"id": cid, "name": dn.get(cid, cid), "up_means": l["up_means"], "half_life_ticks": G["half_life"].get(cid), "mean_heat": round(sum(heat[cid]) / len(heat[cid]), 3) if heat[cid] else None, "reads": reads})
    nl = len(G["links"][top]); share = cnt[top] / N
    # rules check: if conditions were read at a steady rate, a condition's level settles near rate x half-life (decay is by half-life). So, per resource,
    # pull = |mean over its conditions of (+1 build / -1 strain) x (share read up - share read down) x half-life|. Ranked once with the reference's read rates and once with the live reader's.
    def pull(rate):
        res = {}
        for rid, ls in G["links"].items():
            v = [(-1 if l["up_means"] == "strain" else 1) * (rate(dn.get(l["a"], l["a"]), "up") - rate(dn.get(l["a"], l["a"]), "down")) * (G["half_life"].get(l["a"]) or 0) for l in ls]
            res[rid] = abs(sum(v) / len(v))
        order = sorted(res, key=lambda r: -res[r]); return [{"id": r, "name": G["res"][r], "pull": round(res[r], 2)} for r in order[:5]], order.index(top) + 1
    rr = (lambda nm, dr: ((J or {}).get("cond", {}).get(f"{nm} {dr}", 0) / (J or {}).get("n", 1))); lr = (lambda nm, dr: (sum(1 for i in live_items if f"{nm} {dr}" in i["cond"]) / max(1, n_live)))
    pr, rank_r = pull(rr); pl, rank_l = pull(lr)
    over = [f"{r['name']} (live {100 * r['live_share']:.1f}% vs reference {100 * r['ref_share']:.1f}%)" for f in feeders for r in f["reads"].values() if r["flag"] == "over"]
    under = [r["name"] for f in feeders for r in f["reads"].values() if r["flag"] == "under"]
    dom = max(feeders, key=lambda f: abs(f["mean_heat"] or 0))
    if share < 0.4: verdict = {"kind": "none", "text": f"No fixation: the most frequent top mover, {G['res'][top]}, leads {100 * share:.0f}% of {N} samples."}
    elif over: verdict = {"kind": "readings", "text": f"Fixation comes at least partly from the reader: it over-calls {'; '.join(over)}."}
    else:
        verdict = {"kind": "rules", "text": (f"{G['res'][top]} leads {100 * share:.0f}% of samples, but no reading that feeds it is over-called" + (f" (under-called: {', '.join(under)})" if under else "") + ". "
                                              f"It is led by {dom['name']} (mean heat {dom['mean_heat']}, half-life {dom['half_life_ticks']:.0f} ticks). Rules check: if the reader read at exactly the reference's rates, {G['res'][top]} would still rank #{rank_r} of {len(G['res'])} by pull (#{rank_l} at the live rates), "
                                              f"because a resource's heat is the plain average of its {nl} condition(s), each saturating as tanh(level / {UNIT_COND}), and slow conditions pile up.")}
    c2r = {l["a"]: r for r, ls in G["links"].items() for l in ls}; byid = {r["id"]: r["share"] for r in out["resources"]}; jc = (J or {}).get("cond", {}); jn = (J or {}).get("n", 1)
    inv = {v: k for k, v in dn.items()}
    out["over_called"] = []
    for nm in {i for it in live_items for i in it["cond"]}:
        c = sum(1 for it in live_items if nm in it["cond"]); fl = flag(c, n_live, jc.get(nm, 0), jn)
        if fl == "over" and inv.get(nm.rsplit(" ", 1)[0]) in c2r:
            rid = c2r[inv[nm.rsplit(" ", 1)[0]]]; out["over_called"].append({"reading": nm, "live_share": round(c / n_live, 4), "ref_share": round(jc.get(nm, 0) / jn, 4), "resource": G["res"][rid], "resource_top_share": byid.get(rid, 0.0)})
    out["over_called"].sort(key=lambda x: -x["live_share"])
    out["top"] = {"id": top, "name": G["res"][top], "count": cnt[top], "share": round(share, 3), "mean_dp": round(sum(t["dp"] for t in mine) / len(mine), 2), "n_conditions": nl, "feeders": feeders, "verdict": verdict, "pull_reference": pr, "pull_live": pl, "rank_under_reference": rank_r, "rank_under_live": rank_l,
                  "live_stories": n_live}
    return out

def _reader_name(rid, label):
    """What the page shows for a reader: the registry name (the engine's reader label), else the registry name of its id, else the id; never the engine's kind word 'llm'."""
    bad = lambda x: not x or str(x).strip().lower() in ("llm", "unknown")
    if not bad(label): return label
    try:
        import backends
        nm = backends.name(rid)
        if not bad(nm): return nm
    except Exception: pass
    return rid if not bad(rid) else "Clef"

def payload(query=""):
    from urllib.parse import parse_qs
    q = parse_qs(query); n = max(10, min(RING, int((q.get("n") or ["200"])[0] or 200))); want = (q.get("reader") or [None])[0]
    if time.time() - ST["seen_at"] > 20:      # nobody has fed us lately: ask the engine once (this also tells it someone is watching)
        try: ingest(_get(f"/live?since={ST['last_seq']}", 15))
        except Exception: pass
    if ST["graph"] is None:
        try: _graph()
        except Exception: pass
    with LOCK:
        readers = {k: {"label": v["label"], "kind": v["kind"], "items": list(v["items"][-n:])} for k, v in ST["readers"].items()}; cur = ST["current"]
    live = want if want in readers else cur if cur in readers else (max(readers, key=lambda k: readers[k]["items"][-1]["seq"]) if readers else None)
    ref = reference() or {}; sets = ref.get("sets") or {}
    out = {"n_asked": n, "live_reader": live, "engine_current": cur, "reference": {"made": ref.get("made"), "topic_note": (None if "clef_test" in sets else "reference is one tag per story (Jev); a story with several tags can look over-called until the Clef multi-tag reference is built"), "sets": {k: {"n": v["n"], "source": v["source"]} for k, v in sets.items()}},
           "rules": {"over": "Over-call: live share is at least 2 times the reference share, there are at least 5 hits, and the Wilson 95% lower bound of the live share is above the reference share.",
                     "under": "Under-call: the reference expects at least 5 hits in this many stories, the live share is at most half the reference share, and the Wilson 95% upper bound of the live share is below the reference share.",
                     "share": "Share = stories with the hit / stories read in the window  Type is the engine's own rule (fact, forecast, opinion, unclear). Topic counts every tag a story gets (the engine can place a story in several domains), so topic shares can add up to more than 100%; the Jev test labels hold one topic per story, so read topic flags with that in mind."},
           "readers": {}, "seen_at": ST["seen_at"], "last_seq": ST["last_seq"]}
    for k, v in readers.items():
        if not v["items"]: continue
        s = summarize(v["items"], n); s.update(label=_reader_name(k, v["label"]), kind=v["kind"]); out["readers"][k] = s
    out["forecast"] = _forecast(n, readers[live]["items"] if live else [])
    return out
