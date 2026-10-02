"""Budgeted, adaptive layered cascade (version 2). See LAYERED-METHOD.md. RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE.

    /workspace/kev/.venv/bin/python cascade2.py run skin|dental|chest [--plain]   # --plain: do not carry facts into the state
    /workspace/kev/.venv/bin/python cascade2.py report skin|dental|chest [--plain]

Per image: a budget of 100 questions, asked in batches of at most 10 and recounted after every batch.
  L0 gate (10) -> stop if it fails. L1 characteristics (20) -> L2 discriminators (up to 30, chosen by what L1 showed)
  -> L3 deep dive (up to 25) -> backtrack (up to 15: re-ask the unsure or contradictory L1 questions with the facts so far).
Stops at the first batch after which the evidence is a CONSENSUS (votes, not averages). Thresholds are fixed in advance.
Every probability is stored, so the rules can be re-scored without calling the model again.
"""
import json, math, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from cascade import url, post, noul, VOTE_YES, VOTE_NO, GATE_PASS, GATE_MIN, UNCLEAR_FRAC, SUPPORT_BAR, MIN_VOTES, GAP, CONFLICT

HERE = Path(__file__).parent
OUT = Path("/workspace/data/image-lab/runs/winnow-cascade2")
BUDGET, BATCH = 100, 10
CAPS = {"L2": 30, "L3": 25, "BACK": 15}


def vote(p):
    return "yes" if p >= VOTE_YES else "no" if p <= VOTE_NO else "unsure"


def tally(spec, asked):
    items = spec["features"] + spec["discriminators"] + spec.get("deep", [])
    t = {c: [0, 0] for c in spec["classes"]}
    for f in items:
        if f["id"] not in asked: continue
        v = vote(asked[f["id"]])
        if v == "unsure": continue
        for c in f["for"]: t[c][0 if v == "yes" else 1] += 1
        for c in f["against"]: t[c][1 if v == "yes" else 0] += 1
    return t


def ranking(spec, asked):
    t = tally(spec, asked)
    sc = {c: (v[0] / (v[0] + v[1]) if v[0] + v[1] else 0.0, v[0] + v[1], v[0]) for c, v in t.items()}
    return sorted(sc.items(), key=lambda x: (-x[1][0], -x[1][2]))


def gate_ok(spec, asked):
    dec = [(g, vote(asked[g["id"]])) for g in spec["gate"] if g["id"] in asked]
    dec = [(g, v) for g, v in dec if v != "unsure"]
    return not (len(dec) >= GATE_MIN and sum(v == g["pass"] for g, v in dec) / len(dec) < GATE_PASS)


def decide(spec, asked):
    if not gate_ok(spec, asked): return {"code": "NOT_USABLE", "pick": None}
    fv = [vote(asked[f["id"]]) for f in spec["features"] if f["id"] in asked]
    r = ranking(spec, asked); (c1, (s1, n1, _)), (c2, (s2, n2, _)) = r[0], r[1]
    if fv and sum(v == "unsure" for v in fv) / len(fv) >= UNCLEAR_FRAC: return {"code": "UNCLEAR", "pick": c1}
    if s1 >= CONFLICT and s2 >= CONFLICT: return {"code": "CONFLICT", "pick": c1}
    if s1 >= SUPPORT_BAR and n1 >= MIN_VOTES and s1 - s2 >= GAP: return {"code": "CONSENSUS", "pick": c1}
    return {"code": "WEAK", "pick": c1}


def choose(spec, bank, asked, n):
    """next questions from a bank: those that touch the two leading hypotheses, preferring ones whose polarity separates them"""
    lead = [c for c, _ in ranking(spec, asked)[:2]]
    scored = []
    for q in spec.get(bank, []):
        if q["id"] in asked or not (set(q.get("when", spec["classes"])) & set(lead)): continue
        touch = [c for c in lead if c in q["for"] or c in q["against"]]
        if not touch: continue
        pol = {c: (1 if c in q["for"] else -1) for c in touch}
        scored.append((len(touch) + (1 if len(set(pol.values())) > 1 else 0), q))
    scored.sort(key=lambda x: -x[0])
    return [q for _, q in scored[:n]]


