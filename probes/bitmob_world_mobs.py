"""World knowledge pre/post: one model vs the mob method (router + one mob per area) on all 14,042 MMLU questions.

Pre    one member answers everything (every member reported; e5-small is BitMob v1's encoder)
Post   the router (router_reader member, LogisticRegression on the request vector) names each question's area
       (data/bitmob/members.json "areas"); the area's mob answers. The mob per area is chosen on the training half only
       (inner 2-fold accuracy on that area's training questions), so no test answer picks it.
Held out  heads: per member, MMLU option head cross-fitted in two halves (bitmob_bench.member_task). Router: cross-fitted on
          the same halves (trained on every task's other half, area labels only). Every answer comes from models that never
          saw that question.
Pass   post beats the best single member beyond the 95% range (paired bootstrap over questions).
Also   "true-area" = the right area's chosen mob with a perfect router (shows what the router costs).
Writes data/bitmob/world_mobs.json.
Run: HF_HOME=/workspace/data/hf models/embed-zs/.venv/bin/python probes/bitmob_world_mobs.py
"""
import json, sys, pathlib, time
import numpy as np
from joblib import Parallel, delayed
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import pocket_test as pt, bitmob_bench as bb, bitmob_router as br

SEED = bb.SEED; CFG = bb.CFG; MEMBERS = bb.MEMBERS; AREAS = br.AREAS; GEN = br.GEN


def main():
    t0 = time.time(); V, R = bb.vectors(); print(f"vectors ready ({time.time() - t0:.0f} s)", flush=True)
    items = bb.TASKS["mmlu"]; n = len(items); y = np.array([bb.OPT.index(i["expected"]) for i in items])
    h = bb.halves([i["family"] for i in items], SEED); subj = [i["family"][5:] for i in items]
    area = np.array([br.area_of_source.get(f"mmlu:{s}", GEN) for s in subj])

    # heads: every member, cross-fitted (held-out P) + inner-fold P(correct) on the training halves
    out = Parallel(n_jobs=len(MEMBERS), verbose=0)(delayed(bb.member_task)("mmlu", V[m, "mmlu"], y, bb.OPT, h, SEED) for m in MEMBERS)
    P = {m: o[0] for m, o in zip(MEMBERS, out)}; INNER = {m: o[1] for m, o in zip(MEMBERS, out)}
    print(f"heads done ({time.time() - t0:.0f} s)", flush=True)

    # router: cross-fitted on the same halves, trained on every task's other half (OWASP included as code)
    ow = br.owasp_items(pathlib.Path("/workspace/data/sources/owasp/BenchmarkJava"))
    Xow = br.enc(CFG["router_reader"])([f"Is this code a real security vulnerability? | yes / no\n{i['text'][:1500]}" for i in ow["items"]])
    guess = np.empty(n, object)
    for fold in (0, 1):
        Xs, ys = [Xow], [["code"] * len(Xow)]
        for t, its in bb.TASKS.items():
            ht = h if t == "mmlu" else bb.halves([i["expected"] for i in its], SEED); keep = ht != fold
            Xs.append(R[t][keep]); ys.append([br.area_of_source.get(f"mmlu:{i['family'][5:]}" if t == "mmlu" else t, GEN) for i, k in zip(its, keep) if k])
        r = LogisticRegression(C=1.0, max_iter=5000, class_weight="balanced").fit(np.concatenate(Xs), sum(ys, []))
        te = h == fold; guess[te] = r.predict(R["mmlu"][te])
    print(f"router: right on {np.mean(guess == area):.1%} of MMLU questions (held out)", flush=True)

    # mob per area, chosen on training halves only
    chosen = {}; post = np.zeros(n, int); true_area = np.zeros(n, int)
    for fold in (0, 1):
        tr = h != fold; te = h == fold; pick = {}
        for a in AREAS:
            m_a = tr & (area == a)
            pick[a] = max(MEMBERS, key=lambda m: INNER[m][fold][m_a].mean()) if m_a.any() else max(MEMBERS, key=lambda m: INNER[m][fold][tr].mean())
        chosen[fold] = pick
        for k in np.where(te)[0]:
            post[k] = P[pick[guess[k]]][k].argmax(); true_area[k] = P[pick[area[k]]][k].argmax()
    acc = lambda p, m=slice(None): float(np.mean(p[m] == y[m]))
    single = {m: P[m].argmax(1) for m in MEMBERS}; best = max(MEMBERS, key=lambda m: acc(single[m]))
    B = np.random.default_rng(SEED).integers(0, n, (2000, n))
    def vs(a, b):
        d = np.array([np.mean(a[k] == y[k]) - np.mean(b[k] == y[k]) for k in B]); return [acc(a) - acc(b), *np.percentile(d, [2.5, 97.5]).tolist()]
    res = {"n": n, "router_accuracy": float(np.mean(guess == area)), "chosen": chosen,
           "pre": {m: acc(p) for m, p in single.items()}, "post": acc(post), "post_true_area": acc(true_area),
           "post_vs_best_single": vs(post, single[best]), "best_single": best, "per_area": {}}
    print(f"\nWORLD KNOWLEDGE, {n} questions, all held out (chance 25%)")
    print("PRE  (one model): " + ", ".join(f"{m} {v:.1%}" for m, v in sorted(res["pre"].items(), key=lambda kv: -kv[1])))
    d = res["post_vs_best_single"]
    print(f"POST (router + mobs): {res['post']:.1%}   (perfect router: {res['post_true_area']:.1%})")
    print(f"post vs best single ({best}): {d[0]:+.1%} [{d[1]:+.1%}, {d[2]:+.1%}] -> {'PASS' if d[1] > 0 else 'FAIL' if d[2] < 0 else 'no clear difference'}")
    print(f"\n{'area':10}{'n':>6}{'router right':>14}{'mob (fold 0/1)':>40}{'pre best':>10}{'post':>8}")
    for a in AREAS:
        m = area == a
        if not m.any(): continue
        r = {"n": int(m.sum()), "router_right": float(np.mean(guess[m] == a)), "mob": [chosen[0][a], chosen[1][a]],
             "pre_best_single": acc(single[best], m), "post": acc(post, m), "members": {x: acc(single[x], m) for x in MEMBERS}}
        res["per_area"][a] = r
        print(f"{a:10}{r['n']:>6}{r['router_right']:>14.0%}{'/'.join(r['mob']):>40}{r['pre_best_single']:>10.1%}{r['post']:>8.1%}")
        print("          every member here: " + ", ".join(f"{x} {v:.1%}" for x, v in sorted(r["members"].items(), key=lambda kv: -kv[1])))
    json.dump(res, open(bb.OUT / "world_mobs.json", "w"), indent=1); print(f"\nwrote {bb.OUT}/world_mobs.json ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
