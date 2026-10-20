"""How much of the full-text signal survives at each input length? Same stories, same teacher, engine questions and engine rule.
Lengths: c250 = title + description[:250] (already labelled in the pilot), w250 = title + first 250 words of the article, full = title + first 1,200 words.
Stories: CC-News records from a pilot file whose article has >= 300 words (so w250 is shorter than full); first N in pilot order.
Run from /workspace/probes/world-engine (kev venv): WE_RULES=rules_v2 python -I /workspace/newsreader/bitmob/length_test.py <pilot.jsonl> [N] [teacher] [CONC]"""
import sys, os, json, glob, time, threading, urllib.request, concurrent.futures as cf
os.environ.setdefault("WE_RULES", "rules_v2"); sys.path.insert(0, "/workspace/probes/world-engine"); sys.path.insert(0, "/workspace/demo")
import pyarrow.parquet as pq, pyarrow as pa
import classify as C, backends
PILOT = sys.argv[1]; N = int(sys.argv[2]) if len(sys.argv) > 2 else 300; TEACHER = sys.argv[3] if len(sys.argv) > 3 else "jev"; CONC = int(sys.argv[4]) if len(sys.argv) > 4 else 4
B = backends.BACKENDS[TEACHER]; C.O.set_reader(B["url"], B["model"], B["key"], TEACHER)
OUT = "/workspace/data/trainset/length-test.jsonl"
text = {r["url"]: r["text"] for r in pa.concat_tables([pq.read_table(f, columns=["url", "text"]) for f in sorted(glob.glob("/workspace/data/ccnews/raw/plain_text/*.parquet"))]).to_pylist()}
recs = [r for r in map(json.loads, open(PILOT)) if r["source"] == "ccnews" and len((text.get(r["id"][3:]) or "").split()) >= 300][:N]
keys = lambda P: sorted({f"{x['dial']}|{x['direction']}" for x in C.read(P)["readings"] if x["direction"] in ("up", "down")})
def one(r):
    words = text[r["id"][3:]].split(); day = r["date"]
    w250 = C.ask({"published_at": day, "title": r["title"], "description": " ".join(words[:250])}, today=day)
    full = C.ask({"published_at": day, "title": r["title"], "description": " ".join(words[:1200])}, today=day)
    return {"id": r["id"], "words": len(words), "c250": keys(r["P"]), "w250": keys(w250), "full": keys(full)}
t0 = time.time()
with cf.ThreadPoolExecutor(CONC) as ex, open(OUT, "w") as f:
    for rec in ex.map(one, recs): f.write(json.dumps(rec) + "\n")
R = [json.loads(l) for l in open(OUT)]
fp = sum(len(r["full"]) for r in R)
for L in ("c250", "w250"):
    caught = sum(len(set(r[L]) & set(r["full"])) for r in R); extra = sum(len(set(r[L]) - set(r["full"])) for r in R)
    print(json.dumps({"length": L, "stories": len(R), "full_positives": fp, "caught": caught, "catch_rate": round(caught / fp, 3) if fp else None, "extras": extra}))
print(json.dumps({"minutes": round((time.time() - t0) / 60, 1), "median_words": sorted(r["words"] for r in R)[len(R) // 2]}))