def facts(spec, asked, k=14):
    allq = {q["id"]: q["q"] for q in spec["gate"] + spec["features"] + spec["discriminators"] + spec.get("deep", [])}
    dec = sorted(((abs(p - 0.5), i, vote(p)) for i, p in asked.items() if i in allq and vote(p) != "unsure"), reverse=True)[:k]
    if not dec: return ""
    return "\nAnswers already established about this image:\n" + "\n".join(f"- {allq[i]} {v}" for _, i, v in dec)


def run_image(spec, item, carry):
    img = url(item["image"]); asked, order, state = {}, [], {"used": 0}
    rec = {"id": item["id"], "expected": item["expected"], "reask": {}}
    a = post(img, "An image is attached.", {"q": item["question"]})["q"]
    rec["baseline"] = {"yes": float(a["noul"])} if item["question"]["type"] == "noul" else {k: float(v) for k, v in a["probabilities"].items()}

    def ask(qs, st, store=asked):
        qs = qs[: max(0, BUDGET - state["used"])]
        if not qs: return
        ans = post(img, st, {q["id"]: noul(q["q"]) for q in qs}); state["used"] += len(qs)
        for q in qs:
            p = float(ans[q["id"]]["noul"])
            if store is asked: asked[q["id"]] = p; order.append(q["id"])
            else: rec["reask"][q["id"]] = p
    ask(spec["gate"], spec["state_gate"])
    if not gate_ok(spec, asked):
        rec["stop"] = "gate"
    else:
        st = lambda: spec["state_after_gate"] + (facts(spec, asked) if carry else "")
        ask(spec["features"], spec["state_after_gate"])
        rec["stop"] = "L1" if decide(spec, asked)["code"] == "CONSENSUS" else None
        for layer, bank in (("L2", "discriminators"), ("L3", "deep")):
            spent = 0
            while rec["stop"] is None and spent < CAPS[layer]:
                nxt = choose(spec, bank, asked, min(BATCH, CAPS[layer] - spent))
                if not nxt: break
                ask(nxt, st()); spent += len(nxt)
                if decide(spec, asked)["code"] == "CONSENSUS": rec["stop"] = layer
        if rec["stop"] is None:   # backtrack: re-ask the unsure questions with the facts we now have, then recount
            redo = [f for f in spec["features"] if vote(asked[f["id"]]) == "unsure"][: CAPS["BACK"]]
            if redo:
                ask(redo, spec["state_after_gate"] + facts(spec, asked), store=rec["reask"])
                for k, p in rec["reask"].items(): asked[k] = p
            rec["stop"] = "backtrack" if decide(spec, asked)["code"] == "CONSENSUS" else "exhausted"
    rec["asked"], rec["order"], rec["used"] = asked, order, state["used"]
    return rec


def load(name):
    return json.load(open(HERE / "cascades" / "v2" / f"{name}.json")), [json.loads(l) for l in open(HERE / "pilots" / f"{name}.jsonl")]


def run(name, carry=True):
    spec, items = load(name); OUT.mkdir(parents=True, exist_ok=True); t0 = time.time()

    def safe(it):
        try: return run_image(spec, it, carry)
        except Exception as e: return {"id": it["id"], "error": f"{type(e).__name__}: {e}"[:200]}
    with ThreadPoolExecutor(4) as ex: rows = list(ex.map(safe, items))
    f = OUT / f"{name}-{'carry' if carry else 'plain'}.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"{name} ({'carry' if carry else 'plain'}): {len(rows)} images in {time.time() - t0:.0f}s, {sum('error' in r for r in rows)} errors, {sum(r.get('used', 0) for r in rows) / len(rows):.1f} questions per image")


def truth(spec, r): return spec["map"][r["expected"]] if "map" in spec else r["expected"]


def base_pick(spec, r):
    b = r["baseline"]
    if "yes" in b: return next(c for k, c in spec["map"].items() if (k == "yes") == (b["yes"] >= .5))
    return max(b, key=b.get)


def wil(k, n, z=1.96):
    if not n: return (0, 1)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return ((c - m) / d, (c + m) / d)


