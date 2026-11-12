"""Feed each text variant to the registered v6b-student reader (headline-aware windows) and score right-within-two-guesses against the MN-DS human category. No training. Paired bootstrap against V0 (headline + first 300 characters) and V1 (whole article).
    /workspace/models/embed-zs/.venv/bin/python variants_score.py -> runs/pulse/structure_test.json"""
import json, sys, time, math, numpy as np
sys.path.insert(0, "."); import analyze2 as A2; from expert1_runtime import ExpertS
M = json.load(open("specs/topic_to_iptc_v1.json"))["map"]; rows = [json.loads(l) for l in open("runs/harvest/mnds_variants.jsonl")]
e = ExpertS("runs/expert1/expert1_v6b_student.pkl"); cl = e.S["topic_cl"]; rd = A2.Reader(e.S, threads=6, fit_headline=True)
names = {"V0_headline_plus_300_chars": lambda r: r["content"][:300], "V1_whole_article": lambda r: r["content"], "V2_gist": lambda r: r["views"]["gist"], "V3_opening_plus_coverage": lambda r: r["views"]["opening_plus_coverage"], "V4_keyphrases": lambda r: r["views"]["keyphrases"], "V5_theme_openers": lambda r: r["views"]["theme_openers"], "V6_core_triples": lambda r: r["views"]["core_triples"], "V7_combined": lambda r: r["views"]["combined"]}
hit2 = {k: [] for k in names}; hit1 = {k: [] for k in names}; ms = {k: [] for k in names}; words = {k: [] for k in names}
for r in rows:
    g = r["category"]
    for k, fn in names.items():
        t = fn(r); words[k].append(len(t.split())); t0 = time.perf_counter(); pt, _, _ = rd.read(r["title"], t); ms[k].append((time.perf_counter() - t0) * 1000)
        o = np.argsort(-pt)[:2]; hit2[k].append(int(any(g in M.get(cl[x], []) for x in o))); hit1[k].append(int(g in M.get(cl[o[0]], [])))
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return [round((c - h) / d, 3), round((c + h) / d, 3)]
rs = np.random.RandomState(3); n = len(rows); idx = [rs.randint(0, n, n) for _ in range(2000)]
def diff(a, b):
    d = np.array(hit2[a]) - np.array(hit2[b]); bs = [d[i].mean() for i in idx]; return {"diff": round(float(d.mean()), 4), "low": round(float(np.percentile(bs, 2.5)), 4), "high": round(float(np.percentile(bs, 97.5)), 4)}
res = {"v": "structure-test-v0", "articles": n, "reader": "expert1_v6b_student.pkl, headline-aware windows", "scoring": "right within two guesses vs MN-DS human category, map specs/topic_to_iptc_v1.json (scoring only, no training)", "variants": {}}
for k in names:
    res["variants"][k] = {"within_two": round(float(np.mean(hit2[k])), 4), "range": wil(sum(hit2[k]), n), "first_guess": round(float(np.mean(hit1[k])), 4), "median_words_given": int(np.median(words[k])), "median_reader_ms": round(float(np.median(ms[k])), 1), "diff_vs_V0": diff(k, "V0_headline_plus_300_chars") if k != "V0_headline_plus_300_chars" else None, "diff_vs_V1": diff(k, "V1_whole_article") if k != "V1_whole_article" else None}
json.dump(res, open("runs/pulse/structure_test.json", "w"), indent=1)
for k, v in res["variants"].items(): print(f"{k:28} within-two {v['within_two']:.3f} {v['range']} first {v['first_guess']:.3f} | words {v['median_words_given']:4} ms {v['median_reader_ms']:6.1f} | vs V0 {v['diff_vs_V0']} ")
