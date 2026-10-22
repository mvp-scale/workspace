"""Round 5 picker (D-0038): per-condition (78 dial|direction keys) score of 'Clef will read this condition', fitted on Clef-labelled TRAIN stories only, used to pick 3,000 stories for Clef labelling.
  /workspace/kev/.venv/bin/python newsreader/bitmob/picker/pick_r5.py [--n 3000] [--aimed 2400] [--seed 5]
Signals (all CPU, free): (1) free NLP lemmas (compromise + wink via js/nlp.cjs); (2) per-key logistic on lemma tf-idf trained on Clef labels (OOF for the stack); (3) per-key logistic trained on Jev reading labels of
the Jev-labelled stories (weak, 20k, OOF by fold); (4) the story's own stored Jev reading strength for that key. A pooled logistic over (story,key) pairs stacks them, fitted on out-of-fold values of the Clef train stories.
BitMob (mh) scores are NOT used: BitMob was trained on these stories, so its scores on the Clef train stories would be optimistic and the stack would over-trust it (stated deviation from the 'S2 + BitMob' stack of the recon note).
Never uses a frozen-test id: the Clef test (test_in.jsonl / test.jsonl) is asserted absent from every fit and from the pool, also by normalised title. Pool = old Jev stories (night1 train part, round1, round2, loop1-5; NOT testA/length/kt-wiki/jclef/smoke)
+ data/jev-labels/*.jsonl + data/clef-labels/country_in.jsonl stories, minus anything already Clef-labelled. The news queue (sqlite) is skipped (no Jev labels, needs a separate extract)."""
import os, sys, json, re, glob, subprocess, argparse, collections, tempfile, hashlib
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D); W = "/workspace/data"
import numpy as np
from lib import load_jsonl
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=3000); ap.add_argument("--aimed", type=int, default=2400); ap.add_argument("--seed", type=int, default=5); ap.add_argument("--cache", default=D + "/r5_cache"); a = ap.parse_args()
os.makedirs(a.cache, exist_ok=True); rng = np.random.RandomState(a.seed)
norm = lambda t: re.sub(r"[^a-z0-9 ]", "", (t or "").lower()).strip()
# ---- ids and titles that must never be used ----
test_ids = {json.loads(l)["id"] for f in ("test_in", "test") for l in open(f"{W}/clef-labels/{f}.jsonl") if l.strip()}
test_titles = {norm(json.loads(l)["title"]) for l in open(f"{W}/clef-labels/test_in.jsonl")}
# ---- Clef labelled train ----
clef = {}
for f in ("r1_local", "r1b", "pilots_train", "kaggle_pilot2_train", "r3"):
    for l in open(f"{W}/clef-labels/{f}.jsonl"):
        r = json.loads(l)
        if r.get("read") is not None: clef[r["id"]] = r
assert not (set(clef) & test_ids), "frozen test id in the Clef train set"; print(f"ASSERT ok: 0 of {len(clef)} Clef train ids are frozen-test ids ({len(test_ids)} test ids)")
KEYS = sorted({f"{x['dial']}|{x['direction']}" for r in clef.values() for x in r["read"]["readings"] if x["direction"] != "conflict"}); ALLK = None
# the 78 keys come from the engine's dial list (39 dials x up/down)
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo"]
import classify as C
ALLK = sorted({f"{d}|{u}" for (d, u) in C.ATTRS}); KI = {k: i for i, k in enumerate(ALLK)}; print("keys", len(ALLK))
def keys_of(rs, jev=False): return {f"{x['dial']}|{x['direction']}": float(x.get("strength", 1.0)) for x in rs if x["direction"] != "conflict"}
# ---- pool ----
stories = {}   # id -> dict(title, desc, date, jev {key: strength}, src)
def add(i, t, d, day, jev, src):
    if i in stories or i in test_ids: return
    stories[i] = {"id": i, "title": t or "", "description": (d or "")[:250], "date": day, "jev": jev, "src": src}
for f in ("night1", "round1", "round2", "loop1", "loop2", "loop3", "loop4", "loop5"):
    for l in open(f"{W}/trainset/{f}.jsonl"):
        if not l.strip(): continue
        r = json.loads(l); add(r["id"], r["title"], r["description"], r.get("date"), keys_of(r.get("engine_readings") or []), f"trainset/{f}")
