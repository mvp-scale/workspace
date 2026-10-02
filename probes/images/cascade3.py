"""Ontology cascade (version 3): gate, a broad pool of family probes, then drill down into the families that look detectable.
See ONTOLOGY-SCHEMA.md and LAYERED-METHOD.md. RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE.

    /workspace/kev/.venv/bin/python cascade3.py run bone [--budget 100]
    /workspace/kev/.venv/bin/python cascade3.py report bone       # accuracy as a function of questions spent, plus what the model can detect
    /workspace/kev/.venv/bin/python cascade3.py export            # summary.json for the Image Lab

Every image is asked up to the full budget (no early stop) in the order: gate (10), every root probe (breadth), then nodes in priority
order. The ORDER is stored, so the answer can be recomputed at any number of questions and the thresholds can be re-scored offline.
Thresholds are fixed in advance and not tuned on the pilot images.
"""
import json, math, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from cascade import url, post, noul

HERE = Path(__file__).parent
OUT = Path("/workspace/data/image-lab/runs/winnow-cascade3")
BUDGET, BATCH = 100, 10
VOTE_YES, VOTE_NO = 0.65, 0.35           # a probe is a decisive yes at or above this P(yes), a decisive no at or below the other
FAM_YES, FAM_NO, FAM_MIN = 0.60, 0.30, 2  # a family is detected / absent by its share of decisive yes votes (at least FAM_MIN decisive)
GATE_PASS, GATE_MIN = 0.80, 3
SUPPORT_BAR, MIN_FAMS, GAP, CONFLICT = 0.70, 3, 0.15, 0.60
EXPAND_YES, EXPAND_FENCE = 0.50, 0.30      # families at or above EXPAND_YES are drilled first; those between FENCE and YES next


def vote(p): return "yes" if p >= VOTE_YES else "no" if p <= VOTE_NO else "unsure"


def nodes_of(o):
    """flat list of nodes with parent, root family id and the sign map that applies (a child inherits its parent's supports when it has none)"""
    out = []
    def walk(f, parent, root, inherit):
        sup = f.get("supports") if f.get("supports") else inherit
        out.append({"id": f["id"], "name": f["name"], "probes": f["probes"], "parent": parent, "root": root, "supports": sup, "own_supports": f.get("supports", {}), "truth": f.get("truth"), "children": [c["id"] for c in f.get("children", [])]})
        for c in f.get("children", []): walk(c, f["id"], root, sup)
    for f in o["families"]: walk(f, None, f["id"], {})
    return out


def load(name):
    o = json.load(open(HERE / "cascades" / "v3" / f"{name}.json")); items = [json.loads(l) for l in open(HERE / "pilots" / f"{o['pilot']}.jsonl")]
    nd = nodes_of(o); return o, items, nd, {n["id"]: n for n in nd}


def node_score(n, asked):
    dec = [vote(asked[q["id"]]) for q in n["probes"] if q["id"] in asked]; dec = [v for v in dec if v != "unsure"]
    return (sum(v == "yes" for v in dec) / len(dec), len(dec)) if dec else (None, 0)


def subtree_ids(byid, nid):
    n = byid[nid]; ids = [q["id"] for q in n["probes"]]
    for c in n["children"]: ids += subtree_ids(byid, c)
    return ids


def family_scores(o, byid, asked):
    out = {}
    for f in o["families"]:
        dec = [vote(asked[i]) for i in subtree_ids(byid, f["id"]) if i in asked]; dec = [v for v in dec if v != "unsure"]
        out[f["id"]] = (sum(v == "yes" for v in dec) / len(dec), len(dec)) if len(dec) >= FAM_MIN else (None, len(dec))
    return out


def gate_ok(o, asked):
    dec = [(g, vote(asked[g["id"]])) for g in o["gate"] if g["id"] in asked]; dec = [(g, v) for g, v in dec if v != "unsure"]
    return not (len(dec) >= GATE_MIN and sum(v == g["pass"] for g, v in dec) / len(dec) < GATE_PASS)


