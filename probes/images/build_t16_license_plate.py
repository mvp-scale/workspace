"""Persian plate crops. The label column is the plate text, written by the dataset authors."""
import io
import random
import sys
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_choice, provenance, save_image

TASK = "t16_license_plate"
SRC = Path("/workspace/data/sources/image-lab/persian-plates/data/test-00000-of-00001.parquet")
URL = "https://huggingface.co/datasets/hezarai/persian-license-plate-v1"
SEED = 16
MIN_W, MIN_H = 200, 40
_ROWS = None


def rows():
    global _ROWS
    if _ROWS is None:
        table = pq.read_table(SRC, columns=["image_path", "label"])
        _ROWS = []
        for image, label in zip(table.column("image_path").to_pylist(), table.column("label").to_pylist()):
            text = str(label or "").strip()
            path = (image or {}).get("path") or ""
            blob = (image or {}).get("bytes")
            if not text or not path or not blob:
                continue
            _ROWS.append({"path": path, "label": text, "bytes": blob})
    return _ROWS


def index():
    return {row["path"]: row["label"] for row in rows()}


def rederive(item):
    name = item["provenance"]["source_id"]
    found = index()
    if name not in found:
        raise ValueError(f"missing {name}")
    return found[name]


def eligible():
    picked = []
    seen = set()
    for row in rows():
        if row["label"] in seen:
            continue
        im = Image.open(io.BytesIO(row["bytes"]))
        w, h = im.size
        if w < MIN_W or h < MIN_H:
            continue
        seen.add(row["label"])
        picked.append(row)
    return picked


def build():
    if not SRC.is_file():
        raise SystemExit(f"missing {SRC}")
    pool = eligible()
    rng = random.Random(SEED)
    rng.shuffle(pool)
    if len(pool) < 25:
        raise SystemExit(f"only {len(pool)} readable unique plates")
    chosen = pool[:25]
    texts = [row["label"] for row in chosen]
    out = []
    for i, row in enumerate(chosen):
        others = [text for text in texts if text != row["label"]]
        decoys = rng.sample(others, 3)
        im = Image.open(io.BytesIO(row["bytes"]))
        rel = save_image(im, TASK, i)
        question, labels, expected = make_choice(
            "What is the plate number?", [row["label"], *decoys], row["label"], f"{TASK}-{i}"
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
                "Persian license plates, hezarai/persian-license-plate-v1 test split",
                row["path"],
                URL,
                "not stated, local use only",
                "label",
                notes="author label",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print(f"wrote {len(build())}")
