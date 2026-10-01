"""ChartQA test split. The answer is the dataset label when it is one number."""
import hashlib
import io
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

SEED = 7
TASK = "t07_chart_reading"
SRC = Path("/workspace/data/sources/image-lab/chartqa/data/test-00000-of-00001-e2cd0b7a0f9eb20d.parquet")
URL = "https://huggingface.co/datasets/HuggingFaceM4/ChartQA"
NUM = re.compile(r"^-?\d+(\.\d+)?$|^-?\d{1,3}(,\d{3})+(\.\d+)?$")
_ROWS = None

def table():
    global _ROWS
    if _ROWS is None:
        _ROWS = pq.read_table(SRC).to_pylist()
        for i, row in enumerate(_ROWS):
            raw = row["image"]["bytes"]
            row["_i"] = i
            row["_hash"] = hashlib.sha256(raw).hexdigest()
            labs = row.get("label") or []
            row["_num"] = labs[0].strip() if len(labs) == 1 and NUM.fullmatch((labs[0] or "").strip()) else None
    return _ROWS

def groups():
    out = {}
    for row in table():
        out.setdefault(row["_hash"], []).append(row)
    return out

def options_for(row, siblings, seed):
    correct = row["_num"]
    pool = []
    for other in siblings:
        if other["_num"] and other["_num"] != correct and other["_num"] not in pool:
            pool.append(other["_num"])
    rng = random.Random(seed)
    rng.shuffle(pool)
    picked = pool[:3]
    if len(picked) < 3:
        for decoy in decoy_numbers(correct, 6, seed):
            if decoy != correct and decoy not in picked:
                picked.append(decoy)
            if len(picked) == 3:
                break
    if len(picked) < 3 or correct in picked:
        return None
    return picked + [correct]

def select():
    rng = random.Random(SEED)
    chosen = []
    for digest, rows in groups().items():
        numeric = [r for r in rows if r["_num"]]
        if not numeric:
            continue
        rng.shuffle(numeric)
        row = numeric[0]
        opts = options_for(row, rows, SEED + row["_i"])
        if opts is None:
            continue
        chosen.append((row, opts))
    rng.shuffle(chosen)
    if len(chosen) < 25:
        raise RuntimeError(f"only {len(chosen)} usable charts")
    return chosen[:25]

def rederive(item):
    digest, idx = item["provenance"]["source_id"].split(":", 1)
    idx = int(idx)
    row = table()[idx]
    if row["_hash"] != digest:
        return None
    return row["_num"]

def build():
    chosen = select()
    out = []
    for n, (row, opts) in enumerate(chosen):
        question, labels, expected = make_choice(row["query"], opts, row["_num"], SEED + row["_i"])
        im = Image.open(io.BytesIO(row["image"]["bytes"]))
        rel = save_image(im, TASK, n)
        who = "human" if row["human_or_machine"] == 0 else "machine"
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
                "HuggingFaceM4/ChartQA, test split",
                f"{row['_hash']}:{row['_i']}",
                URL,
                "GPL-3.0, local use only",
                "label",
                notes=f"label; human_or_machine={who}",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out

if __name__ == "__main__":
    print("wrote", len(build()))
