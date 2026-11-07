"""Draw a seeded sample of CC-News full articles (seed 20261107) for the label harvester. Writes runs/harvest/sample.jsonl.
    /workspace/models/embed-zs/.venv/bin/python harvest_sample.py [N]"""
import sys, json, random, glob, pyarrow.parquet as pq
N = int(sys.argv[1]) if len(sys.argv) > 1 else 20000; rng = random.Random(20261107); out = []
files = sorted(glob.glob("/workspace/data/ccnews/raw/plain_text/*.parquet")); per = N // len(files)
for f in files:
    pf = pq.ParquetFile(f); total = pf.metadata.num_rows; want = set(rng.sample(range(total), per)); i = 0
    for g in range(pf.num_row_groups):
        t = pf.read_row_group(g, columns=["title", "text", "domain", "date", "url", "description"]); n = t.num_rows
        for k in [k for k in range(n) if i + k in want]: r = {c: t.column(c)[k].as_py() for c in t.column_names}; r["row"] = f.split("/")[-1][:11] + ":" + str(i + k); out.append(r)
        i += n
OUTF = sys.argv[2] if len(sys.argv) > 2 else "runs/harvest/sample.jsonl"
with open(OUTF, "w") as w:
    for r in out: w.write(json.dumps(r) + "\n")
print(len(out), "articles")
