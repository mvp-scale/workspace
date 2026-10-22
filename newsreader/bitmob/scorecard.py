"""Acceptance scorecard (skill step 5.1, D-0013): one card per run. Every criterion of every area, pass or fail against its own pre-stated bar.

  ✅ meets its bar   ❌ measured and below its bar (or a recorded failure)   ⬜ not measured yet (counts as not passed)
Area grade = criteria passed / criteria in the area; an area is done at >= 90% (user, 2026-10-20). Criteria and bars come from
docs/research/2026-10-20 Acceptance criteria draft.md (rev 2) and are fingerprinted: if any criterion or bar changes, the card says so.
Values come from pinned result files; rows marked "rec" carry a status recorded in the ledger (id in the evidence column).
"Stand-in" means the value was measured on a smaller or interim set than the criterion names. Info rows are shown but not counted.
Each card is saved to data/scorecard/<time>.md and appended to data/scorecard/history.jsonl.
  python3 newsreader/bitmob/scorecard.py [label]
"""
import json, glob, os, re, sys, time, statistics, hashlib
try: import numpy as np
except ImportError: os.execv("/workspace/kev/.venv/bin/python", ["/workspace/kev/.venv/bin/python"] + sys.argv)   # numpy lives in the kev venv

W = "/workspace/data"; HIST = f"{W}/scorecard/history.jsonl"; os.makedirs(f"{W}/scorecard", exist_ok=True)
J = lambda p: json.load(open(p)) if os.path.exists(p) else None
JL = lambda p: [json.loads(l) for l in open(p)] if os.path.exists(p) else []
H = JL(HIST); last = (H or [{}])[-1].get("values", {})
PASS, FAIL, TODO, GRADE = "✅", "❌", "⬜", 0.90
ge = lambda b: (lambda v: v >= b); le = lambda b: (lambda v: v <= b); lt = lambda b: (lambda v: v < b)


def newest(pattern):
    c = sorted(glob.glob(pattern), key=os.path.getmtime); return (J(c[-1]), c[-1]) if c else (None, None)


def suite_round():
    """Newest complete suite round: highest data/suite_rN whose ensemble has all four areas (json + npz); else data/suite."""
    for d in sorted(glob.glob(f"{W}/suite_r[0-9]*"), key=lambda d: -int(re.search(r"_r(\d+)$", d).group(1))):
        if all(os.path.exists(f"{d}/ensemble/{a}.{e}") for a in ("type", "topic", "conditions", "country") for e in ("json", "npz")): return d
    return f"{W}/suite"


def k6k8(f):
    """Same method as k6k8.py: threshold per key = max F1 on the night1 held-out rows, scored on testA rows only."""
    z = np.load(f, allow_pickle=True); P, Y, keys, nn = z["P"], z["Y"].astype(bool), list(z["keys"]), int(z["n_night"])
    Pv, Yv, Pt, Yt = P[:nn], Y[:nn], P[nn:], Y[nn:]; out = {}
    for i, k in enumerate(keys):
        best, th = -1, 0.5
        for t in np.unique(np.round(Pv[:, i], 3)):
            pr = Pv[:, i] >= t; tp = (pr & Yv[:, i]).sum(); f1 = 2 * tp / (pr.sum() + Yv[:, i].sum()) if pr.sum() + Yv[:, i].sum() else 0
            if f1 > best: best, th = f1, float(t)
        pr = Pt[:, i] >= th; neg = ~Yt[:, i]; tp = (pr & Yt[:, i]).sum(); fpr = float((pr & neg).sum() / max(1, neg.sum()))
        out[k] = {"threshold": round(th, 3), "fpr": round(fpr, 5), "per_1000": round(1000 * fpr, 2), "precision": round(float(tp / max(1, pr.sum())), 3), "recall": round(float(tp / max(1, Yt[:, i].sum())), 3)}
    hi = Pt >= 0.9
    bins = [{"p_from": float(lo), "n": int(((Pt >= lo) & (Pt < lo + 0.1)).sum()), "share_true": round(float(Yt[(Pt >= lo) & (Pt < lo + 0.1)].mean()), 3) if ((Pt >= lo) & (Pt < lo + 0.1)).any() else None} for lo in np.round(np.arange(0, 1, 0.1), 1)]
    return {"K6_pass_keys": sum(v["fpr"] <= 0.0025 for v in out.values()), "keys": len(out), "K8_share_true_at_p_ge_0.9": round(float(Yt[hi].mean()), 3) if hi.any() else None, "K8_n": int(hi.sum()), "calibration_bins": bins, "per_key": out}


