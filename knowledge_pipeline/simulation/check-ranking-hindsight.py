"""Round F (00.1 Phase 2, plan design/plan-tactical-strategic.md:164): ranking truth first. No ranking code change.
Question: after a freeze, which development ranking rule predicts which developments keep growing? Pre-registered in ledger T158-F1.
Frozen cut = developments_v0.build(td, area, only=first round(0.6 n) articles); later cut = build(td, area, prev=members_of(frozen)) on the whole window.
TRUTH persist(d): the later-cut development holding >= 50% of d's frozen members (highest containment, ties smaller id) contains >= 1 article that is not in the frozen set.
Rules (existing fields only): recency, moved_first (production order), owners, size, contested, reinforced; baseline random (seeded permutation).
Metric: AUC (ties 0.5) with bootstrap 95% CI; precision@top-k with Wilson 95% CI (info). A rule counts only if its AUC CI lower bound beats the upper bound of the recency CI and of the random CI on BOTH bar windows.
Read only, CPU, deterministic (fixed seeds), no model, no network.
    python simulation/check-ranking-hindsight.py"""
import sys, os, json, math, random
os.environ.setdefault("CUDA_VISIBLE_DEVICES", ""); os.environ["WORLD_GPU"] = "0"
HERE = os.path.dirname(os.path.abspath(__file__)); KP = os.path.dirname(HERE); WS = os.path.join(KP, "projects", "world-state")
STRUCT = os.path.abspath(os.path.join(KP, "..", "demo", "mockups", "structure-live"))
SCRATCH_FWD2 = "/tmp/claude-0/-workspace/4de8a31c-a77a-41eb-866f-07c2d4c7a42a/scratchpad/f/fwd2/trace"
sys.path.insert(0, WS)
import developments_v0 as DV
SEED = 20261124; FREEZE = 0.6; BOOT = 2000; MIN_CLASS = 5
BAR = [("W1 runs-e2e-101", os.path.join(STRUCT, "runs-e2e-101", "trace"), "e2e-101"), ("W2 ce1", os.path.join(STRUCT, "area-ce1", "trace"), "ce1")]
INFO = [("I1 u1", os.path.join(STRUCT, "area-u1", "trace"), "u1"), ("I2 c1", os.path.join(STRUCT, "area-c1", "trace"), "c1"), ("I3 runs-fwd2 (scratch build)", SCRATCH_FWD2, "fwd2")]
RULES = ["recency", "moved_first", "owners", "size", "contested", "reinforced"]

def auc(scores, y):
    """Mann-Whitney AUC with ties = 0.5; None when a class is empty"""
    P = [s for s, t in zip(scores, y) if t]; N = [s for s, t in zip(scores, y) if not t]
    if not P or not N: return None
    order = sorted(range(len(scores)), key=lambda i: scores[i]); rank = [0.0] * len(scores); i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]: j += 1
        for k in range(i, j + 1): rank[order[k]] = (i + j) / 2 + 1
        i = j + 1
    rp = sum(r for r, t in zip(rank, y) if t)
    return (rp - len(P) * (len(P) + 1) / 2) / (len(P) * len(N))
def pct(v, p):
    v = sorted(v); k = (len(v) - 1) * p; f = int(math.floor(k)); c = min(f + 1, len(v) - 1); return v[f] + (v[c] - v[f]) * (k - f)
def boot_ci(scores, y, rng):
    n = len(y); out = []
    for _ in range(BOOT):
        ix = [rng.randrange(n) for _ in range(n)]; a = auc([scores[i] for i in ix], [y[i] for i in ix])
        if a is not None: out.append(a)
    return (pct(out, 0.025), pct(out, 0.975)) if out else (None, None)
def wilson(k, n, z=1.96):
    if not n: return (None, None)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return (c - h, c + h)

def window(td, area):
    A = DV._articles(td); n = len(A); nf = int(round(n * FREEZE)); fro = {a["id"] for a in A[:nf]}; seq = {a["id"]: a["seq"] for a in A}
    DV._CACHE.clear(); F = DV.build(td, area, only=fro)
    if not F.get("exists"): return None
    DV._CACHE.clear(); L = DV.build(td, area, prev=DV.members_of(F))
    devs = F["developments"] + F["thin"]; later = {d["id"]: {m["id"] for m in d["members"]} for d in L["developments"] + L["thin"]}; rows = []
    for d in devs:
        mem = {m["id"] for m in d["members"]}; best = None
        for lid, lm in later.items():
            c = len(mem & lm) / len(mem)
            if c >= 0.5 and (best is None or c > best[0] or (c == best[0] and lid < best[1])): best = (c, lid)
        persist = bool(best and (later[best[1]] - fro))
        rec = max(seq[m["id"]] for m in d["members"] if seq.get(m["id"]) is not None)
        rows.append({"id": d["id"], "persist": persist, "articles": d["articles"], "recency": rec, "moved": d["moved"],
                     "owners": d["owners"], "size": d["articles"], "contested": len(d.get("contradictions") or []), "reinforced": d.get("corroborated_assertions") or 0,
                     "moved_first": -DV.MOVED_ORDER[d["moved"]] * 1e6 + rec, "thin": d["thin"]})
    return {"n": n, "frozen": nf, "rows": rows}

