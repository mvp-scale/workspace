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
import collections
rg = {x["id"]: x["region"] for x in rows100}; tr_cnt = collections.Counter()
for f in ("train", "train_rest", "country", "prelabelled_rest", "prelabelled_rest2"):
    for l in open(f"/workspace/data/jev-labels/{f}.jsonl"): tr_cnt[json.loads(l).get("country")] += 1
step = collections.Counter(); err = collections.Counter(); tot = collections.Counter(); conf = collections.Counter()
for n, r in enumerate(R):
    t = r["country"]; p = country(n); tot[t] += 1; ok = p == t
    pr = dict(zip(REG, H["region"][n])); g = max(pr, key=pr.get); treg = "GLOBAL" if t == "global" else rg.get(t)
    if ok: step["correct"] += 1
    elif g != treg: step["region_step_wrong"] += 1
    else: step["country_step_wrong"] += 1
    if not ok: err[t] += 1; conf[(t, p)] += 1
buck = lambda c: "global" if c == "global" else ("0-19 train" if tr_cnt[c] < 20 else "20-99" if tr_cnt[c] < 100 else "100-499" if tr_cnt[c] < 500 else "500+")
b_tot = collections.Counter(); b_err = collections.Counter()
for c, k in tot.items(): b_tot[buck(c)] += k; b_err[buck(c)] += err[c]
res = {"n": len(R), "acc": round(1 - sum(err.values()) / len(R), 4), "where_wrong": {k: round(v / len(R), 4) for k, v in step.items()},
       "by_train_support": {b: {"stories": b_tot[b], "acc": round(1 - b_err[b] / b_tot[b], 3), "share_of_all_errors": round(b_err[b] / max(sum(err.values()), 1), 3)} for b in b_tot},
       "worst_true_countries": [(c, tot[c], err[c]) for c, _ in err.most_common(10)], "top_confusions": [(f"{t}->{p}", k) for (t, p), k in conf.most_common(10)], "global_share_true": round(tot["global"] / len(R), 3)}
json.dump(res, open(a.out, "w"), indent=1); print(json.dumps(res, indent=1))