def measures():
    m = {}; R = suite_round(); E = f"{R}/ensemble"; m["round"] = os.path.basename(R); src = m["sources"] = {}
    S = {r["n"]: r for r in JL(f"{W}/jury/pilot50/country-script-v2.jsonl")}; T = (J("/workspace/newsreader/bitmob/source_country.json") or {}).get("sources", {})
    st = {r["n"]: r for r in JL(f"{W}/jury/pilot50/stories.jsonl")}; none = [n for n, r in S.items() if not r["countries"] and not r["out_of_list"]]
    if none: m["C7"] = sum(re.sub(r"^cc:https?://", "", st[n]["id"]).split("/")[0] in T for n in none) / len(none)
    srcs = {r.get("outlet") or r.get("feed") for f in glob.glob(f"{W}/trainset/*.jsonl") if not f.endswith("pilot1.jsonl") for r in JL(f)} - {None}
    if srcs: m["C9"] = sum(s in T for s in srcs) / len(srcs)
    if S: m["C10"] = statistics.median(r["ms"] for r in S.values())
    cv = J(f"{W}/country-val/country-val.json")
    if cv: m["CV"] = cv
    ty = J(f"{E}/type.json"); ap = (ty or {}).get("per_key_AP", {})
    if all(ap.get(g) is not None for g in ("happened", "announced", "opinion", "forecast")): m["T2"] = {g: ap[g] for g in ("happened", "announced", "opinion", "forecast")}; src["T2"] = f"{E}/type.json"
    tp = J(f"{E}/topic.json")
    if tp: m["P2"] = tp["accuracy"]; src["P2"] = f"{E}/topic.json"
    allst, _ = newest(f"{W}/testA/r*/status.json")
    cj = J(f"{E}/conditions.json")
    if cj:
        ks = {k: {"AP": v, "noise_sd": 0} for k, v in cj["per_key_AP"].items() if v is not None}; sc = list(ks.values()); src["K2"] = f"{E}/conditions.json"
        m["K2keys"] = ks; m["K2"] = (sum(v["AP"] >= 0.70 for v in sc), len(sc)); m["K2m"] = statistics.mean(v["AP"] for v in sc); m["reader"] = f"ensemble e5+TF-IDF / e5 fine-tuned, {m['round']}"
    if allst: m["K3"] = (sum(v["status"] != "rare" for v in allst["keys"].values()), len(allst["keys"])); m["K3keys"] = allst["keys"]
    kz = f"{E}/conditions.npz"
    if os.path.exists(kz):
        kk = k6k8(kz); src["K6"] = src["K8"] = kz
        m["K6"] = (kk["K6_pass_keys"], kk["keys"]); m["K6keys"] = kk["per_key"]; m["K8"] = kk["K8_share_true_at_p_ge_0.9"]; m["K8n"] = kk["K8_n"]; m["K8bins"] = kk["calibration_bins"]
    rs = sorted(glob.glob(f"{W}/testA/r*/status.json"), key=os.path.getmtime)
    if len(rs) >= 2:
        a, b = J(rs[-2])["keys"], J(rs[-1])["keys"]      # regression rule: an accepted (>= 0.70) key falls below 0.70 by more than ~2 noise SD
        m["K10"] = [k for k in a if (a[k].get("AP") or 0) >= 0.70 and b.get(k, {}).get("AP") is not None and b[k]["AP"] < 0.70 - 2 * b[k]["noise_sd"]]
    return m


