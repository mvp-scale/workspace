"""p3_threshold_check (T152 P3c): is a per-field cut-off for precision 0.90 real, or fitted to the same stories it is scored on?
Input: jsonl or json list of per-story rows {"id", "field" (optional, one result per field), "score", and either "correct" (true if the answer matches the labels) or "pred" and "truth"; optional "cites" = number of evidence bundles the answer lists}. Scores on 0..1 are read as 0..1000 (the decider's confidence scale); the grid is 300..950 step 50 as in the plan.
Rule, fixed before the run: split the stories with a fixed seed (--seed, default 7) into a choose half and a confirm half. On the choose half take the LOWEST threshold on the grid where precision (correct among answered, answered = score >= thr) is at least 0.90 with at least 30 answered. Apply it to the confirm half. Pass only if precision on the confirm half is at least 0.90 and at least 30 stories are answered there. Otherwise the field keeps the default threshold (--default-thr 700). The Wilson 95% lower bound is reported beside it (plan P3: at least 0.80, informational here; --wilson-min makes it a pass condition). Coverage (answered share) is reported at the chosen cut-off and at the default so a gain in precision is never shown without what it costs. If rows carry "cites", answered rows with 0 cites are counted (P3: every answer cites at least one bundle) and make the pass false when --require-cites is given.
Label source is required and printed on every line and in the file: --label-kind agreement --label-source <teacher or labeller name> prints 'agreement with <source>'; --label-kind outside prints 'outside truth'. Agreement is not accuracy, so a pass on agreement is reported as such.
Exit 0 pass for every field, 1 fail, 2 bad input.
    /workspace/models/embed-zs/.venv/bin/python validate/p3_threshold_check.py --scores FILE --label-kind agreement --label-source Sonnet [--seed 7] [--default-thr 700]   (from projects/world-state)  -> runs/pulse/validate/p3_threshold_check.json
    /workspace/models/embed-zs/.venv/bin/python validate/p3_threshold_check.py --selftest     (synthetic data with a known answer; writes runs/pulse/validate/p3_threshold_check_selftest.json)"""
import os, sys, json, math, random, argparse, pathlib
WS = pathlib.Path(__file__).resolve().parents[1]; OUTD = WS / "runs/pulse/validate"; GRID = list(range(300, 951, 50))
def wilson_lo(k, n, z=1.96):
    if n == 0: return 0.0
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return (c - r) / d
def stat(rows, thr):
    a = [r for r in rows if r["score"] >= thr]; k = sum(r["correct"] for r in a); return {"thr": thr, "answered": len(a), "correct": k, "precision": round(k / len(a), 4) if a else None, "coverage": round(len(a) / max(len(rows), 1), 4), "wilson_lo": round(wilson_lo(k, len(a)), 4), "no_cite": sum(1 for r in a if r.get("cites") == 0)}
def norm(rows):
    out = []
    for r in rows:
        s = float(r["score"]); s = s * 1000 if s <= 1.0 else s; c = bool(r["correct"]) if "correct" in r else (r["pred"] == r["truth"]); out.append({**r, "score": s, "correct": c})
    return out
def one_field(rows, seed, min_n=30, prec=0.90, default=700, wilson_min=None, require_cites=False):
    rows = sorted(rows, key=lambda r: str(r.get("id"))); rng = random.Random(seed); idx = list(range(len(rows))); rng.shuffle(idx); h = len(idx) // 2; ch = [rows[i] for i in idx[:h]]; cf = [rows[i] for i in idx[h:]]
    chosen = None
    for t in GRID:
        s = stat(ch, t)
        if s["answered"] >= min_n and s["precision"] is not None and s["precision"] >= prec: chosen = t; break
    out = {"n": len(rows), "n_choose": len(ch), "n_confirm": len(cf), "choose_table": [stat(ch, t) for t in GRID], "chosen_thr": chosen}
    if chosen is None: out.update({"keeps": default, "confirm": stat(cf, default), "at_default_all": stat(rows, default), "pass": False, "why": "no threshold on the choose half reaches precision %.2f with >= %d answered" % (prec, min_n)}); return out
    c = stat(cf, chosen); ok = c["precision"] is not None and c["precision"] >= prec and c["answered"] >= min_n; why = None if ok else ("confirm precision %s below %.2f" % (c["precision"], prec) if not (c["precision"] is not None and c["precision"] >= prec) else "confirm half answered %d < %d" % (c["answered"], min_n))
    if ok and wilson_min is not None and c["wilson_lo"] < wilson_min: ok = False; why = "Wilson lower bound %.3f < %.2f" % (c["wilson_lo"], wilson_min)
    if ok and require_cites and c["no_cite"]: ok = False; why = "%d answered rows cite no bundle" % c["no_cite"]
    out.update({"confirm": c, "at_default_confirm": stat(cf, default), "pass": ok, "why": why, "keeps": chosen if ok else default}); return out
def run(rows, kind, source, seed=7, **kw):
    rows = norm(rows); fields = sorted({r.get("field", "all") for r in rows}); res = {f: one_field([r for r in rows if r.get("field", "all") == f], seed, **kw) for f in fields}
    lab = "agreement with %s" % source if kind == "agreement" else "outside truth"
    return {"label": lab, "seed": seed, "grid": [GRID[0], GRID[-1], 50], "fields": res, "pass": all(v["pass"] for v in res.values()), "note": "agreement is not accuracy" if kind == "agreement" else "scored against a truth set outside the system"}