def summarize(name, carry=True):
    spec, _ = load(name); f = OUT / f"{name}-{'carry' if carry else 'plain'}.jsonl"
    rows = [r for r in map(json.loads, open(f)) if "error" not in r]; n = len(rows); res = {}
    dec = {r["id"]: decide(spec, r["asked"]) for r in rows}
    ok = lambda r, pick: pick is not None and pick == truth(spec, r)
    single = sum(base_pick(spec, r) == truth(spec, r) for r in rows)
    forced = sum(ok(r, dec[r["id"]]["pick"]) for r in rows)
    cons = [r for r in rows if dec[r["id"]]["code"] == "CONSENSUS"]; cr = sum(ok(r, dec[r["id"]]["pick"]) for r in cons)
    stops = {}
    for r in rows:
        s = stops.setdefault(r["stop"], {"n": 0, "right": 0, "used": 0}); s["n"] += 1; s["right"] += ok(r, dec[r["id"]]["pick"]); s["used"] += r["used"]
    res.update(name=name, mode="carry" if carry else "plain", n=n, classes=spec["classes"], chance=1 / len(spec["classes"]), single=single, forced=forced, consensus_n=len(cons), consensus_right=cr,
               used_avg=sum(r["used"] for r in rows) / n, used_max=max(r["used"] for r in rows), stops=stops, status=spec.get("status"))
    if "map" in spec:
        pos = spec["map"]["yes"]
        res["fp"] = {"single": sum(base_pick(spec, r) == pos and truth(spec, r) != pos for r in rows), "cascade": sum(dec[r["id"]]["pick"] == pos and truth(spec, r) != pos for r in rows),
                     "consensus": sum(dec[r["id"]]["pick"] == pos and truth(spec, r) != pos for r in cons)}
    return res


def report(name, carry=True):
    s = summarize(name, carry); n = s["n"]; iv = lambda k: "%d%% (%d%% to %d%%)" % (round(k / n * 100), round(wil(k, n)[0] * 100), round(wil(k, n)[1] * 100))
    print(f"\n== {name} [{s['mode']}]: {n} images, chance {s['chance'] * 100:.0f}% ==")
    print(f"single original question : {iv(s['single'])}")
    print(f"layered, best guess      : {iv(s['forced'])}")
    c = s["consensus_n"]; print(f"layered, on consensus    : handled {c}/{n} = {c / n * 100:.0f}%, right on {s['consensus_right']}/{c}" + (f" = {s['consensus_right'] / c * 100:.0f}%" if c else ""))
    print(f"questions per image      : average {s['used_avg']:.1f}, most {s['used_max']} (budget {BUDGET})")
    print("where each image stopped : stop layer   images   avg questions   right if forced")
    for k in ("gate", "L1", "L2", "L3", "backtrack", "exhausted"):
        if k in s["stops"]:
            v = s["stops"][k]; print(f"                           {k:10s} {v['n']:6d}   {v['used'] / v['n']:12.1f}   {v['right']}/{v['n']}")
    if "fp" in s: print(f"false positives          : single {s['fp']['single']}, layered best guess {s['fp']['cascade']}, layered consensus {s['fp']['consensus']}")


TASK_OF = {"skin": "t40_skin_lesion", "dental": "t44_dental_xray", "chest": "t42_chest_xray"}
TITLE = {"skin": "Skin lesion", "dental": "Dental X-ray", "chest": "Chest X-ray"}


