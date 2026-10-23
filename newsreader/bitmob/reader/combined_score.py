"""Score combined-reader outputs on the six contract steps with the SAME definitions as newsreader/bitmob/mh/score_mh.py (P-0016..P-0021), against Clef's stored full-battery answers (data/clef-labels/test.jsonl).
  /workspace/kev/.venv/bin/python newsreader/bitmob/reader/combined_score.py OUT.jsonl [SCORE.json]
OUT.jsonl lines: {"id", "out": read_story(...) result, optional "ctrl": {...}}. Differences from score_mh by necessity: the topic AP rule needs >=20 Clef positives, applied to this smaller sample (fewer domains reach it)."""
import os, sys, json, numpy as np
os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path.insert(0, "/workspace/newsreader/bitmob/reader")
import combined_reader as CR, classify as C
R = {}; [R.__setitem__(json.loads(l)["id"], json.loads(l)) for l in open("/workspace/data/clef-labels/test.jsonl")]
KEYS = json.load(open("/workspace/data/diag/combined/bitmob_keys.json")); DIALS = KEYS["severity"]
def ap_score(y, s):
    o = np.argsort(-s); y = np.asarray(y)[o]; tp = np.cumsum(y); return float((tp / np.arange(1, len(y) + 1))[y == 1].mean()) if y.sum() else float("nan")
def score(recs):
    gate_ok = []; tp = fp = fn = tn = 0; tm = []; tc = []; pm = []; cok = []; eok = []; sev_ok = []; sev_n = 0
    for x in recs:
        r = R[x["id"]]; o = x["out"]; rd = o["read"]; gate_ok.append(rd["gate_ok"] == r["read"]["gate_ok"])
        mk = {(y["dial"], y["direction"]) for y in rd["readings"] if y["direction"] != "conflict"}; ck = {(y["dial"], y["direction"]) for y in r["read"]["readings"] if y["direction"] != "conflict"}
        allk = {(d, u) for d in DIALS for u in ("up", "down")}; tp += len(mk & ck); fn += len(ck - mk); fp += len(mk - ck); tn += len(allk - mk - ck)
        tm.append({p["id"]: p["tagged"] for p in o["place"]}); tc.append({p["id"]: p["tagged"] for p in r["place"]}); pm.append({p["id"]: max(p["p_choice"], p["p_yes"]) for p in o["place"]})
        cok.append(o["country"] == r["country"]); eok.append({(y["dial"], y["direction"]) for y in o["expected"]} == {(y["dial"], y["direction"]) for y in r["expected"]})
        for d, v in r["severity"].items(): sev_n += 1; sev_ok.append(o["severity_level"][d] == v["level"])
    TPR = tp / max(tp + fn, 1); FPR = fp / max(fp + tn, 1); out = {}
    out["P-0016"] = {"step": "gate agreement", "bar": ">= 0.90", "value": round(float(np.mean(gate_ok)), 4), "pass": bool(np.mean(gate_ok) >= .9)}
    out["P-0017"] = {"step": "conditions", "bar": "TPR>=.95 & FPR<=.0025, or TPR>=.9 & FPR<=.001", "value": {"TPR": round(TPR, 4), "FPR": round(FPR, 5), "positives": tp + fn, "false_alarms": fp}, "pass": bool((TPR >= .95 and FPR <= .0025) or (TPR >= .9 and FPR <= .001))}
    aps = {}
    for d in tc[0]:
        y = [int(t[d]) for t in tc]
        if sum(y) >= 20: aps[d] = ap_score(y, np.array([p[d] for p in pm]))
    mt, ct = np.mean([sum(t.values()) for t in tm]), np.mean([sum(t.values()) for t in tc]); frac = float(np.mean([v >= .7 for v in aps.values()])) if aps else float("nan")
    out["P-0018"] = {"step": "topics", "bar": "AP>=.70 on >=80% of domains with >=20 Clef positives; topics/story within +-20% of Clef", "value": {"domains_scored": len(aps), "share_AP>=.7": round(frac, 3), "mean_topics_model": round(float(mt), 3), "mean_topics_clef": round(float(ct), 3), "weak": {d: round(v, 3) for d, v in sorted(aps.items(), key=lambda a: a[1])[:5]}}, "pass": bool(aps and frac >= .8 and abs(mt / ct - 1) <= .2)}
    out["P-0019"] = {"step": "country accuracy", "bar": ">= 0.90", "value": round(float(np.mean(cok)), 4), "pass": bool(np.mean(cok) >= .9)}
    out["P-0020"] = {"step": "expected same set", "bar": ">= 0.75 of stories", "value": round(float(np.mean(eok)), 4), "pass": bool(np.mean(eok) >= .75)}
    out["P-0021"] = {"step": "severity same level", "bar": ">= 0.75 of changes", "value": round(float(np.mean(sev_ok)), 4), "n_changes": sev_n, "pass": bool(np.mean(sev_ok) >= .75)}
    out["meta"] = {"n": len(recs)}
    return out
if __name__ == "__main__":
    recs = [json.loads(l) for l in open(sys.argv[1])]; s = score(recs)
    for k, v in s.items(): print(k, v)
    if len(sys.argv) > 2: json.dump(s, open(sys.argv[2], "w"), indent=1)
