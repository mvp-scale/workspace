"""BitMob area router: read a TypeSafe request, name its area, send it to that area's mob (data/bitmob/members.json "areas").

Router   LogisticRegression(balanced) on the router_reader member's vector of the request (instructions + criteria + state),
         trained on labelled examples of each area (the areas' "sources"). Held out: OWASP by its own train/test split,
         everything else by a seeded half split; the router is scored only on requests it did not train on.
Pass     1) the router names the area right on >= 95% of held-out requests
         2) routed answers beat "always the general mob" in each area beyond the 95% range (paired bootstrap)
End to end
  code     OWASP Benchmark (2,740 Java cases, train 1,835 / test 905, real vulnerability yes/no, balanced accuracy):
           heads for the general and the code mob trained on the train part; each test case answered by the mob the router chose
  science / general   MMLU (14,042): per mob, one option head, cross-fitted in two halves; each question answered by the mob the
           router chose; scored separately on science subjects and on the rest
Writes data/bitmob/router.json.
Run: HF_HOME=/workspace/data/hf models/embed-zs/.venv/bin/python probes/bitmob_router.py
"""
import json, sys, pathlib, time
import numpy as np
from joblib import Parallel, delayed
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import pocket_test as pt, bitmob_bench as bb

CFG = bb.CFG; AREAS = [a for a in CFG["areas"] if not a.startswith("_")]; GEN = "general"
OUT = bb.OUT; SEED = bb.SEED
area_of_source = {s: a for a in AREAS for s in CFG["areas"][a]["sources"] if s != "*"}
area_member = {a: CFG["areas"][a]["member"] for a in AREAS}
encs = {}


def enc(mid):
    if mid not in encs: encs[mid] = bb.encoder(next(m for m in CFG["members"] if m["id"] == mid))
    return encs[mid]


def boot(y, a, b, f, n=2000):
    """Paired bootstrap of f(y, routed) - f(y, general): mean and 95% range."""
    B = np.random.default_rng(SEED).integers(0, len(y), (n, len(y)))
    d = np.array([f(y[k], a[k]) - f(y[k], b[k]) for k in B]); return [float(f(y, a) - f(y, b)), *map(float, np.percentile(d, [2.5, 97.5]))]


