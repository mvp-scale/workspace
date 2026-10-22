"""Round 6 warm-start dataset (D-0038): NEW Clef rows + a REPLAY sample of the round-5 training set, one training dir. Never the frozen test; the tune set stays the round-5 tune set (new rows never enter it).
  /workspace/kev/.venv/bin/python newsreader/bitmob/mh/build_warm.py OUT_DIR TUNE_DIR_COPY --new f1.jsonl [f2.jsonl ...] [--replay 6000] [--base data/kaggle/mh_r5] [--seed 6]
New rows: Clef records (normal or fast mode; 'fast': true rows have P(328)+read only and train gate/scope/cond/reading, other heads masked). Built by build_mh_data2.py (--no_old, no Jev, tune_frac 0), so labels use the same code as every round.
Replay: from BASE/ds (targets.npz arrays already built): priority 1 rows holding positives of rare reading keys (< 200 positives in the pool; at most half of N), 2 Clef rows (w>=2), 3 random Jev rows; a replay row whose id is in the new set is dropped (the new label wins).
Asserts: no frozen-test id in training, no tune id in training, ids unique. Per-key reading pos_weight recomputed on the merged rows."""
import os, sys, json, argparse, subprocess, shutil, tempfile
import numpy as np
sys.path[:0] = ["/workspace/newsreader/bitmob/mh"]
ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("tune"); ap.add_argument("--new", nargs="+", required=True); ap.add_argument("--replay", type=int, default=6000)
ap.add_argument("--base", default="/workspace/data/kaggle/mh_r5"); ap.add_argument("--seed", type=int, default=6); a = ap.parse_args()
W = "/workspace/data"; PY = "/workspace/kev/.venv/bin/python"
test = set()
for f in ("test_in", "test", "test_noraw_partial"):
    p = f"{W}/clef-labels/{f}.jsonl"
    if os.path.exists(p): test |= {json.loads(l)["id"] for l in open(p) if l.strip()}
for f in a.new: assert "test" not in os.path.basename(f), f"refusing {f}"
bk = json.load(open(f"{a.base}/ds/keys.json")); tune_ids = set(bk["tune_ids"])
# new rows: drop ids that are test or tune (tune stays untouched) BEFORE building
tmp = tempfile.mkdtemp(prefix="warm_new_"); clean = []
for f in a.new:
    out = f"{tmp}/{os.path.basename(f)}"; n = d = 0
    with open(out, "w") as g:
        for l in open(f):
            if not l.strip(): continue
            r = json.loads(l); n += 1
            if r["id"] in test or r["id"] in tune_ids: d += 1; continue
            g.write(l)
    print(f"new rows {os.path.basename(f)}: {n} read, {d} dropped (test/tune ids)"); clean.append(out)
subprocess.run([PY, "/workspace/newsreader/bitmob/mh/build_mh_data2.py", f"{tmp}/new", f"{tmp}/unused", "--clef", *clean, "--jev", "--no_old", "--tune_frac", "0"], check=True, env={**os.environ, "WE_RULES": "rules_v2", "WORLD_GPU": "0"})
NK = json.load(open(f"{tmp}/new/keys.json")); NT = json.load(open(f"{tmp}/new/texts.json")); NZ = dict(np.load(f"{tmp}/new/targets.npz"))
BK = bk; BT = json.load(open(f"{a.base}/ds/texts.json")); BZ = dict(np.load(f"{a.base}/ds/targets.npz"))
for k in ("gate", "scope", "cond", "topic_c", "topic_y", "region", "country", "expected", "reading", "levels", "severity"): assert NK[k] == BK[k], f"key layout differs for {k}"
new_ids = set(NK["ids"]); rng = np.random.RandomState(a.seed); N0 = len(BT)
cand = np.array([i for i in range(N0) if BK["ids"][i] not in new_ids]); w = BZ["w"][cand]; pos = (BZ["reading"] * BZ["reading_mask"])[cand]
rare = pos.sum(0) < 200; rare_rows = cand[(pos[:, rare] > 0).any(1)] if rare.any() else np.array([], int)
if len(rare_rows) > a.replay // 2: rare_rows = rng.choice(rare_rows, a.replay // 2, replace=False)
chosen = list(rare_rows); have = set(chosen)
clef_rows = [i for i in cand[w >= 2] if i not in have]; rng.shuffle(clef_rows); take = clef_rows[:max(0, a.replay - len(chosen))]; chosen += take; have |= set(take)
jev_rows = [i for i in cand if i not in have]; rng.shuffle(jev_rows); chosen += jev_rows[:max(0, a.replay - len(chosen))]; chosen = sorted(set(chosen))
print(f"replay: {len(chosen)} rows (rare-key positive rows {len(rare_rows)}, rare keys {int(rare.sum())}, Clef rows {len([i for i in chosen if BZ['w'][i] >= 2])}) from {N0}")
M = {}
for k in NZ:
    if k == "reading_pw": continue
    M[k] = np.concatenate([NZ[k], BZ[k][chosen]], 0)
ids = NK["ids"] + [BK["ids"][i] for i in chosen]; texts = NT + [BT[i] for i in chosen]
assert len(set(ids)) == len(ids), "duplicate ids"; assert not (set(ids) & test), "frozen-test id in the warm training set"; assert not (set(ids) & tune_ids), "tune id in the warm training set"
pos = (M["reading"] * M["reading_mask"]).sum(0); neg = ((1 - M["reading"]) * M["reading_mask"]).sum(0); M["reading_pw"] = np.tile(np.clip(np.sqrt(neg / np.maximum(pos, 1)), 1, 20)[None, :], (len(ids), 1)).astype(np.float32)
os.makedirs(a.out, exist_ok=True); np.savez_compressed(f"{a.out}/targets.npz", **M); json.dump(texts, open(f"{a.out}/texts.json", "w"))
keys = {k: v for k, v in NK.items() if k != "ids"}; json.dump({"ids": ids, "n_new": len(NK["ids"]), "n_replay": len(chosen), **keys}, open(f"{a.out}/keys.json", "w"))
shutil.copytree(f"{a.base}/tune", a.tune, dirs_exist_ok=True); shutil.rmtree(tmp)
print(f"warm set: {len(ids)} rows = {len(NK['ids'])} new + {len(chosen)} replay; heads rows:", {h: int(M['m_' + h].sum()) for h in ("gate", "scope", "cond", "topic_c", "topic_y", "region", "country", "reading")}, "| tune copied", a.tune)