def criteria(m):
    """(area, id, criterion, bar text, value, test(value) -> bool or None, evidence). value None = not measured. test None = recorded status in evidence."""
    cv = m.get("CV") or {}; c1, c2, c4, c5, c6, c8 = (cv.get(k) for k in ("C1", "C2", "C4", "C5", "C6", "C8"))
    stab = lambda x: "stable dev->fresh" if x and x.get("stable") else ("NOT stable" if x else "")
    k2 = m.get("K2"); k3 = m.get("K3"); t2 = m.get("T2")
    return [
        ("Country", "C1", "Named countries found (recall)", ">= 0.97", c1["fresh_random"] if c1 else None, ge(0.97), f"fresh random vs reviewer; dev {c1['dev']:.3f}; {stab(c1)} (F-0060+)" if c1 else "needs reviewer labels"),
        ("Country", "C2", "No false country (precision)", ">= 0.97", c2["fresh_all"] if c2 else None, ge(0.97), f"all 300 fresh vs reviewer; dev {c2['dev']:.3f}; {stab(c2)}; club probes 0.53" if c2 else "-"),
        ("Country", "C3", "Every one of the 100 when named", "18/20 per country; region >= 0.95", None, None, "probe set not built"),
        ("Country", "C4", "Name, demonym, city, region", ">= 0.95/0.95/0.90/0.90", None, None, f"partial: demonym {c4['demonym']:.3f}, city {c4['city']:.3f} pass; name and region probes not built" if c4 else "probe set not built"),
        ("Country", "C5", "Look-alikes never swapped", "0 swaps", c5["swaps"] if c5 else None, (lambda v: v == 0), f"{c5['stories']} look-alike probes" if c5 else "probe set not built"),
        ("Country", "C6", "Ambiguous words go to review", ">= 0.95 routed", min(c6["club_clean"], c6["ambiguous_clean"]) if c6 else None, ge(0.95), f"share of probe stories given no false country: club {c6['club_clean']:.2f}, ambiguous {c6['ambiguous_clean']:.2f} (30 probes each)" if c6 else "-"),
        ("Country", "C7", "Fallback matches outlet table", "100%", m.get("C7"), ge(1.0), "stand-in: pilot50 stories naming no place"),
        ("Country", "C8", "Off-list places never forced on a neighbour", "0 forced, P-outside >= 50", (c8["off_list_stories"] - c8["handled"]) if c8 else None, (lambda v: v == 0), f"{c8['handled']}/{c8['off_list_stories']} off-list stories handled; dedicated probe set (>= 50) not built" if c8 else "-"),
        ("Country", "C9", "Source table complete", "100%", m.get("C9"), ge(1.0), "all sources in labelled sets"),
        ("Country", "C10", "Speed", "< 20 ms/story", m.get("C10"), lt(20), "median, pilot50"),
        ("Country", "C11", "Regression", "no drop", None, None, "no rounds yet"),
        ("Story type", "T1", "Codebook agreement", "alpha >= 0.8 per type", None, None, "definition test T-0011 not run"),
        ("Story type", "T2", "Per type AP", "happened 0.95, announced 0.90, opinion 0.85, forecast 0.85", t2, (lambda v: v["happened"] >= 0.95 and v["announced"] >= 0.90 and v["opinion"] >= 0.85 and v["forecast"] >= 0.85), f"{m.get('round')} ensemble on night1 held-out + testA vs Jev"),
        *[("Story type", f"T{i}", n, b, None, None, "not built") for i, n, b in ((3, "Opinion from URL or feed", "recall >= 0.95"), (4, "Announced vs happened on plan words", ">= 0.90"), (5, "Forecast vs report of a forecast", ">= 0.85"),
            (6, "Flip test (will raise / raised)", "drop >= half"), (7, "False alarms on non-news", "<= 50 per 1,000"), (8, "Calibration", "0.9 conf -> >= 90% right"), (9, "Headline-only cases", "within 0.05 of T2"), (10, "Regression", "no drop"))],
        *[("Scope/focus", f"S{i}", n, b, None, None, "not built") for i, n, b in ((1, "Codebook agreement", "alpha >= 0.8"), (2, "Each label: national, local, new, recent", "AP >= 0.85 each"), (3, "US/foreign focus from the country rule", "100% consistent"),
            (4, "Old events not recent", "recall >= 0.90"), (5, "Local places read as local", ">= 0.85"), (6, "National markers read as national", ">= 0.85"), (7, "Calibration", "0.9 conf -> >= 90% right"), (8, "Regression", "no drop"), (9, "No scope for stories without one", "<= 50 per 1,000"))],
        ("Topic", "P1", "Codebook agreement", "alpha >= 0.8 per topic", None, None, "not run; sport gap (F-0051)"),
        ("Topic", "P2", "Overall accuracy", ">= 0.85", m.get("P2"), ge(0.85), f"{m.get('round')} ensemble on night1 held-out + testA vs Jev"),
        *[("Topic", f"P{i}", n, b, None, None, "not built") for i, n, b in ((3, "Every topic works", "recall >= 0.70 each"), (4, "Confusable pairs", ">= 0.80"), (5, "'Other' not a dump", "<= 10% and precision >= 0.80"), (6, "Section hint agrees with text", ">= 0.90"),
            (7, "Non-news not given an economic topic", "<= 20 per 1,000"), (8, "Calibration", "0.9 conf -> >= 90% right"), (9, "Top-2 contains the jury topic", ">= 0.95"), (10, "Regression", "no drop"))],
        ("Conditions", "K1", "Codebook agreement per key", "alpha >= 0.8", "rec", False, "rec: juror overlap 0.34-0.41 (F-0049)"),
        ("Conditions", "K2", "Per-key quality", "AP >= 0.70 on every accepted key", k2, (lambda v: v[0] == v[1]), f"{k2[0]} of {k2[1]} keys; reader: {m.get('reader')}" if k2 else "-"),
        ("Conditions", "K3", "Enough positives to score", ">= 30 per key (77 keys)", k3, (lambda v: v[0] == v[1]), f"{k3[0]} of {k3[1]} keys" if k3 else "-"),
        *[("Conditions", f"K{i}", n, b, None, None, "not built") for i, n, b in ((4, "Direction never swapped (flip pairs)", "wrong-direction p drops >= half"), (5, "Passing mention does not count", "<= 50 per 1,000"))],
        ("Conditions", "K6", "False alarms on stories with no condition", "<= 2.5 per 1,000 per key", m.get("K6"), (lambda v: v[0] == v[1]), "thresholds set on night1 held-out, scored on testA"),
        ("Conditions", "K7", "Engine tolerance (the goal, F-0020)", "all keys inside tolerance (d)", None, None, "not built"),
        ("Conditions", "K8", "Calibration", "0.9 conf -> >= 90% right", m.get("K8"), ge(0.90), f"testA, {m.get('K8n')} predictions at p >= 0.9"),
        ("Conditions", "K9", "Per-item proof", ">= 18 of 20 false alarms explained", None, None, "not built"),
        ("Conditions", "K10", "Regression", "no accepted key drops beyond its interval", m.get("K10"), (lambda v: not v), "frozen test, last two rounds"),
    ]


