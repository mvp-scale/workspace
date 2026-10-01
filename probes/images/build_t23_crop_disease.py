"""Plant-leaf photos. The answer is the ClassLabel name on the row."""
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

SEED = 23
TASK = "t23_crop_disease"
SRC = Path("/workspace/data/sources/image-lab/plant-leaf/data/train-00000-of-00002.parquet")
URL = "https://huggingface.co/datasets/Project-AgML/plant_leaf_disease_classification"
NAMES = [
    "Anthracnose", "Anthracnose lesions", "Black Rot", "Downey mildew", "Downy mildew",
    "Eggplant Cercopora leaf spot", "Eggplant begomovirus", "Eggplant fresh leaf",
    "Eggplant verticillium wilt", "Fresh leaf", "Fusarium wilt", "Mosaic virus",
    "Tomato Bacterial spot", "Tomato Fresh leaf", "Tomato leaf curl virus", "Tomato spotted wilt",
]
FOUR = ["Fresh leaf", "Black Rot", "Anthracnose", "Mosaic virus"]
QUESTION = "What condition does this leaf show?"
_ROWS = None

def table():
    global _ROWS
    if _ROWS is None:
        _ROWS = pq.read_table(SRC).to_pylist()
    return _ROWS

def select():
    rng = random.Random(SEED)
    pools = {name: [] for name in FOUR}
    for i, row in enumerate(table()):
        name = NAMES[row["label"]]
        if name in pools:
            pools[name].append(i)
    order = FOUR[:]
    rng.shuffle(order)
    chosen = []
    for rank, name in enumerate(order):
        need = 7 if rank == 0 else 6
        rng.shuffle(pools[name])
        if len(pools[name]) < need:
            raise RuntimeError(f"{name} has {len(pools[name])}")
        chosen.extend((i, name) for i in pools[name][:need])
    return chosen

def rederive(item):
    idx = int(str(item["provenance"]["source_id"]).split()[-1])
    return NAMES[table()[idx]["label"]]

def build():
    out = []
    for n, (i, name) in enumerate(select()):
        row = table()[i]
        question, labels, expected = make_choice(QUESTION, FOUR, name, SEED + i)
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
                "Project-AgML/plant_leaf_disease_classification, shard data/train-00000-of-00002.parquet",
                f"row {i}",
                URL,
                "CC-BY-4.0",
                "label class name",
                notes="label class name",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out

if __name__ == "__main__":
    print("wrote", len(build()))
