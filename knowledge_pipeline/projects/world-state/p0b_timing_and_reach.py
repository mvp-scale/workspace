"""P0b (ledger T149): (1) time per element on the simulation bench, (2) does reading more text change the Domain top-1 (consistency only, no truth set).
Run: CUDA_VISIBLE_DEVICES="" HF_HUB_OFFLINE=1 /workspace/models/embed-zs/.venv/bin/python p0b_timing_and_reach.py {m1|m2}   (from projects/world-state)
m1 needs the bench on :18770 (read only, concurrency 1). m2 uses the bench for (a),(b) and an in-process copy of the same code (new Reader, cap raised) for (c) and float scores."""
import json, sys, time, re, os, urllib.request, statistics as st, collections
BENCH = "http://127.0.0.1:18770"; OUT = "runs/pulse/p0b/"
def get(p): return json.load(urllib.request.urlopen(BENCH + p, timeout=120))
def post(d):
    t = time.perf_counter(); r = urllib.request.Request(BENCH + "/api/run", json.dumps(d).encode(), {"Content-Type": "application/json"})
    j = json.load(urllib.request.urlopen(r, timeout=300)); return j, (time.perf_counter() - t) * 1000
def pct(v, q): v = sorted(v); k = (len(v) - 1) * q; f = int(k); c = min(f + 1, len(v) - 1); return v[f] + (v[c] - v[f]) * (k - f)
def corr(x, y):
    mx, my = st.mean(x), st.mean(y); sx = sum((a - mx) ** 2 for a in x) ** .5; sy = sum((b - my) ** 2 for b in y) ** .5
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)
def rank(v):
    o = sorted(range(len(v)), key=lambda i: v[i]); r = [0] * len(v)
    for k, i in enumerate(o): r[i] = k
    return r
def m1():
    arts = get("/api/articles"); print(len(arts), "stories"); a0 = get("/api/article?id=" + arts[0]["id"]); post({"title": a0["title"], "body": a0["body"], "date": a0["date"], "sparse": False})  # warm-up, discarded
    rows = []
    for k, a in enumerate(arts):
        art = get("/api/article?id=" + a["id"]); j, wall = post({"title": art["title"], "body": art["body"], "date": art["date"], "sparse": False})
        el = {"ms." + k_: v for k_, v in j["ms"].items()}; el["bench.claims_ms"] = j["claims_ms"]; el["bench.pulse_ms(extra Condition read)"] = j["pulse_ms"]; el["bench.place_ms"] = j["place_ms"]
        for m in j["models"]:
            if m.get("ms") is not None: el["model: " + m["name"][:70]] = m["ms"]
        for t in j["tools"]:
            if t.get("ms") is not None: el["tool: " + t["step"]] = t["ms"]
        el["client_wall_ms (whole POST)"] = wall
        rows.append({"id": a["id"], "words": a["words"], "windows": j["story"].get("windows"), "el": el})
        if k % 40 == 0: print(k, round(wall), flush=True)
    json.dump(rows, open(OUT + "m1_raw.json", "w"))
    names = sorted({n for r in rows for n in r["el"]}); summ = {}
    for n in names:
        v = [r["el"][n] for r in rows if n in r["el"]]; summ[n] = {"n": len(v), "median": pct(v, .5), "p90": pct(v, .9), "max": max(v)}
    tot = [r["el"]["ms.total_ms"] for r in rows]; w = [r["words"] for r in rows]
    summ["_total_ms_corr_words"] = {"pearson": corr(w, tot), "spearman": corr(rank(w), rank(tot))}
    wall = [r["el"]["client_wall_ms (whole POST)"] for r in rows]; summ["_wall_corr_words"] = {"pearson": corr(w, wall), "spearman": corr(rank(w), rank(wall))}
    summ["_share_total_under_100ms"] = sum(t < 100 for t in tot) / len(tot); summ["_share_wall_under_100ms"] = sum(t < 100 for t in wall) / len(wall)
    summ["_words"] = {"median": pct(w, .5), "max": max(w), "min": min(w)}
    json.dump(summ, open(OUT + "m1_summary.json", "w"), indent=1)
    for n, s in summ.items():
        print(n, {k: round(v, 3) if isinstance(v, float) else v for k, v in s.items()})
