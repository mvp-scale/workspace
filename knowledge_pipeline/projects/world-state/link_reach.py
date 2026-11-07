"""Link reach: how many stored articles still carry links in their text (the 300 inventory articles; first 2000 full-text queue items). Writes runs/harvest/link_reach.json."""
import json, re, random, sqlite3
U = re.compile(r"https?://[^\s<>\")\]]+|\bwww\.[^\s<>\")\]]+", re.I)
R = [r for r in map(json.loads, open("runs/harvest/sample.jsonl")) if len(r["text"] or "") >= 800]; random.Random(20261107).shuffle(R); R = R[:300]
c = sqlite3.connect("file:/workspace/data/newsreader/queue.sqlite?mode=ro", uri=True); rows = c.execute("select body from items where depth='full' and body is not null limit 2000").fetchall()
img = c.execute("select sum(image is not null), count(*) from items").fetchone()
res = {"cc_articles": len(R), "cc_with_link": sum(bool(U.search(r["text"])) for r in R), "cc_links": sum(len(U.findall(r["text"])) for r in R), "queue_bodies": len(rows), "queue_with_link": sum(bool(U.search(b[0])) for b in rows), "queue_items": img[1], "queue_with_image_url": img[0]}
json.dump(res, open("runs/harvest/link_reach.json", "w"), indent=1); print(res)
