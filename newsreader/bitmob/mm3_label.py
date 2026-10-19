"""Label news stories with MM3-style scans on local Clef and collect the answers in a training queue, not in a ledger.
Each worker has its own throwaway MM3 home (data/mm3-train/w<k>/): it writes a batch of stories there, runs one `scan`, moves
every answer into data/mm3-train/queue.jsonl (one row per story, with its text, so training never needs the news reader's
7-day store), then deletes the batch and that run's ledger. The project ledger (/workspace/.mm3) is never touched.
Questions per condition: states (yes = it moves), concrete (yes = a concrete event shows it), reversed (yes = it eases).
Local only: TYPESAFE_BASE_URL is forced to Clef (:8018) and the key is a dummy, so a hosted call is impossible.
Run: python3 newsreader/bitmob/mm3_label.py [--minutes 60] [--workers 4] [--limit N] [--include-old] [--battery file.json] [--teasers]   (stop early: touch data/mm3-train/STOP)"""
import json, os, re, sys, time, shutil, sqlite3, subprocess, threading, argparse

ROOT = "/workspace"; OUT = f"{ROOT}/data/mm3-train"; QUEUE = f"{OUT}/queue.jsonl"
MM3 = "/root/.claude/plugins/cache/mvp-scale/mm3/035c10697964/bin/mm3.mjs"
TEACHER = os.environ.get("MM3_TEACHER_MODEL", "clef-flash-q4km"); BASE = os.environ.get("MM3_TEACHER_URL", "http://127.0.0.1:8018"); BATCH = 30
SUFFIX = "" if TEACHER == "clef-flash-q4km" else "-" + re.sub(r"[^a-z0-9]+", "-", TEACHER.lower())          # a second teacher writes its own queue file
ONLY = None   # set from --ids: a JSON list of story ids to label (e.g. the test split only)
# condition id (rules_v2 dials), direction, and the three probes: states, concrete, reversed
CONDS = [
    ("prices", "up", "report that prices people pay are rising", "a concrete price increase, such as a fare, bill, tariff or inflation figure going up", "prices falling, easing or holding steady"),
    ("energy_fuel", "up", "report that energy or fuel is getting more expensive or scarcer", "a concrete energy event, such as a fuel price rise, supply cut or power shortage", "energy or fuel getting cheaper or more plentiful"),
    ("war_terror", "up", "report armed conflict or terrorism getting worse", "a concrete attack, battle, strike, threat or escalation between armed groups or states", "a ceasefire, peace deal or a conflict calming down"),
    ("civil_unrest", "up", "report protests, riots or civil unrest", "people gathering, marching or striking against a government or employer", "protests ending or tensions on the streets calming"),
    ("social_division", "up", "report society becoming more divided or polarised", "a concrete clash between groups, parties or communities", "groups coming together or finding common ground"),
    ("trust_institutions", "down", "report people losing trust in government, courts, police or institutions", "a concrete scandal, cover-up, failure or broken promise by an institution", "an institution earning trust back or being cleared"),
    ("crime", "up", "report a crime or rising crime", "a concrete criminal act, arrest, charge or police investigation", "crime falling or a place becoming safer"),
    ("health_risk", "up", "report a rising risk to people's health", "a concrete health threat, such as an outbreak, injuries, deaths or a harmful product", "a health threat easing, or a cure or treatment helping people"),
    ("cyber_insecurity", "up", "report a rising cyber or digital security risk", "a concrete hack, data breach, flaw or online scam", "a security flaw being fixed or a hacking threat shrinking"),
]
ANGLES = ("states", "concrete", "reversed")
DECISIONS = [
    ("topic", "choice", "Which area is the story in {file} mainly about?", ["economy", "politics_or_conflict", "crime_justice", "health", "environment", "technology", "culture_or_sport", "none_fits"]),
    ("scope", "choice", "Where does the story in {file} mainly take place or matter?", ["whole_world", "one_country", "one_city_or_region", "none_fits"]),
    ("size", "scale", "How much does the story in {file} change ordinary people's lives?", ["no_effect", "a_few_people", "many_people_in_one_country", "many_countries"]),
    ("kind", "choice", "What kind of story is {file}?", ["news_report", "opinion", "analysis_explainer", "feature_or_human_interest", "none_fits"]),
    ("visible", "choice", "Can this be answered from the story text shown?", ["enough", "partial", "missing"]),
]


