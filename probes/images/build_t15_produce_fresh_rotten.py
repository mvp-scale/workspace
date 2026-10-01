"""Fresh vs rotten fruit. Class names are fresh (0) and rotten (1) in the parquet schema."""
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

SEED = 15
TASK = "t15_produce_fresh_rotten"
ROOT = Path("/workspace/data/sources/image-lab/fresh-rotten/raw")
FRESH = "train-00000-of-00004.parquet"
ROTTEN = "train-00002-of-00004.parquet"
URL = "https://huggingface.co/datasets/Project-AgML/fresh_rotten_fruit_classification"
NAMES = ["fresh", "rotten"]
_CACHE = {}

def load(name):
    if name not in _CACHE:
        _CACHE[name] = pq.read_table(ROOT / name).to_pylist()
    return _CACHE[name]

def is_rotten(label):
    return "rotten" in NAMES[label]

def select_shard(name, need):
    rng = random.Random(f"{SEED}-{name}")
    pools = {}
    for i, row in enumerate(load(name)):
        pools.setdefault(row["fruit_type"], []).append(i)
    types = sorted(pools)
    rng.shuffle(types)
    chosen = []
    # Spread across fruit types. The extra images, if need is not a multiple, go to the first types.
    base, extra = divmod(need, len(types))
    for rank, fruit in enumerate(types):
        rng.shuffle(pools[fruit])
        take = base + (1 if rank < extra else 0)
        if len(pools[fruit]) < take:
            raise RuntimeError(f"{name} {fruit} has {len(pools[fruit])}")
        chosen.extend((name, i) for i in pools[fruit][:take])
    return chosen

def select():
    # 13 rotten, 12 fresh.
    return select_shard(ROTTEN, 13) + select_shard(FRESH, 12)

def rederive(item):
    shard, idx = item["provenance"]["source_id"].split(" row ")
    row = load(shard)[int(idx)]
    return "yes" if is_rotten(row["label"]) else "no"

def build():
    out = []
    for n, (shard, i) in enumerate(select()):
        row = load(shard)[i]
        rotten = is_rotten(row["label"])
        question, labels, expected = make_yesno(
            "Is this fruit rotten?",
            "The fruit is rotten",
            "The fruit is fresh",
            rotten,
        )
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
                "Project-AgML/fresh_rotten_fruit_classification, raw config",
                f"{shard} row {i}",
                URL,
                "CC-BY-4.0",
                "label class name",
                notes=f"label class name; fruit_type={row['fruit_type']}",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out

if __name__ == "__main__":
    print("wrote", len(build()))
