"""Pilot on REAL public images with the dataset's own labels (nothing written by us).
  CORD v2 test (CC-BY-4.0): receipt total, number of line items, was a discount applied.
  CountBench (Paiss et al., licence not stated; local use only): "how many" photographs, the true count is the dataset's `number`.
Raw data: /workspace/data/sources/image-lab/ (git-ignored). Run: /workspace/kev/.venv/bin/python real_pilot.py [--n 40]
"""
import argparse, io, json, random, re, statistics, urllib.error
from pathlib import Path
import pyarrow.parquet as pq
from PIL import Image
from suite import ask

S = Path("/workspace/data/sources/image-lab")
WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}

def rows(path):
    for b in pq.ParquetFile(path).iter_batches(batch_size=8):
        yield from b.to_pylist()

def amount_ok(s): return isinstance(s, str) and re.fullmatch(r"[\d.,]+", s.strip() or "x") is not None

def decoys(total, rng):
    digits = [i for i, c in enumerate(total) if c.isdigit()]; out = set()
    while len(out) < 3:
        t = list(total); i = rng.choice(digits); t[i] = str((int(t[i]) + rng.randint(1, 9)) % 10)
        if "".join(t) != total: out.add("".join(t))
    return list(out)

def cord_items(n, rng):
    items = []
    for r in rows(next((S / "cord-v2/data").glob("test-*.parquet"))):
        gt = json.loads(r["ground_truth"])["gt_parse"]; img = Image.open(io.BytesIO(r["image"]["bytes"])).convert("RGB")
        total = (gt.get("total") or {}).get("total_price")
        if isinstance(total, str) and amount_ok(total):
            opts = decoys(total, rng) + [total]; rng.shuffle(opts)
            items.append(("cord_total", img, {"type": "choice", "instructions": "What is the total amount on this receipt?", "criteria": {o: None for o in opts}}, total))
        menu = gt.get("menu"); k = len(menu) if isinstance(menu, list) else (1 if menu else 0)
        if 1 <= k <= 8:
            items.append(("cord_item_count", img, {"type": "choice", "instructions": "How many different line items are on this receipt?", "criteria": {str(i): None for i in range(1, 9)}}, str(k)))
        disc = (gt.get("sub_total") or {}).get("discount_price")
        items.append(("cord_discount", img, {"type": "noul", "instructions": "Does this receipt show a discount?"}, bool(disc)))
        if len(items) >= n * 3: break
    return items

def count_items(n, rng):
    items = []
    for r in rows(next((S / "countbench/data").glob("*.parquet"))):
        num, text = r["number"], r["text"]
        if num not in WORDS or not r["image"] or not r["image"].get("bytes"): continue
        m = re.search(rf"\b({WORDS[num]}|{num})\b", text, re.I)
        if not m: continue
        masked = text[:m.start()] + "___" + text[m.end():]
        img = Image.open(io.BytesIO(r["image"]["bytes"])).convert("RGB")
        items.append(("countbench", img, {"type": "choice", "instructions": f"A caption for this photo reads: \"{masked}\". Which number belongs in the blank?", "criteria": {str(i): None for i in range(2, 11)}}, str(num)))
        if len(items) >= n: break
    return items

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=40); ap.add_argument("--endpoint", default="http://127.0.0.1:8091"); a = ap.parse_args()
    rng = random.Random(0); out = Path("/workspace/data/vision-runs/winnow-real"); (out / "images").mkdir(parents=True, exist_ok=True); res = []
    items = cord_items(a.n, rng)[: a.n * 3] + count_items(a.n * 2, rng)
    per = {}
    for cat, im, q, exp in items:
        per[cat] = per.get(cat, 0) + 1
        if per[cat] > (a.n * 2 if cat == "countbench" else a.n): continue
        name = f"{cat}-{per[cat]:03d}.jpg"; im.save(out / "images" / name, quality=85)
        try: ans, dt, toks = ask(a.endpoint, "Winnow-12B", im, q)
        except urllib.error.HTTPError as e:
            res.append({"category": cat, "image": name, "question": q["instructions"], "expected": exp, "error": f"HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}", "size": im.size}); continue
        if q["type"] == "noul": p = ans["noul"]; pred = p >= 0.5; pc = p if exp else 1 - p
        else: pred = ans["choice"]; pc = ans["probabilities"].get(exp, 0.0)
        res.append({"category": cat, "image": name, "question": q["instructions"], "expected": exp, "predicted": pred, "correct": pred == exp, "p_correct": pc, "latency_s": dt, "input_tokens": toks, "size": im.size})
    (out / "results.jsonl").write_text("\n".join(json.dumps(x) for x in res) + "\n")
    errs = [x for x in res if "error" in x]; res = [x for x in res if "error" not in x]
    for e in errs: print("ERROR", e["image"], e["size"], e["error"])
    for cat in dict.fromkeys(x["category"] for x in res):
        r = [x for x in res if x["category"] == cat]
        print(f"{cat:16s} {sum(x['correct'] for x in r):3d}/{len(r)}  mean p(correct)={statistics.mean(x['p_correct'] for x in r):.2f}  tokens~{int(statistics.mean(x['input_tokens'] or 0 for x in r))}  p50 {statistics.median(x['latency_s'] for x in r) * 1000:.0f} ms")

if __name__ == "__main__":
    main()
