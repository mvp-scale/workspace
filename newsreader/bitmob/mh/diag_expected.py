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
# ---- diagnosis of P-0020 (round 4): which input makes the expected set differ from Clef's ----
import collections
def cl_allowed(r): return C.allowed_dials(r["place"])
V = collections.Counter(); types = collections.Counter(); N = len(R)
yt, ys = collections.defaultdict(list), collections.defaultdict(list)
for n, r in enumerate(R):
    P = mkP(n); rd = C.read(P); mrep = {x["dial"] for x in rd["readings"] if x["direction"] != "conflict"}; crep = {x["dial"] for x in r["read"]["readings"] if x["direction"] != "conflict"}
    pl = place(n); mal = C.allowed_dials(pl); cal = cl_allowed(r); ce = {(x["dial"], x["direction"]) for x in r["expected"]}
    V["v0_model_rep_model_allowed"] += expected(n, mrep, mal) == ce; V["v1_clef_rep"] += expected(n, crep, mal) == ce
    V["v2_clef_allowed"] += expected(n, mrep, cal) == ce; V["v3_clef_rep_and_allowed"] += expected(n, crep, cal) == ce
    e3 = expected(n, crep, cal); me = expected(n, mrep, mal)
    t = "both_empty" if not me and not ce else "model_empty_clef_has" if not me else "model_has_clef_empty" if not ce else "same" if me == ce else "overlap" if me & ce else "disjoint"; types[t] += 1
    V["clef_empty_share"] += (not ce); V["model_rep_nonempty_when_clef_rep_nonempty"] += (bool(mrep) and bool(crep)); V["clef_rep_nonempty"] += bool(crep)
    if "e_raw" in r and r["e_raw"]:
        pe = dict(zip(EXPK, H["expected"][n]))
        for k, v in r["e_raw"].items():
            if isinstance(v, (int, float)) and k.startswith("e|"): yt[k.split("|")[1] + "|" + k.split("|")[2]].append(int(v >= .5)); ys[k.split("|")[1] + "|" + k.split("|")[2]].append(float(pe[f"{k.split('|')[1]}|{k.split('|')[2]}"]))
def auc(y, s):
    y = np.array(y); s = np.array(s)
    if y.sum() < 5 or (1 - y).sum() < 5: return None
    o = s.argsort().argsort() + 1; return float((o[y == 1].sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (1 - y).sum()))
au = {k: auc(yt[k], ys[k]) for k in yt}; au = {k: v for k, v in au.items() if v is not None}
res = {"n": N, "match_rates": {k: round(v / N, 4) for k, v in V.items()}, "mismatch_types": {k: round(v / N, 4) for k, v in types.items()}, "e_raw_stories": sum(1 for r in R if r.get("e_raw")),
       "auc_model_e_vs_clef_e_raw": {"dials_scored": len(au), "mean": round(float(np.mean(list(au.values()))), 3) if au else None, "min": round(min(au.values()), 3) if au else None, "share_ge_.8": round(float(np.mean([v >= .8 for v in au.values()])), 3) if au else None}}
json.dump(res, open(a.out, "w"), indent=1); print(json.dumps(res, indent=1))
