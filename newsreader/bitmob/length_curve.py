"""Where does input length plateau? Same 300 stories as length_test.py (its output gives the full-text keys and 250 words), more lengths in words.
Run from /workspace/probes/world-engine (kev venv): WE_RULES=rules_v2 python -I /workspace/newsreader/bitmob/length_curve.py [teacher] [CONC]"""
import sys, os, json, glob, time, concurrent.futures as cf
os.environ.setdefault("WE_RULES", "rules_v2"); sys.path.insert(0, "/workspace/probes/world-engine"); sys.path.insert(0, "/workspace/demo")
import pyarrow.parquet as pq, pyarrow as pa
import classify as C, backends
TEACHER = sys.argv[1] if len(sys.argv) > 1 else "jev"; CONC = int(sys.argv[2]) if len(sys.argv) > 2 else 4
B = backends.BACKENDS[TEACHER]; C.O.set_reader(B["url"], B["model"], B["key"], TEACHER)
LT = [json.loads(l) for l in open("/workspace/data/trainset/length-test.jsonl")]
pilot = {r["id"]: r for r in map(json.loads, open("/workspace/data/trainset/pilot1.jsonl"))}
text = {r["url"]: r["text"] for r in pa.concat_tables([pq.read_table(f, columns=["url", "text"]) for f in sorted(glob.glob("/workspace/data/ccnews/raw/plain_text/*.parquet"))]).to_pylist()}
LENGTHS = [50, 100, 150, 400, 600]; OUT = "/workspace/data/trainset/length-curve.jsonl"
keys = lambda P: sorted({f"{x['dial']}|{x['direction']}" for x in C.read(P)["readings"] if x["direction"] in ("up", "down")})
def one(r):
    p = pilot[r["id"]]; words = text[r["id"][3:]].split(); out = dict(r)
    for n in LENGTHS:
        out[f"w{n}"] = keys(C.ask({"published_at": p["date"], "title": p["title"], "description": " ".join(words[:n])}, today=p["date"]))
    return out
t0 = time.time()
with cf.ThreadPoolExecutor(CONC) as ex, open(OUT, "w") as f:
    for rec in ex.map(one, LT): f.write(json.dumps(rec) + "\n")
R = [json.loads(l) for l in open(OUT)]; fp = sum(len(r["full"]) for r in R)
for L in ["c250", "w50", "w100", "w150", "w250", "w400", "w600"]:
    caught = sum(len(set(r[L]) & set(r["full"])) for r in R); extra = sum(len(set(r[L]) - set(r["full"])) for r in R)
    print(json.dumps({"length": L, "catch_rate": round(caught / fp, 3), "caught": caught, "of": fp, "extras": extra}))
print(json.dumps({"minutes": round((time.time() - t0) / 60, 1)}))
