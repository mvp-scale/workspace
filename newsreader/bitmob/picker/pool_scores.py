"""Free-picker scores for the whole training-side pool (round 5 add-on). One pass of the round-4 multi-head model (CPU, nice) over the pool -> data/picker/pool_scores.jsonl:
id, title, description, date, gate_margin (borderline read-or-skip: higher = closer to the engine's gate cut), worldwide (P(region GLOBAL) + keyword cue), us_uk_global_close, per-condition score (reading max-attr prob per key, 78), any_condition, picker version.
Pool = stories of data/trainset/{night1,round1,round2,loop1..5}.jsonl and data/jev-labels/*.jsonl, minus Clef-labelled ids, minus test ids (asserted), deduped by normalised title.
  nice -n 10 /workspace/kev/.venv/bin/python newsreader/bitmob/picker/pool_scores.py"""
import os, sys, json, glob, re, time
os.environ["CUDA_VISIBLE_DEVICES"] = ""; sys.path[:0] = ["/workspace/newsreader/bitmob/mh", "/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo"]
import numpy as np, torch
from mh_common import load, predict
torch.set_num_threads(6); W = "/workspace/data"; MODEL = f"{W}/kaggle/mh_r4/out/mh"; VERSION = "pool_scores v1: mh_r4 model + keyword cues, 2026-10-22"
test = {json.loads(l)["id"] for f in ("test_in", "test") for l in open(f"{W}/clef-labels/{f}.jsonl")}
done = set()
for f in glob.glob(f"{W}/clef-labels/*.jsonl"):
    if os.path.basename(f).startswith(("test", "r5_in", "r3_in", "train_in", "r1_", "country_in", "pilot4", "prelabelled")) or f.endswith("_in.jsonl"): continue
    for l in open(f):
        try: done.add(json.loads(l)["id"])
        except Exception: pass
norm = lambda t: re.sub(r"[^a-z0-9 ]", "", (t or "").lower()).strip()
seen, rows = set(), []
LOOK = {}
for f in glob.glob(f"{W}/trainset/*.jsonl") + [f"{W}/clef-labels/country_in.jsonl"]:
    for l in open(f):
        try: r = json.loads(l)
        except Exception: continue
        if r.get("id") and r.get("title"): LOOK.setdefault(r["id"], r)
files = [f"{W}/trainset/{n}.jsonl" for n in ("night1", "round1", "round2", "loop1", "loop2", "loop3", "loop4", "loop5")] + sorted(glob.glob(f"{W}/jev-labels/*.jsonl"))
for f in files:
    for l in open(f):
        try: r = json.loads(l)
        except Exception: continue
        i = r.get("id")
        if not r.get("title") and i in LOOK: r = LOOK[i]
        if not r.get("title"): continue
        if not i or i in test or i in done or i in seen: continue
        t = norm(r.get("title"))
        if t in seen: continue
        seen.add(i); seen.add(t); rows.append({"id": i, "title": r["title"], "description": (r.get("description") or "")[:250], "date": r.get("date") or r.get("day")})
assert not ({r["id"] for r in rows} & test), "test id in pool"; print("pool", len(rows), "test ids excluded:", len(test), flush=True)
CUE = re.compile(r"\b(global|globally|worldwide|world-wide|around the world|across the world|countries|international|worldwide|the world|nations|united nations|g20|g7|opec|who |imf|world bank)\b", re.I)
model, tok, K = load(MODEL); model.cond_cuts = None; G = K["gate"]; REG = K["region"]; COND = K["cond"]; gi = {k: i for i, k in enumerate(G)}; grp = {}
for j, k in enumerate(COND): d, dr, i = k.split("|"); grp.setdefault(f"{d}|{dr}", []).append(j)
out = open(f"{W}/picker/pool_scores.jsonl", "w") if os.path.isdir(f"{W}/picker") else (os.makedirs(f"{W}/picker") or open(f"{W}/picker/pool_scores.jsonl", "w"))
t0 = time.time(); bs = 256
for s in range(0, len(rows), bs):
    chunk = rows[s:s + bs]; H = predict(model, tok, [f"{r['title']}. {r['description']}" for r in chunk])
    for n, r in enumerate(chunk):
        g = H["gate"][n]; margin = -min(abs(max(g[gi["g|happened"]], g[gi["g|announced"]]) - .5), abs(g[gi["g|opinion"]] - .5), abs(g[gi["x|recent"]] - .3))
        pr = H["region"][n]; pg = float(pr[REG.index("GLOBAL")]); pc = np.sort(H["country"][n])[::-1]; cue = bool(CUE.search(r["title"] + " " + r["description"]))
        cs = {k: round(float(H["cond"][n][j].max()), 4) for k, j in grp.items()}
        r.update(gate_margin=round(float(margin), 4), worldwide=round(pg + (0.3 if cue else 0), 4), p_global_region=round(pg, 4), top2_gap=round(float(pc[0] - pc[1]), 4), cue=cue, any_condition=max(cs.values()), cond=cs, version=VERSION)
        out.write(json.dumps(r) + "\n")
    if (s // bs) % 10 == 0: print(s, f"{time.time() - t0:.0f}s", flush=True)
out.close(); print("done", len(rows))
