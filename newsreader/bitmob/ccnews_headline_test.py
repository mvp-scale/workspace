"""Headline test on CC-News: does title + description carry the World engine's keys, and how fast does Clef read it?
Clef answers the engine's 328 questions twice per article: (h) title + description only, (f) title + up to 1,200 words (the engine's own input).
Sample: N articles, seed 0, from 65 established outlets (OUTLETS), with a description and >= 80 words of text. Each article is read as of its own date.
Progress and ETA go to data/ccnews/progress.log (tail -f it). Resumable: pairs already written are skipped.
Run from /workspace/probes/world-engine with the kev venv:  WE_RULES=rules_v2 python -I /workspace/newsreader/bitmob/ccnews_headline_test.py <h|f> [N] [CONC]"""
import sys, os, json, time, glob, random, threading, concurrent.futures as cf
os.environ.setdefault("WE_RULES", "rules_v2"); sys.path.insert(0, "/workspace/probes/world-engine")
import pyarrow.parquet as pq, pyarrow as pa
import classify as C
C.O.set_reader("http://127.0.0.1:8018", "clef-flash-q4km", "", "clef-flash-q4km")
MODE, N, CONC = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 400, int(sys.argv[3]) if len(sys.argv) > 3 else 6
D = "/workspace/data/ccnews"; OUT = f"{D}/labels-{MODE}.jsonl"; LOG = f"{D}/progress.log"
OUTLETS = ["uk.reuters.com", "www.reuters.com", "in.reuters.com", "indianexpress.com", "www.cnn.com", "nationalpost.com", "www.taiwannews.com.tw", "www.seattletimes.com",
           "allafrica.com", "www.theguardian.com", "www.cbc.ca", "abcnews.go.com", "www.bbc.co.uk", "www.bbc.com", "www.nbcnews.com", "www.nzherald.co.nz", "www.usatoday.com",
           "globalnews.ca", "www.theglobeandmail.com", "www.smh.com.au", "www.npr.org", "www.telegraph.co.uk", "www.channelnewsasia.com", "www.irishtimes.com",
           "www.business-standard.com", "www.financialexpress.com", "economictimes.indiatimes.com", "www.foxnews.com", "www.philly.com", "www.thestar.com", "www.aljazeera.com",
           "apnews.com", "www.washingtonpost.com", "www.nytimes.com", "www.latimes.com", "www.independent.co.uk", "www.scmp.com", "www.straitstimes.com", "www.abc.net.au",
           "www.thehindu.com", "www.hindustantimes.com", "www.dw.com", "www.france24.com", "www.euronews.com", "www.japantimes.co.jp", "www.ft.com", "www.economist.com",
           "www.bloomberg.com", "www.cnbc.com", "www.politico.com", "thehill.com", "www.voanews.com", "www.rte.ie", "www.stuff.co.nz", "www.news.com.au", "www.theatlantic.com",
           "www.pbs.org", "www.cbsnews.com", "www.dawn.com", "www.thenews.com.pk", "nation.com.pk", "www.firstpost.com", "www.therecord.com", "www.thespec.com",
           "www.irishexaminer.com", "www.breakingnews.ie", "www.chicagotribune.com", "www.sfgate.com", "www.miamiherald.com", "www.bostonglobe.com", "www.startribune.com"]
def log(msg):
    line = f"{time.strftime('%F %T')}  {msg}"; print(line, flush=True); open(LOG, "a").write(line + "\n")
t = pa.concat_tables([pq.read_table(f) for f in sorted(glob.glob(f"{D}/raw/plain_text/*.parquet"))]).to_pylist()
keep = set(OUTLETS)
pool = [r for r in t if r["domain"] in keep and r["description"] and r["text"] and len(r["text"].split()) >= 80]
pool.sort(key=lambda r: r["url"]); random.Random(0).shuffle(pool); sample = pool[:N]
done = {json.loads(l)["url"] for l in open(OUT)} if os.path.exists(OUT) else set()
todo = [r for r in sample if r["url"] not in done]
log(f"[{MODE}] start: {len(todo)} of {N} articles to read ({'title + description' if MODE == 'h' else 'title + up to 1,200 words'}), pool {len(pool)} from {len(keep)} outlets, {CONC} at a time")
lock, t0, n = threading.Lock(), time.time(), [0]
def one(r):
    day = (r["date"] or "")[:10] or time.strftime("%F")
    desc = r["description"] if MODE == "h" else " ".join(r["text"].split()[:1200])
    s = time.time(); P = C.ask({"published_at": day, "title": r["title"], "description": desc}, today=day); rd = C.read(P)
    rec = {"url": r["url"], "domain": r["domain"], "date": day, "title": r["title"], "mode": MODE, "chars": len(r["title"]) + 1 + len(desc), "P": P,
           "keys": sorted({f"{x['dial']}|{x['direction']}" for x in rd["readings"] if x["direction"] in ("up", "down")}), "gate_ok": rd["gate_ok"], "s": round(time.time() - s, 1)}
    with lock:
        open(OUT, "a").write(json.dumps(rec) + "\n"); n[0] += 1
        if n[0] % 20 == 0 or n[0] == len(todo):
            el = time.time() - t0; rate = n[0] / el * 60
            log(f"[{MODE}] {n[0]}/{len(todo)} read, {rate:.1f} articles/min, {el / 60:.1f} min so far, ETA {(len(todo) - n[0]) / rate:.0f} min")
with cf.ThreadPoolExecutor(CONC) as ex:
    for f in cf.as_completed([ex.submit(one, r) for r in todo]):
        if f.exception(): log(f"[{MODE}] error: {repr(f.exception())[:160]}")
log(f"[{MODE}] DONE {n[0]} articles in {(time.time() - t0) / 60:.1f} min")
