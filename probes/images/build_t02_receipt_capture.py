"""CORD v2 test receipts: total amount, or number of line items. Answers come from ground_truth."""
import io
import json
import random
import re
import sys
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import decoy_numbers, make_choice, provenance, save_image

SEED = 2
TASK = "t02_receipt_capture"
SRC = next(Path("/workspace/data/sources/image-lab/cord-v2/data").glob("test-*.parquet"))
URL = "https://huggingface.co/datasets/naver-clova-ix/cord-v2"
N_TOTAL = 13
N_COUNT = 12

def amount_ok(s):
    return isinstance(s, str) and re.fullmatch(r"[\d.,]+", s.strip() or "x") is not None

def rows():
    table = pq.read_table(SRC)
    for i, row in enumerate(table.to_pylist()):
        yield i, row

def parse_gt(row):
    return json.loads(row["ground_truth"])["gt_parse"]

def total_price(parse):
    total = parse.get("total")
    if not isinstance(total, dict):
        return None
    price = total.get("total_price")
    return price if amount_ok(price) else None

def item_count(parse):
    menu = parse.get("menu")
    k = len(menu) if isinstance(menu, list) else (1 if isinstance(menu, dict) else 0)
    return k if 1 <= k <= 8 else None

def rederive(item):
    idx = int(str(item["provenance"]["source_id"]).split()[-1])
    kind = item["provenance"]["notes"]
    row = pq.read_table(SRC).to_pylist()[idx]
    parse = parse_gt(row)
    if kind == "gt_parse.total.total_price":
        return total_price(parse)
    if kind == "len(gt_parse.menu)":
        k = item_count(parse)
        return None if k is None else str(k)
    raise ValueError(f"unknown field {kind}")

def select():
    totals, counts = [], []
    for i, row in rows():
        parse = parse_gt(row)
        price = total_price(parse)
        k = item_count(parse)
        if price is not None:
            totals.append(i)
        if k is not None:
            counts.append((i, k))
    rng = random.Random(SEED)
    by_k = {}
    for i, k in counts:
        by_k.setdefault(k, []).append(i)
    for k in by_k:
        rng.shuffle(by_k[k])
    picked_count = []
    while len(picked_count) < N_COUNT:
        moved = False
        for k in range(1, 9):
            bucket = by_k.get(k) or []
            if bucket and len(picked_count) < N_COUNT:
                picked_count.append(bucket.pop())
                moved = True
        if not moved:
            break
    if len(picked_count) < N_COUNT:
        raise RuntimeError(f"only {len(picked_count)} count rows")
    used = set(picked_count)
    total_pool = [i for i in totals if i not in used]
    rng.shuffle(total_pool)
    picked_total = total_pool[:N_TOTAL]
    if len(picked_total) < N_TOTAL:
        raise RuntimeError(f"only {len(picked_total)} total rows")
    return picked_total, picked_count

def build():
    by_index = {i: row for i, row in rows()}
    picked_total, picked_count = select()
    items = [("total", i) for i in picked_total] + [("count", i) for i in picked_count]
    out = []
    for n, (kind, i) in enumerate(items):
        row = by_index[i]
        parse = parse_gt(row)
        im = Image.open(io.BytesIO(row["image"]["bytes"]))
        rel = save_image(im, TASK, n)
        if kind == "total":
            price = total_price(parse)
            options = decoy_numbers(price, 3, SEED + i) + [price]
            question, labels, expected = make_choice(
                "What is the total amount on this receipt?", options, price, SEED + i
            )
            origin = "gt_parse.total.total_price"
        else:
            k = str(item_count(parse))
            question, labels, expected = make_choice(
                "How many different line items are on this receipt?",
                [str(x) for x in range(1, 9)],
                k,
                SEED + i,
            )
            origin = "len(gt_parse.menu)"
        out.append({
            "id": f"{TASK}-{n:03d}",
            "family": TASK,
            "state": "An image is attached.",
            "images": [rel],
            "question": question,
            "labels": labels,
            "expected": expected,
            "split": "public",
            "group": None,
            "provenance": provenance(
                "CORD v2 test split",
                f"row {i}",
                URL,
                "CC-BY-4.0",
                origin,
                notes=origin,
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out

if __name__ == "__main__":
    rows_out = build()
    print(f"wrote {len(rows_out)}")
