"""event_diag: why the resource-state event-peak test hits 25/122 (L2885). Classification rule and fixes pre-registered in ledger L2890 (item EVENTS). Read-only on resource_truth.py (imports it); CPU, no network.
    python3 event_diag.py [--ticks <ticks.jsonl>] [--json <out>]   (ticks.jsonl = ledger_split.py --persist output on the v7 trace; built to a temp file when absent)"""
import sys, os, re, json, collections, statistics, subprocess, tempfile
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import resource_truth as RT
def opt(f): return sys.argv[sys.argv.index(f) + 1] if f in sys.argv else None
def load(ticks):
    titles = {}
    for ln in open(RT.TRACE + "/chain.jsonl"):
        x = json.loads(json.loads(ln)["line"]); titles[x["id"]] = x.get("title") or ""
    T = [json.loads(l) for l in open(ticks)]
    for t in T: t["title"] = titles.get(t["id"], "")
    return T
def spec_words():
    sp = json.load(open(RT.SPEC)); W = collections.defaultdict(set); stop = {"rate", "level", "cost", "stress", "flow", "growth", "output", "condition", "quality", "risk", "strain", "security", "values", "insecurity", "loss", "reliability", "adoption", "division"}
    for r in sp["rows"]:
        for w in re.findall(r"[a-z]{4,}", (r["condition"].replace("_", " ") + " " + r["resource"].replace("_", " ")).lower()):
            if w not in stop: W[r["resource"]].add(w)
    return {k: re.compile(r"\b(" + "|".join(sorted(v)) + ")", re.I) for k, v in W.items() if v}
def mean(a): return sum(a) / len(a) if a else 0.0
def shares(snap, ok, extra=None):
    """resource -> day -> share of day mass over ok days; extra = {(r,d): added mass} (fix F-B)"""
    tot = collections.Counter(); m = collections.defaultdict(dict)
    for r, x in snap["resource_day"].items():
        for d in ok: v = (x[d]["mass"] if d in x else 0.0) + (extra or {}).get((r, d), 0.0); m[r][d] = v; tot[d] += v
    for (r, d), v in (extra or {}).items():
        if r not in m and d in ok: m[r] = {dd: 0.0 for dd in ok}; m[r][d] = v; tot[d] += v
    return {r: {d: (v / tot[d] if tot[d] else 0.0) for d, v in x.items()} for r, x in m.items()}
def peak_share(shr, ok, r): return max(ok, key=lambda x: (shr[r][x], x))
def peak_dshare(shr, ok, r):
    best = None
    for d in ok:
        prev = [p for p in ok if RT.day_add(d, -7) <= p < d]
        if not prev: continue
        v = shr[r][d] - mean([shr[r][p] for p in prev])
        if best is None or (v, d) > best: best = (v, d)
    return best[1] if best else None
def classify(u, T, snap, ok, shr, rxk):
    d, r = u["date"], u["resource"]; W = {RT.day_add(d, k) for k in (-1, 0, 1)}; rx = RT.RX[r]
    m = [t for t in T if t["day"] in W and rx.search(t["title"])]; K = len(m); routed = sum(1 for t in m if any(e[0] == r for e in t["events"]))
    med = statistics.median([shr[r][x] for x in ok]); rise = max([shr[r][x] for x in ok if x in W] or [0.0])
    row = {"K": K, "routed": routed, "share_W_max": round(rise, 4), "median_share": round(med, 4)}
    if K < 5: c = "1 coverage"
    elif routed / K < 0.5: c = "2 mapping"
    elif med > 0 and rise >= 1.25 * med: c = "3 peak-definition"
    else: c = "4 minor-or-false-positive"
    return c, row