def score_window(label, td, area, rng):
    out = {"label": label}
    if not os.path.exists(os.path.join(td, "slow_consolidate", "knowledge.json")): out["skip"] = "no knowledge.json"; return out
    w = window(td, area)
    if not w: out["skip"] = "build failed"; return out
    rows = w["rows"]; y = [r["persist"] for r in rows]; npos = sum(y); nneg = len(y) - npos
    out.update({"articles": w["n"], "frozen": w["frozen"], "developments": len(rows), "thin": sum(1 for r in rows if r["thin"]), "persisting": npos, "base_rate": round(npos / len(rows), 3) if rows else None})
    if npos < MIN_CLASS or nneg < MIN_CLASS: out["unscorable"] = "persisting %d, not persisting %d (need >= %d each)" % (npos, nneg, MIN_CLASS); return out
    # random: AUC of seeded random scores
    rnd = [auc([rng.random() for _ in rows], y) for _ in range(BOOT)]; out["random"] = {"auc": 0.5, "ci": (pct(rnd, 0.025), pct(rnd, 0.975))}
    k = max(1, math.ceil(len(rows) / 4)); table = {}
    for rule in RULES:
        sc = [r[rule] for r in rows]; a = auc(sc, y); lo, hi = boot_ci(sc, y, rng)
        order = sorted(range(len(rows)), key=lambda i: (-sc[i], -rows[i]["recency"], rows[i]["id"])); top = sum(1 for i in order[:k] if y[i]); wl = wilson(top, k)
        table[rule] = {"auc": a, "ci": (lo, hi), "p_at_k": "%d/%d" % (top, k), "p_ci": wl, "distinct": len(set(sc))}
    out["table"] = table; out["k"] = k
    return out

def fmt(v): return "n/a" if v is None else "%.3f" % v
def main():
    rng = random.Random(SEED); res = []; ok_rules = {r: [] for r in RULES}
    for label, td, area in BAR + INFO:
        r = score_window(label, td, area, rng); res.append((label, r, label in [b[0] for b in BAR]))
        if "skip" in r: print("%s: SKIPPED (%s)" % (label, r["skip"]), flush=True); continue
        print("%s: %d articles, freeze at %d, %d developments (%d thin), %d persist (base rate %s)" % (label, r["articles"], r["frozen"], r["developments"], r["thin"], r["persisting"], r["base_rate"]), flush=True)
        if "unscorable" in r: print("   UNSCORABLE: " + r["unscorable"], flush=True); continue
        print("   random   AUC 0.500 CI [%s, %s]" % (fmt(r["random"]["ci"][0]), fmt(r["random"]["ci"][1])))
        for rule, t in r["table"].items():
            print("   %-12s AUC %s CI [%s, %s]  top-%d precision %s Wilson [%s, %s]  distinct scores %d" % (rule, fmt(t["auc"]), fmt(t["ci"][0]), fmt(t["ci"][1]), r["k"], t["p_at_k"], fmt(t["p_ci"][0]), fmt(t["p_ci"][1]), t["distinct"]), flush=True)
    # the bar
    print("\nBAR: a rule counts only if its AUC CI lower bound beats the upper bound of recency and of random on BOTH bar windows")
    bar_res = [(l, r) for l, r, isbar in res if isbar]; counts = []
    for rule in RULES:
        if rule == "recency": continue
        per = []
        for l, r in bar_res:
            if "table" not in r: per.append(False); continue
            lo = r["table"][rule]["ci"][0]; ref = max(r["table"]["recency"]["ci"][1], r["random"]["ci"][1])
            per.append(lo is not None and lo > ref)
        print("  %-12s %s" % (rule, " ".join("%s=%s" % (l.split()[0], "beats" if p else "no") for (l, _), p in zip(bar_res, per))))
        if all(per) and len(per) == len(BAR): counts.append(rule)
    verdict = "RANKING SIGNAL: " + ", ".join(counts) if counts else "no ranking signal yet"
    print("RESULT: " + verdict, flush=True)
    return 0 if counts else 1
if __name__ == "__main__": sys.exit(main())
