"""BitMob bench: every member in data/bitmob/members.json on the same tests, alone and combined, every answer held out.

Tests   world knowledge = all 57 MMLU subjects as one task (14,042 four-option questions), and each of the 15 other published
        sets in probes/v2/ (coding: websec = OWASP, memsafety = Juliet).
Heads   sets: per member and set, LogisticRegression(C=1, balanced) on the state vector -> the set's labels (as BitMob v1).
        MMLU: per member, one shared head scores each (question, option) pair from [q, o, q*o, |q-o|]; softmax over the four.
Ways to combine members
  alone            each member by itself
  stack            all members' vectors joined into one, one head
  set router       per task, the member best inside the training half (inner 2-fold): BitMob v1's router
  request router   per request, from the TypeSafe request alone (instructions + criteria + state, read by the router_reader
                   member): one ridge regression per member predicts "will this member get it right" from the request vector,
                   trained across all tasks on inner-fold outcomes of the training halves; the request goes to the highest
                   prediction. This is the router a live /v1/systemone call can use: it needs no task name and no answer.
  oracle           best member per item chosen with the answer (a ceiling, not a result)
Cross-fitting: every task split in two halves (stratified by label; MMLU by subject), seeded; train on one, answer the other,
then swap. Routers only ever see training-half outcomes.
Writes data/bitmob/bench.json (summary) and data/bitmob/bench_items.npz (per-item held-out probabilities).
Run: HF_HOME=/workspace/data/hf models/embed-zs/.venv/bin/python probes/bitmob_bench.py
"""
import json, sys, random, pathlib, time
import numpy as np
from joblib import Parallel, delayed
from sklearn.linear_model import LogisticRegression, Ridge

sys.path.insert(0, str(pathlib.Path(__file__).parent)); import pocket_test as pt
SEED = 20261016; ROOT = pathlib.Path("/workspace"); OUT = ROOT / "data" / "bitmob"; VEC = OUT / "vectors"
CFG = json.loads((OUT / "members.json").read_text()); MEMBERS = [m["id"] for m in CFG["members"]]
OPT = ["A", "B", "C", "D"]


def unit(x): return (x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-9)).astype(np.float32)


def encoder(m):
    if m["kind"] == "static":
        from model2vec import StaticModel
        M = StaticModel.from_pretrained(m["source"]); return lambda t: unit(np.asarray(M.encode(t), np.float32))
    if m["kind"] == "e5-onnx":
        import state_depth as sd; return lambda t: sd.embed(t)[0]
    raise ValueError(f"unknown member kind {m['kind']}")


# ---- tasks ----
def load(f): return [json.loads(l) for l in open(f)]
TASKS = {"mmlu": [i for f in sorted((ROOT / "probes/v2").glob("mmlu_*.jsonl")) for i in load(f)]}
for f in sorted((ROOT / "probes/v2").glob("*.jsonl")):
    if not f.stem.startswith("mmlu_"): TASKS[f.stem] = load(f)


def request_text(i):
    q = i["question"]; crit = q.get("criteria") or {}
    return f"{q.get('instructions', '')} | {' / '.join(str(v) for v in crit.values())[:400]}\n{str(i['state'])[:1500]}"


# ---- vectors per member and task (cached; MMLU seeded from data/pocket-test/mmlu_vectors.npz, same encoders) ----
def vectors():
    seed = {"general-8m": 0, "code-16m": 1, "science-8m": 2, "e5-small": 3}; old = OUT.parent / "pocket-test" / "mmlu_vectors.npz"
    old = dict(np.load(old)) if old.exists() else {}
    V = {}; R = {}
    for m in CFG["members"]:
        d = VEC / m["id"]; d.mkdir(parents=True, exist_ok=True); enc = None
        for t, items in TASKS.items():
            f = d / f"{t}.npz"
            if not f.exists():
                if t == "mmlu" and m["id"] in seed and f"q{seed[m['id']]}" in old:
                    np.savez(f, q=old[f"q{seed[m['id']]}"], o=old[f"o{seed[m['id']]}"])
                else:
                    enc = enc or encoder(m); t0 = time.time()
                    q = enc([str(i["state"]) for i in items])
                    o = enc([str(i["question"]["criteria"][l]) for i in items for l in OPT]).reshape(len(items), 4, -1) if t == "mmlu" else np.zeros((0,))
                    np.savez(f, q=q, o=o); print(f"  encoded {t} with {m['id']} in {time.time() - t0:.0f} s", flush=True)
            z = np.load(f); V[m["id"], t] = (z["q"], z["o"] if t == "mmlu" else None)
        if m["id"] == CFG["router_reader"]:
            f = d / "requests.npz"
            if not f.exists(): enc = enc or encoder(m); np.savez(f, **{t: enc([request_text(i) for i in items]) for t, items in TASKS.items()})
            R = dict(np.load(f))
    return V, R


# ---- heads ----
def mmlu_feat(Q, O, ks):
    q, o = Q[ks], O[ks]
    return np.concatenate([np.repeat(q[:, None], 4, 1), o, q[:, None] * o, np.abs(q[:, None] - o)], 2).reshape(len(ks) * 4, -1)


def fit_proba(t, vec, y, labels, tr, te):
    """Held-out probabilities (len(te) x len(labels)) from a head trained on tr."""
    Q, O = vec
    if t == "mmlu":
        yy = (np.arange(4)[None, :] == y[tr][:, None]).astype(int).ravel()
        clf = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(mmlu_feat(Q, O, tr), yy)
        s = clf.decision_function(mmlu_feat(Q, O, te)).reshape(len(te), 4); e = np.exp(s - s.max(1, keepdims=True)); return e / e.sum(1, keepdims=True)
    P = np.zeros((len(te), len(labels)))
    if len(set(y[tr])) < 2: P[:, y[tr][0]] = 1; return P
    clf = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(Q[tr], y[tr]); P[:, clf.classes_] = clf.predict_proba(Q[te]); return P