for p in sorted(glob.glob(f"{W}/jev-labels/*.jsonl")):
    if "pilot" in p: continue
    for l in open(p):
        if not l.strip(): continue
        r = json.loads(l); st = r["state_text"]; t, d = (st.split(". ", 1) + [""])[:2]
        add(r["id"], t, d, r.get("day"), keys_of(r["read"]["readings"]), "jev-labels/" + os.path.basename(p))
for l in open(f"{W}/clef-labels/country_in.jsonl"):
    if not l.strip(): continue
    r = json.loads(l); add(r["id"], r["title"], r["description"], r.get("date"), {}, "country_in")
# jev-labels records carry state_text 'title. desc': keep original title/desc where the id is in the in-files for exact schema
for f in ("train_in", "r3_in", "country_in", "r1_local_in", "r1_kaggle_in"):
    for l in open(f"{W}/clef-labels/{f}.jsonl"):
        if not l.strip(): continue
        r = json.loads(l)
        if r["id"] in stories: stories[r["id"]].update(title=r["title"], description=(r["description"] or "")[:250], date=r.get("date"))
# Clef-labelled stories (for fitting) may also be missing from stories: add with their Jev readings if present
jev_of = {i: s["jev"] for i, s in stories.items()}
for i, r in clef.items():
    if i not in stories:
        t, d = (r["state_text"].split(". ", 1) + [""])[:2]; stories[i] = {"id": i, "title": t, "description": d, "date": r.get("day"), "jev": {}, "src": "clef-only"}
    stories[i]["text"] = r["state_text"]
for s in stories.values(): s.setdefault("text", f"{s['title']}. {s['description']}")
clef_titles = {norm(stories[i]["title"]) for i in clef}
pool = []; seen_t = set(test_titles) | clef_titles; dup = collections.Counter()
for i, s in stories.items():
    if i in clef: continue
    t = norm(s["title"])
    if not t or len(s["description"]) < 20: dup["short"] += 1; continue
    if t in seen_t: dup["title_dup_or_test_title"] += 1; continue
    seen_t.add(t); pool.append(s)
assert not any(s["id"] in test_ids for s in pool) and not any(norm(s["title"]) in test_titles for s in pool); print(f"ASSERT ok: pool {len(pool)} stories, 0 frozen-test ids/titles; dropped {dict(dup)}")
# ---- NLP lemmas (cached) ----
def nlp(rows, name):
    out = f"{a.cache}/{name}.nlp.jsonl"; inp = f"{a.cache}/{name}.in.jsonl"
    if os.path.exists(out) and sum(1 for _ in open(out)) == len(rows): return {j["id"]: j for j in map(json.loads, open(out))}
    open(inp, "w").write("\n".join(json.dumps({"id": r["id"], "state_text": r["text"]}) for r in rows) + "\n"); subprocess.check_call(["node", D + "/js/nlp.cjs", inp, out]); return {j["id"]: j for j in map(json.loads, open(out))}
allrows = [stories[i] for i in clef] + pool; N = nlp(allrows, "all"); doc = lambda i: " ".join(N[i]["lem"])
cid = list(clef); Xc_txt = [doc(i) for i in cid]; Pxt = [doc(s["id"]) for s in pool]
vec = TfidfVectorizer(sublinear_tf=True, ngram_range=(1, 2), min_df=3, max_features=60000).fit(Xc_txt + Pxt + [doc(i) for i in stories if i not in clef and i in N][:0])
Xc = vec.transform(Xc_txt); Xp = vec.transform(Pxt)
Yc = np.zeros((len(cid), len(ALLK)), np.int8)
for n, i in enumerate(cid):
    for k in keys_of(clef[i]["read"]["readings"]): Yc[n, KI[k]] = 1
pos = Yc.sum(0); print("Clef positives per key: median", int(np.median(pos)), "keys<50:", int((pos < 50).sum()), "zero:", int((pos == 0).sum()))
# Jev weak labels over all Jev-labelled stories (pool + Clef train): Yj
jid = [i for i in list(clef) + [s["id"] for s in pool]]; Yj = np.zeros((len(jid), len(ALLK)), np.int8); Sj = np.zeros((len(jid), len(ALLK)), np.float32)
for n, i in enumerate(jid):
    for k, v in stories[i]["jev"].items(): Yj[n, KI[k]] = 1; Sj[n, KI[k]] = v
