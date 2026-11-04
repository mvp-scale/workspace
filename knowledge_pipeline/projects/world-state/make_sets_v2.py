"""T20 step 0, corrected (ledger L439): natural, later, unseen sets from the live queue. Writes ids and, for DEVQ, the items to be Sonnet-labelled; SEALED gets ids + SHA-256 only. No labels are read or made here. CPU, local, no hosted calls.
    /workspace/kev/.venv/bin/python make_sets_v2.py"""
import sqlite3, json, re, random, hashlib, pathlib
db = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); k = lambda t: re.sub(r"\W+", " ", t.lower()).strip()[:120]
ptxt = {k(json.loads(l)["text"]) for l in open("data/pool_train.jsonl")}
rows = db.execute("select id, title, teaser, published from items where teaser is not null and length(teaser)>40 and title is not null and published is not null order by published").fetchall()
seen = set(); new = []
for i, t, d, p in rows:
    text = re.sub(r"\s+", " ", t.strip() + ". " + d.strip()); key = k(text)
    if key in ptxt or key in seen or p < "2026-10-29": continue
    seen.add(key); new.append({"id": "q:" + i, "text": text, "date": p[:10], "from": "queue", "published": p})
n = len(new); late = new[-2800:]; early = new[:-2800]; r = random.Random(20261102)
sealed = r.sample(late, 1500); sset = {x["id"] for x in sealed}; devq = r.sample([x for x in early], 2000)
out = pathlib.Path("runs/pulse"); out.mkdir(exist_ok=True)
(out / "devq_items.jsonl").write_text("".join(json.dumps({k_: x[k_] for k_ in ("id", "text", "date", "from")}) + "\n" for x in devq)); (out / "queue_texts.jsonl").write_text("".join(json.dumps({"id": x["id"], "text": x["text"]}) + "\n" for x in devq + sealed))
sid = "\n".join(sorted(sset)) + "\n"; (out / "sealed_q_ids.txt").write_text(sid); sha = hashlib.sha256(sid.encode()).hexdigest()
info = {"new_queue_items": n, "late_pool": len(late), "early_pool": len(early), "devq": len(devq), "sealed": len(sealed), "sealed_ids_sha256": sha, "devq_published_range": [min(x["published"] for x in devq)[:10], max(x["published"] for x in devq)[:10]], "sealed_published_range": [min(x["published"] for x in sealed)[:16], max(x["published"] for x in sealed)[:16]]}
(out / "sets_v2.json").write_text(json.dumps(info, indent=1)); print(json.dumps(info, indent=1))
