"""One D-Fire test shard. A non-empty label string is a boxed fire or smoke region. An empty string is neither."""
import io
import random
import sys
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_yesno, provenance, save_image

TASK = "t19_fire_smoke"
SRC = Path("/workspace/data/sources/image-lab/dfire/data/test-00000-of-00003.parquet")
URL = "https://huggingface.co/datasets/badsaarow/d-fire"
SEED = 19


def rows():
    return pq.read_table(SRC, columns=["filename", "label", "image"]).to_pylist()


def has_region(label):
    return bool(str(label or "").strip())


_LABELS = None


def labels():
    global _LABELS
    if _LABELS is None:
        _LABELS = {row["filename"]: row["label"] for row in pq.read_table(SRC, columns=["filename", "label"]).to_pylist()}
    return _LABELS


def rederive(item):
    name = item["provenance"]["source_id"]
    if name not in labels():
        raise ValueError(f"missing {name}")
    return "yes" if has_region(labels()[name]) else "no"


def build():
    if not SRC.is_file():
        raise SystemExit(f"missing {SRC}")
    yes, no = [], []
    for row in rows():
        if not row["image"] or not row["image"].get("bytes"):
            continue
        (yes if has_region(row["label"]) else no).append(row)
    rng = random.Random(SEED)
    rng.shuffle(yes)
    rng.shuffle(no)
    # 13 yes, 12 no. Stop if this shard cannot fill both.
    if len(yes) < 13 or len(no) < 12:
        raise SystemExit(f"shard has {len(yes)} with a box and {len(no)} empty; need 13 and 12")
    chosen = [(True, row) for row in yes[:13]] + [(False, row) for row in no[:12]]
    rng.shuffle(chosen)
    out = []
    for i, (flag, row) in enumerate(chosen):
        im = Image.open(io.BytesIO(row["image"]["bytes"]))
        rel = save_image(im, TASK, i)
        question, labels, expected = make_yesno(
            "Is there fire or smoke in this frame?",
            "A boxed region is marked fire or smoke.",
            "The label file has no box.",
            flag,
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
                "D-Fire test shard 0, badsaarow/d-fire",
                row["filename"],
                URL,
                "not stated, local use only",
                "label string empty or not",
                notes="non-empty YOLO label vs empty string",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print(f"wrote {len(build())}")
