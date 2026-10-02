"""CORD receipts not already used in t02. The answer is how many menu lines the file lists."""
import io
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_choice, provenance, save_image

TASK = "t31_receipt_lines"
SRC = next(Path("/workspace/data/sources/image-lab/cord-v2/data").glob("test-*.parquet"))
URL = "https://huggingface.co/datasets/naver-clova-ix/cord-v2"
SEED = 31
OPTIONS = ["1", "2", "3", "4 or more"]


def load_rows():
    return pq.read_table(SRC).to_pylist()


def parse_gt(row):
    return json.loads(row["ground_truth"])["gt_parse"]


def item_count(parse):
    menu = parse.get("menu")
    if isinstance(menu, list):
        return len(menu)
    if isinstance(menu, dict):
        return 1
    return 0


def used_in_t02():
    path = Path(__file__).resolve().parent / "t02_receipt_capture.jsonl"
    used = set()
    for line in path.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            used.add(int(str(row["provenance"]["source_id"]).split()[-1]))
    return used


def bin_of(k):
    if k == 1:
        return "1"
    if k == 2:
        return "2"
    if k == 3:
        return "3"
    if k >= 4:
        return "4 or more"
    return None


def rederive(item):
    idx = int(str(item["provenance"]["source_id"]).split()[-1])
    k = item_count(parse_gt(load_rows()[idx]))
    got = bin_of(k)
    if got is None:
        raise ValueError(f"row {idx} has {k} lines")
    return got


def build():
    used = used_in_t02()
    buckets = defaultdict(list)
    rows = load_rows()
    for i, row in enumerate(rows):
        if i in used:
            continue
        label = bin_of(item_count(parse_gt(row)))
        if label:
            buckets[label].append(i)
    rng = random.Random(SEED)
    need = {"1": 7, "2": 6, "3": 6, "4 or more": 6}
    chosen = []
    for label, n in need.items():
        rng.shuffle(buckets[label])
        if len(buckets[label]) < n:
            raise SystemExit(f"{label} has {len(buckets[label])}, need {n}")
        chosen.extend((label, i) for i in buckets[label][:n])
    rng.shuffle(chosen)
    out = []
    for n, (label, i) in enumerate(chosen):
        im = Image.open(io.BytesIO(rows[i]["image"]["bytes"]))
        rel = save_image(im, TASK, n)
        question, labels, expected = make_choice(
            "How many different line items are on this receipt?", OPTIONS, label, f"{TASK}-{n}"
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
                "len(gt_parse.menu), binned",
                notes=f"len(gt_parse.menu) -> {label}",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print(f"wrote {len(build())}")
