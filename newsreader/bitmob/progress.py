"""Live progress for the ontology trainer (T-0025): jobs post events here, and build() writes one status file the /mockups/trainer page polls.

  python3 newsreader/bitmob/progress.py event <job> <state> "<message>" [--pid N] [--win]   state: queued|running|training|scoring|done|failed
  python3 newsreader/bitmob/progress.py build        (also run by the Claude Code PostToolUse hook, so the page follows every step)
From Python: from progress import event; event("setfit:topic", "training", "epoch 1/2", pid=os.getpid())
Sources: data/progress/events.jsonl (jobs), ledger (facts, predictions, tasks), data/scorecard/ (cards), MM3 evidence in the ledger.
"""
import glob, json, os, sys, time, subprocess, collections

W = "/workspace"; EV = f"{W}/data/progress/events.jsonl"; OUT = f"{W}/demo/mockups/trainer/live.json"


def event(job, state, msg, pid=None, win=False, **data):
    os.makedirs(os.path.dirname(EV), exist_ok=True)
    with open(EV, "a") as f: f.write(json.dumps({"ts": time.time(), "job": job, "state": state, "msg": msg, "pid": pid, "win": win, **data}) + "\n")
    subprocess.Popen(["python3", os.path.abspath(__file__), "build"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)   # always the current code, never blocks the job


def alive(pid):
    try: os.kill(int(pid), 0); return True
    except Exception: return False


def ledger():
    r = subprocess.run(["node", f"{W}/tools/ledger.mjs", "list", "--json"], capture_output=True, text=True, timeout=10)
    return [json.loads(l) for l in r.stdout.splitlines() if l.strip()]


def pin(f, want, cache):
    """ok / CHANGED / MISSING for a pinned file, hashed once per (mtime, size)."""
    import hashlib
    path = f if f.startswith("/") else f"{W}/{f}"
    try: st = os.stat(path)
    except OSError: return "MISSING"
    k = f"{path}|{st.st_mtime}|{st.st_size}"
    if k not in cache:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for b in iter(lambda: fh.read(1 << 20), b""): h.update(b)
        cache[k] = h.hexdigest()
    return "ok" if cache[k] == want else "CHANGED"


def ledger_view(items):
    """Every ledger item with its evidence and a proof verdict: validated (proven, evidence present, all pins unchanged), weak (proven but a pin changed or no evidence), unproven."""
    cf = f"{W}/data/progress/sha-cache.json"; cache = json.load(open(cf)) if os.path.exists(cf) else {}
    out = []
    for it in items:
        ev = []
        for e in it.get("evidence") or []:
            src = e.get("src"); what = e.get("file") or e.get("mm3") or e.get("item") or e.get("url") or e.get("text") or e.get("stated") or ""
            ev.append({"eid": e.get("eid"), "src": src, "stance": e.get("stance"), "what": str(what)[:300], "note": e.get("note"), "cmd": e.get("cmd"), "ts": e.get("ts"),
                       "pin": pin(e["file"], e.get("sha256"), cache) if src == "file" and e.get("sha256") else None})
        bad = [e for e in ev if e["pin"] in ("CHANGED", "MISSING")]
        verdict = "unproven" if it["proof"] != "proven" else ("weak" if bad or not ev else "validated")
        if it["proof"] in ("disproven", "retracted"): verdict = it["proof"]
        out.append({"id": it["id"], "kind": it["kind"], "title": it["title"], "body": it.get("body"), "proof": it["proof"], "state": it["state"], "step": it.get("step"),
                    "refs": it.get("refs") or [], "created": it.get("created"), "verdict": verdict, "evidence": ev,
                    "n": {s: sum(e["src"] == s for e in ev) for s in ("mm3", "file", "item")}, "bad": len(bad),
                    "predictions": [{"rid": p.get("rid"), "text": p.get("text"), "p": p.get("p"), "result": p.get("result"), "actual": p.get("actual")} for p in it.get("predictions") or []]})
    json.dump(cache, open(cf, "w"))
    return out


PLAIN = [("Codebook agreement", "Reviewers agree on definitions"), ("alpha >=", "reviewer agreement >="), ("alpha", "reviewer agreement"), ("Per type AP", "Per kind ranking score"), ("AP >=", "ranking score >="),
         (">=", "≥"), ("<=", "≤"), ("conf ->", "confidence ->"), ("tolerance (d)", "the engine's tolerance"), ("P-outside", "off-list probes"), ("Per-key", "Per-condition"),
         (" keys", " conditions"), (" key", " condition"), ("p drops", "probability drops"), ("within 0.05 of T2", "within 0.05 of the story-kind score"), ("demonym", "nationality word"), ("(the goal, F-0020)", "(the goal)")]


def plain(t):
    for a, b in PLAIN: t = t.replace(a, b)
    return t


def criteria_view(card, models):
    """One row per acceptance criterion: plain name, pass mark, state from the card, and the best value now (from the card numbers or the per-model grid)."""
    if not card: return []
    import scorecard
    ms = models.get("models") or []
    def best(area, key):
        c = [(m["areas"][area], m["name"]) for m in ms if area in m.get("areas", {}) and key(m["areas"][area]) is not None]
        return max(c, key=lambda x: key(x[0])) if c else (None, None)
    pct = lambda v: f"{round(100 * v)}%"
    out = []
    for area, cid, name, bar, *_ in scorecard.criteria({}):
        v = card["values"].get(cid); n = (card.get("nums") or {}).get(cid); val = model = None
        if cid == "T2": c, model = best("type", lambda c: (c["pass"], c["score"])); val = c and f"{c['pass']} of 4 kinds"
        elif cid == "P2": c, model = best("topic", lambda c: c["score"]); val = c and pct(c["score"])
        elif cid == "K2": c, model = best("conditions", lambda c: c["pass"]); val = c and f"{c['pass']} of {c['of']} conditions"
        elif cid == "K6": c, model = best("conditions", lambda c: c["k6"][0] if c.get("k6") and c["k6"][0] is not None else None); val = c and f"{c['k6'][0]} of {c['k6'][1]} conditions"
        elif n is not None:
            val = f"{n:.1f} ms" if cid == "C10" else pct(n) + (" of conditions" if cid == "K3" else ""); model = "country script" if cid[0] == "C" else None
        out.append({"id": cid, "area": area, "name": plain(name), "bar": plain(bar), "state": {"✅": "pass", "❌": "fail"}.get(v, "none"), "best": val, "model": model})
    return out


CONTRACT_IDS = ["P-0016", "P-0017", "P-0018", "P-0019", "P-0020", "P-0021", "P-0022", "P-0023"]
LABEL_JOBS = [("clef-test", "Frozen test", 2000, "test.jsonl"), ("clef-country", "Country-mined", 1200, "country.jsonl"), ("clef-train", "Train", 6000, "train.jsonl"), ("clef-r1local", "Round 1 train (5090, part 1)", 500, "r1_local.jsonl"), ("clef-r1b", "Round 1 train (5090, part 2)", 500, "r1b.jsonl")]


BARS = {"P-0016": 0.90, "P-0017": 0.90, "P-0018": 0.80, "P-0019": 0.90, "P-0020": 0.75, "P-0021": 0.75}   # numeric pass marks (higher is better), as in the ledger targets; P-0022 open, P-0023 not numeric


def shortfall(v, bar):
    return max(0.0, (bar - v) / bar) if isinstance(v, (int, float)) and isinstance(bar, (int, float)) and bar else None


def rounds_view(rounds):
    """Per round: value line = sum over rows of normalised shortfall max(0,(bar-value)/bar) at the previous round minus this round (rows measured in both), per 1,000 stories and per GPU hour."""
    out = []
    for i, r in enumerate(rounds):
        rows = r.get("rows") or {}; prev = (rounds[i - 1].get("rows") or {}) if i else {}; closed, n_rows, before = 0.0, 0, 0.0
        for pid in BARS:
            c, p = rows.get(pid) or {}, prev.get(pid) or {}; bar = c.get("bar", BARS[pid])
            a, b = shortfall(p.get("value"), p.get("bar", BARS[pid])), shortfall(c.get("value"), bar)
            if a is not None and b is not None: closed += a - b; n_rows += 1; before += a
        lab = r.get("labelling") or {}; gh = (r.get("kaggle_gpu_h") or 0) + (r.get("five090_min") or 0) / 60
        added = r.get("stories_added") or 0
        out.append({"round": r["round"], "made": r.get("made"), "stories_added": r.get("stories_added"), "stories_total": r.get("stories_total"), "five090": lab.get("five090"), "kaggle": lab.get("kaggle") or [],
                    "wall_min": r.get("wall_min"), "five090_min": r.get("five090_min"), "kaggle_gpu_h": r.get("kaggle_gpu_h"), "lever": r.get("lever"), "tried": r.get("tried"), "lesson": r.get("lesson"),
                    "rows": {pid: {k: v for k, v in (rows.get(pid) or {}).items()} | {"change": (None if not isinstance((rows.get(pid) or {}).get("value"), (int, float)) or not isinstance((prev.get(pid) or {}).get("value"), (int, float)) else round(rows[pid]["value"] - prev[pid]["value"], 4))} for pid in rows},
                    "value_line": {"closed": round(closed, 4) if n_rows else None, "share_closed": round(closed / before, 4) if n_rows and before else None, "rows_compared": n_rows, "per_1000_stories": round(closed / added * 1000, 4) if n_rows and added else None, "gpu_h": round(gh, 3),
                                   "per_gpu_h": round(closed / gh, 4) if n_rows and gh else None}})
    return out


def resources(evs):
    """What is running right now. Kaggle CLI is cached 60 s and fails soft."""
    res = {"local": [], "kaggle": [], "quota": None, "stop": os.path.exists(f"{W}/data/progress/STOP"), "at": time.time()}
    try:
        for l in subprocess.run(["pgrep", "-af", "clef_label.py"], capture_output=True, text=True, timeout=5).stdout.splitlines():
            if "bash -c" in l or "timeout" in l.split()[1:2]: continue
            pid, cmd = l.split(" ", 1); parts = cmd.split(); out = next((x for x in parts if x.endswith(".jsonl") and "_in" not in x), None)
            n = sum(1 for _ in open(out if out.startswith("/") else f"{W}/{out}")) if out and os.path.exists(out if out.startswith("/") else f"{W}/{out}") else 0
            res["local"].append({"pid": int(pid), "out": out, "stories_in_file": n, "workers": parts[parts.index("--workers") + 1] if "--workers" in parts else None})
    except Exception as e: res["local_err"] = str(e)[:80]
    cache = f"{W}/data/progress/.kaggle_status.json"
    try:
        c = json.load(open(cache)) if os.path.exists(cache) else {}
        if time.time() - c.get("t", 0) > 60:
            kv = f"{W}/tools/.kaggle-venv/bin/kaggle"; ks = []
            for l in subprocess.run([kv, "kernels", "list", "--mine", "--page-size", "6"], capture_output=True, text=True, timeout=25).stdout.splitlines()[2:8]:
                ref = l.split()[0]
                if "bitmob" not in ref: continue
                s = subprocess.run([kv, "kernels", "status", ref], capture_output=True, text=True, timeout=20).stdout.strip().split('has status')[-1].strip().strip('"').replace("KernelWorkerStatus.", "")
                ks.append({"kernel": ref, "status": s})
            c = {"t": time.time(), "kernels": ks}; json.dump(c, open(cache, "w"))
        res["kaggle"] = c.get("kernels", [])
    except Exception as e: res["kaggle_err"] = str(e)[:80]
    try:
        q = subprocess.run(["python3", f"{W}/tools/kaggle/runs.py", "quota"], capture_output=True, text=True, timeout=30, env=dict(os.environ, KAGGLE_RUNS_LEDGER=f"{W}/data/kaggle/runs.jsonl")).stdout.splitlines()
        res["quota"] = q[0] if q else None
    except Exception as e: res["quota_err"] = str(e)[:80]
    return res


_RM = {"t": 0, "v": None}


def readers_meta():
    """Speed and size of each reader for the Models grid: Clef from the labelling log (F-0104), BitMob live from its /health, latest candidate from data/progress/readers_meta.json (written by the captain when a round is scored)."""
    if time.time() - _RM["t"] < 30 and _RM["v"]: return _RM["v"]
    out = {"clef": {"ms": None, "ram_mb": None, "gpu_s": 4.1, "note": "gpu s/story: 4.1 wall per story at 2 workers on the 5090 (F-0104)"}, "live": {"ms": None, "ram_mb": None, "gpu_s": 0.0, "scored": False}, "latest": {}}
    try:
        import urllib.request
        h = json.load(urllib.request.urlopen("http://127.0.0.1:8021/health", timeout=2)); out["live"].update(ms=h.get("median_read_ms"), ram_mb=h.get("rss_mb"), up=True)
    except Exception: out["live"]["up"] = False
    try: out["latest"] = json.load(open(f"{W}/data/progress/readers_meta.json")).get("latest", {})
    except Exception: pass
    _RM.update(t=time.time(), v=out); return out


def contract_view(items, evs):
    """Contract scorecard (D-0038): bars come from the ledger rows, values per round from data/progress/contract.json; plus Clef label progress."""
    byid = {i["id"]: i for i in items}
    try: cj = json.load(open(f"{W}/data/progress/contract.json"))
    except Exception: cj = {}
    rounds, explain = cj.get("rounds", []), cj.get("explain", {})
    rows = []
    for pid in CONTRACT_IDS:
        it = byid.get(pid) or {}; hist = [(r["round"], (r.get("rows") or {}).get(pid) or {}) for r in rounds]
        cur = hist[-1][1] if hist else {}; prev = hist[-2][1] if len(hist) > 1 else {}
        ch = None
        if isinstance(cur.get("value"), (int, float)) and isinstance(prev.get("value"), (int, float)): ch = round(cur["value"] - prev["value"], 4)
        rows.append({"id": pid, "name": (it.get("title") or "").split(":", 1)[0].replace("Contract ", ""), "title": it.get("title"), "bar": it.get("target"), "ledger_state": it.get("state"), "proof": it.get("proof"),
                     "open_decision": pid == "P-0022", "value": cur.get("value"), "value_text": cur.get("text"), "pass": cur.get("pass"), "note": cur.get("note"), "change": ch,
                     "history": [{"round": r, "value": h.get("value"), "text": h.get("text"), "pass": h.get("pass")} for r, h in hist]})
    last = {}
    for e in evs:
        if str(e.get("job", "")).startswith("clef-"): last[e["job"]] = e
    lab = []
    for job, name, target, fn in LABEL_JOBS:
        f = f"{W}/data/clef-labels/{fn}"; n = sum(1 for _ in open(f)) if os.path.exists(f) else 0
        e = last.get(job) or {}; lab.append({"job": job, "name": name, "done": n, "target": target, "state": e.get("state"), "msg": e.get("msg"), "ts": e.get("ts"), "pid": e.get("pid")})
    return {"rounds_detail": rounds_view(rounds), "resources": resources(evs), "bars": BARS, "rows": rows, "rounds": [r["round"] for r in rounds], "made": rounds[-1].get("made") if rounds else None, "labels": lab, "explain": explain, "hybrid": cj.get("hybrid", {}), "readers": cj.get("readers", [])}


def build():
    evs = [json.loads(l) for l in open(EV)] if os.path.exists(EV) else []
    jobs = {}
    for e in evs:
        j = jobs.setdefault(e["job"], {"job": e["job"], "started": e["ts"]})
        if e["state"] == "queued": j["started"] = e["ts"]
        j.update(state=e["state"], msg=e["msg"], ts=e["ts"], pid=e.get("pid") or j.get("pid"))
    for j in jobs.values():   # a job that says it is working but whose process is gone has died
        if j["state"] in ("running", "training", "scoring") and j.get("pid") and not alive(j["pid"]): j["state"] = "failed"; j["msg"] += " (process gone)"
    items = ledger(); preds, mm3 = [], []
    facts, tasks = [i for i in items if i["kind"] == "fact"], [i for i in items if i["kind"] == "task"]
    for it in items:
        for p in it.get("predictions") or []: preds.append(p | {"item": it["id"]})
        for e in it.get("evidence") or []:
            if e.get("src") == "mm3": mm3.append({"ts": e.get("ts"), "item": it["id"], "run": e.get("mm3"), "note": e.get("note")})
    scored = [p for p in preds if p.get("result")]
    hist = [json.loads(l) for l in open(f"{W}/data/scorecard/history.jsonl")] if os.path.exists(f"{W}/data/scorecard/history.jsonl") else []
    tags = sorted((os.path.basename(d)[5:] for d in glob.glob(f"{W}/data/suite_r[0-9]*") if all(os.path.exists(f"{d}/ensemble/{a}.json") for a in ("type", "topic", "conditions", "country"))), key=lambda t: -int(t[2:]))
    tag = tags[0] if tags else ""    # newest complete suite round (data/suite_rN), else round 0 (data/suite)
    subprocess.run([f"{W}/models/embed-zs/.venv/bin/python", f"{W}/newsreader/bitmob/suite_card.py"], capture_output=True, timeout=20, env=dict(os.environ, SUITE_TAG=tag))   # numpy lives in this venv
    models = json.load(open(f"{W}/data/scorecard/models{tag}.json")) if os.path.exists(f"{W}/data/scorecard/models{tag}.json") else {}
    models["round"] = tag or "_r0"
    budget = subprocess.run([f"{W}/tools/mm3local", "budget"], capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
    st = {"built": time.time(),
          "jobs": sorted(jobs.values(), key=lambda j: -j["ts"]),
          "feed": evs[-60:][::-1],
          "wins": [e for e in evs if e.get("win")][-12:][::-1],
          "card": hist[-1] if hist else None, "card_hist": [{"ts": h["ts"], "values": h["values"]} for h in hist[-15:]], "card_prev": hist[-2] if len(hist) > 1 else None, "cards": len(hist),
          "models": models,
          "facts": [{"id": f["id"], "title": f["title"], "created": f["created"], "proof": f["proof"]} for f in facts[-15:]][::-1],
          "tasks": [{"id": t["id"], "title": t["title"], "state": t["state"]} for t in tasks if t["state"] in ("open", "active", "blocked")],
          "predictions": {"made": len(preds), "scored": len(scored), "right": sum(p["result"] == "right" for p in scored),
                          "waiting": [{"id": p.get("rid"), "item": p["item"], "text": p.get("text"), "p": p.get("p")} for p in preds if not p.get("result")][-10:],
                          "recent": [{"id": p.get("rid"), "item": p["item"], "text": p.get("text"), "p": p.get("p"), "result": p["result"], "actual": p.get("actual")} for p in sorted(scored, key=lambda p: p.get("scored") or "")[-8:][::-1]]},
          "mm3": sorted(mm3, key=lambda m: m["ts"] or "")[-8:][::-1], "mm3_budget": next((l for l in budget if "runs" in l), None)}
    st["criteria"] = criteria_view(st["card"], models)
    lv = ledger_view(items); st["proof"] = {v: sum(i["verdict"] == v for i in lv) for v in ("validated", "weak", "unproven", "disproven", "retracted")}
    st["readers_meta"] = readers_meta()
    st["loop"] = json.load(open(f"{W}/data/progress/loop.json")) if os.path.exists(f"{W}/data/progress/loop.json") else {}   # round counter, kept by the captain
    st["contract"] = contract_view(items, evs)
    st["needs_you"] = json.load(open(f"{W}/data/progress/needs-you.json")) if os.path.exists(f"{W}/data/progress/needs-you.json") else []
    os.makedirs(os.path.dirname(OUT), exist_ok=True); tmp = f"{OUT}.{os.getpid()}.tmp"
    json.dump(lv, open(tmp, "w"), default=str); os.replace(tmp, os.path.join(os.path.dirname(OUT), "ledger.json"))
    json.dump(st, open(tmp, "w"), default=str); os.replace(tmp, OUT)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "event":
        pid = int(a[a.index("--pid") + 1]) if "--pid" in a else None
        event(a[1], a[2], a[3], pid=pid, win="--win" in a)
    else: build()
