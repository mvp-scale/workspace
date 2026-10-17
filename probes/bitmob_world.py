"""BitMob v1 on the world-knowledge set (MMLU, 14,042 four-option questions, 57 subjects, probes/v2/mmlu_*.jsonl).

BitMob v1 = a mob of members (encoders) + a tiny router.
  members  general potion-base-8M, code potion-code-16M-v2, science potion-science-8M, e5-small int8 (BitMob's encoder)
  readout  per member, one shared head scores each (question, option) pair from [q, o, q*o, |q-o|] (LogisticRegression C=1,
           balanced); the answer is the highest-scoring option; probabilities = softmax of the four scores
  router   LogisticRegression on the general pocket's question vector -> subject; each subject goes to the member that was
           best on it inside the training half only (inner 2-fold), so the router never sees test answers
Cross-fitting: items split in two halves within every subject (seeded); train on one half, answer the other, then swap, so
every item has a held-out answer. Also reported: every member alone, and a perfect router (best member per subject chosen
on the test answers themselves: a ceiling, not a result).
Writes data/pocket-test/bitmob_world.json and data/probe-runs-v2/bitmob-mmlu_<subject>/results.jsonl (Scenario lab format).
Run: HF_HOME=/workspace/data/hf models/embed-zs/.venv/bin/python probes/bitmob_world.py
"""
import json, sys, random, collections, pathlib, time
import numpy as np
from sklearn.linear_model import LogisticRegression
sys.path.insert(0, str(pathlib.Path(__file__).parent)); import pocket_test as pt

