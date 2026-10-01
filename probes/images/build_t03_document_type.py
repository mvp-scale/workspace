"""RVL-CDIP images from the small hf-tuner copy. The class name is the label id."""
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

SEED = 3
TASK = "t03_document_type"
SRC = Path("/workspace/data/sources/image-lab/rvl-cdip/data/test-00000-of-00001.parquet")
URL = "https://huggingface.co/datasets/hf-tuner/rvl-cdip-document-classification"
NAMES = [
    "letter", "form", "email", "handwritten", "advertisement", "scientific report",
    "scientific publication", "specification", "file folder", "news article", "budget",
    "invoice", "presentation", "questionnaire", "resume", "memo",
]
QUESTION = "What type of document is this?"
_ROWS = None

def table():
    global _ROWS
    if _ROWS is None:
        _ROWS = pq.read_table(SRC).to_pylist()
    return _ROWS

def select():
    rng = random.Random(SEED)
    pools = {i: [] for i in range(len(NAMES))}
    for i, row in enumerate(table()):
        pools[row["label"]].append(i)
    # Eight classes, three images each, plus one extra class with one image: 25.
    order = list(range(len(NAMES)))
    rng.shuffle(order)
    used = order[:9]
    chosen = []
    for rank, lab in enumerate(used):
        need = 3 if rank < 8 else 1
        rng.shuffle(pools[lab])
        chosen.extend((i, lab) for i in pools[lab][:need])
    return chosen

def options_for(lab, seed):
    rng = random.Random(seed)
    others = [n for i, n in enumerate(NAMES) if i != lab]
    rng.shuffle(others)
    return others[:3] + [NAMES[lab]]

def rederive(item):
    idx = int(str(item["provenance"]["source_id"]).split()[-1])
    return NAMES[table()[idx]["label"]]

def build():
    out = []
    for n, (i, lab) in enumerate(select()):
        row = table()[i]
        name = NAMES[lab]
        question, labels, expected = make_choice(QUESTION, options_for(lab, SEED + i), name, SEED + i)
        im = Image.open(io.BytesIO(row["image"]["bytes"]))
        rel = save_image(im, TASK, n)
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
                "hf-tuner/rvl-cdip-document-classification, test split",
                f"row {i}",
                URL,
                "not stated, local use only",
                "label class name",
                notes="label class name",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out

if __name__ == "__main__":
    print("wrote", len(build()))
