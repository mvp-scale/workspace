"""freeze_replay (T150 P1a): freeze the 230 bench stories and what analyze2 stores for each, then diff a later run against the freeze.
Stories: the 200 golden (runs/pulse/golden/articles.jsonl, ids g0..g199) plus the 30 queue stories the bench draws (queue.sqlite read-only, rows with body > 600 chars, random.Random(7) shuffle, first 30, ids q<rowid>; server.py:16-18). The queue 30 are snapshotted by id and text into runs/pulse/validate/queue30_snapshot.jsonl on the first freeze and reused afterwards, so later queue changes cannot move the set (--resnapshot redraws).
Per story the freeze stores (same entry points the bench uses: Analyzer(threads=8, fit_headline=True).analyze and Reader.read, FL.facts_for ungated, as in the plan): fields.<field>.{outcome, answer, proposed, confidence, how}, evidence.{windows, encoder_skipped, parse_ran, stated_amounts, stated_dates, span_rules items+counts}, topic and story probability vectors (pt, ps), facts as (kind, s, e, text, status, value, noun, verb). Not replicated: the bench's clean_input step (server.py) before analyze; only analyze2 is frozen. Timings are kept beside the data but are not hashed and not compared.
diff re-runs the stories stored in the freeze file (not the live queue) and compares: discrete fields must be identical; probabilities (pt, ps, confidence) may differ by at most --tol (default 1e-6). Keys that exist now but not in the freeze are ignored (add-only changes are allowed). Exit 0 only if there are zero changes; else each changed story and field is listed. Run it twice before any change (two baseline replays) to measure ORT nondeterminism; if that exceeds the tol, the plan sets the regression tolerance to 10x the observed difference.
    CUDA_VISIBLE_DEVICES="" /workspace/models/embed-zs/.venv/bin/python validate/freeze_replay.py freeze [--limit N] [--out FILE] [--sparse]   (from projects/world-state; full 230 about 2-3 min, run only when the bench is idle)
    CUDA_VISIBLE_DEVICES="" /workspace/models/embed-zs/.venv/bin/python validate/freeze_replay.py diff [--frozen FILE] [--tol 1e-6]   -> runs/pulse/validate/frozen_230.jsonl, replay_diff.json
--limit N takes N evenly spaced stories of the 230 (self-test only; the output is then not the baseline, so give --out)."""
import os, sys, json, re, time, hashlib, random, sqlite3, argparse, pathlib
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
WS = pathlib.Path(__file__).resolve().parents[1]; os.chdir(WS); sys.path.insert(0, str(WS)); OUTD = pathlib.Path("runs/pulse/validate"); FROZEN = OUTD / "frozen_230.jsonl"; SNAP = OUTD / "queue30_snapshot.jsonl"
PROB = ("pt", "ps")
def sha(b): return hashlib.sha256(b).hexdigest()
def fsha(p): return sha(open(p, "rb").read())
def canon(o): return json.dumps(o, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
def golden(): return [{"id": "g%d" % i, "group": "Golden set", "title": g["title"], "body": g["body"], "date": g.get("date")} for i, g in ((i, json.loads(l)) for i, l in enumerate(open("runs/pulse/golden/articles.jsonl")))]
def queue30(resnap=False):
    if SNAP.exists() and not resnap: return [json.loads(l) for l in open(SNAP)]
    db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); rows = db.execute("select id, title, body, published from items where body is not null and length(body) > 600").fetchall(); random.Random(7).shuffle(rows)
    q = [{"id": "q%s" % r[0], "group": "Queue sample", "title": r[1] or "", "body": r[2], "date": (r[3] or "")[:10] or None} for r in rows[:30]]
    OUTD.mkdir(parents=True, exist_ok=True); open(SNAP, "w").write("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in q)); return q
def setup(threads=8, sparse=False):
    import analyze2 as A2, facts_lib as FL
    from expert1_runtime import ExpertS
    E = ExpertS("runs/expert1/expert1_v6b_student.pkl"); FT = json.load(open("runs/pulse/field_table.json")); X = {"dense": A2.Analyzer(E.S, FT, threads=threads, fit_headline=True)}
    if sparse: X["sparse"] = A2.Analyzer(E.S, FT, threads=threads, fit_headline=True, sparse="runs/expert1/sparse_heads_v2.pkl")
    return A2, FL, E, X
def one(st, A2, FL, E, X):
    title = re.sub(r"\s+", " ", st["title"]).strip(); body = st["body"]; date = st["date"]; data = {}; ms = {}
    for name, an in X.items():
        res = an.analyze(title, body, date); ms[name] = res["ms"]; ev = res["evidence"]
        d = {"fields": {k: {"outcome": v["outcome"], "answer": v["answer"], "proposed": v["proposed"], "confidence": v["confidence"], "how": v["how"]} for k, v in res["fields"].items()},
             "evidence": {k: ev[k] for k in ("windows", "encoder_skipped", "parse_ran", "stated_amounts", "stated_dates")}, "span_rules": ev["span_rules"]}
        if not ev["encoder_skipped"]: pt, ps, nw = an.reader.read(title, body); d["pt"] = [float(x) for x in pt]; d["ps"] = [float(x) for x in ps]
        data[name] = d
    text = re.sub(r"\s+", " ", title + ". " + body)[:12000]; anchor = (date + "T00:00:00Z") if date else None; t0 = time.perf_counter(); fx = FL.facts_for(text, anchor)[0]; ms["facts_all_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    data["facts"] = [[f["kind"], f["s"], f["e"], f["text"], f["status"], f["value"], f.get("noun"), f.get("verb")] for f in fx]
    return {"id": st["id"], "group": st["group"], "title": st["title"], "body": body, "date": date, "data": data, "ms": ms}
def pick(stories, limit):
    if not limit or limit >= len(stories): return stories
    return [stories[round(i * (len(stories) - 1) / max(limit - 1, 1))] for i in range(limit)]
def content_hash(rows): return sha(canon([[r["id"], r["title"], r["body"], r["date"], r["data"]] for r in rows]).encode())
def freeze(a):
    stories = pick(golden() + queue30(a.resnapshot), a.limit); A2, FL, E, X = setup(a.threads, a.sparse); rows = []; t0 = time.time()
    for i, st in enumerate(stories):
        rows.append(one(st, A2, FL, E, X))
        if (i + 1) % 25 == 0: print("frozen", i + 1, "of", len(stories), round(time.time() - t0), "s", flush=True)
    hdr = {"kind": "header", "n": len(rows), "hash": content_hash(rows), "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "threads": a.threads, "sparse": a.sparse, "fit_headline": True, "limit": a.limit or None,
           "code_sha256": {f: fsha(f) for f in ("analyze2.py", "facts_lib.py", "stated_facts.py", "decider.py", "span_rules.py", "../../simulation/server.py")}, "queue_snapshot_sha256": fsha(SNAP) if SNAP.exists() else None}
    out = pathlib.Path(a.out or FROZEN); out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as w:
        w.write(json.dumps(hdr) + "\n"); [w.write(json.dumps(r, ensure_ascii=False, default=str) + "\n") for r in rows]
    print("froze %d stories, hash %s, %.1f s -> %s" % (len(rows), hdr["hash"][:16], time.time() - t0, out)); return 0
def cmp(a, b, path, tol, ch):
    if isinstance(a, dict):
        if not isinstance(b, dict): ch.append((path, "type", a, b)); return
        for k in a: cmp(a[k], b.get(k, "<missing>"), path + "." + k, tol, ch)   # keys only in b are ignored (add-only)
    elif path.split(".")[-1] in PROB or path.endswith(".confidence"):
        if isinstance(a, list): d = max((abs(x - y) for x, y in zip(a, b)), default=0) if isinstance(b, list) and len(a) == len(b) else float("inf")
        elif a is None or b is None: d = 0 if a == b else float("inf")
        else: d = abs(a - b)
        if d > tol: ch.append((path, "prob", d))
    elif a != b: ch.append((path, "discrete", str(a)[:120], str(b)[:120]))
def diff(a):
    fz = pathlib.Path(a.frozen or FROZEN); L = [json.loads(l) for l in open(fz)]; hdr, rows = L[0], L[1:]
    if content_hash(rows) != hdr["hash"]: print("frozen file hash mismatch: the file was altered or corrupted"); return 2
    A2, FL, E, X = setup(hdr.get("threads", 8), hdr.get("sparse", False)); changed = []; maxp = 0.0; t0 = time.time()
    for st in rows:
        new = one(st, A2, FL, E, X); ch = []; cmp(st["data"], new["data"], "data", a.tol, ch)
        for c in ch:
            if c[1] == "prob": maxp = max(maxp, c[2])
        if ch: changed.append({"id": st["id"], "changes": [list(c) for c in ch]})
    code_now = {f: fsha(f) for f in hdr["code_sha256"]}; moved = [f for f in code_now if code_now[f] != hdr["code_sha256"][f]]
    rep = {"frozen": str(fz), "n": len(rows), "tol": a.tol, "stories_changed": len(changed), "max_prob_diff_among_exceeding": maxp, "changed": changed[:200], "code_files_changed_since_freeze": moved, "seconds": round(time.time() - t0, 1), "pass": not changed}
    OUTD.mkdir(parents=True, exist_ok=True); json.dump(rep, open(a.out or OUTD / "replay_diff.json", "w"), indent=1)
    print("diff vs %s: %d stories, %d changed (tol %g); code files changed since freeze: %s -> %s" % (fz, len(rows), len(changed), a.tol, moved or "none", "PASS" if not changed else "FAIL"))
    for c in changed[:15]: print(" ", c["id"], [x[0] + ":" + x[1] for x in c["changes"][:6]])
    return 0 if not changed else 1
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("mode", choices=("freeze", "diff")); ap.add_argument("--limit", type=int); ap.add_argument("--out"); ap.add_argument("--frozen"); ap.add_argument("--tol", type=float, default=1e-6); ap.add_argument("--threads", type=int, default=8); ap.add_argument("--sparse", action="store_true"); ap.add_argument("--resnapshot", action="store_true"); a = ap.parse_args()
    sys.exit(freeze(a) if a.mode == "freeze" else diff(a))