def cv_bound(spec, rows, folds=5):
    """supervised upper bound on whether the answers hold the information: 5-fold cross-validated logistic regression on the gate and L1 answers"""
    import numpy as np
    ids = [x["id"] for x in spec["gate"] + spec["features"]]; cl = spec["classes"]
    rows = [r for r in rows if all(i in r["asked"] for i in ids)]
    X = np.array([[r["asked"][i] for i in ids] for r in rows]); X = (X - X.mean(0)) / (X.std(0) + 1e-6); y = np.array([cl.index(truth(spec, r)) for r in rows])
    idx = np.random.RandomState(0).permutation(len(rows)); right = 0
    for k in range(folds):
        te = idx[k::folds]; tr = np.setdiff1d(idx, te); W = np.zeros((X.shape[1], len(cl))); b = np.zeros(len(cl)); Y = np.eye(len(cl))[y[tr]]
        for _ in range(400):
            Z = X[tr] @ W + b; P = np.exp(Z - Z.max(1, keepdims=True)); P /= P.sum(1, keepdims=True); G = (P - Y) / len(tr); W -= 0.5 * (X[tr].T @ G + 0.05 * W); b -= 0.5 * G.sum(0)
        right += int(((X[te] @ W + b).argmax(1) == y[te]).sum())
    return {"correct": right, "n": len(rows)}


def export():
    """one summary file for the Image Lab: /workspace/data/image-lab/runs/winnow-cascade2/summary.json"""
    import cascade as v1
    out = []
    gate = json.load(open(OUT / "gate-test.json")) if (OUT / "gate-test.json").exists() else {}
    for name in ("skin", "dental", "chest"):
        if not (OUT / f"{name}-carry.jsonl").exists(): continue
        spec, _ = load(name); s = summarize(name, True); rows = [r for r in map(json.loads, open(OUT / f"{name}-carry.jsonl")) if "error" not in r]
        plain = summarize(name, False) if (OUT / f"{name}-plain.jsonl").exists() else None
        gstops = s["stops"].get("gate", {"n": 0})["n"]
        feats = []
        for q in spec["gate"] + spec["features"]:
            m = {cl: [r["asked"][q["id"]] for r in rows if q["id"] in r["asked"] and truth(spec, r) == cl] for cl in spec["classes"]}
            m = {cl: (sum(v) / len(v) if v else None) for cl, v in m.items()}
            vals = [v for v in m.values() if v is not None]
            feats.append({"id": q["id"], "q": q["q"], "layer": "gate" if "pass" in q else "characteristics", "for": q.get("for", []), "against": q.get("against", []), "mean_by_class": m, "spread": (max(vals) - min(vals)) if len(vals) > 1 else 0})
        # version 1 (fixed battery, no budget) on the same pilot images, if it was run
        v1s = None
        f1 = v1.OUT / f"{name}.jsonl"
        if f1.exists():
            s1 = json.load(open(HERE / "cascades" / f"{name}.json")); r1 = [r for r in map(json.loads, open(f1)) if "error" not in r]
            o1 = {r["id"]: v1.outcome(s1, r) for r in r1}
            v1s = {"n": len(r1), "forced": sum(o1[r["id"]]["pick"] == v1.truth(s1, r) for r in r1 if o1[r["id"]]["pick"]), "consensus_n": sum(o1[r["id"]]["code"] == "CONSENSUS" for r in r1),
                   "consensus_right": sum(o1[r["id"]]["code"] == "CONSENSUS" and o1[r["id"]]["pick"] == v1.truth(s1, r) for r in r1), "questions": len(s1["gate"]) + len(s1["features"]) + sum(len(r["stage2"]) for r in r1) / len(r1)}
        out.append({"name": name, "task_id": TASK_OF[name], "title": TITLE[name], "summary": s, "plain": plain, "gate_passed": s["n"] - gstops,
                    "forced_gate_passed": s["forced"], "gate_test": gate.get(name), "cv": cv_bound(spec, rows), "v1": v1s, "features": feats,
                    "layers": {"gate": [{"id": q["id"], "q": q["q"]} for q in spec["gate"]], "characteristics": [{"id": q["id"], "q": q["q"]} for q in spec["features"]],
                               "discriminators": [{"id": q["id"], "q": q["q"]} for q in spec["discriminators"]], "deep": [{"id": q["id"], "q": q["q"]} for q in spec.get("deep", [])]}})
    (OUT / "summary.json").write_text(json.dumps({"budget": BUDGET, "cascades": out}, indent=1))
    print("wrote summary.json for", [c["name"] for c in out])


if __name__ == "__main__":
    cmd, name = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None; carry = "--plain" not in sys.argv
    export() if cmd == "export" else {"run": run, "report": report}[cmd](name, carry)