Xj = vec.transform([doc(i) for i in jid]); jpos = {i: n for n, i in enumerate(jid)}
def fitlr(X, y, C_=1.0):
    if y.sum() < 3 or (1 - y).sum() < 3: return None
    return LogisticRegression(C=C_, class_weight="balanced", max_iter=400, solver="liblinear").fit(X, y)
def dec(m, X): return np.full(X.shape[0], -3.0) if m is None else m.decision_function(X)
# ---- OOF over Clef train stories (5 folds by story) ----
folds = np.arange(len(cid)) % 5; rng.shuffle(folds); Fc = np.full((len(cid), len(ALLK)), -3.0); Fj = np.full((len(cid), len(ALLK)), -3.0)
cj_idx = np.array([jpos[i] for i in cid])
for f in range(5):
    tr = np.where(folds != f)[0]; te = np.where(folds == f)[0]
    jmask = np.ones(len(jid), bool); jmask[cj_idx[te]] = False
    for k in range(len(ALLK)):
        Fc[te, k] = dec(fitlr(Xc[tr], Yc[tr, k]), Xc[te]); Fj[te, k] = dec(fitlr(Xj[jmask], Yj[jmask, k], 0.5), Xc[te])
    print("fold", f, "done", flush=True)
# ---- stack: pooled over (story,key) ----
def feats(fc, fj, sj, kprior): return np.column_stack([fc, fj, sj, (sj > 0).astype(float), np.repeat(kprior[None, :], fc.shape[0], 0).ravel() if False else kprior])
kprior = np.log((pos + 1) / (len(cid) + 2)).astype(float)
F = np.column_stack([Fc.ravel(), Fj.ravel(), Sj[cj_idx].ravel(), (Sj[cj_idx] > 0).ravel().astype(float), np.tile(kprior, len(cid))]); y = Yc.ravel()
stack = LogisticRegression(C=1.0, class_weight=None, max_iter=500).fit(F, y); print("stack coefs [clef_text, jev_text, jev_strength, jev_fired, key_prior]:", np.round(stack.coef_[0], 3).tolist())
oof = stack.predict_proba(F)[:, 1].reshape(len(cid), len(ALLK))
# ---- final models on all training data, score pool ----
Pc = np.zeros((len(pool), len(ALLK))); Pj = np.zeros_like(Pc)
for k in range(len(ALLK)): Pc[:, k] = dec(fitlr(Xc, Yc[:, k]), Xp); Pj[:, k] = dec(fitlr(Xj, Yj[:, k], 0.5), Xp)
Sp = np.array([[stories[s["id"]]["jev"].get(k, 0.0) for k in ALLK] for s in pool], np.float32)
Fp = np.column_stack([Pc.ravel(), Pj.ravel(), Sp.ravel(), (Sp > 0).ravel().astype(float), np.tile(kprior, len(pool))]); prob = stack.predict_proba(Fp)[:, 1].reshape(len(pool), len(ALLK))
# ---- pick ----
need = np.maximum(50 - pos, 0); rare = [k for k in range(len(ALLK)) if pos[k] < 50]
quota = np.zeros(len(ALLK)); w = np.minimum(need, 60).astype(float); quota[rare] = w[rare] / w[rare].sum() * a.aimed; quota = np.maximum(np.floor(quota), 3).astype(int)
while quota.sum() > a.aimed: quota[np.argmax(quota)] -= 1
taken = {}; order = sorted(rare, key=lambda k: -quota[k]); left = quota.copy(); cand = {k: np.argsort(-prob[:, k]) for k in rare}; ptr = {k: 0 for k in rare}
while (left > 0).any():
    prog = False
    for k in order:
        if left[k] <= 0: continue
        while ptr[k] < len(pool) and int(cand[k][ptr[k]]) in taken: ptr[k] += 1
        if ptr[k] >= len(pool): left[k] = 0; continue
        j = int(cand[k][ptr[k]]); taken[j] = k; left[k] -= 1; prog = True
    if not prog: break