def halves(groups, seed):
    h = np.zeros(len(groups), int); r = random.Random(seed)
    for g in sorted(set(groups)):
        ks = [k for k, v in enumerate(groups) if v == g]; r.shuffle(ks); h[ks[: len(ks) // 2]] = 1
    return h


def member_task(t, vec, y, labels, h, seed):
    """One member on one task: held-out P (all items) and, per fold, inner-fold P(correct) on the training half."""
    P = np.zeros((len(y), len(labels))); inner = np.zeros((2, len(y)))
    for fold in (0, 1):
        tr, te = np.where(h != fold)[0], np.where(h == fold)[0]; P[te] = fit_proba(t, vec, y, labels, tr, te)
        ih = halves(list(y[tr]), seed + 1 + fold)
        for f2 in (0, 1):
            a, b = tr[ih != f2], tr[ih == f2]; inner[fold, b] = fit_proba(t, vec, y, labels, a, b)[np.arange(len(b)), y[b]]
    return P, inner


def main():
    V, R = vectors(); res = {"members": CFG["members"], "tasks": {}}; store = {}
    info = {}
    for t, items in TASKS.items():
        labels = OPT if t == "mmlu" else list(items[0]["labels"])
        y = np.array([labels.index(i["expected"]) for i in items])
        h = halves([i["family"] for i in items] if t == "mmlu" else list(y), SEED); info[t] = (labels, y, h)
    jobs = [(m, t) for m in MEMBERS for t in TASKS] + [("stack", t) for t in TASKS]
    def vec(m, t):
        if m != "stack": return V[m, t]
        return (np.concatenate([V[x, t][0] for x in MEMBERS], 1), np.concatenate([V[x, t][1] for x in MEMBERS], 2) if t == "mmlu" else None)
    t0 = time.time()
    out = Parallel(n_jobs=8, verbose=5)(delayed(member_task)(t, vec(m, t), info[t][1], info[t][0], info[t][2], SEED) for m, t in jobs)
    print(f"heads done in {time.time() - t0:.0f} s", flush=True)
    P = {(m, t): o[0] for (m, t), o in zip(jobs, out)}; INNER = {(m, t): o[1] for (m, t), o in zip(jobs, out)}

    # request router: across all tasks, per fold, ridge per member on the request vector -> inner P(correct)
    route = {t: np.zeros(len(TASKS[t]), int) for t in TASKS}
    for fold in (0, 1):
        Xtr = np.concatenate([R[t][info[t][2] != fold] for t in TASKS])
        pred = []
        for m in MEMBERS:
            ytr = np.concatenate([INNER[m, t][fold][info[t][2] != fold] for t in TASKS])
            reg = Ridge(alpha=1.0).fit(Xtr, ytr); pred.append({t: reg.predict(R[t][info[t][2] == fold]) for t in TASKS})
        for t in TASKS:
            te = np.where(info[t][2] == fold)[0]; route[t][te] = np.argmax([p[t] for p in pred], 0)

    for t in TASKS:
        labels, y, h = info[t]; n = len(y); row = {}
        acc = lambda Pm: float(np.mean(Pm.argmax(1) == y))
        for m in MEMBERS + ["stack"]: row[m] = acc(P[m, t])
        sr = np.zeros((n, len(labels))); chosen = {}
        for fold in (0, 1):
            tr, te = h != fold, h == fold
            best = max(MEMBERS, key=lambda m: INNER[m, t][fold][tr].mean()); chosen[fold] = best; sr[te] = P[best, t][te]
        row["set router"] = acc(sr)
        rr = np.stack([P[m, t] for m in MEMBERS])[route[t], np.arange(n)]; row["request router"] = acc(rr)
        row["oracle"] = float(np.mean(np.any([P[m, t].argmax(1) == y for m in MEMBERS], 0)))
        ci = {k: pt.wilson(int(round(v * n)), n) for k, v in row.items()}
        share = {m: float(np.mean(route[t] == j)) for j, m in enumerate(MEMBERS)}
        res["tasks"][t] = {"n": n, "chance": 1 / len(labels), "accuracy": row, "ci": ci, "set_router_chose": chosen, "request_router_share": share}
        for k, Pk in [("set router", sr), ("request router", rr), ("stack", P["stack", t])]: store[f"{t}|{k}"] = Pk
        store[f"{t}|route"] = route[t]
    json.dump(res, open(OUT / "bench.json", "w"), indent=1); np.savez_compressed(OUT / "bench_items.npz", **store)

    cols = MEMBERS + ["stack", "set router", "request router", "oracle"]
    print(f"\n{'task':24}{'n':>6} " + " ".join(f"{c[:12]:>12}" for c in cols))
    for t, r in res["tasks"].items():
        print(f"{t:24}{r['n']:>6} " + " ".join(f"{r['accuracy'][c]:>12.1%}" for c in cols))
    sets = [t for t in TASKS if t != "mmlu"]
    print(f"{'15-set average':24}{'':>6} " + " ".join(f"{np.mean([res['tasks'][t]['accuracy'][c] for t in sets]):>12.1%}" for c in cols))
    print("\nrequest router, share of MMLU sent to each member:", {m: f"{v:.0%}" for m, v in res["tasks"]["mmlu"]["request_router_share"].items()})


if __name__ == "__main__":
    main()
