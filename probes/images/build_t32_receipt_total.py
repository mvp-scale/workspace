"""CORD receipts not already used in t02 or t31. The total is the file's total_price."""
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

TASK = "t32_receipt_total"
SRC = next(Path("/workspace/data/sources/image-lab/cord-v2/data").glob("test-*.parquet"))
URL = "https://huggingface.co/datasets/naver-clova-ix/cord-v2"
SEED = 32


def load_rows():
    return pq.read_table(SRC).to_pylist()


def amount_ok(s):
    return isinstance(s, str) and re.fullmatch(r"[\d.,]+", s.strip() or "x") is not None


def total_price(row):
    total = json.loads(row["ground_truth"])["gt_parse"].get("total")
    if not isinstance(total, dict):
        return None
    price = total.get("total_price")
    return price if amount_ok(price) else None


def used_rows():
    used = set()
    here = Path(__file__).resolve().parent
    for name in ("t02_receipt_capture.jsonl", "t31_receipt_lines.jsonl"):
        path = here / name
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                used.add(int(str(row["provenance"]["source_id"]).split()[-1]))
    return used


def rederive(item):
    idx = int(str(item["provenance"]["source_id"]).split()[-1])
    price = total_price(load_rows()[idx])
    if price is None:
        raise ValueError(f"row {idx} has no total_price")
    return price


def build():
    rows = load_rows()
    used = used_rows()
    pool = [i for i, row in enumerate(rows) if i not in used and total_price(row)]
    rng = random.Random(SEED)
    rng.shuffle(pool)
    if len(pool) < 25:
        raise SystemExit(f"only {len(pool)} unused totals")
    out = []
    for n, i in enumerate(pool[:25]):
        price = total_price(rows[i])
        im = Image.open(io.BytesIO(rows[i]["image"]["bytes"]))
        rel = save_image(im, TASK, n)
        options = decoy_numbers(price, 3, SEED + i) + [price]
        question, labels, expected = make_choice(
            "What is the total amount on this receipt?", options, price, f"{TASK}-{n}"
        )
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
                "gt_parse.total.total_price",
                notes="gt_parse.total.total_price",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print(f"wrote {len(build())}")
