"""Forward test (owner principle L2760: live news is the judge, no preplanning). The frozen topic pipeline is run only on queue articles that arrived AFTER the freeze,
in consecutive windows (each run starts where the last one ended), and the publisher-section check is pooled over every window. Refuses if the frozen model changed.
    /workspace/models/embed-zs/.venv/bin/python forward_test.py [--minutes 25]   -> runs/pulse/topic_loop/forward/results.json (key change_pts; the pooled value before this run is kept in forward/previous-results.json, so cards use that file as the baseline)"""
import sys, os, json, glob, hashlib, sqlite3, subprocess, random, collections, time
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
FREEZE = 1795161530.8141637; MODEL = "runs/pulse/topic_loop/r1/primary_reranker.pkl"; MODEL_SHA16 = "e289945b3c9fcfe2"
ROOT = "/workspace/demo/mockups/structure-live"; OUT = "runs/pulse/topic_loop/forward"; os.makedirs(OUT, exist_ok=True)
PY = "/workspace/models/embed-zs/.venv/bin/python"; MIN = float(sys.argv[sys.argv.index("--minutes") + 1]) if "--minutes" in sys.argv else 25
PRIOR = json.load(open(OUT + "/results.json")) if os.path.exists(OUT + "/results.json") else None  # read before anything is overwritten
if hashlib.sha256(open(MODEL, "rb").read()).hexdigest()[:16] != MODEL_SHA16: sys.exit("refusing: the frozen re-ranker changed; this would not be a forward test")
def traced(tr):
    for l in open(tr + "/chain.jsonl"):
        a = json.loads(json.loads(l)["line"])
        if a.get("state") == "traced": yield a
dirs = sorted(glob.glob(ROOT + "/runs-fwd*/trace"), key=lambda p: int("".join(c for c in p.split("runs-fwd")[1].split("/")[0] if c.isdigit()) or 0))
start = max([FREEZE] + [max((a["ready_at"] for a in traced(d)), default=FREEZE) + 1e-3 for d in dirs if os.path.exists(d + "/chain.jsonl")])
n = 1 + max([int("".join(c for c in d.split("runs-fwd")[1].split("/")[0] if c.isdigit()) or 0) for d in dirs] or [0])
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); waiting = db.execute("select count(*) from items where ready_at>=?", (start,)).fetchone()[0]
if not waiting: sys.exit("no articles arrived after %.3f; no new forward window, nothing to score" % start)  # a re-pool of old windows is not a result
if waiting:
    pd = "%s/runs-fwd%d" % (ROOT, n); os.makedirs(pd + "/trace", exist_ok=True)
    if os.path.lexists("%s/trace-fwd%d" % (ROOT, n)): os.remove("%s/trace-fwd%d" % (ROOT, n))
    os.symlink("runs-fwd%d/trace" % n, "%s/trace-fwd%d" % (ROOT, n))
    env = dict(os.environ, START=str(start), DURATION=str(int(MIN * 60)), POLL="15", THREADS="4", PAGE_DIR=pd)
    subprocess.run([PY, "live_trace.py"], env=env, check=True, stdout=open(OUT + "/fwd%d.log" % n, "w"), stderr=subprocess.STDOUT)
    dirs.append(pd + "/trace")
import spacy; from structure_pack import Pack
P = Pack(spacy.blank("en")); L1 = {P.lab(q).lower(): q for q in P.node if len(P.chain(q)) == 1}
SEC = {"business": "economy, business and finance", "science": "science and technology", "tech": "science and technology", "health": "health", "entertain": "arts, culture, entertainment and media", "politic": "politics and government", "environment": "environment", "climate": "environment"}
rows = []; per = []
for d in dirs:
    k = 0
    for a in traced(d):
        f = (db.execute("select feed from items where id=?", (a["id"],)).fetchone() or [""])[0] or ""; f = f.lower()
        hit = {v for s, v in SEC.items() if s in f}
        if len(hit) != 1 or "world" in f: continue
        t = next((s for s in a["stages"] if s["name"] == "topic_landing"), {}); o = t.get("out") or {}
        if not o.get("rerank"): continue
        g = L1[hit.pop()]; rows.append((a["source"], o.get("landing_l1_code") == g, o["rerank"]["l1_code"] == g)); k += 1
    per.append({"trace": d, "section_articles": k})
N = len(rows); al = sum(r[1] for r in rows) / N if N else None; ar = sum(r[2] for r in rows) / N if N else None
by = collections.defaultdict(list)
for r in rows: by[r[0]].append(r)
pubs = list(by); rng = random.Random(0); boot = []
for _ in range(2000):
    s = [x for p in (rng.choice(pubs) for _ in pubs) for x in by[p]]
    if s: boot.append(100 * (sum(x[2] for x in s) - sum(x[1] for x in s)) / len(s))
boot.sort(); res = {"frozen_model": MODEL_SHA16, "freeze_epoch": FREEZE, "written": time.strftime("%Y-%m-%d %H:%M"), "windows": per, "section_articles": N, "publishers": len(pubs),
    "agree_landing": round(al, 4) if N else None, "agree_rerank": round(ar, 4) if N else None, "change_pts": round(100 * (ar - al), 2) if N else None,
    "change_pts_ci95_publisher_bootstrap": [round(boot[50], 2), round(boot[1949], 2)] if boot else None}
if PRIOR: json.dump(PRIOR, open(OUT + "/previous-results.json", "w"), indent=1)  # snapshot of the pooled result before this run, so a card baseline never shares a key with its result
json.dump(res, open(OUT + "/results.json", "w"), indent=1); print(json.dumps(res))
