"""D-0037 step 3 report from data/bitmob-integration/replay/*.jsonl -> data/bitmob-integration/validation.json (plain pass/fail).
  python3 newsreader/bitmob/reader/validate_report.py"""
import json, numpy as np, statistics as st
R = "/workspace/data/bitmob-integration/replay"; L = lambda f: {json.loads(l)["id"]: json.loads(l) for l in open(f"{R}/{f}.jsonl")}
cl, bc, bp = L("clef-flash-q4km"), L("bitmob-clef"), L("bitmob-cpu"); ids = sorted(set(cl) & set(bc) & set(bp)); K = json.load(open("/workspace/data/kaggle/ds_r5/keys.json"))["cond_keys"]; U = set(K)
J = lambda a, b: (len(a & b) / len(a | b)) if (a | b) else 1.0
def tprfpr(rs, keys):
    tp = fn = fp = tn = 0
    for r in rs:
        t = set(r["truth"]["keys"]) & keys; p = set(r["keys"]) & keys
        tp += len(t & p); fn += len(t - p); fp += len(p - t); tn += len(keys) - len(t | p)
    return {"TPR": round(tp / max(1, tp + fn), 4), "FPR": round(fp / max(1, fp + tn), 5), "true_pairs": tp + fn, "fired_pairs": tp + fp}
def tol(x): return bool((x["TPR"] >= 0.95 and x["FPR"] <= 0.0025) or (x["TPR"] >= 0.90 and x["FPR"] <= 0.001))
out = {"n_stories": len(ids), "source": "seeded sample of testA (held out from every training set), Jev labels as truth", "readers": {}}
Rd = {"clef": [cl[i] for i in ids], "bitmob_clef": [bc[i] for i in ids], "bitmob_cpu": [bp[i] for i in ids]}
for n, rs in Rd.items():
    allkeys = set().union(*[set(r["truth"]["keys"]) | set(r["keys"]) for r in rs]) | U
    o = {"gate_ok_vs_jev": round(float(np.mean([r["gate_ok"] == bool(r["truth"]["gate_ok"]) for r in rs])), 4), "topic_top1_vs_jev": round(float(np.mean([r["topic_choice"] == r["truth"]["topic"] for r in rs])), 4),
         "topic_tagged_contains_jev": round(float(np.mean([r["truth"]["topic"] in r["tagged"] for r in rs])), 4), "country_vs_jev": round(float(np.mean([r["country"] == r["truth"]["country"] or (r["country"] == "global" and r["truth"]["country"] == "global") for r in rs])), 4),
         "conditions_52keys_vs_jev": tprfpr(rs, U), "conditions_all_keys_vs_jev": tprfpr(rs, allkeys), "mean_fired_keys_per_story": round(float(np.mean([len(r["keys"]) for r in rs])), 3), "mean_expected_readings": round(float(np.mean([len(r["expected"]) for r in rs])), 3)}
    o["F-0020_tolerance_52keys"] = "pass" if tol(o["conditions_52keys_vs_jev"]) else "FAIL"; o["F-0020_tolerance_all_keys"] = "pass" if tol(o["conditions_all_keys_vs_jev"]) else "FAIL"
    tt = [r["t"]["total"] for r in rs]; o["seconds_per_story_median"] = round(st.median(tt), 3); o["seconds_per_story_p95"] = round(float(np.percentile(tt, 95)), 3)
    out["readers"][n] = o
for n in ("bitmob_clef", "bitmob_cpu"):
    rs = Rd[n]; c = Rd["clef"]; out["readers"][n]["vs_clef"] = {"gate_ok_agree": round(float(np.mean([a["gate_ok"] == b["gate_ok"] for a, b in zip(rs, c)])), 4), "topic_top1_agree": round(float(np.mean([a["topic_choice"] == b["topic_choice"] for a, b in zip(rs, c)])), 4),
        "entry_country_agree": round(float(np.mean([a["country"] == b["country"] for a, b in zip(rs, c)])), 4), "condition_keys_same_set": round(float(np.mean([a["keys"] == b["keys"] for a, b in zip(rs, c)])), 4),
        "condition_keys_jaccard_mean": round(float(np.mean([J(set(a["keys"]) & U, set(b["keys"]) & U) for a, b in zip(rs, c)])), 4), "expected_set_same": round(float(np.mean([{(x["dial"], x["direction"]) for x in a["expected"]} == {(x["dial"], x["direction"]) for x in b["expected"]} for a, b in zip(rs, c)])), 4)}
# per-area comparison and cost
gpu = lambda rs, ph: round(float(np.mean([sum(r["t"][p] for p in ph) for r in rs])), 3)
out["gpu_seconds_per_story"] = {"clef": gpu(Rd["clef"], ("ask_read", "country", "place", "expected", "severity")), "bitmob_clef": gpu(Rd["bitmob_clef"], ("expected", "severity")), "bitmob_cpu": 0.0}
out["cpu_ms_per_story_bitmob_read"] = {"note": "service median_read_ms for one story, 8 threads, torch fp32 (from replay log stats)"}
for n in ("bitmob-cpu", "bitmob-clef"):
    try: s = json.loads(open(f"{R}/{n}.log").read().strip().splitlines()[-1])["stats_after"]; out["cpu_ms_per_story_bitmob_read"][n] = {"median_read_ms": s["median_read_ms"], "rss_mb": s["rss_mb"], "clef_s_total": round(s["clef_s"], 1), "clef_questions": s["clef_questions"]}
    except Exception as e: out["cpu_ms_per_story_bitmob_read"][n] = str(e)
pre = {"R-0162": {"gate_agree>=0.85": out["readers"]["bitmob_clef"]["vs_clef"]["gate_ok_agree"] >= .85, "topic_vs_jev>=0.75": out["readers"]["bitmob_clef"]["topic_top1_vs_jev"] >= .75, "country_vs_jev>=0.70": out["readers"]["bitmob_clef"]["country_vs_jev"] >= .70},
       "R-0163": {"bitmob_fails_F0020": out["readers"]["bitmob_clef"]["F-0020_tolerance_52keys"] == "FAIL"}, "R-0164": {"cpu_only_s<1.5": out["readers"]["bitmob_cpu"]["seconds_per_story_median"] < 1.5, "cpu_only_<0.3_of_clef": out["readers"]["bitmob_cpu"]["seconds_per_story_median"] < .3 * out["readers"]["clef"]["seconds_per_story_median"],
       "bitmob_clef_gpu<40%_of_clef": out["gpu_seconds_per_story"]["bitmob_clef"] < .4 * out["gpu_seconds_per_story"]["clef"]}}
out["predictions"] = pre; json.dump(out, open("/workspace/data/bitmob-integration/validation.json", "w"), indent=1); print(json.dumps(out, indent=1))