def main(label):
    m = measures(); rows = criteria(m); print(f"inputs: suite round {m['round']}; " + "; ".join(f"{k} <- {v}" for k, v in m["sources"].items()), file=sys.stderr)
    fp = hashlib.sha256(json.dumps([(r[1], r[2], r[3]) for r in rows]).encode()).hexdigest()[:12]
    prev_fp = next((h.get("criteria_fp") for h in reversed(H) if h.get("criteria_fp")), None)
    lines, vals, nums, grade, area, notes, fails = [], {}, {}, {}, None, [], []
    for a, cid, name, bar, v, test, ev in rows:
        if isinstance(v, float): nums[cid] = v
        elif isinstance(v, tuple): nums[cid] = v[0] / v[1] if v[1] else None
        if v is None: s = TODO
        elif v == "rec": s = PASS if test else FAIL
        else: s = PASS if test(v) else FAIL
        grade.setdefault(a, [0, 0]); grade[a][1] += 1; grade[a][0] += s == PASS; vals[cid] = s
        if a != area: lines += ["", f"**{a}**", "", "| # | Criterion | Bar | Value | | Parts | Why / evidence |", "|---|---|---|---|---|---|---|"]; area = a
        pp, why = detail(cid, s, v, m, ev)
        if s == FAIL: fails.append(f"{cid} ({name}): {why}")
        val = "-" if v in (None, "rec") else (f"{v:.3f}" if isinstance(v, float) else "/".join(map(str, v)) if isinstance(v, tuple) else ", ".join(f"{k} {x}" for k, x in v.items()) if isinstance(v, dict) else (str(len(v)) + " dropped" if isinstance(v, list) else str(v)))
        ch = "" if cid not in last or last[cid] == s else f" (was {last[cid]})"
        dg = diagnose(cid, s, nums.get(cid), bar)
        if dg: notes.append(f"{cid} {dg}")
        lines.append(f"| {cid} | {name} | {bar} | {val} | {s}{ch}{' · ' + dg if dg else ''} | {pp} | {why} |")
    tot = [sum(g[0] for g in grade.values()), sum(g[1] for g in grade.values())]
    summary = ["| Area | Passed | Grade | Done (>= 90%) |", "|---|---|---|---|"] + [f"| {a} | {p}/{n} | {p / n:.0%} | {'✅' if p / n >= GRADE else '—'} |" for a, (p, n) in grade.items()] + [f"| **All** | **{tot[0]}/{tot[1]}** | **{tot[0] / tot[1]:.0%}** | {'✅' if tot[0] / tot[1] >= GRADE else '—'} |"]
    info = f"Info (not counted): conditions mean AP {m['K2m']:.3f} ({m.get('reader')})." if "K2m" in m else ""
    lock = "criteria unchanged since last card" if prev_fp in (None, fp) else f"⚠ CRITERIA OR BARS CHANGED since last card ({prev_fp} -> {fp}): record the reason in the ledger"
    card = f"## Scorecard {time.strftime('%F %H:%M')} — {label}\n\nCriteria fingerprint {fp}: {lock}.\n\n" + "\n".join(summary) + "\n\n" + info + "\n" + "\n".join(lines) + "\n\n**Why each failure failed**\n\n" + "\n".join(f"- {f}" for f in fails) + "\n"
    changes = [f"{c} {last[c]}->{v}" for c, v in vals.items() if c in last and last[c] != v]
    stamp = time.strftime("%Y%m%d-%H%M%S"); path = f"{W}/scorecard/{stamp}.md"; open(path, "w").write(card)
    open(HIST, "a").write(json.dumps({"ts": stamp, "label": label, "criteria_fp": fp, "values": vals, "nums": nums, "grade": grade, "info": {"K2m": m.get("K2m")}}, ensure_ascii=False) + "\n")
    print(card)
    if "--no-ledger" not in sys.argv: ledger(label, tot, grade, vals, changes, notes, lock, path, fails)