def class_support(o, byid, asked, mode="family"):
    t = {c: [0, 0] for c in o["classes"]}
    if mode == "family":
        for f in o["families"]:
            s, n = family_scores(o, byid, asked)[f["id"]]
            if s is None or not f.get("supports"): continue
            d = "yes" if s >= FAM_YES else "no" if s <= FAM_NO else None
            if d is None: continue
            for c, sign in f["supports"].items(): t[c][0 if (sign > 0) == (d == "yes") else 1] += 1
    else:   # probe level: every decisive probe votes with its family's signs
        for n in byid.values():
            if not n["supports"]: continue
            for q in n["probes"]:
                if q["id"] not in asked: continue
                v = vote(asked[q["id"]])
                if v == "unsure": continue
                for c, sign in n["supports"].items(): t[c][0 if (sign > 0) == (v == "yes") else 1] += 1
    return {c: ((a / (a + b)) if a + b else 0.0, a + b, a) for c, (a, b) in t.items()}


def decide(o, byid, asked, mode="family"):
    if not gate_ok(o, asked): return {"code": "NOT_USABLE", "pick": None}
    sc = sorted(class_support(o, byid, asked, mode).items(), key=lambda x: (-x[1][0], -x[1][2]))
    (c1, (s1, n1, _)), (c2, (s2, n2, _)) = sc[0], sc[1]
    mf = MIN_FAMS if mode == "family" else 5
    if s1 >= CONFLICT and s2 >= CONFLICT: return {"code": "CONFLICT", "pick": c1}
    if s1 >= SUPPORT_BAR and n1 >= mf and s1 - s2 >= GAP: return {"code": "CONSENSUS", "pick": c1}
    return {"code": "WEAK", "pick": c1}


def run_image(o, nd, byid, item):
    img = url(item["image"]); asked, order = {}, []
    rec = {"id": item["id"], "expected": item["expected"], "meta": item.get("meta", {})}
    a = post(img, "An image is attached.", {"q": item["question"]})["q"]
    rec["baseline"] = {"yes": float(a["noul"])} if item["question"]["type"] == "noul" else {k: float(v) for k, v in a["probabilities"].items()}
    used = 0

    def ask(qs, state):
        nonlocal used
        qs = qs[: max(0, BUDGET - used)]
        for i in range(0, len(qs), BATCH):
            b = qs[i:i + BATCH]; ans = post(img, state, {q["id"]: noul(q["q"]) for q in b}); used += len(b)
            for q in b: asked[q["id"]] = float(ans[q["id"]]["noul"]); order.append(q["id"])
    ask(o["gate"], o["state_gate"])
    if not gate_ok(o, asked):
        rec.update(stop="gate", asked=asked, order=order, used=used); return rec
    ask([q for f in o["families"] for q in f["probes"]], o["state_after_gate"])         # breadth: every root family
    rec["breadth_end"] = used
    done = set(); expanded = []
    while used < BUDGET:
        # candidate nodes: children of nodes whose own score is at least EXPAND_FENCE (roots by family score), not yet asked
        pool = []
        for n in nd:
            if n["id"] in done or any(q["id"] in asked for q in n["probes"]): continue
            par = byid.get(n["parent"]) if n["parent"] else None
            if par is None: continue
            ps, _ = node_score(par, asked)
            if ps is None or ps < EXPAND_FENCE: continue
            sup = 1 if n["supports"] else 0
            pool.append(((1 if ps >= EXPAND_YES else 0, sup, ps), n))
        if not pool: break
        pool.sort(key=lambda x: x[0], reverse=True)
        batch, bq = [], 0
        for _, n in pool:
            if bq + len(n["probes"]) > BATCH and batch: break
            batch.append(n); bq += len(n["probes"])
        ask([q for n in batch for q in n["probes"]], o["state_after_gate"])
        for n in batch: done.add(n["id"]); expanded.append(n["id"])
    rec.update(stop="budget" if used >= BUDGET else "no more to expand", asked=asked, order=order, used=used, expanded=expanded)
    return rec


