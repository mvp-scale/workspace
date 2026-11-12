"""T92 prep: make the T91 supported triples readable by t77_map.py / t79_constrain.py. Writes <OUT>/queue.jsonl (id 'cc:<url>', text = title. description, domain, date) for the articles that hold a supported triple, and <OUT>/t76_supported_triples.json with 'article' as the row index into that queue (the name t77 expects).
    python3 t92_prep.py  (embed-zs venv python)"""
import json, glob, os, pyarrow.parquet as pq, pyarrow as pa, pyarrow.compute as pc
# SRC selects another supported-triples file (T98 uses the T97 one)
OUT = os.environ.get("OUT", "runs/pulse/t92"); os.makedirs(OUT, exist_ok=True)
SUP = json.load(open(os.environ.get("SRC", "runs/pulse/t91/t91_supported_triples.json"))); urls = sorted({s["article"] for s in SUP}); meta = {}
for f in sorted(glob.glob("/workspace/data/ccnews/raw/plain_text/*.parquet")):
    t = pq.read_table(f, columns=["url", "title", "description", "domain", "date"]); mk = pc.is_in(t["url"], value_set=pa.array(urls))
    for r in t.filter(mk).to_pylist(): meta[r["url"]] = r
ix = {u: i for i, u in enumerate(urls)}
with open(OUT + "/queue.jsonl", "w") as w:
    for u in urls:
        r = meta.get(u, {}); ti = " ".join((r.get("title") or "").split()); d = " ".join((r.get("description") or "").split())
        w.write(json.dumps({"id": "cc:" + u, "text": ti + ". " + d, "domain": r.get("domain"), "date": str(r.get("date"))[:10]}) + "\n")
json.dump([{**s, "article": ix[s["article"]]} for s in SUP], open(OUT + "/t76_supported_triples.json", "w"))
R = {"articles": len(urls), "found_in_parquet": len(meta), "triples": len(SUP)}; json.dump(R, open(OUT + "/prep_result.json", "w")); print(json.dumps(R))
