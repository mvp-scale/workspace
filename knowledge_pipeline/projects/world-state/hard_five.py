import json, os, glob, itertools
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np
from model2vec import StaticModel
H0 = __import__("pathlib").Path(__file__).resolve().parent; J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
m = StaticModel.from_pretrained("minishlab/potion-base-8M"); base = json.load(open(H0 / "specs/world_state_v2_frozen_haiku.json")); P = {}
for l in [l for l in base["guideline"] if " | up = " in l and not l.startswith("CONDITIONS")]:
    cid, rest = l.split(":", 1); p = [x.strip() for x in rest.split("|")]; P[cid] = (p[1].replace("up =", "").strip(), p[2].replace("down =", "").strip())
C = sorted(P); PE = m.encode([t for c in C for t in P[c]]); unit = lambda a: a / (np.linalg.norm(a, axis=-1, keepdims=True) + 1e-9)
pool = {r["id"]: r for r in J(H0 / "data/pool_train.jsonl")}; ids = json.load(open(H0 / "runs/bakeoff/b300/ids.json")); allid = [i for v in ids.values() for i in v]
H = {}; S = {}
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): H[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): S[r["item_id"]] = r["label"]
B = {f: {r["item_id"]: {k: v for k, v in r["label"].items() if v != "none"} for r in J(H0 / f"runs/bakeoff/b300/{f}/labels.jsonl")} for f in ("haiku", "sonnet")}
mu = m.encode([pool[i]["text"] for i in list(pool)[:3000]]).mean(0); cen = lambda x: unit(x - mu); PEc = cen(PE)
rows = []
for i in allid:
    if i not in B["haiku"] or i not in B["sonnet"] or i not in H or i not in S: continue
    sets = {"A-Haiku": {c["condition"] + ":" + c["direction"] for c in H[i]["conditions"]}, "A-Sonnet": {c["condition"] + ":" + c["direction"] for c in S[i]["conditions"]},
            "B-Haiku": {k + ":" + v for k, v in B["haiku"][i].items()}, "B-Sonnet": {k + ":" + v for k, v in B["sonnet"][i].items()}}
    names = {k: {x.split(":")[0] for x in v} for k, v in sets.items()}
    if sum(1 for v in names.values() if v) < 3: continue
    jac = [len(a & b) / len(a | b) for a, b in itertools.combinations(names.values(), 2) if a | b]
    s = cen(m.encode([pool[i]["text"]])) @ PEc.T; s = np.maximum(s[0, 0::2], s[0, 1::2]); top = [C[j] for j in np.argsort(s)[::-1][:3]]
    rows.append((np.mean(jac), i, sets, top, H[i]["topic"]))
rows.sort(key=lambda r: r[0]); seen = set(); pick = []
for r in rows:
    if r[4] in seen: continue
    seen.add(r[4]); pick.append(r)
    if len(pick) == 5: break
for n, (j, i, sets, top, tp) in enumerate(pick, 1):
    print(f"\n#{n}  [{tp}]  agreement across the four AI answers {j:.2f}"); print(pool[i]["text"].replace("\n", " "))
    for k, v in sets.items(): print(f"   {k:9s}", ", ".join(sorted(v)) or "none")
    print("   Embedding top-3:", ", ".join(top))
