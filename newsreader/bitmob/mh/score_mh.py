"""Score a multi-head model against Clef labels (the frozen test) on the contract rows P-0016..P-0021 (D-0038). CPU only. Never trains.
  CUDA_VISIBLE_DEVICES= models/embed-zs/.venv/bin/python newsreader/bitmob/mh/score_mh.py MODEL_DIR LABELS.jsonl OUT.json [--n N]
The model's heads are turned into the engine's own P (328 answers) and run through classify.read(); topics, country, expected and severity follow place()/ask_country_detailed()/expected()/severity() rules.
P-0022 (so-what) and P-0023 (engine replay) are not computed here."""
import os, sys, json, argparse, time
os.environ.setdefault("WE_RULES", "rules_v2"); os.environ.setdefault("WORLD_GPU", "0"); os.environ["CUDA_VISIBLE_DEVICES"] = ""
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import numpy as np, torch, classify as C
from mh_common import load, predict
ap = argparse.ArgumentParser(); ap.add_argument("model"); ap.add_argument("labels"); ap.add_argument("out"); ap.add_argument("--n", type=int, default=0); ap.add_argument("--threads", type=int, default=8); a = ap.parse_args()
torch.set_num_threads(a.threads); R = [json.loads(l) for l in open(a.labels) if l.strip()]; R = R[:a.n] if a.n else R
model, tok, K = load(a.model); t0 = time.time(); H = predict(model, tok, [r["state_text"] for r in R]); read_s = time.time() - t0
G, S, COND = K["gate"], K["scope"], K["cond"]; DIALS = K["severity"]; LV = K["levels"]; EXPK = K["expected"]; DOM = K["topic_c"]; DOMY = K["topic_y"]; REG, CTY = K["region"], K["country"]
rows100 = C._country_rows(); reg_of = {x["id"]: x["region"] for x in rows100}
def ap_score(y, s):
    o = np.argsort(-s); y = np.asarray(y)[o]; tp = np.cumsum(y); return float((tp / np.arange(1, len(y) + 1))[y == 1].mean()) if y.sum() else float("nan")
def mkP(n):
    P = {}
    for j, k in enumerate(G): P[k] = float(H["gate"][n, j])
    for j, k in enumerate(S): P[k] = float(H["scope"][n, j])
    for j, k in enumerate(COND): d, dr, i = k.split("|"); P[f"a|{d}|{dr}|{i}|0"] = P[f"a|{d}|{dr}|{i}|1"] = float(H["cond"][n, j])
    return P
def place(n):
    pc = dict(zip(DOM, H["topic_c"][n])); py = dict(zip(DOMY, H["topic_y"][n])); tag = {d: (pc[d] >= .2 or py.get(d, 0) >= .5) and d != "other" or (d == "other" and pc[d] >= .2) for d in DOM}
    if not any(tag.values()): tag[max(pc, key=pc.get)] = True
    return [{"id": d, "tagged": bool(tag[d]), "p_choice": float(pc[d]), "p_yes": float(py.get(d, 0.0))} for d in DOM]
def country(n):
    pr = dict(zip(REG, H["region"][n])); g = max(pr, key=pr.get)
    if g == "GLOBAL": return "global"
    pc = dict(zip(CTY, H["country"][n])); cand = [x["id"] for x in rows100 if x["region"] == g] + ["other_here"]; c = max(cand, key=lambda x: pc[x]); return "global" if c == "other_here" else c
def expected(n, reported, allowed):
    pe = dict(zip(EXPK, H["expected"][n])); out = []
    for d in DIALS:
        if d in reported or d not in allowed: continue
        pu, pdn = float(pe[f"{d}|up"]), float(pe[f"{d}|down"]); net = pu - pdn
        if max(pu, pdn) >= C.EXPECT_MIN and abs(net) > .05: out.append((abs(net), d, "up" if net > 0 else "down"))
    return {(d, dr) for _, d, dr in sorted(out, reverse=True)[:C.EXPECT_TOP]}
