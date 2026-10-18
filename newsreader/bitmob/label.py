"""Teaching pass: Clef answers the World engine's 328 questions on news stories from the reader's queue, several stories at once (Clef has 8 slots).
Writes one JSON line per story: id, source, region, title, the text read (title + up to 1,200 words), Clef's probability per question (P) and the readings
the engine derives from them. Text stays in data/ (git-ignored). Resumable: stories already labelled are skipped.
Run from /workspace/probes/world-engine with the kev venv:  WE_RULES=rules_v2 python -I /workspace/newsreader/bitmob/label.py [N] [CONCURRENCY]"""
import sys, os, json, time, sqlite3, threading, concurrent.futures as cf
os.environ.setdefault("WE_RULES", "rules_v2"); sys.path.insert(0, "/workspace/probes/world-engine")
import classify as C
C.O.set_reader("http://127.0.0.1:8018", "clef-flash-q4km", "", "clef-flash-q4km")
N, CONC = int(sys.argv[1]) if len(sys.argv) > 1 else 2000, int(sys.argv[2]) if len(sys.argv) > 2 else 6
OUT = "/workspace/data/newsreader/labels/clef-q4km.jsonl"
json.dump({"teacher": "clef-flash-q4km", "questions": len(C.QS), "rules": "rules_v2", "text": "title + up to 1,200 words of the article"}, open(OUT.replace(".jsonl", ".meta.json"), "w"))
done = {json.loads(l)["id"] for l in open(OUT)} if os.path.exists(OUT) else set()
db = sqlite3.connect("/workspace/data/newsreader/queue.sqlite")
rows = db.execute("SELECT id, source, region, title, body FROM items WHERE depth='full' AND body IS NOT NULL ORDER BY found_at").fetchall()
by_src = {}
for r in rows:
    if r[0] not in done: by_src.setdefault(r[1], []).append(r)
todo = []                                       # round-robin across outlets so no one source dominates the teaching set
while len(todo) < N and any(by_src.values()):
    for s in list(by_src):
        if by_src[s]: todo.append(by_src[s].pop())
todo = todo[:N]; print(f"{len(done)} already labelled; labelling {len(todo)} from {len({r[1] for r in todo})} outlets, {CONC} at a time", flush=True)
lock, t0, n = threading.Lock(), time.time(), [0]
def one(r):
    sid, src, reg, title, body = r; text = " ".join(body.split()[:1200]); t = time.time()
    P = C.ask({"published_at": time.strftime("%Y-%m-%d"), "title": title, "description": text}); rd = C.read(P)
    rec = {"id": sid, "source": src, "region": reg, "title": title, "text": text, "P": P, "readings": rd["readings"], "gate": rd["gate"], "gate_ok": rd["gate_ok"], "s": round(time.time() - t, 1)}
    with lock:
        open(OUT, "a").write(json.dumps(rec) + "\n"); n[0] += 1
        if n[0] % 20 == 0: el = time.time() - t0; print(f"{n[0]} labelled, {n[0] / el * 60:.1f} stories/min, {el / 60:.1f} min", flush=True)
with cf.ThreadPoolExecutor(CONC) as ex:
    for f in cf.as_completed([ex.submit(one, r) for r in todo]):
        if f.exception(): print("error:", repr(f.exception())[:200], flush=True)
print("DONE", n[0], flush=True)
