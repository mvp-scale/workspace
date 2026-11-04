"""Does the embedding probe support option B's extra 'yes' answers? Pooled AUC over (item, condition) pairs, raw cosine vs per-probe z-score. CPU only."""
import json, os, glob, random, pathlib
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np
from sklearn.metrics import roc_auc_score
from model2vec import StaticModel
H0 = pathlib.Path(__file__).resolve().parent; J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
m = StaticModel.from_pretrained("minishlab/potion-base-8M"); base = json.load(open(H0 / "specs/world_state_v2_frozen_haiku.json"))
P = {}
for l in [l for l in base["guideline"] if " | up = " in l and not l.startswith("CONDITIONS")]:
    cid, rest = l.split(":", 1); p = [x.strip() for x in rest.split("|")]; P[cid] = (p[1].replace("up =", "").strip(), p[2].replace("down =", "").strip())
C = sorted(P); PE = m.encode([t for c in C for t in P[c]]); unit = lambda a: a / (np.linalg.norm(a, axis=-1, keepdims=True) + 1e-9)
pool = {r["id"]: r["text"] for r in J(H0 / "data/pool_train.jsonl")}; ids = json.load(open(H0 / "runs/bakeoff/b300/ids.json"))
allb = {i for v in ids.values() for i in v}; ref = random.Random(2).sample([i for i in pool if i not in allb], 2000)
R = m.encode([pool[i] for i in ref]); mu = R.mean(0); cen = lambda x: unit(x - mu); PEc = cen(PE)
Rs = cen(R) @ PEc.T; Rs = np.maximum(Rs[:, 0::2], Rs[:, 1::2]); rm, rsd = Rs.mean(0), Rs.std(0) + 1e-9
B = {f: {r["item_id"]: {k for k, v in r["label"].items() if v != "none"} for r in J(H0 / f"runs/bakeoff/b300/{f}/labels.jsonl")} for f in ("haiku", "sonnet")}
out = {}
for st, l in ids.items():
    l = [i for i in l if i in B["haiku"] and i in B["sonnet"]]; E = m.encode([pool[i] for i in l]); S = cen(E) @ PEc.T; S = np.maximum(S[:, 0::2], S[:, 1::2]); Z = (S - rm) / rsd
    y = np.array([[int(c in B["haiku"][i] and c in B["sonnet"][i]) for c in C] for i in l])
    out[st] = {"pairs": int(y.size), "positives": int(y.sum()), "auc_raw": round(float(roc_auc_score(y.ravel(), S.ravel())), 3) if 0 < y.sum() < y.size else None, "auc_z": round(float(roc_auc_score(y.ravel(), Z.ravel())), 3) if 0 < y.sum() < y.size else None}
json.dump(out, open(H0 / "runs/bakeoff/b300/embed_support.json", "w"), indent=1); print(json.dumps(out, indent=1))
