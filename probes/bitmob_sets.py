"""BitMob v1 on the published probe sets (probes/v2/<set>.jsonl, every set except the 57 MMLU subjects).

Same method as probes/bitmob_world.py:
  members  general potion-base-8M, code potion-code-16M-v2, science potion-science-8M, e5-small int8 (BitMob's encoder)
  head     per member and set, LogisticRegression(C=1, balanced) on the state vector -> the set's labels (BitMob reads the
           text only; the question wording is fixed per set, so it adds nothing to a per-set head)
  router   per set, the member with the best accuracy inside the training half only (inner 2-fold), never the test answers
Cross-fitting: each set split in two halves stratified by label (seeded); train on one, answer the other, then swap, so every
item has a held-out answer. Writes data/probe-runs-v2/bitmob-<set>/results.jsonl (Scenario lab format) and
data/pocket-test/bitmob_sets.json (per set: accuracy of every member and of BitMob, which member was chosen).
Run: HF_HOME=/workspace/data/hf models/embed-zs/.venv/bin/python probes/bitmob_sets.py
"""
import json, sys, random, collections, pathlib, time
import numpy as np
from sklearn.linear_model import LogisticRegression
sys.path.insert(0, str(pathlib.Path(__file__).parent)); import pocket_test as pt

SEED = 20261016
SETS = sorted(f.stem for f in pathlib.Path("/workspace/probes/v2").glob("*.jsonl") if not f.stem.startswith("mmlu_"))
RUNS = pathlib.Path("/workspace/data/probe-runs-v2"); OUT = pathlib.Path("/workspace/data/pocket-test")
encs = pt.encoders(); members = list(encs)


def halves(y, seed):
    """0/1 per item, stratified by label."""
    h = np.zeros(len(y), int); r = random.Random(seed)
    for lab in sorted(set(y)):
        ks = [k for k, v in enumerate(y) if v == lab]; r.shuffle(ks)
        for k in ks[: len(ks) // 2]: h[k] = 1
    return h


def fit_predict(X, y, tr, te, labels):
    """Probabilities over all labels for items te (a label never seen in training gets 0)."""
    if len(set(y[tr])) < 2: P = np.zeros((len(te), len(labels))); P[:, labels.index(y[tr][0])] = 1; return P
    clf = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(X[tr], y[tr])
    P = np.zeros((len(te), len(labels))); P[:, [labels.index(c) for c in clf.classes_]] = clf.predict_proba(X[te]); return P


summary = {}
for st in SETS:
    items = [json.loads(l) for l in open(f"/workspace/probes/v2/{st}.jsonl")]
    labels = list(items[0]["labels"]); y = np.array([i["expected"] for i in items])
    t0 = time.time(); X = {m: encs[m]([str(i["state"]) for i in items]) for m in members}
    P = {m: np.zeros((len(items), len(labels))) for m in members}; best_P = np.zeros((len(items), len(labels))); chose = {}
    h = halves(list(y), SEED)
    for fold in (0, 1):
        tr, te = np.where(h != fold)[0], np.where(h == fold)[0]
        for m in members: P[m][te] = fit_predict(X[m], y, tr, te, labels)
        # router: best member inside the training half (inner 2-fold), judged on training answers only
        inner = halves(list(y[tr]), SEED + 1 + fold); score = {}
        for m in members:
            ok = 0
            for f2 in (0, 1):
                a, b = tr[inner != f2], tr[inner == f2]
                ok += np.sum(np.array(labels)[fit_predict(X[m], y, a, b, labels).argmax(1)] == y[b])
            score[m] = ok / len(tr)
        pick = max(members, key=lambda m: score[m]); chose[fold] = pick; best_P[te] = P[pick][te]
    acc = {m: float(np.mean(np.array(labels)[P[m].argmax(1)] == y)) for m in members}
    pred = np.array(labels)[best_P.argmax(1)]; acc["BitMob v1"] = float(np.mean(pred == y))
    lo, hi = pt.wilson(int(np.sum(pred == y)), len(y))
    summary[st] = {"n": len(items), "chance": 1 / len(labels), "accuracy": acc, "bitmob_ci": [lo, hi], "member_chosen": chose}
    print(f"{st:24} n={len(items):4} chance {1/len(labels):4.0%} | BitMob {acc['BitMob v1']:5.1%} [{lo:.0%}-{hi:.0%}] via {chose[0].split()[0]}/{chose[1].split()[0]} | "
          + "  ".join(f"{m.split()[0]} {acc[m]:.0%}" for m in members) + f"  ({time.time() - t0:.0f}s)", flush=True)
    d = RUNS / f"bitmob-{st}"; d.mkdir(parents=True, exist_ok=True)
    with open(d / "results.jsonl", "w") as f:
        for k, it in enumerate(items):
            p = {l: float(best_P[k, j]) for j, l in enumerate(labels)}
            f.write(json.dumps({"task_id": it["id"], "family": it.get("family"), "split": it.get("split"), "group": it.get("group"), "ts": time.time(),
                                "status": "ok", "ok": True, "valid": True, "correct": bool(pred[k] == y[k]), "predicted": str(pred[k]), "probs": p, "probs_as_returned": p,
                                "probs_source": "bitmob v1: held-out half (cross-fitted), member chosen per set on training answers only", "model": "bitmob",
                                "member": chose[int(h[k])], "error": None}) + "\n")
json.dump(summary, open(OUT / "bitmob_sets.json", "w"), indent=1)
print(f"wrote {OUT}/bitmob_sets.json and {len(SETS)} result sets under {RUNS}/bitmob-*/")
