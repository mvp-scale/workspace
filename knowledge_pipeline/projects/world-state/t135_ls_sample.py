"""Build the label-store sample for T135: sonnet-labelled CC-News stories (item_id cc:<url>) with their text from the CC-News parquet files (the queue no longer keeps their body). -> /workspace/data/newsreader/labels/t135_ls_sample.jsonl"""
import json, random, glob
import pyarrow.parquet as pq, pyarrow as pa, pyarrow.compute as pc
rng = random.Random(135); L = {}
for l in open("runs/label_store/labels.jsonl"):
    x = json.loads(l)
    if x.get("family") == "sonnet" and x["item_id"].startswith("cc:") and x["item_id"] not in L: L[x["item_id"]] = x
ids = list(L); rng.shuffle(ids); want = {i[3:] for i in ids[:400]}; out = []
for f in sorted(glob.glob("/workspace/data/ccnews/raw/plain_text/*.parquet")):
    t = pq.read_table(f, columns=["url", "title", "text", "date"]); m = pc.is_in(t["url"], value_set=pa.array(list(want)))
    for r in t.filter(m).to_pylist():
        w = " ".join((r["text"] or "").split())
        if len(w.split()) >= 80 and len((r["title"] or "").strip()) >= 10:
            x = L["cc:" + r["url"]]; out.append({"id": x["item_id"], "title": r["title"].strip(), "body": " ".join(w.split()[:1200]), "published": str(r["date"])[:10] if r.get("date") else None, "ls_story_type": x["story_type"], "ls_topic": x["topic"]})
    if len(out) >= 60: break
rng.shuffle(out); open("/workspace/data/newsreader/labels/t135_ls_sample.jsonl", "w").write("\n".join(json.dumps(o) for o in out[:60])); print(len(out))