SEED = 20261016; L = ["A", "B", "C", "D"]
OUT = pathlib.Path("/workspace/data/pocket-test"); RUNS = pathlib.Path("/workspace/data/probe-runs-v2")
items = [json.loads(l) for f in sorted(pathlib.Path("/workspace/probes/v2").glob("mmlu_*.jsonl")) for l in open(f)]
for i in items: i["subject"] = i["family"][5:]
subjects = sorted({i["subject"] for i in items}); S = np.array([subjects.index(i["subject"]) for i in items])
ans = np.array([L.index(i["expected"]) for i in items])
rng = random.Random(SEED); half = np.zeros(len(items), int)
for s in subjects:
    ks = [k for k, i in enumerate(items) if i["subject"] == s]; rng.shuffle(ks)
    for k in ks[: len(ks) // 2]: half[k] = 1

# ---- vectors per member (cached) ----
cache = OUT / "mmlu_vectors.npz"; V = dict(np.load(cache)) if cache.exists() else {}
encs = pt.encoders(); members = list(encs)
for j, (name, enc) in enumerate(encs.items()):
    if f"q{j}" in V: continue
    t0 = time.time(); q = enc([i["state"] for i in items]); o = enc([str(i["question"]["criteria"][l]) for i in items for l in L]).reshape(len(items), 4, -1)
    V[f"q{j}"] = q / np.linalg.norm(q, axis=1, keepdims=True); V[f"o{j}"] = o / np.linalg.norm(o, axis=2, keepdims=True)
    print(f"encoded with {name} in {time.time() - t0:.0f} s", flush=True); np.savez(cache, **V)


def feat(j, ks):
    Q, O = V[f"q{j}"][ks], V[f"o{j}"][ks]
    return np.concatenate([np.repeat(Q[:, None], 4, 1), O, Q[:, None] * O, np.abs(Q[:, None] - O)], 2).reshape(len(ks) * 4, -1)


def fit_score(j, tr, te):
    """Train member j's shared head on items tr, return (n_te x 4) option scores for items te."""
    y = (np.arange(4)[None, :] == ans[tr][:, None]).astype(int).ravel()
    clf = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(feat(j, tr), y)
    return clf.decision_function(feat(j, te)).reshape(len(te), 4)


scores = np.zeros((len(members), len(items), 4)); routed = np.zeros(len(items), int); chosen = {}
for fold in (0, 1):
    tr = np.where(half != fold)[0]; te = np.where(half == fold)[0]
    # member answers on the held-out half
    for j in range(len(members)): scores[j, te] = fit_score(j, tr, te); print(f"fold {fold}: {members[j]} done", flush=True)
    # which member is best per subject, judged inside the training half only (inner 2-fold)
    inner = np.zeros(len(tr), int); r2 = random.Random(SEED + fold)
    for s in range(len(subjects)):
        ks = [x for x, k in enumerate(tr) if S[k] == s]; r2.shuffle(ks); inner[ks[: len(ks) // 2]] = 1
    right = np.zeros((len(members), len(tr)), bool)
    for j in range(len(members)):
        for f2 in (0, 1):
            a, b = tr[inner != f2], tr[inner == f2]
            right[j, np.where(inner == f2)[0]] = fit_score(j, a, b).argmax(1) == ans[b]
    best = {s: int(np.argmax([right[j, S[tr] == s].mean() for j in range(len(members))])) for s in range(len(subjects))}
    chosen[fold] = {subjects[s]: members[m] for s, m in best.items()}
    # the router: question vector (general pocket) -> subject -> that subject's member
    router = LogisticRegression(C=1.0, max_iter=3000).fit(V["q0"][tr], S[tr])
    guess = router.predict(V["q0"][te]); routed[te] = [best[g] for g in guess]
    print(f"fold {fold}: router subject accuracy {np.mean(guess == S[te]):.1%}", flush=True)

pred = {m: scores[j].argmax(1) for j, m in enumerate(members)}
bm = scores[routed, np.arange(len(items))]; pred["BitMob v1 (router)"] = bm.argmax(1)
perfect = np.array([max(range(len(members)), key=lambda j: np.mean(pred[members[j]][S == s] == ans[S == s])) for s in range(len(subjects))])
pred["perfect router (ceiling)"] = scores[perfect[S], np.arange(len(items))].argmax(1)

res = {"n": len(items), "chance": 0.25, "members": members, "router_choices": chosen, "results": {}}
print(f"\nMMLU, all {len(items)} questions, every answer held out (chance 25%; Clef Flash Q4 91.7%, Jev 91.6% on the same items)")
for name, p in pred.items():
    ok = p == ans; lo, hi = pt.wilson(ok.sum(), len(ok))
    per = {s: float(ok[S == k].mean()) for k, s in enumerate(subjects)}
    res["results"][name] = {"accuracy": float(ok.mean()), "ci": [lo, hi], "per_subject": per}
    print(f"  {name:32} {ok.mean():.1%}  [{lo:.1%}-{hi:.1%}]")
use = collections.Counter(members[m] for m in routed); res["routing_share"] = {k: v / len(items) for k, v in use.items()}
print("\nwhere the router sent questions:", {k: f"{v:.0%}" for k, v in res["routing_share"].items()})
json.dump(res, open(OUT / "bitmob_world.json", "w"), indent=1)

# Scenario lab format: one results.jsonl per subject, probabilities = softmax of BitMob's four option scores
ex = np.exp(bm - bm.max(1, keepdims=True)); P = ex / ex.sum(1, keepdims=True)
for k, s in enumerate(subjects):
    d = RUNS / f"bitmob-mmlu_{s}"; d.mkdir(parents=True, exist_ok=True)
    with open(d / "results.jsonl", "w") as f:
        for x in np.where(S == k)[0]:
            p = {l: float(P[x, n]) for n, l in enumerate(L)}; g = L[int(bm[x].argmax())]
            f.write(json.dumps({"task_id": items[x]["id"], "family": items[x]["family"], "split": items[x].get("split"), "group": None, "ts": time.time(),
                                "status": "ok", "ok": True, "valid": True, "correct": g == items[x]["expected"], "predicted": g, "probs": p, "probs_as_returned": p,
                                "probs_source": "bitmob v1: softmax of the routed member's option scores (held-out half, cross-fitted)", "model": "bitmob",
                                "member": members[routed[x]], "error": None}) + "\n")
print(f"wrote {OUT}/bitmob_world.json and {len(subjects)} result files under {RUNS}/bitmob-mmlu_*/")