def detail(cid, s, v, m, ev):
    """Parts passed / parts total, and a reason in plain words (which parts failed and by how much)."""
    if s == TODO: return "-", f"not measured: {ev}"
    if v == "rec": return "-", ev
    if cid == "T2":
        bars = {"happened": 0.95, "announced": 0.90, "opinion": 0.85, "forecast": 0.85}; bad = [f"{g} {v[g]:.2f} < {b}" for g, b in bars.items() if v[g] < b]
        return f"{4 - len(bad)}/4", ("fails on " + ", ".join(bad) if bad else "all four types meet their bars") + f"; {ev}"
    if cid == "K2":
        ks = sorted(m["K2keys"].items(), key=lambda x: x[1]["AP"]); bad = [x for x in ks if x[1]["AP"] < 0.70]
        near = [f"{k} {x['AP']:.2f}" for k, x in bad if x["AP"] >= 0.70 - 2 * x.get("noise_sd", 0)]
        return f"{v[0]}/{v[1]}", (f"{len(bad)} keys below 0.70; worst: " + ", ".join(f"{k} {x['AP']:.2f}" for k, x in bad[:4]) + (f"; within noise of the bar: {', '.join(near)}" if near else "") + f"; {ev}")
    if cid == "K3":
        rare = sorted(((k, x["train_pos"]) for k, x in m["K3keys"].items() if x["status"] == "rare"), key=lambda x: x[1])
        return f"{v[0]}/{v[1]}", f"{len(rare)} keys under 30 training positives; fewest: " + ", ".join(f"{k} {n}" for k, n in rare[:5])
    if cid == "K6":
        bad = sorted(((k, x) for k, x in m["K6keys"].items() if x["fpr"] > 0.0025), key=lambda x: -x[1]["per_1000"])
        return f"{v[0]}/{v[1]}", f"{len(bad)} keys above 2.5 per 1,000; worst: " + ", ".join(f"{k} {x['per_1000']}/1,000 (precision {x['precision']})" for k, x in bad[:4])
    if cid == "K8":
        b = [f"{x['p_from']:.1f}+: {x['share_true']}" for x in m["K8bins"] if x["n"] and x["p_from"] >= 0.5]
        return ("1/1" if v >= 0.90 else "0/1"), f"{v:.0%} of p >= 0.9 predictions are true (bar 90%); share true by probability band: " + ", ".join(b)
    if cid == "K10": return ("1/1" if not v else "0/1"), ("no accepted key dropped beyond its noise" if not v else "dropped: " + ", ".join(v))
    if cid == "P2": return ("1/1" if v >= 0.85 else "0/1"), (f"{v:.3f} vs bar 0.85 (gap {0.85 - v:.3f}); {ev}" if v < 0.85 else ev)
    if isinstance(v, float): return ("1/1" if s == PASS else "0/1"), ev
    return "-", ev


