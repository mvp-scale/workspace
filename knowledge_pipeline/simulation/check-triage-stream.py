"""check-triage-stream: concept-delta design round R1 (playbook/design/concept-delta-design.md sections 1.6, 2, 4.1, 4.4, 6) on a REAL stream window. PROVISIONAL, observational: measures, does not edit the pipeline.
Reads one chain window (default runs-e2e-101: ~460 articles from the news queue through live_trace -> slow_clock -> slow_consolidate by kit/live/chain_windows.py) read only; the seeded control works on scratch copies.
  S1 timings    per stage wall seconds, articles per minute, against the design's measured table (2.1) and projection (2.3)
  S2 triage     concepts_v0.build (read only import) replays the window in seq order: first 2/3 = 'previous look', last 1/3 = 'since your last look'; verdict shares and compression = items in / items shown
  S3 seeded     50 synthetic changes (polarity, amount, status reversal, direction, new actor link; 10 each) injected into scratch copies of later articles' facts; control build (precursors only) must label them 'known', test build counts how many stay 'known' (hidden) and how many reach 'conflict'
  S4 sampled    40 random items labelled 'known': structural diff on the consolidated store (a slot / identity / link whose first appearance is this item = hidden change); rate with Wilson 95% CI (no human labels); the whole known population is reported too
  S5 identity   slow-clock identity ms per article as the store grows (bins 1-50, 51-150, 151-300, 301+), and a micro-benchmark of the g4_align 'similar v0' Python scan against one matmul at the store sizes of those bins
Pass bars (design 4.1, PROVISIONAL): hidden change rate <= 5%, missed contradictions = 0, seeded changes all leave 'known'. A row that misses its bar prints FAIL: that is a finding to route (the script exits 0 unless the window or a build is missing).
    /workspace/models/embed-zs/.venv/bin/python simulation/check-triage-stream.py [window dir] [--out DIR]
Writes <window>/triage-stream-summary.json (short, for the Status page) and <out>/triage-stream-results.json (full)."""
import sys, os, json, time, math, random, shutil, copy, collections
HERE = os.path.dirname(os.path.abspath(__file__)); KP = os.path.dirname(HERE); WS = os.path.join(KP, "projects", "world-state"); sys.path.insert(0, WS)
SL = os.path.abspath(os.path.join(KP, "..", "demo", "mockups", "structure-live"))
args = [a for a in sys.argv[1:] if not a.startswith("--") and a != (sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None)]; WIN = os.path.abspath(args[0]) if args else os.path.join(SL, "runs-e2e-101")
OUT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "/tmp/claude-0/-workspace/3ed8559b-0aa2-49c4-a429-a0452a913be2/scratchpad"
TD = os.path.join(WIN, "trace"); SEED = 20261122; N_PER_KIND = 10; N_SAMPLE = 40
import concepts_v0 as CV
res = []; R = {"window": WIN, "version": "triage-stream-v1", "provisional": True}
def ok(name, cond, msg=""): res.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name + (("  " + msg) if msg else ""), flush=True)
def jl(p, d=None):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d
def pct(x, n): return round(100.0 * x / n, 1) if n else None
def wilson(k, n, z=1.96):
    if not n: return [None, None]
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return [round(100 * (c - h) / d, 1), round(100 * (c + h) / d, 1)]
def med(v): v = sorted(v); return v[len(v) // 2] if v else None
def q(v, p): v = sorted(v); return v[min(len(v) - 1, int(p * len(v)))] if v else None

# ---------------------------------------------------------------- S1 timings
M = jl(os.path.join(WIN, "window.json"), {}) or {}; steps = {s["name"]: s for s in M.get("steps", [])}
chain = []
for l in open(os.path.join(TD, "chain.jsonl"), encoding="utf-8"):
    try:
        x = json.loads(l); ln = json.loads(x["line"]) if isinstance(x.get("line"), str) else x["line"]
        if ln.get("state") == "traced": chain.append(ln)
    except Exception: pass
slow = [json.loads(l) for l in open(os.path.join(TD, "slow.jsonl"), encoding="utf-8") if l.strip()]
N = len(chain); fast_ms = [c["total_ms"] for c in chain if c.get("total_ms") is not None]
fast_busy = sum(fast_ms) / 1000.0; slow_tot = [s["ms"]["total"] for s in slow if s.get("ms")]
def spm(n, secs): return round(n / (secs / 60.0), 1) if secs else None
sl_s = (steps.get("slow") or {}).get("seconds"); co_s = (steps.get("consol") or {}).get("seconds"); lv_s = (steps.get("live") or {}).get("seconds")
e2e_s = fast_busy + (sl_s or 0) + (co_s or 0)
S1 = {"articles_traced": N, "slow_records": len(slow),
      "fast_chain": {"live_step_wall_s": lv_s, "busy_s_sum_of_total_ms": round(fast_busy, 1), "p50_ms": med(fast_ms), "p90_ms": q(fast_ms, 0.9), "mean_ms": round(sum(fast_ms) / max(1, len(fast_ms)), 1), "articles_per_min_busy": spm(N, fast_busy), "design_p50_ms": 334, "design_p90_ms": 748, "note": "live step wall includes waiting out the fixed DURATION poll; busy = sum of per-article chain ms"},
      "slow_clock": {"wall_s": sl_s, "articles_per_min": spm(len(slow), sl_s), "p50_ms": med(slow_tot), "p90_ms": q(slow_tot, 0.9), "mean_ms": round(sum(slow_tot) / max(1, len(slow_tot)), 1), "design_p50_ms": "986 (c1) / 881 (mix)", "design_p90_ms": "2029 / 2202"},
      "consolidation": {"wall_s": co_s, "s_per_article": round(co_s / N, 2) if co_s else None, "articles_per_min": spm(N, co_s), "design_s_per_article": 1.35},
      "end_to_end": {"s_total_busy": round(e2e_s, 1), "articles_per_min": spm(N, e2e_s), "s_per_article": round(e2e_s / N, 2), "design_today_s_per_article": 2.7, "design_projection": "2000 articles on 1 process: 90 min; 8 processes 11.2 min (2.3); this run is ONE process"}}
S1["slow_parts_p50_ms"] = {k: med([s["ms"][k] for s in slow if s.get("ms") and k in s["ms"]]) for k in ("claims", "build_rec", "heads", "identity_g4", "contradictions")}
S1["projection_2000_single_process_min"] = round(2000 * e2e_s / N / 60, 1)
R["S1_timings"] = S1; print("S1", json.dumps(S1)[:1100], flush=True)
ok("S1 stream size", 300 <= N <= 500 and len(slow) == N, "%d traced, %d slow records (want 300-500, slow = traced)" % (N, len(slow)))

# ---------------------------------------------------------------- S2 triage replay
t0 = time.time(); B = CV.build(TD); R["build_s"] = round(time.time() - t0, 1)
ok("S2 build", B.get("exists"), "concepts_v0.build exists=%s (%.1f s)" % (B.get("exists"), R["build_s"]))
if not B.get("exists"):
    R["error"] = B.get("why"); os.makedirs(OUT, exist_ok=True); json.dump(R, open(os.path.join(OUT, "triage-stream-results.json"), "w"), indent=1); sys.exit(1)
TRI = sorted(B["triage"], key=lambda t: (t["seq"] if t["seq"] is not None else 1e9)); n = len(TRI); cut = round(n * 2 / 3); VERDS = ("known", "update", "new_link", "new_concept", "conflict")
owners_by_c = {c["id"]: c["owners"] for c in B["concepts"]}
for r in TRI: r["followed"] = bool(r.get("concept") and owners_by_c.get(r["concept"], 0) >= 2)   # 'followed' proxy: the concept has >= 2 independent owners in the window (design 1.6)
def shares(rows):
    c = collections.Counter(r["verdict"] for r in rows); k = len(rows); shown = k - c["known"]
    um = sum(1 for r in rows if r["verdict"] == "new_concept" and r["counts"].get("new_concept", 0) == r.get("unmapped", 0))   # new_concept rows whose only reason is facts anchored on no graph concept
    strict = c["conflict"] + c["new_link"] + c["new_concept"] + sum(1 for r in rows if r["verdict"] == "update" and r["followed"]); graph_level = strict - um
    return {"n": k, "counts": {v: c[v] for v in VERDS}, "share_pct": {v: pct(c[v], k) for v in VERDS}, "shown_non_known": shown, "compression_in_over_shown": round(k / shown, 2) if shown else None,
            "shown_strict": strict, "compression_strict": round(k / strict, 2) if strict else None, "unmapped_only_rows": um, "unmapped_only_pct": pct(um, k), "shown_graph_level": graph_level, "compression_graph_level": round(k / graph_level, 2) if graph_level else None, "graph_before_first_last": [rows[0].get("graph_before"), rows[-1].get("graph_before")] if rows else None}
S2 = {"previous_look_first_2_3": shares(TRI[:cut]), "since_last_look_last_1_3": shares(TRI[cut:]), "whole_window": shares(TRI),
      "note": "strict = conflict + new_link + new_concept + update on a concept with >= 2 owners; triage replays in seq order with state carried, so the last third is 'since your last look'; concept membership is incremental (v2: a concept is in the graph from the article at which it met its own membership rule; row.graph_before = concepts in the graph before that article); unmapped_only = new_concept rows whose only reason is facts anchored on no graph concept"}
R["S2_triage"] = S2; print("S2", json.dumps(S2)[:1400], flush=True)
ok("S2 compression (design 4.4 >= 10:1 on 2000 articles, PROVISIONAL)", (S2["whole_window"]["compression_strict"] or 0) >= 10, "strict %s:1, non-known %s:1" % (S2["whole_window"]["compression_strict"], S2["whole_window"]["compression_in_over_shown"]))

# ---------------------------------------------------------------- S3 seeded control
D = CV.load(TD); C = D["C"]; ents = D["ents"]; arts = D["arts"]; canon = CV.make_canon(ents, None); MS = {c["id"] for c in B["concepts"]}
seq_of = {a: v["seq"] for a, v in arts.items()}; base_v = {t["art"]: t["verdict"] for t in TRI}; late = [t["art"] for t in TRI[cut:]]; early = [t["art"] for t in TRI[:cut]]
rng = random.Random(SEED)
def scratch(name):
    d = os.path.join(OUT, "triage-stream-scratch", name, "trace"); shutil.rmtree(d, ignore_errors=True); os.makedirs(os.path.join(d, "slow_consolidate")); os.makedirs(os.path.join(d, "g4"))
    for f in ("chain.jsonl", "slow.jsonl"):
        if os.path.exists(os.path.join(TD, f)): shutil.copy(os.path.join(TD, f), d)
    if os.path.exists(os.path.join(TD, "g4", "store.jsonl")): shutil.copy(os.path.join(TD, "g4", "store.jsonl"), os.path.join(d, "g4"))
    shutil.copy(os.path.join(TD, "slow_consolidate", "knowledge.json"), os.path.join(d, "slow_consolidate")); return d
A0 = [e for e in C["edges"] if e.get("kind") == "assertion"]
by_art = collections.defaultdict(list)
for e in A0:
    for f in e.get("fragments") or []:
        if f.get("art") in arts: by_art[f["art"]].append((e, f))
INS = {c["id"]: c.get("in_graph_from_seq") for c in B["concepts"]}
def early_c(c, a): return c in MS and (INS.get(c) is None or INS[c] < seq_of[a])   # incremental membership: the concept was already in the graph before this article
def touches(e, a): return early_c(canon(e.get("anchor") or e.get("subj")), a)
cands = [a for a in late if any(touches(e, a) for e, f in by_art[a])]
cands.sort(key=lambda a: (base_v.get(a) != "known", rng.random()))   # baseline-known articles first: a change there is the one that could hide
KINDS = ["polarity", "amount", "status_reversal", "direction", "new_actor_link"]; PAIR = {"is": "is not", "open": "close", "win": "lose", "rise": "fall", "fall": "rise", "approve": "reject", "start": "stop", "increase": "decrease", "agree": "refuse"}
plan = []; used = set(); ci = 0
for k in KINDS:
    got = 0
    while got < N_PER_KIND and ci < len(cands):
        a = cands[ci]; ci += 1
        if a in used: continue
        e, f = next(((e, f) for e, f in by_art[a] if touches(e, a)), (None, None))
        if e is None: continue
        plan.append({"kind": k, "art": a, "edge": e["id"], "baseline": base_v.get(a)}); used.add(a); got += 1
ok("S3 seeded count", len(plan) == N_PER_KIND * len(KINDS), "%d synthetic changes planned (want 50)" % len(plan))
PRE = {p["edge"] + p["art"]: (early[rng.randrange(len(early))], early[rng.randrange(len(early))]) for p in plan}
def mk_scratch(mutate):
    d = scratch("mutated" if mutate else "control"); Cc = copy.deepcopy(C); E = {e["id"]: e for e in Cc["edges"]}; new = []
    for i, p in enumerate(plan):
        e = E[p["edge"]]; f = next(x for x in e["fragments"] if x.get("art") == p["art"]); a1, a2 = PRE[p["edge"] + p["art"]]
        e["fragments"].append(dict(f, art=a1, day=arts[a1]["day"], polarity="positive", direction=None))   # precursor: the same owner already read this slot earlier, so the unmutated later article is a repeat = 'known'
        for e0, f0 in by_art[p["art"]]:   # v2: every other fact of the target article also gets an earlier same-owner read, so 'known' needs ALL of its facts known
            if e0["id"] != p["edge"]: E[e0["id"]]["fragments"].append(dict(f0, art=a1, day=arts[a1]["day"]))
        if p["kind"] == "direction":
            e["fragments"].append(dict(f, art=a2, pub="seed-owner-A", day=arts[a2]["day"], polarity="positive", direction="up"))   # an independent owner read the concept going up
        f["polarity"] = "positive"; f["direction"] = None
        if not mutate: continue
        if p["kind"] == "polarity": f["polarity"] = "negative"
        elif p["kind"] == "direction": f["direction"] = "down"
        else:
            e["fragments"].remove(f); e2 = copy.deepcopy(e); e2["id"] = "seed%03d" % i; e2["fragments"] = [f]; e2["fragments_n"] = 1
            if p["kind"] == "amount": e2["obj"] = (e["obj"] or "") + " 40 percent"
            elif p["kind"] == "status_reversal": e2["pred"] = PAIR.get(e["pred"], "not " + str(e["pred"]))
            else: e2["obj"] = next((m for m in sorted(MS) if m != canon(e["subj"]) and m != canon(e["obj"]) and not m.startswith("resource:") and early_c(m, p["art"])), None)
            e2["key"] = "%s | %s | %s" % (e2["subj"], e2["pred"], e2["obj"]); new.append(e2)
    Cc["edges"] = Cc["edges"] + new; json.dump(Cc, open(os.path.join(d, "slow_consolidate", "consolidated.json"), "w")); return d
def verdicts(d): return {t["art"]: t["verdict"] for t in CV.build(d)["triage"]}
vc = verdicts(mk_scratch(False)); vm = verdicts(mk_scratch(True))
rows = [{**p, "control_verdict": vc.get(p["art"]), "mutated_verdict": vm.get(p["art"])} for p in plan]
per = {k: {"n": 0, "hidden_known": 0, "conflict": 0, "control_known": 0} for k in KINDS}
for r in rows:
    x = per[r["kind"]]; x["n"] += 1; x["hidden_known"] += r["mutated_verdict"] == "known"; x["conflict"] += r["mutated_verdict"] == "conflict"; x["control_known"] += r["control_verdict"] == "known"
hid = sum(x["hidden_known"] for x in per.values()); conf = sum(x["conflict"] for x in per.values()); ctl = sum(x["control_known"] for x in per.values())
S3 = {"n": len(rows), "control_known_before_mutation": ctl, "hidden_known_after_mutation": hid, "reached_conflict": conf, "not_labelled_conflict": len(rows) - conf, "per_kind": per, "mutated_verdict_counts": dict(collections.Counter(r["mutated_verdict"] for r in rows)),
      "method": "scratch copy of consolidated.json: a precursor read (same owner, earlier article) is added to each target slot so the unmutated later article is 'known' (control); then ONE change per later article: polarity flip, '40 percent' appended to the object, predicate reversed, direction down against an independent 'up' read, object replaced by another known concept; knowledge.json (the full path's contested pairs) is NOT regenerated, so 'conflict' here is triage's own polarity / direction rule only",
      "rows": rows}
R["S3_seeded"] = S3; print("S3", json.dumps({k: v for k, v in S3.items() if k not in ("rows", "method")}), flush=True)
ok("S3 seeded hidden (bar: 0 of 50 stay known)", hid == 0, "%d of %d seeded changes labelled known after mutation (control: %d of %d known before)" % (hid, len(rows), ctl, len(rows)))
four = sum(per[k]["conflict"] for k in ("polarity", "amount", "status_reversal", "direction")); nl = per["new_actor_link"]
ok("S3 missed conflicts (bar: 0 of 40 polarity/amount/status/direction missed)", four == 40, "conflict reached: " + ", ".join("%s %d/%d" % (k, per[k]["conflict"], per[k]["n"]) for k in KINDS) + "; new_actor_link non-known %d/%d (new_link %d)" % (nl["n"] - nl["hidden_known"], nl["n"], sum(1 for r in rows if r["kind"] == "new_actor_link" and r["mutated_verdict"] == "new_link")))

# ---------------------------------------------------------------- S4 sampled audit (+ S6 duplicate control)
def audit(td, TRIx, sample_from, n_sample):
    """structural diff on a consolidated store: a 'known' item is a hidden change when its first appearance introduces an edge key (slot), an entity id or an unordered subject-object pair absent from every earlier item in seq order"""
    Dx = CV.load(td); Cx = Dx["C"]; ax = Dx["arts"]; cn = CV.make_canon(Dx["ents"], None); sq = {a: v["seq"] for a, v in ax.items()}; ba = collections.defaultdict(list)
    for e in [e for e in Cx["edges"] if e.get("kind") == "assertion"]:
        for f in e.get("fragments") or []:
            if f.get("art") in ax: ba[f["art"]].append((e, f))
    fs = {}; fi = {}; fp = {}; pa = collections.defaultdict(lambda: {"slots": set(), "ids": set(), "pairs": set()})
    for a in sorted(ba, key=lambda x: sq[x]):
        for e, f in ba[a]:
            sj = cn(e.get("subj")); ob = cn(e.get("obj")); pr = tuple(sorted((str(sj), str(ob))))
            for store, key, bucket in ((fs, e.get("key") or e["id"], "slots"), (fi, sj, "ids"), (fi, ob, "ids"), (fp, pr, "pairs")):
                if key and key not in store: store[key] = a; pa[a][bucket].add(key)
    def hid(t): x = pa.get(t["art"]); return bool(x and (x["slots"] or x["ids"] or x["pairs"]))
    smp = rng.sample(sample_from, min(n_sample, len(sample_from))); return {"known_items": len(TRIx), "sample_n": len(smp), "hidden_in_sample": sum(hid(t) for t in smp), "population_hidden": sum(hid(t) for t in TRIx)}
known = [t for t in TRI if t["verdict"] == "known"]; A1 = audit(TD, known, known, N_SAMPLE)
# S6: duplicate-heavy control. scratch copy of the window where the LAST 100 articles are replayed a second time right after the window (same owner, same facts, new article ids, later seq): the second pass should be mostly 'known'
LAST = [t["art"] for t in TRI[-100:]]
def mk_dup():
    d = os.path.join(OUT, "triage-stream-scratch", "dup", "trace"); shutil.rmtree(d, ignore_errors=True); os.makedirs(os.path.join(d, "slow_consolidate")); os.makedirs(os.path.join(d, "g4"))
    if os.path.exists(os.path.join(TD, "g4", "store.jsonl")): shutil.copy(os.path.join(TD, "g4", "store.jsonl"), os.path.join(d, "g4"))
    shutil.copy(os.path.join(TD, "slow_consolidate", "knowledge.json"), os.path.join(d, "slow_consolidate"))
    mx = max(v["seq"] for v in arts.values() if v["seq"] is not None); did = {a: "dup-" + a for a in LAST}; dseq = {a: mx + 1 + i for i, a in enumerate(sorted(LAST, key=lambda x: seq_of[x]))}
    with open(os.path.join(d, "chain.jsonl"), "w", encoding="utf-8") as o:
        for l in open(os.path.join(TD, "chain.jsonl"), encoding="utf-8"):
            o.write(l if l.endswith("\n") else l + "\n")
            try: x = json.loads(l); inner = CV._inner(x)
            except Exception: continue
            if inner and inner.get("id") in did:
                i2 = dict(inner, id=did[inner["id"]], seq=dseq[inner["id"]]); o.write(json.dumps({"seq": i2["seq"], "line": json.dumps(i2)}) + "\n")
    Cd = copy.deepcopy(C)
    for e in Cd["edges"]:
        add = [dict(f, art=did[f["art"]]) for f in (e.get("fragments") or []) if f.get("art") in did]
        if add: e["fragments"] = e["fragments"] + add
    json.dump(Cd, open(os.path.join(d, "slow_consolidate", "consolidated.json"), "w")); return d, set(did.values())
dd_, DUP = mk_dup(); BD = CV.build(dd_); TD2 = sorted(BD["triage"], key=lambda t: t["seq"]); second = [t for t in TD2 if t["art"] in DUP]; first = [t for t in TD2 if t["art"] in set(LAST)]
sc = collections.Counter(t["verdict"] for t in second); fc = collections.Counter(t["verdict"] for t in first)
S6 = {"replayed_articles": len(second), "second_pass_counts": dict(sc), "second_pass_known_pct": pct(sc["known"], len(second)), "ci95_wilson_pct": wilson(sc["known"], len(second)), "first_pass_counts_same_articles": dict(fc), "first_pass_known_pct": pct(fc["known"], len(first)),
      "second_pass_not_known_examples": [{"seq": t["seq"], "verdict": t["verdict"], "detail": t["detail"][:120]} for t in second if t["verdict"] != "known"][:6],
      "method": "scratch copy: the last 100 articles (seq order) duplicated with new ids and later seq, same publisher and same fragments on every edge; triage replays the original then the duplicates"}
R["S6_duplicate_control"] = S6; print("S6", json.dumps(S6)[:900], flush=True)
ok("S6 duplicate control (bar: second pass >= 80% known)", (S6["second_pass_known_pct"] or 0) >= 80, "%s%% of %d replayed articles known (CI %s); first pass of the same articles %s%% known" % (S6["second_pass_known_pct"], len(second), S6["ci95_wilson_pct"], S6["first_pass_known_pct"]))
A2 = audit(dd_, [t for t in second if t["verdict"] == "known"], [t for t in second if t["verdict"] == "known"], N_SAMPLE)
pool_n = A1["sample_n"] + A2["sample_n"]; pool_h = A1["hidden_in_sample"] + A2["hidden_in_sample"]
S4 = {"window_known_items": A1["known_items"], "window_sample": A1, "window_known_with_no_extracted_fact": sum(1 for t in known if t.get("facts") == 0), "duplicate_pass_sample": A2,
      "pooled_sample_n": pool_n, "pooled_hidden": pool_h, "hidden_rate_pct": pct(pool_h, pool_n), "ci95_wilson_pct": wilson(pool_h, pool_n),
      "method": "structural diff on the consolidated store (no human labels), pooled over (a) every sampled 'known' item of the real window and (b) a sample of up to %d 'known' items of the duplicate pass; items with no assertion edge introduce nothing. The real window has few 'known' items after v2, so the pool leans on (b)" % N_SAMPLE}
R["S4_sampled"] = S4; print("S4", json.dumps(S4), flush=True)
ok("S4 hidden-change rate (bar <= 5%, upper CI reported)", S4["hidden_rate_pct"] is not None and S4["hidden_rate_pct"] <= 5.0, "%s%% (Wilson CI %s) over %d sampled known items (real window known %d, duplicate pass %d)" % (S4["hidden_rate_pct"], S4["ci95_wilson_pct"], pool_n, A1["sample_n"], A2["sample_n"]))

# ---------------------------------------------------------------- S5 identity scaling
sl = sorted(slow, key=lambda s: s["seq"]); idm = [(i + 1, s["ms"].get("identity_g4")) for i, s in enumerate(sl) if s.get("ms") and s["ms"].get("identity_g4") is not None]
curve = []
for lo, hi in ((1, 50), (51, 150), (151, 300), (301, 10 ** 6)):
    v = [m for i, m in idm if lo <= i <= hi]
    if v: curve.append({"articles": "%d-%s" % (lo, hi if hi < 10 ** 6 else "end"), "n": len(v), "identity_ms_p50": round(med(v), 1), "identity_ms_mean": round(sum(v) / len(v), 1), "identity_ms_p90": round(q(v, 0.9), 1)})
try:
    import numpy as np
    bench = []; r_ = np.random.RandomState(0)
    for n_art in (50, 150, 300, 460):
        nv = 22 * n_art; Vm = r_.randn(nv, 384).astype("float32"); Vm /= np.linalg.norm(Vm, axis=1, keepdims=True); Qs = r_.randn(22, 384).astype("float32"); Qs /= np.linalg.norm(Qs, axis=1, keepdims=True)
        store = [(i // 22, i, Vm[i]) for i in range(nv)]; t0 = time.perf_counter()
        for vec in Qs:
            best = None
            for (pa, paid, pv) in store:
                s_ = float(np.dot(pv, vec))
                if s_ >= 0.86 and (best is None or s_ > best[0]): best = (s_, paid)
        py_ms = (time.perf_counter() - t0) * 1000; t0 = time.perf_counter(); S_ = Qs @ Vm.T; mm_ms = (time.perf_counter() - t0) * 1000
        bench.append({"articles_in_store": n_art, "vectors": nv, "python_scan_ms_per_article": round(py_ms, 1), "one_matmul_ms_per_article": round(mm_ms, 2)})
except Exception as e: bench = [{"error": repr(e)}]
S5 = {"identity_ms_curve_from_slow_clock": curve, "g4_align_similar_scan_microbench_22_vectors_per_article": bench,
      "note": "identity_g4 ms is the slow clock's own timer (align minus contradictions) while the store grows as the window runs; the micro-benchmark times the g4_align.py 'for (pa, paid, pv) in S.vec' scan alone (22 new vectors against all stored ones) versus one matmul"}
R["S5_identity"] = S5; print("S5", json.dumps(S5)[:1200], flush=True)
ok("S5 identity measured", len(curve) >= 3, "%d bins" % len(curve))

# ---------------------------------------------------------------- write
R["gates"] = {"pass": sum(res), "of": len(res)}
os.makedirs(OUT, exist_ok=True); json.dump(R, open(os.path.join(OUT, "triage-stream-results.json"), "w"), indent=1)
summ = {"version": "triage-stream-summary-v1", "provisional": True, "window": os.path.relpath(WIN, os.path.join(KP, "..")), "articles": N, "articles_per_min_end_to_end_single_process": S1["end_to_end"]["articles_per_min"],
        "stage_s": {"fast_busy": S1["fast_chain"]["busy_s_sum_of_total_ms"], "slow": sl_s, "consol": co_s},
        "verdict_share_pct": {"previous_look": S2["previous_look_first_2_3"]["share_pct"], "since_last_look": S2["since_last_look_last_1_3"]["share_pct"]},
        "compression": {"non_known": S2["whole_window"]["compression_in_over_shown"], "strict": S2["whole_window"]["compression_strict"]},
        "seeded": {"n": S3["n"], "hidden_known": hid, "control_known": ctl, "reached_conflict": conf}, "sampled": {"n": S4["pooled_sample_n"], "hidden": S4["pooled_hidden"], "rate_pct": S4["hidden_rate_pct"], "ci95": S4["ci95_wilson_pct"]}, "duplicate_control": {"known_pct": S6["second_pass_known_pct"], "ci95": S6["ci95_wilson_pct"]},
        "identity_ms_curve": curve, "bars": {"hidden_rate_le_5pct": S4["hidden_rate_pct"] is not None and S4["hidden_rate_pct"] <= 5.0, "seeded_hidden_eq_0": hid == 0}}
json.dump(summ, open(os.path.join(WIN, "triage-stream-summary.json"), "w"), indent=1); json.dump(summ, open(os.path.join(OUT, "triage-stream-summary.json"), "w"), indent=1)
print("%d/%d rows pass; summary %s" % (sum(res), len(res), os.path.join(WIN, "triage-stream-summary.json")))
