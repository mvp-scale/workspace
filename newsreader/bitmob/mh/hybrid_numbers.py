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
# ---- hybrid: Clef double-checks the stories BitMob ranks most likely to carry a reading (round 6) ----
allk = [(d, u) for d in DIALS for u in ("up", "down")]; N = len(R); tp = np.zeros(N); fn = np.zeros(N); fp = np.zeros(N); neg = np.zeros(N); sc = np.zeros(N)
for n, r in enumerate(R):
    P = mkP(n); rd = C.read(P); mk = {(x["dial"], x["direction"]) for x in rd["readings"] if x["direction"] != "conflict"}; ck = {(x["dial"], x["direction"]) for x in r["read"]["readings"] if x["direction"] != "conflict"}
    tp[n] = len(mk & ck); fn[n] = len(ck - mk); fp[n] = len(mk - ck); neg[n] = len(allk) - len(ck | mk) + len(mk - ck); sc[n] = float(np.max(H["cond"][n]))
order = np.argsort(-sc); res = []; P_tot = tp.sum() + fn.sum(); N_tot = neg.sum()
for X in (0, .1, .2, .3, .4, .5, .6, .7, .8, 1.0):
    k = int(round(X * N)); chk = np.zeros(N, bool); chk[order[:k]] = True
    TP = (tp + fn)[chk].sum() + tp[~chk].sum(); FP = fp[~chk].sum(); res.append({"checked_share": X, "stories_checked": k, "TPR": round(float(TP / P_tot), 4), "FPR": round(float(FP / N_tot), 5)})
ok = [x for x in res if x["TPR"] >= .9 and x["FPR"] <= .001]
out = {"n": N, "positives": int(P_tot), "model": a.model, "table": res, "smallest_share_reaching_F0020": ok[0] if ok else None, "note": "checked stories are assumed read exactly as Clef (all their readings caught, no false alarms); unchecked stories keep the model's own readings; score = max condition output"}
json.dump(out, open(a.out, "w"), indent=1); print(json.dumps(out, indent=1))