def selftest():
    rng = random.Random(11); rows = []
    for i in range(600):   # known answer: true precision is 0.5 + 0.5*score/1000 clipped, so precision 0.90 is first reached near score 800; every answer above 850 is right 97% of the time
        sc = rng.randint(300, 999); p = 0.55 if sc < 700 else 0.80 if sc < 800 else 0.93 if sc < 850 else 0.97; rows.append({"id": "s%d" % i, "field": "domain", "score": sc, "correct": rng.random() < p, "cites": 1})
    r1 = run(rows, "agreement", "Sonnet"); f = r1["fields"]["domain"]; assert f["chosen_thr"] is not None and 750 <= f["chosen_thr"] <= 850, f["chosen_thr"]; assert f["pass"] and f["confirm"]["precision"] >= 0.90 and f["confirm"]["answered"] >= 30 and r1["label"] == "agreement with Sonnet", f
    weak = [{"id": "w%d" % i, "field": "area", "score": rng.randint(300, 999), "correct": rng.random() < 0.6} for i in range(600)]; r2 = run(weak, "outside", None); fw = r2["fields"]["area"]; assert not fw["pass"] and fw["keeps"] == 700 and r2["label"] == "outside truth", fw   # no real signal, so no cut-off may pass
    few = [{"id": "f%d" % i, "field": "tiny", "score": 990, "correct": True} for i in range(50)]; r3 = run(few, "outside", None); ft = r3["fields"]["tiny"]; assert ft["confirm"]["answered"] == 25 and not ft["pass"]   # 25 answered per half is under the 30 floor even at precision 1.0
    leak = [{"id": "l%d" % i, "field": "overfit", "score": rng.randint(300, 999), "correct": rng.random() < 0.88} for i in range(400)]; r4 = run(leak, "outside", None, seed=7)   # true precision 0.88 everywhere: any pass would be a lucky split; the seed is fixed so this is reproducible
    r5 = run(rows, "agreement", "Sonnet", require_cites=True); r6 = run([dict(x, cites=0) for x in rows], "agreement", "Sonnet", require_cites=True); assert r5["pass"] and not r6["pass"] and "cite" in r6["fields"]["domain"]["why"]
    assert run(rows, "agreement", "Sonnet")["fields"]["domain"]["chosen_thr"] == f["chosen_thr"]   # same seed, same answer
    return {"known_answer_pass": {"chosen_thr": f["chosen_thr"], "confirm": f["confirm"], "label": r1["label"]}, "no_signal_fails": {"keeps": fw["keeps"], "why": fw["why"]}, "too_few_answered_fails": {"confirm_answered": ft["confirm"]["answered"], "why": ft["why"]}, "flat_088_field": {"pass": r4["fields"]["overfit"]["pass"], "chosen_thr": r4["fields"]["overfit"]["chosen_thr"], "confirm": r4["fields"]["overfit"].get("confirm")}, "cites_required": "pass with cites, fail with cites=0", "deterministic": True}
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--scores"); ap.add_argument("--label-kind", choices=("agreement", "outside")); ap.add_argument("--label-source"); ap.add_argument("--seed", type=int, default=7); ap.add_argument("--default-thr", type=int, default=700); ap.add_argument("--wilson-min", type=float); ap.add_argument("--require-cites", action="store_true"); ap.add_argument("--selftest", action="store_true"); ap.add_argument("--out"); a = ap.parse_args(); OUTD.mkdir(parents=True, exist_ok=True)
    if a.selftest:
        try: r = selftest(); ok = True
        except AssertionError as ex: import traceback; traceback.print_exc(); r = {"assertion_failed": True}; ok = False
        json.dump(r, open(a.out or OUTD / "p3_threshold_check_selftest.json", "w"), indent=1); print("selftest:", "PASS" if ok else "FAIL", json.dumps(r)[:400]); sys.exit(0 if ok else 1)
    if not a.scores or not os.path.exists(a.scores) or not a.label_kind or (a.label_kind == "agreement" and not a.label_source): print("NOT RUN: need --scores FILE and --label-kind agreement --label-source <name> | outside"); sys.exit(2)
    txt = open(a.scores).read(); rows = json.loads(txt) if txt.lstrip().startswith("[") else [json.loads(l) for l in txt.splitlines() if l.strip()]
    r = run(rows, a.label_kind, a.label_source, a.seed, default=a.default_thr, wilson_min=a.wilson_min, require_cites=a.require_cites); json.dump(r, open(a.out or OUTD / "p3_threshold_check.json", "w"), indent=1)
    for f, v in r["fields"].items(): c = v.get("confirm") or {}; print("%-12s [%s] chosen thr %s -> keeps %s | confirm precision %s, answered %s of %s, coverage %s (at default %s) | %s" % (f, r["label"], v["chosen_thr"], v["keeps"], c.get("precision"), c.get("answered"), v["n_confirm"], c.get("coverage"), (v.get("at_default_confirm") or v.get("confirm") or {}).get("coverage"), "PASS" if v["pass"] else "FAIL: " + str(v["why"])))
    sys.exit(0 if r["pass"] else 1)