TEASERS = False  # set from --teasers
BATTERY = None   # set from --battery: {"name", "concerns": [{"atom", "probes": {angle: question}}], "decisions": [[name, kind, question, options]]}


def request(folder, batch_no, n_stories):
    """The scan request, and a map from question number to its training key."""
    if BATTERY: return request_battery(folder, batch_no, n_stories)
    L = ["mak:", "  goal: Each story gives clear evidence that moves at least one world condition", "  verb: scan", "  depth: thorough",
         "  over:", f"    file: {folder}/*.md", "  ask:", "    file:", "      concerns:"]
    key, n = {}, 0
    for d, dirn, s, c, r in CONDS:
        L += [f"        {d.replace('_', '')[:14]}-{dirn}:", "          family: correctness", "          pass: no"]
        for angle, q in zip(ANGLES, (f"Does the story in {{file}} {s}?", f"Does {{file}} describe {c}?", f"Does the story in {{file}} report {r}?")):
            n += 1; L.append(f"          {n}: {q}"); key[n] = f"{d}|{dirn}|{angle}"
    L.append("      decisions:")
    for name, kind, q, opts in DECISIONS:
        n += 1; key[n] = name
        L += [f"        {name}:", f"          pass: [{opts[-1] if kind == 'choice' else opts[0]}]", f"          {n}:", f"            {kind}: {q}", f"            {'options' if kind == 'choice' else 'levels'}: [{', '.join(opts)}]"]
    L += ["mdl:", "  why: find", "  area: data", "  stage: build", "  problem: Label news stories against the World engine ontology to train a CPU tagger",
          f"  touches: [{', '.join(d for d, *_ in CONDS[:5])}]", f"  dataset: mm3-train batch {batch_no} ({n_stories} stories)", f"  teacher: {TEACHER}", '  tags: ["#world-engine", "#training-labels"]']
    return "\n".join(L) + "\n", key


OLD = f"{ROOT}/data/newsreader/labels/clef-q4km.jsonl"


def request_battery(folder, batch_no, n_stories):
    B = BATTERY; L = ["mak:", f"  goal: {json.dumps(B['goal'])}", "  verb: scan", "  depth: thorough", "  over:", f"    file: {folder}/*.md", "  ask:", "    file:", "      concerns:"]
    key, n = {}, 0
    for c in B["concerns"]:
        L += [f"        {c['cat']}:", "          family: correctness", "          pass: no"]
        for angle, q in c["probes"].items(): n += 1; L.append(f"          {n}: {q}"); key[n] = f"{c['atom']}|{angle}"
    L.append("      decisions:")
    for name, kind, q, opts in B["decisions"]:
        n += 1; key[n] = name
        L += [f"        {name}:", f"          pass: [{opts[-1] if kind == 'choice' else opts[0]}]", f"          {n}:", f"            {kind}: {q}", f"            {'options' if kind == 'choice' else 'levels'}: [{', '.join(opts)}]"]
    L += ["mdl:", "  why: find", "  area: data", "  stage: build", f"  problem: {json.dumps(B['problem'])}", f"  dataset: mm3-train {B['name']} batch {batch_no} ({n_stories} stories)",
          f"  teacher: {TEACHER}", f"  battery: {B['name']}", '  tags: ["#world-engine", "#training-labels", "#evidence-atoms"]']
    return "\n".join(L) + "\n", key


