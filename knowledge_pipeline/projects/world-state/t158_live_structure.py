"""T158 live walk-through (temporary, observational, no pass bar): run the structure pack on real articles as the news reader finds them.
Reads the news reader queue read-only; only items with found_at >= START, oldest first, each once. Text = title + teaser + first 500 body characters if the body is already extracted. No gold labels are read.
Per article: noun words, each placed (exact / synonym / one hop up) on an IPTC node or not placed; a topic prior (bge-small nearest IPTC top-level label); a word counts "in topic" when its node sits under the top-1 prior.
Writes an append-only log (every line carries the text hash and the code hash) and a small JSON the page polls. Stops itself after DURATION seconds.
    START=<epoch> DURATION=3600 POLL=20 PAGE_DIR=/workspace/demo/mockups/structure-live LOG=runs/pulse/t158/live.jsonl /workspace/models/embed-zs/.venv/bin/python -u t158_live_structure.py"""
import os, sys, json, time, hashlib, sqlite3, statistics
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, spacy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from structure_pack import Pack, SRC
START = float(os.environ.get("START", time.time())); DURATION = float(os.environ.get("DURATION", 3600)); POLL = float(os.environ.get("POLL", 20))
PAGE = os.environ.get("PAGE_DIR", "/workspace/demo/mockups/structure-live"); LOG = os.environ.get("LOG", "runs/pulse/t158/live.jsonl"); os.makedirs(PAGE, exist_ok=True); os.makedirs(os.path.dirname(LOG), exist_ok=True)
fh = hashlib.sha256()
for p in (os.path.abspath(__file__), os.path.join(os.path.dirname(os.path.abspath(__file__)), "structure_pack.py"), SRC + "/iptc/medtop.json", SRC + "/wordnet/wordnet/data.noun", SRC + "/wordnet/wordnet/index.noun"): fh.update(open(p, "rb").read())
CODE = fh.hexdigest()[:16]
nlp = spacy.load("en_core_web_sm", disable=["ner"]); pack = Pack(nlp)
from sentence_transformers import SentenceTransformer
import torch; torch.set_num_threads(4)
emb = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); emb.max_seq_length = 128
names = list(pack.L1); LE = emb.encode([f"{n}: {pack.node[pack.L1[n]]['definition']['en-GB']}" for n in names], normalize_embeddings=True, convert_to_numpy=True)
done = set()
if os.path.exists(LOG):
    for l in open(LOG):
        try: done.add(json.loads(l).get("id"))
        except Exception: pass
log = open(LOG, "a"); log.write(json.dumps({"kind": "start", "start": START, "code": CODE, "ts": time.time(), "duration": DURATION}) + "\n"); log.flush()
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True)
recent = []; stats = {"processed": 0, "terms": 0, "placed": 0, "in_topic": 0}; ms_all = []; topics = {}; t_end = time.time() + DURATION
def write_page(backlog):
    ms = sorted(ms_all)
    d = {"start": START, "now": time.time(), "code": CODE, "ends": t_end, "processed": stats["processed"], "backlog": backlog, "terms": stats["terms"], "placed": stats["placed"], "in_topic": stats["in_topic"],
         "median_ms": statistics.median(ms) if ms else None, "p90_ms": ms[int(0.9 * len(ms))] if ms else None, "topics": dict(sorted(topics.items(), key=lambda kv: -kv[1])), "items": recent[-30:][::-1]}
    open(PAGE + "/data.tmp", "w").write(json.dumps(d)); os.replace(PAGE + "/data.tmp", PAGE + "/data.json")
write_page(0)
while time.time() < t_end:
    rows = db.execute("select id,source,title,teaser,body,found_at,published,url from items where found_at>=? order by found_at limit 300", (START,)).fetchall()
    rows = [r for r in rows if r[0] not in done]; total_new = db.execute("select count(*) from items where found_at>=?", (START,)).fetchone()[0] - len(done)
    for k in range(0, len(rows), 32):
        if time.time() >= t_end: break
        chunk = rows[k:k + 32]; texts = []
        for r in chunk:
            tx = ((r[2] or "") + ". " + (r[3] or "") + ((" " + r[4][:500]) if r[4] else "")).strip(); texts.append(tx)
        t0 = time.perf_counter(); E = emb.encode(texts, batch_size=32, normalize_embeddings=True, convert_to_numpy=True); S = E @ LE.T; emb_ms = (time.perf_counter() - t0) * 1000 / len(chunk)
        for r, tx, sc in zip(chunk, texts, S):
            done.add(r[0])
            if len(tx) < 25: continue
            t0 = time.perf_counter(); doc = nlp(tx); order = np.argsort(-sc)[:3]; top = pack.L1[names[int(order[0])]]; words = []
            for w in pack.terms(doc):
                c = pack.place(w); f = [x for x in c if pack.chain(x[1])[0] == top]
                if f: x = f[0]; words.append({"w": w, "hop": x[0], "via": x[2], "path": pack.path(x[1]), "in_topic": True})
                elif c: x = c[0]; words.append({"w": w, "hop": x[0], "via": x[2], "path": pack.path(x[1]), "in_topic": False})
                else: words.append({"w": w, "hop": None})
            ms = (time.perf_counter() - t0) * 1000 + emb_ms; ms_all.append(ms)
            rec = {"id": r[0], "source": r[1], "title": r[2], "found_at": r[5], "published": r[6], "sha": hashlib.sha1(tx.encode()).hexdigest()[:12], "code": CODE, "chars": len(tx), "text": tx[:420],
                   "topic_prior": [[names[int(j)], round(float(sc[j]), 3)] for j in order], "words": words, "n_terms": len(words), "n_placed": sum(1 for x in words if x["hop"]), "n_in_topic": sum(1 for x in words if x.get("in_topic")), "ms": round(ms, 1)}
            log.write(json.dumps(rec) + "\n"); log.flush(); recent.append(rec)
            stats["processed"] += 1; stats["terms"] += rec["n_terms"]; stats["placed"] += rec["n_placed"]; stats["in_topic"] += rec["n_in_topic"]; topics[names[int(order[0])]] = topics.get(names[int(order[0])], 0) + 1
        write_page(max(0, total_new - stats["processed"]))
    write_page(max(0, total_new - stats["processed"]))
    if len(rows) < 300: time.sleep(POLL)
log.write(json.dumps({"kind": "stop", "ts": time.time(), "processed": stats["processed"]}) + "\n"); log.close(); write_page(0)