def run(name, budget=BUDGET):
    global BUDGET; BUDGET = budget
    o, items, nd, byid = load(name); OUT.mkdir(parents=True, exist_ok=True); t0 = time.time()

    def safe(it):
        try: return run_image(o, nd, byid, it)
        except Exception as e: return {"id": it["id"], "error": f"{type(e).__name__}: {e}"[:200]}
    with ThreadPoolExecutor(4) as ex: rows = list(ex.map(safe, items))
    (OUT / f"{name}.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"{name}: {len(rows)} images in {time.time() - t0:.0f}s, {sum('error' in r for r in rows)} errors, {sum(r.get('used', 0) for r in rows) / len(rows):.1f} questions per image")


# ---------------- scoring ----------------
def truth(o, r): return o["map"][r["expected"]] if "map" in o else r["expected"]


def base_pick(o, r):
    b = r["baseline"]
    return next(c for k, c in o["map"].items() if (k == "yes") == (b["yes"] >= .5)) if "yes" in b else max(b, key=b.get)


def prefix(r, k):
    ids = r["order"][:k]; return {i: r["asked"][i] for i in ids}


def wil(k, n, z=1.96):
    if not n: return (0, 1)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return ((c - m) / d, (c + m) / d)


def auc(pos, neg):
    if not pos or not neg: return None
    s = sum((p > q) + 0.5 * (p == q) for p in pos for q in neg); return s / (len(pos) * len(neg))


STEPS = (10, 20, 30, 40, 50, 60, 70, 80, 90, 100)


def curve(o, byid, rows, mode="family"):
    out = []
    for k in STEPS:
        d = {r["id"]: decide(o, byid, prefix(r, k), mode) for r in rows}
        gp = [r for r in rows if d[r["id"]]["code"] != "NOT_USABLE"]
        forced = sum(d[r["id"]]["pick"] == truth(o, r) for r in gp); cons = [r for r in gp if d[r["id"]]["code"] == "CONSENSUS"]
        out.append({"k": k, "gate_passed": len(gp), "forced": forced, "consensus": len(cons), "consensus_right": sum(d[r["id"]]["pick"] == truth(o, r) for r in cons)})
    return out


def capability(o, nd, byid, rows):
    """what can the model detect: for each family with a truth binding, how well does its confidence separate images where the dataset says it is present"""
    res = []
    for n in nd:
        t = n["truth"]
        if not t: continue
        pos, neg = [], []
        for r in rows:
            if t["meta"] not in r["meta"] or r["stop"] == "gate": continue
            v = r["meta"][t["meta"]]
            try: present = bool(eval(t["rule"], {"__builtins__": {}}, {"v": v}))
            except Exception: continue
            ids = subtree_ids(byid, n["id"]); ps = [r["asked"][i] for i in ids if i in r["asked"]]
            if not ps: continue
            (pos if present else neg).append(sum(ps) / len(ps))
        if len(pos) >= 3 and len(neg) >= 3:
            thr = (sum(pos) / len(pos) + sum(neg) / len(neg)) / 2
            res.append({"id": n["id"], "name": n["name"], "truth": f"{t['meta']} {t['rule']}", "present": len(pos), "absent": len(neg), "auc": auc(pos, neg), "mean_present": sum(pos) / len(pos), "mean_absent": sum(neg) / len(neg),
                        "balanced_acc": 0.5 * (sum(p > thr for p in pos) / len(pos) + sum(q <= thr for q in neg) / len(neg))})
    return res


def report(name):
    o, items, nd, byid = load(name); rows = [r for r in map(json.loads, open(OUT / f"{name}.jsonl")) if "error" not in r]; n = len(rows)
    single = sum(base_pick(o, r) == truth(o, r) for r in rows); iv = lambda k, m: "%d%% (%d%% to %d%%)" % (round(k / m * 100), round(wil(k, m)[0] * 100), round(wil(k, m)[1] * 100)) if m else "–"
    print(f"\n== {name}: {n} images, chance {100 / len(o['classes']):.0f}%, {len(nd)} nodes ==")
    print(f"single original question: {iv(single, n)}")
    be = sum(r.get("breadth_end", 0) for r in rows) / n
    print(f"gate stops: {sum(r['stop'] == 'gate' for r in rows)} of {n}; breadth ends at {be:.0f} questions")
    for mode in ("family", "probe"):
        print(f"\nlayered answer by questions spent ({mode}-level votes), among images that passed the gate:")
        print("  questions  gate-passed  best guess              handled on consensus   right on consensus")
        for c in curve(o, byid, rows, mode):
            print(f"  {c['k']:9d}  {c['gate_passed']:11d}  {iv(c['forced'], c['gate_passed']):22s}  {c['consensus']:3d}/{n} = {c['consensus'] / n * 100:3.0f}%        {iv(c['consensus_right'], c['consensus']) if c['consensus'] else '–'}")
    cap = capability(o, nd, byid, rows)
    if cap:
        print("\nwhat can it detect (families scored against the dataset's own metadata):")
        for c in sorted(cap, key=lambda x: -(x["auc"] or 0)): print(f"  {c['name'][:34]:34s} {c['truth'][:26]:26s} present {c['present']:3d} absent {c['absent']:3d}  AUC {c['auc']:.2f}  balanced accuracy {c['balanced_acc']:.2f}")


TASK_OF = {"skin": ("t40_skin_lesion", "Skin lesion"), "bone": ("t41_bone_fracture", "Bone fracture"), "chest": ("t42_chest_xray", "Chest X-ray"), "retina": ("t43_retina", "Retina OCT"),
           "dental": ("t44_dental_xray", "Dental X-ray"), "pathology": ("t45_pathology_patch", "Pathology patch"), "endoscopy": ("t46_endoscopy", "Endoscopy"), "brain": ("t47_brain_mri", "Brain MRI")}


def export():
    """one summary file for the Image Lab: /workspace/data/image-lab/runs/winnow-cascade3/summary.json"""
    out = []
    for name, (tid, title) in TASK_OF.items():
        f = OUT / f"{name}.jsonl"
        if not f.exists(): continue
        o, items, nd, byid = load(name); rows = [r for r in map(json.loads, open(f)) if "error" not in r]; n = len(rows)
        if not n: continue
        classes = o["classes"]; tr = lambda r: truth(o, r)
        fam = []
        for f_ in o["families"]:
            ids = subtree_ids(byid, f_["id"])
            m = {}
            for c in classes:
                vals = [sum(r["asked"][i] for i in ids if i in r["asked"]) / max(1, sum(i in r["asked"] for i in ids)) for r in rows if tr(r) == c and r["stop"] != "gate"]
                m[c] = sum(vals) / len(vals) if vals else None
            v = [x for x in m.values() if x is not None]
            fam.append({"id": f_["id"], "name": f_["name"], "supports": f_.get("supports", {}), "probes_root": len(f_["probes"]), "probes_tree": len(ids), "children": len(f_.get("children", [])),
                        "mean_by_class": m, "spread": (max(v) - min(v)) if len(v) > 1 else 0, "probe_questions": [q["q"] for q in f_["probes"]]})
        stops = {}
        for r in rows: stops[r["stop"]] = stops.get(r["stop"], 0) + 1
        cvf = json.load(open(OUT / "cv_families.json")).get(name) if (OUT / "cv_families.json").exists() else None
        out.append({"name": name, "task_id": tid, "title": title, "cv_families": cvf, "n": n, "classes": classes, "chance": 1 / len(classes), "status": o["status"], "single": sum(base_pick(o, r) == tr(r) for r in rows),
                    "gate_stops": stops.get("gate", 0), "breadth_end": round(sum(r.get("breadth_end", 0) for r in rows if r["stop"] != "gate") / max(1, sum(r["stop"] != "gate" for r in rows))),
                    "used_avg": sum(r["used"] for r in rows) / n, "curve_family": curve(o, byid, rows, "family"), "curve_probe": curve(o, byid, rows, "probe"),
                    "capability": capability(o, nd, byid, rows), "families": fam, "gate": [g["q"] for g in o["gate"]], "tree": {"families": len(o["families"]), "nodes": len(nd), "questions": sum(len(x["probes"]) for x in nd)}})
    (OUT / "summary.json").write_text(json.dumps({"budget": BUDGET, "steps": list(STEPS), "tasks": out}, indent=1))
    print("wrote summary.json for", [t["name"] for t in out])


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "run": run(sys.argv[2], int(sys.argv[sys.argv.index("--budget") + 1]) if "--budget" in sys.argv else BUDGET)
    elif cmd == "report": report(sys.argv[2])
    elif cmd == "export": export()
