"""Plateau test on long articles: share of key positives (reference = first 3,000 words) caught at 250, 400, 600, 800, 1,000, 1,500 words.
Stories: N CC-News articles over 1,500 words from the approved outlets (D-0010 filter on title + description), seed 2. Same teacher and engine rule as length_curve.py.
Run from /workspace/probes/world-engine (kev venv): WE_RULES=rules_v2 python -I /workspace/newsreader/bitmob/length_long.py [N] [teacher] [CONC]"""
import sys, os, re, json, glob, time, random, concurrent.futures as cf
os.environ.setdefault("WE_RULES", "rules_v2"); sys.path.insert(0, "/workspace/probes/world-engine"); sys.path.insert(0, "/workspace/demo")
import pyarrow.parquet as pq, pyarrow as pa
import classify as C, backends
N = int(sys.argv[1]) if len(sys.argv) > 1 else 300; TEACHER = sys.argv[2] if len(sys.argv) > 2 else "jev"; CONC = int(sys.argv[3]) if len(sys.argv) > 3 else 6
B = backends.BACKENDS[TEACHER]; C.O.set_reader(B["url"], B["model"], B["key"], TEACHER)
src = open("/workspace/newsreader/bitmob/ccnews_headline_test.py").read()
OUTLETS = set(re.findall(r'"([a-z0-9.-]+\.[a-z]{2,})"', src.split("OUTLETS = [")[1].split("]")[0]))
LENGTHS, REF = [250, 400, 600, 800, 1000, 1500], 3000; OUT = "/workspace/data/trainset/length-long.jsonl"; LOG = "/workspace/data/trainset/length-long.log"
def log(m): line = f"{time.strftime('%F %T')}  {m}"; print(line, flush=True); open(LOG, "a").write(line + "\n")
cc = pa.concat_tables([pq.read_table(f, columns=["url", "domain", "date", "title", "description", "text"]) for f in sorted(glob.glob("/workspace/data/ccnews/raw/plain_text/*.parquet"))]).to_pylist()
pool = [r for r in cc if r["domain"] in OUTLETS and r["description"] and r["text"] and len(r["text"].split()) > 1500]
pool.sort(key=lambda r: r["url"]); random.Random(2).shuffle(pool); sample = pool[:N]
keys = lambda P: sorted({f"{x['dial']}|{x['direction']}" for x in C.read(P)["readings"] if x["direction"] in ("up", "down")})
log(f"start: {len(sample)} of {len(pool)} long articles (> 1,500 words), lengths {LENGTHS}, reference {REF} words, {CONC} at a time")
def one(r):
    words = r["text"].split(); day = (r["date"] or "")[:10] or time.strftime("%F"); out = {"url": r["url"], "words": len(words)}
    for n in LENGTHS + [REF]:
        out[f"w{n}"] = keys(C.ask({"published_at": day, "title": r["title"], "description": " ".join(words[:n])}, today=day))
    return out
t0, done = time.time(), 0
with cf.ThreadPoolExecutor(CONC) as ex, open(OUT, "w") as f:
    for rec in ex.map(one, sample):
        f.write(json.dumps(rec) + "\n"); done += 1
        if done % 25 == 0: el = time.time() - t0; log(f"{done}/{len(sample)}, {done / el * 60:.1f}/min, ETA {(len(sample) - done) / (done / el):.0f} s")
R = [json.loads(l) for l in open(OUT)]; fp = sum(len(r[f"w{REF}"]) for r in R)
for n in LENGTHS:
    c = sum(len(set(r[f"w{n}"]) & set(r[f"w{REF}"])) for r in R); e = sum(len(set(r[f"w{n}"]) - set(r[f"w{REF}"])) for r in R)
    log(json.dumps({"length": n, "catch_rate": round(c / fp, 3), "caught": c, "of": fp, "extras": e}))
log(f"DONE {len(R)} in {(time.time() - t0) / 60:.1f} min; median words {sorted(r['words'] for r in R)[len(R) // 2]}")