gate_ok = []; tp = fp = fn = tn = 0; tagged_m = []; tagged_c = []; cok = []; eok = []; sev_ok = []; sev_n = 0
for n, r in enumerate(R):
    P = mkP(n); rd = C.read(P); gate_ok.append(rd["gate_ok"] == r["read"]["gate_ok"])
    mk = {(x["dial"], x["direction"]) for x in rd["readings"] if x["direction"] != "conflict"}; ck = {(x["dial"], x["direction"]) for x in r["read"]["readings"] if x["direction"] != "conflict"}
    allk = {(d, u) for d in DIALS for u in ("up", "down")}; tp += len(mk & ck); fn += len(ck - mk); fp += len(mk - ck); tn += len(allk - mk - ck)
    pl = place(n); tagged_m.append({x["id"]: x["tagged"] for x in pl}); tagged_c.append({x["id"]: x["tagged"] for x in r["place"]})
    cok.append(country(n) == r["country"]); rep = {d for d, _ in mk}; allowed = C.allowed_dials(pl)
    eok.append(expected(n, rep, allowed) == {(x["dial"], x["direction"]) for x in r["expected"]})
    sv = H["severity"][n]
    for d, v in r["severity"].items(): sev_n += 1; sev_ok.append(LV[int(sv[DIALS.index(d)].argmax())] == v["level"])
TPR = tp / max(tp + fn, 1); FPR = fp / max(fp + tn, 1); out = {}
out["P-0016"] = {"bar": "gate accept/reject agrees with Clef >= 0.90", "value": round(float(np.mean(gate_ok)), 4), "pass": bool(np.mean(gate_ok) >= .9)}
out["P-0017"] = {"bar": "TPR>=.95 & FPR<=.0025, or TPR>=.9 & FPR<=.001 (F-0020), pooled over 78 dial|direction keys vs Clef readings", "value": {"TPR": round(TPR, 4), "FPR": round(FPR, 5), "positives": tp + fn}, "pass": bool((TPR >= .95 and FPR <= .0025) or (TPR >= .9 and FPR <= .001))}
aps = {}
for d in DOM:
    y = [int(t[d]) for t in tagged_c]
    if sum(y) >= 20: aps[d] = ap_score(y, np.array([max(p["p_choice"], p["p_yes"]) for p in [next(x for x in place(n) if x["id"] == d) for n in range(len(R))]]))
mt, ct = np.mean([sum(t.values()) for t in tagged_m]), np.mean([sum(t.values()) for t in tagged_c]); frac = float(np.mean([v >= .7 for v in aps.values()])) if aps else float("nan")
out["P-0018"] = {"bar": "per-domain AP>=.70 on >=80% of domains with >=20 Clef positives; mean topics/story within +-20% of Clef", "value": {"domains_scored": len(aps), "share_AP>=.7": round(frac, 3), "mean_topics_model": round(float(mt), 3), "mean_topics_clef": round(float(ct), 3), "weak": {d: round(v, 3) for d, v in sorted(aps.items(), key=lambda x: x[1])[:8]}}, "pass": bool(aps and frac >= .8 and abs(mt / ct - 1) <= .2)}
out["P-0019"] = {"bar": "country accuracy >= 0.90 vs Clef over 100 + global (two-step)", "value": round(float(np.mean(cok)), 4), "pass": bool(np.mean(cok) >= .9)}
out["P-0020"] = {"bar": "same expected-condition set as Clef on >= 75% of stories", "value": round(float(np.mean(eok)), 4), "pass": bool(np.mean(eok) >= .75)}
out["P-0021"] = {"bar": "same severity level as Clef on >= 75% of changes", "value": round(float(np.mean(sev_ok)), 4) if sev_ok else None, "n_changes": sev_n, "pass": bool(sev_ok and np.mean(sev_ok) >= .75)}
out["meta"] = {"n": len(R), "model": a.model, "labels": a.labels, "read_s_per_story_cpu": round(read_s / max(len(R), 1), 4)}
json.dump(out, open(a.out, "w"), indent=1); print(json.dumps({k: (v["value"] if isinstance(v, dict) and "value" in v else v) for k, v in out.items()}, default=str)[:1500])
