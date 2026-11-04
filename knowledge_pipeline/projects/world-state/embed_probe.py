"""CPU probe: zero-training condition detection with static embeddings. Probes are generated from the guideline text (no hand-written phrases).
Run with /workspace/models/embed-zs/.venv/bin/python embed_probe.py"""
import json, os, re, glob, pathlib, random
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np
from sklearn.metrics import roc_auc_score
from model2vec import StaticModel
H0 = pathlib.Path(__file__).resolve().parent; J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
m = StaticModel.from_pretrained("minishlab/potion-base-8M")
base = json.load(open(H0 / "specs/world_state_v2_frozen_haiku.json"))
defs = [l for l in base["guideline"] if " | up = " in l and not l.startswith("CONDITIONS")]; P = {}
for l in defs:
    cid, rest = l.split(":", 1); parts = [p.strip() for p in rest.split("|")]
    P[cid] = {"meaning": parts[0], "up": parts[1].replace("up =", "").strip(), "down": parts[2].replace("down =", "").strip()}
C = sorted(P)
H = {}; S = {}
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): H[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): S[r["item_id"]] = r["label"]
pool = {r["id"]: r["text"] for r in J(H0 / "data/pool_train.jsonl")}; ids = sorted(i for i in S if i in H)
ref_ids = random.Random(1).sample([i for i in pool if i not in set(ids)], 2000)       # normaliser reference: items never evaluated
def windows(t, w=5, stride=2):
    ws = t.split(); out = [t]
    out += [" ".join(ws[i:i + w]) for i in range(0, max(len(ws) - w + 1, 1), stride)]
    return out
def unit(a): return a / (np.linalg.norm(a, axis=-1, keepdims=True) + 1e-9)
PT = {(c, k): P[c][k] for c in C for k in ("meaning", "up", "down")}; keys = list(PT); PE = m.encode([PT[k] for k in keys])
allw = {}; offs = {}
def embed_items(idl):
    W = []; o = []
    for i in idl: ws = windows(pool[i]); o.append((len(W), len(W) + len(ws))); W += ws
    return m.encode(W), o
Rw, Ro = embed_items(ref_ids); mu = Rw.mean(0)                                         # centre by the mean embedding (all-but-the-mean)
cen = lambda x: unit(x - mu); PEc = cen(PE); Rc = cen(Rw); Rs = Rc @ PEc.T                # reference similarities, windows x probes
rmean, rstd = Rs.mean(0), Rs.std(0) + 1e-9
Ew, Eo = embed_items(ids); Es = cen(Ew) @ PEc.T; Eraw = unit(Ew) @ unit(PE).T
res = {"raw_full": [], "z_full": [], "z_window": []}; kidx = {k: j for j, k in enumerate(keys)}; per = {}; dir_ok = dir_n = 0
for c in C:
    y = np.array([1 if (c in {x["condition"] for x in H[i]["conditions"]} and c in {x["condition"] for x in S[i]["conditions"]}) else 0 if (c not in {x["condition"] for x in H[i]["conditions"]} and c not in {x["condition"] for x in S[i]["conditions"]}) else -1 for i in ids])
    keep = y >= 0
    if y[keep].sum() < 15: continue
    a = {"raw_full": [], "z_full": [], "z_window": []}
    for n, i in enumerate(ids):
        s, e = Eo[n]; sc = Es[s:e]; rw = Eraw[s:e]
        jm, ju, jd = kidx[(c, "meaning")], kidx[(c, "up")], kidx[(c, "down")]
        a["raw_full"].append(max(rw[0, ju], rw[0, jd]))
        z = (sc - rmean) / rstd; a["z_full"].append(max(z[0, ju], z[0, jd])); a["z_window"].append(max(z[:, ju].max(), z[:, jd].max()))
        if y[n] == 1:
            d = {x["condition"]: x["direction"] for x in H[i]["conditions"]}.get(c); dz = z[:, ju].max() - z[:, jd].max()
            dir_n += 1; dir_ok += ((dz > 0) == (d == "up"))
    per[c] = {k: round(float(roc_auc_score(y[keep], np.array(v)[keep])), 3) for k, v in a.items()}; per[c]["n_pos"] = int(y[keep].sum())
    for k in res: res[k].append(per[c][k])
out = {"conditions_scored": len(per), "mean_auc": {k: round(float(np.mean(v)), 3) for k, v in res.items()}, "conditions_auc_0.75_or_more_window": sum(1 for p in per.values() if p["z_window"] >= 0.75),
       "direction_accuracy_agreed_items": round(dir_ok / max(dir_n, 1), 3), "direction_n": dir_n, "per_condition": per, "items": len(ids), "probes_generated": len(keys)}
json.dump(out, open(H0 / "runs/embedprobe/yield.json", "w"), indent=1); print(json.dumps({k: v for k, v in out.items() if k != "per_condition"}, indent=1))
print(sorted(((p["z_window"], c) for c, p in per.items()), reverse=True)[:5], sorted(((p["z_window"], c) for c, p in per.items()))[:5])

# routing: which condition(s) to ask about. For items where both models agree on at least one condition, is an agreed condition in the top-k?
cs = lambda L: {x["condition"] for x in L["conditions"]}
modes = {"raw_full": [], "z_full": [], "z_window": []}; up_share = []
for n, i in enumerate(ids):
    A = cs(H[i]) & cs(S[i])
    if not A: continue
    s0, e0 = Eo[n]; sc = Es[s0:e0]; rw = Eraw[s0:e0]; z = (sc - rmean) / rstd
    sc_raw = [max(rw[0, kidx[(c, "up")]], rw[0, kidx[(c, "down")]]) for c in C]
    sc_zf = [max(z[0, kidx[(c, "up")]], z[0, kidx[(c, "down")]]) for c in C]
    sc_zw = [max(z[:, kidx[(c, "up")]].max(), z[:, kidx[(c, "down")]].max()) for c in C]
    for name, v in (("raw_full", sc_raw), ("z_full", sc_zf), ("z_window", sc_zw)):
        order = [C[j] for j in np.argsort(v)[::-1]]; modes[name].append([int(any(c in A for c in order[:k])) for k in (1, 3, 5)])
    dd = {x["condition"]: x["direction"] for x in H[i]["conditions"]}
    up_share += [dd[c] == "up" for c in A if c in dd]
out["routing_hit_rate_top1_top3_top5"] = {k: [round(float(np.mean([r[j] for r in v])), 3) for j in range(3)] for k, v in modes.items()}; out["routing_items"] = len(modes["raw_full"])
out["direction_majority_baseline_up"] = round(float(np.mean(up_share)), 3)
json.dump(out, open(H0 / "runs/embedprobe/yield.json", "w"), indent=1); print(json.dumps({k: out[k] for k in ("routing_hit_rate_top1_top3_top5", "routing_items", "direction_majority_baseline_up")}, indent=1))