def m2():
    os.environ["CUDA_VISIBLE_DEVICES"] = ""; sys.argv = ["x"]; sys.path.insert(0, "/workspace/knowledge_pipeline/simulation")
    import server as SV, analyze2 as A2; import numpy as np
    arts = [json.loads(l) for l in open("runs/pulse/golden/articles.jsonl")]
    Rb = SV.AN[False].reader; Rc = A2.Reader(SV.E.S, threads=8, cap=10 ** 6); S = SV.E.S
    def local(R, title, body, date):
        t, b, d, cl = SV.clean_input(title, body, date); t = re.sub(r"\s+", " ", t).strip(); pt, ps, nw = R.read(t, b)
        dom = collections.defaultdict(float)
        for n, p in zip(S["topic_cl"], pt): dom[(SV.TOPIC2DOM.get(n) or ["unmapped"])[0]] += float(p)
        top = max(dom.items(), key=lambda kv: kv[1]); return top[0], top[1], nw
    rows = []
    for i, a in enumerate(arts):
        t, b, d = a["title"], a["body"], a.get("date"); words = len(b.split())
        ja, _ = post({"title": t, "body": b[:300], "date": d, "sparse": False}); jb, _ = post({"title": t, "body": b, "date": d, "sparse": False})
        # (a) is title + first 300 characters of body; bench posts that as the body, so the reader sees title + 300 chars
        r = {"i": i, "title": t, "words": words, "bench_a": ja["story"]["domain"]["top"][0], "bench_b": jb["story"]["domain"]["top"][0]}
        la = local(Rb, t, b[:300], d); lb = local(Rb, t, b, d); lc = local(Rc, t, b, d)
        r.update({"a": la[:2], "b": lb[:2], "c": lc[:2], "win_b": lb[2], "win_c": lc[2]}); rows.append(r)
        if i % 25 == 0: print(i, flush=True)
    json.dump(rows, open(OUT + "m2_raw.json", "w"))
    agree = sum(1 for r in rows if r["bench_a"]["name"] == r["a"][0]) , sum(1 for r in rows if r["bench_b"]["name"] == r["b"][0])
    def share(f, rs): return sum(f(r) for r in rs) / len(rs) if rs else None
    buckets = {"<300": lambda w: w < 300, "300-600": lambda w: 300 <= w <= 600, ">600": lambda w: w > 600, "all": lambda w: True}
    res = {"n": len(rows), "local_vs_bench_top1_agree_a_b": agree, "words_gt_500": sum(r["words"] > 500 for r in rows), "windows_b_ge_12": sum(r["win_b"] >= 12 for r in rows), "windows_c_gt_12": sum(r["win_c"] > 12 for r in rows), "buckets": {}}
    for k, f in buckets.items():
        rs = [r for r in rows if f(r["words"])]
        res["buckets"][k] = {"n": len(rs), "ab_changed": share(lambda r: r["a"][0] != r["b"][0], rs), "bc_changed": share(lambda r: r["b"][0] != r["c"][0], rs), "ac_changed": share(lambda r: r["a"][0] != r["c"][0], rs),
            "mean_score_a": st.mean(r["a"][1] for r in rs) if rs else None, "mean_score_b": st.mean(r["b"][1] for r in rs) if rs else None, "mean_score_c": st.mean(r["c"][1] for r in rs) if rs else None,
            "mean_top1_score_change_b_minus_a": st.mean(r["b"][1] - r["a"][1] for r in rs) if rs else None, "mean_top1_score_change_c_minus_b": st.mean(r["c"][1] - r["b"][1] for r in rs) if rs else None,
            "mean_abs_change_b_minus_a": st.mean(abs(r["b"][1] - r["a"][1]) for r in rs) if rs else None}
    ch = [r for r in rows if r["a"][0] != r["b"][0] or r["b"][0] != r["c"][0]]; import random; random.Random(0).shuffle(ch)
    res["examples"] = [{"title": r["title"][:100], "words": r["words"], "a": "%s %.2f" % (r["a"][0], r["a"][1]), "b": "%s %.2f" % (r["b"][0], r["b"][1]), "c": "%s %.2f" % (r["c"][0], r["c"][1])} for r in ch[:10]]
    json.dump(res, open(OUT + "m2_summary.json", "w"), indent=1); print(json.dumps(res, indent=1))
if __name__ == "__main__": {"m1": m1, "m2": m2}[sys.argv[1]]()