def main():
    t0 = time.time(); reader = enc(CFG["router_reader"])
    # ---- requests with their area, and a held-out flag ----
    root = pathlib.Path("/workspace/data/sources/owasp/BenchmarkJava")
    ow = owasp_items(root); ow_te = set(ow["test"])
    req, area, held, src = [], [], [], []
    for k, i in enumerate(ow["items"]):
        req.append(f"Is this code a real security vulnerability? | yes / no\n{i['text'][:1500]}"); area.append(area_of_source["owasp"]); held.append(k in ow_te); src.append("owasp")
    for t, items in bb.TASKS.items():
        h = bb.halves([i["family"] for i in items] if t == "mmlu" else [i["expected"] for i in items], SEED)
        for k, i in enumerate(items):
            s = f"mmlu:{i['family'][5:]}" if t == "mmlu" else t
            req.append(bb.request_text(i)); area.append(area_of_source.get(s, GEN)); held.append(bool(h[k])); src.append(s)
    area = np.array(area); held = np.array(held); src = np.array(src)
    X = reader(req); print(f"{len(req)} requests read by {CFG['router_reader']} in {time.time() - t0:.0f} s", flush=True)

    # ---- the router ----
    router = LogisticRegression(C=1.0, max_iter=5000, class_weight="balanced").fit(X[~held], area[~held])
    guess = router.predict(X)
    acc = float(np.mean(guess[held] == area[held]))
    conf = {a: {b: int(np.sum((area[held] == a) & (guess[held] == b))) for b in AREAS} for a in AREAS}
    per_src = {}
    for s in sorted(set(src[held]), key=lambda s: (s.startswith("mmlu:"), s)):
        m = held & (src == s); per_src[s] = {"area": str(area[m][0]), "n": int(m.sum()), "right": float(np.mean(guess[m] == area[m]))}
    print(f"\nROUTER: names the area right on {acc:.1%} of {held.sum()} held-out requests (pass: >= 95%)")
    print("  true area -> routed to: " + "; ".join(f"{a}: " + ", ".join(f"{b} {conf[a][b]}" for b in AREAS) for a in AREAS))
    worst = sorted(per_src.items(), key=lambda kv: kv[1]["right"])[:8]
    print("  hardest sources: " + ", ".join(f"{s} ({v['area']}) {v['right']:.0%}" for s, v in worst))

    res = {"router": {"reader": CFG["router_reader"], "accuracy": acc, "n_held_out": int(held.sum()), "confusion": conf, "per_source": per_src}, "end_to_end": {}}

    # ---- code: OWASP ----
    tr, te = np.array(ow["train"]), np.array(ow["test"]); y = np.array([i["y"] for i in ow["items"]])
    texts = [i["text"] for i in ow["items"]]; P = {}
    for a in (GEN, "code"):
        V = enc(area_member[a])(texts)
        P[a] = LogisticRegression(C=1.0, max_iter=5000, class_weight="balanced").fit(V[tr], y[tr]).predict(V[te])
    gte = guess[:len(ow["items"])][te]
    routed = np.where(gte == "code", P["code"], P[GEN])
    r = {"n_test": len(te), "always_general": float(pt.bal(y[te], P[GEN])), "always_code": float(pt.bal(y[te], P["code"])),
         "routed": float(pt.bal(y[te], routed)), "sent_to_code": float(np.mean(gte == "code")),
         "routed_vs_general": boot(y[te], routed, P[GEN], pt.bal)}
    res["end_to_end"]["code (OWASP)"] = r
    print(f"\nCODE (OWASP, {len(te)} held-out cases, balanced accuracy): always general mob {r['always_general']:.1%} | "
          f"always code mob {r['always_code']:.1%} | routed {r['routed']:.1%} ({r['sent_to_code']:.0%} sent to code)")
    d = r["routed_vs_general"]; print(f"  routed vs general: {d[0]:+.1%} [{d[1]:+.1%}, {d[2]:+.1%}] -> {'PASS' if d[1] > 0 else 'FAIL'}")

    # ---- science / general: MMLU ----
    items = bb.TASKS["mmlu"]; ya = np.array([bb.OPT.index(i["expected"]) for i in items]); h = bb.halves([i["family"] for i in items], SEED)
    mm = sorted(set(area_member.values()))
    def mob_preds(m):
        z = np.load(bb.VEC / m / "mmlu.npz"); Q, O = z["q"], z["o"]
        p = np.zeros(len(items), int)
        for fold in (0, 1):
            trm, tem = np.where(h != fold)[0], np.where(h == fold)[0]; p[tem] = bb.fit_proba("mmlu", (Q, O), ya, bb.OPT, trm, tem).argmax(1)
        return m, p
    PM = dict(Parallel(n_jobs=len(mm))(delayed(mob_preds)(m) for m in mm))
    off = len(ow["items"]); gm = guess[off:off + len(items)]; am = area[off:off + len(items)]
    routed = np.array([PM[area_member[g]][k] for k, g in enumerate(gm)]); general = PM[area_member[GEN]]
    accf = lambda yy, pp: float(np.mean(yy == pp))
    for a in ("science", GEN):
        m = am == a; d = boot(ya[m], routed[m], general[m], accf)
        r = {"n": int(m.sum()), "always_general": accf(ya[m], general[m]), "always_own_mob": accf(ya[m], PM[area_member[a]][m]),
             "routed": accf(ya[m], routed[m]), "routed_vs_general": d, "router_right": float(np.mean(gm[m] == a))}
        res["end_to_end"][f"{a} (MMLU)"] = r
        print(f"\n{a.upper()} (MMLU, {m.sum()} questions, held-out halves): always general mob {r['always_general']:.1%} | "
              f"always {area_member[a]} {r['always_own_mob']:.1%} | routed {r['routed']:.1%} (router right {r['router_right']:.0%})")
        print(f"  routed vs general: {d[0]:+.1%} [{d[1]:+.1%}, {d[2]:+.1%}] -> {'PASS' if d[1] > 0 else 'no clear difference' if d[2] > 0 else 'FAIL'}")
    json.dump(res, open(OUT / "router.json", "w"), indent=1); print(f"\nwrote {OUT}/router.json ({time.time() - t0:.0f} s)")


def owasp_items(root):
    """Same items and the same train/test split as probes/pocket_test.py owasp()."""
    import csv, re, random, collections
    rows = [r for r in csv.reader(open(root / "expectedresults-1.2.csv")) if r and not r[0].startswith("#")]
    src = root / "src/main/java/org/owasp/benchmark/testcode"; items = []
    for name, cat, real, cwe in rows:
        t = (src / f"{name}.java").read_text(); t = re.sub(r"^\s*/\*\*.*?\*/\s*", "", t, flags=re.S)
        t = "\n".join(l for l in t.splitlines() if not re.match(r"\s*(package|import)\s", l)).strip()
        items.append({"id": name, "cat": cat, "y": int(real == "true"), "text": t})
    rng = random.Random(pt.SEED); strata = collections.defaultdict(list)
    for k, i in enumerate(items): strata[(i["cat"], i["y"])].append(k)
    test = set()
    for ks in strata.values(): rng.shuffle(ks); test |= set(ks[: len(ks) // 3])
    return {"items": items, "train": [k for k in range(len(items)) if k not in test], "test": sorted(test)}


if __name__ == "__main__":
    main()