rest = [j for j in range(len(pool)) if j not in taken]; rnd = rng.choice(rest, a.n - len(taken), replace=False)
picked = [(j, ALLK[k], float(prob[j, k])) for j, k in taken.items()] + [(int(j), "random", float(prob[j].max())) for j in rnd]
assert not any(pool[j]["id"] in test_ids or pool[j]["id"] in clef for j, _, _ in picked); print(f"ASSERT ok: {len(picked)} picked, none in test ids or already Clef-labelled")
with open(f"{W}/clef-labels/r5_in.jsonl", "w") as f:
    for j, pk, sc in picked: s = pool[j]; f.write(json.dumps({"id": s["id"], "title": s["title"], "description": s["description"], "date": s["date"], "picked_for": pk, "pick_score": round(sc, 4)}) + "\n")
# ---- report ----
pj = np.array([j for j, _, _ in picked]); expk = prob[pj].sum(0); aimed_j = np.array([j for j, k in taken.items()]); exp_aimed = prob[aimed_j].sum(0)
# OOF precision check: among Clef-train (story,key) pairs, stack prob calibration in the top bins
bins = [(0.5, 1.01), (0.3, 0.5), (0.15, 0.3), (0.05, 0.15)]; cal = {f"{lo}-{min(hi,1):.2f}": {"pairs": int(((oof >= lo) & (oof < hi)).sum()), "observed_rate": round(float(Yc[(oof >= lo) & (oof < hi)].mean()), 3) if ((oof >= lo) & (oof < hi)).any() else None, "mean_pred": round(float(oof[(oof >= lo) & (oof < hi)].mean()), 3) if ((oof >= lo) & (oof < hi)).any() else None} for lo, hi in bins}
def oof_prec(k):
    thr = np.sort(prob[[j for j, kk in taken.items() if kk == k], k])[0] if any(kk == k for kk in taken.values()) else None
    if thr is None: return None
    m = oof[:, k] >= thr; return {"oof_stories_at_or_above_pick_threshold": int(m.sum()), "oof_precision": round(float(Yc[m, k].mean()), 3) if m.any() else None}
tab = []
for k in range(len(ALLK)):
    nk = sum(1 for kk in taken.values() if kk == k); e = float(expk[k])
    tab.append({"key": ALLK[k], "clef_train_positives_now": int(pos[k]), "rare_under_50": bool(pos[k] < 50), "picked_for_it": nk, "expected_new_positives_all_picks": round(e, 1), "expected_new_from_aimed_picks": round(float(exp_aimed[k]), 1),
                "expected_total_after": round(pos[k] + e, 1), "reaches_50": bool(pos[k] + e >= 50), "mean_stack_prob_of_its_picks": round(float(np.mean([prob[j, k] for j, kk in taken.items() if kk == k])), 3) if nk else None, "oof_check": oof_prec(k) if nk else None})
exp_pos_aimed_story = float(np.mean(prob[aimed_j].sum(1))); exp_pos_rand = float(np.mean(prob[np.array(rnd)].sum(1)))
rep = {"made": __import__("time").strftime("%FT%T"), "n_picked": len(picked), "aimed": len(taken), "random": len(rnd), "pool_size": len(pool), "clef_train_stories": len(cid), "keys_under_50": len(rare),
       "median_positives_now": int(np.median(pos)), "expected_new_condition_examples_total": round(float(expk.sum()), 0), "expected_new_per_aimed_story": round(exp_pos_aimed_story, 2), "expected_new_per_random_story": round(exp_pos_rand, 2),
       "expected_conditions_reaching_50": int(sum(t["reaches_50"] for t in tab)), "keys_reaching_50_now": int((pos >= 50).sum()), "stack_coefs": dict(zip(["clef_text", "jev_text", "jev_strength", "jev_fired", "key_prior"], np.round(stack.coef_[0], 3).tolist())),
       "calibration_oof_pairs": cal, "how_measured": "stack probabilities of the picked stories (expected yield = sum of per-key probabilities); calibration checked on 5-fold out-of-fold Clef train pairs (observed vs predicted rate per bin); per-key oof_check = precision among OOF Clef stories scoring at/above that key's lowest pick score",
       "not_used": ["BitMob scores (saw these stories in training)", "news queue sqlite (no Jev labels)"], "pool_sources": dict(collections.Counter(s["src"].split("/")[0] for s in pool)), "table": tab}
json.dump(rep, open(f"{W}/clef-labels/r5_pick_report.json", "w"), indent=1)
print(json.dumps({k: v for k, v in rep.items() if k not in ("table", "calibration_oof_pairs")}, indent=1)); print(json.dumps(cal))