def stories(include_old=False):
    """Unlabelled full-text stories from the news reader; with include_old, also the stories the old 328-question battery labelled."""
    seen = {json.loads(l)["id"] for l in open(QUEUE)} if os.path.exists(QUEUE) else set()
    if BATTERY:                                                     # a new battery relabels every story already in the main queue
        main = f"{OUT}/queue.jsonl"; rows = list({r["id"]: r for r in map(json.loads, open(main))}.values())
        return [{"id": r["id"], "source": r["source"], "country": r["country"], "region": r["region"], "category": r["category"], "title": r["title"],
                 "published": r["published"], "body": r["text"], "words": len(r["text"].split()), "depth": r.get("depth", "full")} for r in rows if r["id"] not in seen and (ONLY is None or r["id"] in ONLY)]
    old = [json.loads(l) for l in open(OLD)] if os.path.exists(OLD) else []
    if include_old:
        return [{"id": r["id"], "source": r["source"], "country": None, "region": r.get("region"), "category": None, "title": r["title"], "published": None,
                 "body": r["text"], "words": len(r["text"].split())} for r in old if r["id"] not in seen and r.get("text")]
    seen |= {r["id"] for r in old}
    if TEASERS:                                                     # headline + summary only: the stories whose full text could not be fetched
        db = sqlite3.connect(f"file:{ROOT}/data/newsreader/queue.sqlite?mode=ro", uri=True); db.row_factory = sqlite3.Row
        rows = db.execute("SELECT id, source, country, region, category, title, published, teaser AS body FROM items WHERE depth='teaser' AND teaser IS NOT NULL "
                          "AND length(teaser) >= 60 AND (lang IS NULL OR lang LIKE 'en%') ORDER BY found_at").fetchall()
        return [dict(r) | {"words": len(r["body"].split())} for r in rows if r["id"] not in seen]
    db = sqlite3.connect(f"file:{ROOT}/data/newsreader/queue.sqlite?mode=ro", uri=True); db.row_factory = sqlite3.Row
    rows = db.execute("SELECT id, source, country, region, category, title, published, body, words FROM items WHERE depth='full' AND body IS NOT NULL "
                      "AND words BETWEEN 150 AND 4000 AND (lang IS NULL OR lang LIKE 'en%') ORDER BY found_at").fetchall()
    return [dict(r) for r in rows if r["id"] not in seen]


lock = threading.Lock(); STATS = {"stories": 0, "batches": 0, "failed": 0, "clef_s": 0.0}