def diagnose(cid, s, num, bar):
    """Is a criterion possibly too weak (passed from its first measurement by a wide margin) or too hard (failed on >= 3 cards, value not improving)?"""
    past = [(h["values"].get(cid), (h.get("nums") or {}).get(cid)) for h in H if h.get("values", {}).get(cid) in (PASS, FAIL)]
    if s == PASS and past and all(p[0] == PASS for p in past) and num is not None:
        b = re.findall(r"[\d.]+", bar); b = float(b[0]) if b else None
        if b and b <= 1 and num >= b + 0.5 * (1 - b) and num < 1: return "possibly too weak (wide margin since first card)"
    # count runs, not reprints: consecutive cards with the same value are one run
    runs = [p for i, p in enumerate(past) if p[1] is not None and (i == 0 or p[1] != past[i - 1][1])]
    ns = [p[1] for p in runs if p[0] == FAIL] + ([num] if s == FAIL and num is not None and (not runs or num != runs[-1][1]) else [])
    if s == FAIL and len(ns) >= 3 and ns[-1] <= ns[-3] + 1e-9: return "possibly too hard (failed 3+ runs, not improving): consensus per D-0013"
    return ""


def ledger(label, tot, grade, vals, changes, notes, lock, path, fails=()):
    """Record this card as a ledger fact with the card file pinned (the ledger is the record of every iteration)."""
    import subprocess
    t = f"Scorecard {label}: {tot[0]}/{tot[1]} criteria pass ({tot[0] / tot[1]:.0%}); " + "; ".join(f"{a} {p}/{n}" for a, (p, n) in grade.items())
    body = (f"Passed: {', '.join(c for c, v in vals.items() if v == PASS) or 'none'}. Failed: {', '.join(c for c, v in vals.items() if v == FAIL) or 'none'}. "
            f"Why failed: {' | '.join(fails) or 'none'}. Not measured: {sum(v == TODO for v in vals.values())}. Changes since last card: {', '.join(changes) or 'none'}. Diagnoses: {'; '.join(notes) or 'none'}. {lock}.")
    L = ["node", "/workspace/tools/ledger.mjs"]
    fid = subprocess.run(L + ["add", "fact", t, "--step", "3", "--tag", "scorecard", "--tag", "ontology-trainer", "--ref", "D-0018", "--body", body], capture_output=True, text=True).stdout.strip().split()[0]
    subprocess.run(L + ["evidence", fid, "--file", os.path.relpath(path, "/workspace"), "--cmd", "python3 newsreader/bitmob/scorecard.py " + label, "--supports"], capture_output=True, cwd="/workspace")
    subprocess.run(L + ["prove", fid, "--why", "scorecard computed from pinned results"], capture_output=True, cwd="/workspace")
    print(f"ledger: {fid}")


def history():
    """Every criterion across every recorded card."""
    hs = [h for h in H if h.get("criteria_fp")]
    if not hs: print("no cards yet"); return
    ids = list(hs[-1]["values"]); print("| Card | " + " | ".join(h["ts"][4:13] for h in hs) + " |"); print("|---|" + "---|" * len(hs))
    tot = lambda h: f"{sum(v == PASS for v in h['values'].values())}/{len(h['values'])}"
    print("| **Passed** | " + " | ".join(tot(h) for h in hs) + " |")
    for c in ids: print(f"| {c} | " + " | ".join(h["values"].get(c, " ") for h in hs) + " |")


if __name__ == "__main__":
    if "--history" in sys.argv: history()
    else: main(next((a for a in sys.argv[1:] if not a.startswith("--")), "manual"))
