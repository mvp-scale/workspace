"""Step 1 (ledger S-0001, D-0003): a third Clef wording per engine attribute, to measure how much Clef varies with wording (assumption A-0009).
The third wording is each attribute's own written definition (probes/persona/rules_v2/dial_attributes*.csv), as "This story reports that <definition>.",
so it means the same as the attribute by construction. Clef answers it for the 880 stories already in clef-q4km.jsonl, on the same stored text.
Writes one line per story: id and P3 {a|dial|dir|i|2: probability}. Resumable. Local Clef only (:8018).
Run from /workspace/probes/world-engine:  WE_RULES=rules_v2 /workspace/kev/.venv/bin/python /workspace/newsreader/bitmob/label_w3.py [CONCURRENCY]"""
import sys, os, json, time, threading, concurrent.futures as cf
os.environ.setdefault("WE_RULES", "rules_v2"); sys.path.insert(0, "/workspace/probes/world-engine")
import classify as C
C.O.set_reader("http://127.0.0.1:8018", "clef-flash-q4km", "", "clef-flash-q4km")
CONC = int(sys.argv[1]) if len(sys.argv) > 1 else 6
SRC = "/workspace/data/newsreader/labels/clef-q4km.jsonl"; OUT = "/workspace/data/newsreader/labels/clef-q4km-w3.jsonl"
Q3 = {f"a|{d}|{dirn}|{i}|2": f"This story reports that {r['definition'].strip().rstrip('.')}." for (d, dirn), lst in C.ATTRS.items() for i, r in enumerate(lst)}
json.dump({"teacher": "clef-flash-q4km", "questions": len(Q3), "rules": "rules_v2", "wording": "attribute definition: 'This story reports that <definition>.'",
           "text": "the same stored text as clef-q4km.jsonl (title + up to 1,200 words)", "ledger": "S-0001 / D-0003 / A-0009"}, open(OUT.replace(".jsonl", ".meta.json"), "w"))
done = {json.loads(l)["id"] for l in open(OUT)} if os.path.exists(OUT) else set()
todo = [r for r in map(json.loads, open(SRC)) if r["id"] not in done]
print(f"{len(done)} done; asking {len(Q3)} questions on {len(todo)} stories, {CONC} at a time", flush=True)
lock, t0, n = threading.Lock(), time.time(), [0]; names = list(Q3)
def one(r):
    state = f"News item (published {time.strftime('%Y-%m-%d')}; today is {time.strftime('%Y-%m-%d')}):\n{r['title']}. {r['text']}"; P3 = {}
    for j in range(0, len(names), 20):
        a = C.O.call(state, {k: {"type": "noul", "instructions": Q3[k]} for k in names[j:j + 20]}); P3.update({k: a[k]["noul"] for k in a})
    with lock:
        open(OUT, "a").write(json.dumps({"id": r["id"], "P3": P3}) + "\n"); n[0] += 1
        if n[0] % 20 == 0: el = time.time() - t0; print(f"{n[0]} labelled, {n[0] / el * 60:.1f} stories/min, {el / 60:.1f} min", flush=True)
with cf.ThreadPoolExecutor(CONC) as ex:
    for f in cf.as_completed([ex.submit(one, r) for r in todo]):
        if f.exception(): print("error:", repr(f.exception())[:200], flush=True)
print("DONE", n[0], round((time.time() - t0) / 60, 1), "min", flush=True)