def worker(k, todo, deadline):
    home = f"{OUT}/w{k}{SUFFIX}"; os.makedirs(f"{home}/.mm3", exist_ok=True)
    shutil.copy(f"{ROOT}/.mm3/config.yaml", f"{home}/.mm3/config.yaml")
    env = dict(os.environ, MM3_HOME=home, TYPESAFE_BASE_URL=BASE, TYPESAFE_API_KEY="local", JEV_MODEL=TEACHER, JEV_TIMEOUT_MS="300000")
    if "127.0.0.1" not in BASE and "localhost" not in BASE: raise SystemExit("refusing a non-local teacher: " + BASE)
    while time.time() < deadline and not os.path.exists(f"{OUT}/STOP"):
        with lock:
            if not todo: return
            batch, STATS["batches"] = [todo.pop(0) for _ in range(min(BATCH, len(todo)))], STATS["batches"] + 1; bno = STATS["batches"]
        folder = f"b{bno:04d}"; shutil.rmtree(f"{home}/{folder}", ignore_errors=True); os.makedirs(f"{home}/{folder}")
        by_file = {}
        for i, r in enumerate(batch):
            name = f"story-{i + 1:02d}.md"; by_file[f"{folder}/{name}"] = r
            open(f"{home}/{folder}/{name}", "w").write(f"# {r['title']}\n\nSource: {r['source']} · Country: {r['country'] or 'world'} · Published: {r['published']}\n\n" + " ".join(r["body"].split()[:1200]) + "\n")
        req, key = request(folder, bno, len(batch)); open(f"{home}/{folder}.yaml", "w").write(req)
        p = subprocess.run(["node", MM3, "scan", f"{folder}.yaml"], cwd=home, env=env, capture_output=True, text=True, timeout=1800)
        runs = [json.loads(l) for l in open(f"{home}/.mm3/log.jsonl")] if os.path.exists(f"{home}/.mm3/log.jsonl") else []
        run = next((x for x in reversed(runs) if x.get("kind") == "run" and x.get("verb") == "scan"), None)
        if p.returncode not in (0, 1) or not run:
            with lock: STATS["failed"] += len(batch)
            print(f"w{k} {folder}: failed exit {p.returncode}: {(p.stdout + p.stderr)[-300:]}", flush=True)
        else:
            A, rows = run["answers"], []
            for f, r in by_file.items():
                ans = {}
                for n, kname in key.items():
                    a = A.get(f"{f}#{n}")
                    if a: ans[kname] = round(a["p"], 4) if a["kind"] == "yesno" else {o: round(v, 4) for o, v in a["dist"].items()}
                if len(ans) < len(key): continue
                rows.append({"id": r["id"], "source": r["source"], "country": r["country"], "region": r["region"], "category": r["category"], "title": r["title"],
                             "published": r["published"], "text": " ".join(r["body"].split()[:1200]), "teacher": TEACHER, "run": run["id"], "batch": bno,
                             "labelled_at": run["ts"], "depth": r.get("depth", "teaser" if TEASERS else "full"), "answers": ans})
            secs = sum(t.get("latencyMs", 0) for t in run.get("telemetry", [])) / 1000
            with lock:
                with open(QUEUE, "a") as q: q.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in rows)
                STATS["stories"] += len(rows); STATS["failed"] += len(batch) - len(rows); STATS["clef_s"] += secs
            print(f"w{k} {folder}: {len(rows)}/{len(batch)} stories, Clef {secs:.1f}s · total {STATS['stories']}", flush=True)
        shutil.rmtree(f"{home}/{folder}", ignore_errors=True); os.remove(f"{home}/{folder}.yaml")
        for f in ("log.jsonl", "index.db"):                               # the run ledger is throwaway: answers now live in the queue
            if os.path.exists(f"{home}/.mm3/{f}"): os.remove(f"{home}/.mm3/{f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--minutes", type=float, default=60); ap.add_argument("--workers", type=int, default=4); ap.add_argument("--limit", type=int, default=0); ap.add_argument("--include-old", action="store_true"); ap.add_argument("--battery"); ap.add_argument("--teasers", action="store_true"); ap.add_argument("--ids")
    a = ap.parse_args(); os.makedirs(OUT, exist_ok=True)
    if SUFFIX and not a.battery: raise SystemExit("a second teacher needs --battery (it must never write to Clef's queue.jsonl)")
    TEASERS = a.teasers; ONLY = set(json.load(open(a.ids))) if a.ids else None
    if a.battery:
        BATTERY = json.load(open(a.battery)); QUEUE = f"{OUT}/queue-{BATTERY['name']}{SUFFIX}.jsonl"
    todo = stories(a.include_old)[: a.limit or None]; t0 = time.time(); deadline = t0 + a.minutes * 60
    print(f"{len(todo)} stories to label, {a.workers} workers, stop after {a.minutes:.0f} min", flush=True)
    ts = [threading.Thread(target=worker, args=(k, todo, deadline)) for k in range(a.workers)]
    [t.start() for t in ts]; [t.join() for t in ts]
    el = time.time() - t0
    print(json.dumps({**STATS, "wall_s": round(el, 1), "stories_per_hour": round(STATS["stories"] / el * 3600), "left": len(todo)}), flush=True)
