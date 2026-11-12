"""Test F: build a SECOND a FRESH MN-DS slice for scoring once. Rows of train.jsonl whose title was not in items_T28 or items_T28b, 800+ characters of content, 100 per category over the 16 categories of gold_T28b, seeded. Scoring only. Writes items_fresh.jsonl and gold_fresh.json next to the other anchor files (git-ignored data folder)."""
import json, random, collections
D = "/workspace/data/anchors/mn_ds/"
rows = [json.loads(l) for l in open(D + "train.jsonl")]
used = set()
for f in ("items_T28.jsonl", "items_T28b.jsonl", "items_fresh.jsonl"):
    for l in open(f if f.startswith("/") else D + f): used.add(json.loads(l)["text"].split(". ")[0].strip()[:60])
cats = sorted({v["l1"] for v in json.load(open(D + "gold_T28b.json")).values()})
by = collections.defaultdict(list)
for r in rows:
    if r["category_level_1"] in cats and len(r.get("content") or "") >= 800 and (r["title"] or "").strip()[:60] not in used and (r["title"] or "").strip(): by[r["category_level_1"]].append(r)
rng = random.Random(20261109); sel = []
for c in cats:
    rng.shuffle(by[c]); sel += by[c][:100]
items = []; gold = {}
for r in sel:
    i = "mn4:" + str(r["data_id"]); items.append({"id": i, "text": ((r["title"] or "").strip() + ". " + r["content"].strip())[:500]}); gold[i] = {"l1": r["category_level_1"], "l2": r["category_level_2"]}
open(D + "items_fresh2.jsonl", "w").write("\n".join(json.dumps(x) for x in items) + "\n"); json.dump(gold, open(D + "gold_fresh2.json", "w"))
leak = sum(1 for r in sel if (r["title"] or "").strip()[:60] in used)
print(len(items), "categories", len(cats), "available per category min", min(len(by[c]) for c in cats), "title overlap with T28/T28b", leak)
