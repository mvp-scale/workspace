"""NEU steel surfaces already on disk. The class name in label_str is the answer."""
import io
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

TASK = "t21_surface_defect"
SRC = Path("/workspace/data/sources/image-lab/neudet-peek/data/train-00000-of-00001.parquet")
URL = "https://huggingface.co/datasets/newguyme/neu_det_caption"
CLASSES = ["crazing", "inclusion", "patches", "scratches"]
SEED = 21


def table_rows():
    table = pq.read_table(SRC, columns=["filename", "label_str", "image"])
    return table.to_pylist()


_INDEX = None


def index():
    global _INDEX
    if _INDEX is None:
        _INDEX = {row["filename"]: row["label_str"] for row in pq.read_table(SRC, columns=["filename", "label_str"]).to_pylist()}
    return _INDEX


def rederive(item):
    name = item["provenance"]["source_id"]
    return index().get(name)


def build():
    buckets = defaultdict(list)
    for row in table_rows():
        name = row["label_str"]
        if name in CLASSES and row["image"] and row["image"].get("bytes"):
            buckets[name].append(row)
    rng = random.Random(SEED)
    for name in CLASSES:
        rng.shuffle(buckets[name])
    need = [7, 6, 6, 6]
    chosen = []
    for name, n in zip(CLASSES, need):
        if len(buckets[name]) < n:
            raise SystemExit(f"{name} has {len(buckets[name])}, need {n}")
        chosen.extend(buckets[name][:n])
    rng.shuffle(chosen)
    out = []
    for i, row in enumerate(chosen):
        im = Image.open(io.BytesIO(row["image"]["bytes"]))
        rel = save_image(im, TASK, i)
        question, labels, expected = make_choice(
            "Which defect is on this steel surface?", CLASSES, row["label_str"], f"{TASK}-{i}"
        )
        out.append({
            "id": f"{TASK}-{i:03d}",
            "family": TASK,
            "state": "An image is attached.",
            "images": [rel],
            "question": question,
            "labels": labels,
            "expected": expected,
            "split": "public",
            "group": None,
            "provenance": provenance(
                "NEU surface defect, newguyme/neu_det_caption",
                row["filename"],
                URL,
                "not stated, local use only",
                "label_str",
                notes=row["label_str"],
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print(f"wrote {len(build())}")