def hits(units, f): return sum(1 for u in units if f(u))
def main():
    snap = json.load(open(RT.SNAP)); ev = RT.load_events(); sc = RT.score_events(snap, ev); ok = sc["checkable_days"]
    tk = opt("--ticks")
    if not tk:
        d = tempfile.mkdtemp(prefix="event-diag-"); subprocess.run([RT.PYNP, H + "/ledger_split.py", RT.TRACE, "--state", d + "/s.json", "--persist", d + "/t.jsonl", "--state-only"], check=True, capture_output=True); tk = d + "/t.jsonl"
    T = load(tk); shr = shares(snap, ok); C = [u for u in sc["units"] if u["checkable"]]; miss = [u for u in C if not u["hit"]]; out = {"checkable": len(C), "hits": len(C) - len(miss), "misses": len(miss)}
    cause = collections.Counter(); rows = []
    for u in miss:
        c, r = classify(u, T, snap, ok, shr, None); cause[c] += 1; rows.append({**{k: u[k] for k in ("date", "resource", "n_events", "example", "peak_share_day")}, "cause": c, **r})
    out["cause_counts"] = dict(sorted(cause.items())); out["miss_rows"] = rows
    by_res = collections.defaultdict(collections.Counter)
    for r in rows: by_res[r["resource"]][r["cause"]] += 1
    out["cause_by_resource"] = {k: dict(v) for k, v in sorted(by_res.items())}
    # peak-day concentration: how many resources peak on each day
    out["peak_day_of_resource"] = dict(collections.Counter(peak_share(shr, ok, r) for r in shr)); out["ok_days"] = ok
    # fixes
    sel_days = set(ok[0::2]); held_days = set(ok[1::2]); sel = [u for u in C if u["date"] in sel_days]; held = [u for u in C if u["date"] in held_days]; out["split"] = {"select_days": sorted(sel_days), "heldout_days": sorted(held_days), "select_units": len(sel), "heldout_units": len(held)}
    SW = spec_words(); extra = collections.Counter()
    for t in T:
        for r, rx in SW.items():
            if t["day"] in set(ok) and rx.search(t["title"]): extra[(r, t["day"])] += 1
    # F-B mass unit: the mean per-article mass of the snapshot so +1 title is comparable (one title = one average article tick)
    tm = sum(x[d]["mass"] for x in snap["resource_day"].values() for d in x); ti = sum(x[d]["items"] for x in snap["resource_day"].values() for d in x); unit = tm / ti if ti else 1.0
    shrB = shares(snap, ok, {k: v * unit for k, v in extra.items()})
    def chance(units, pk): return round(mean([sum(1 for x in ok if RT.days_apart(x, pk(u["resource"])) <= 1) / len(ok) for u in units]), 4) if units else None
    rules = {"old": lambda r: peak_share(shr, ok, r), "F-A dShare peak": lambda r: peak_dshare(shr, ok, r) or peak_share(shr, ok, r), "F-B title-evidence route": lambda r: peak_share(shrB, ok, r) if r in shrB else peak_share(shr, ok, r)}
    res = {}
    for n, pk in rules.items():
        res[n] = {}
        for nm, us in (("all", C), ("select", sel), ("heldout", held)):
            h = hits(us, lambda u: RT.days_apart(pk(u["resource"]), u["date"]) <= 1); res[n][nm] = {"hits": h, "n": len(us), "rate": round(h / len(us), 4) if us else None, "chance": chance(us, pk)}
    out["share_spread"] = {r: {"min": round(min(x.values()), 4), "max": round(max(x.values()), 4), "median": round(statistics.median(x.values()), 4), "max_over_median": round(max(x.values()) / statistics.median(x.values()), 2) if statistics.median(x.values()) else None} for r, x in sorted(shr.items())}
    mm = [v["max_over_median"] for v in out["share_spread"].values() if v["max_over_median"]]; out["share_spread_summary"] = {"resources": len(mm), "median_of_max_over_median": round(statistics.median(mm), 2), "resources_max_under_1.5x_median": sum(1 for x in mm if x < 1.5)}
    out["rules"] = res; out["F-B"] = {"unit_mass": round(unit, 5), "title_hits": sum(extra.values()), "resources_with_words": sorted(SW)}
    out["peak_day_of_resource_dshare"] = dict(collections.Counter(peak_dshare(shr, ok, r) for r in shr))
    p = opt("--json") or RT.TRUTH + "/event-diag-v7.json"; json.dump(out, open(p, "w"), indent=1, ensure_ascii=False)
    print("checkable", out["checkable"], "hits", out["hits"]); print("causes", out["cause_counts"]); print("peak day per resource (share)", out["peak_day_of_resource"]); print("split", out["split"]); print("share spread", out["share_spread_summary"])
    for n, v in res.items(): print(n, {k: "%d/%d=%s ch%s" % (x["hits"], x["n"], x["rate"], x["chance"]) for k, x in v.items()})
    print("wrote", p)
if __name__ == "__main__": main()
