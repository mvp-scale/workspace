"""Grocery shelf photos. annotation.txt counts the products; the answer is a bin of that count."""
import random
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_choice, provenance, save_image

TASK = "t13_shelf_out_of_stock"
ROOT = Path("/workspace/data/sources/image-lab/grocery-shelves")
ANN = ROOT / "annotation.txt"
IMG = ROOT / "ShelfImages"
URL = "https://github.com/gulvarol/grocerydataset"
BINS = [("10-24", 10, 24), ("25-35", 25, 35), ("36-46", 36, 46), ("47-80", 47, 80)]
NEED = [7, 6, 6, 6]
SEED = 13
_COUNTS = None


def bin_of(count):
    for name, low, high in BINS:
        if low <= count <= high:
            return name
    return None


def counts():
    global _COUNTS
    if _COUNTS is None:
        found = {}
        for line in ANN.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            name, count, rest = parts[0], int(parts[1]), parts[2:]
            if len(rest) % 5 != 0 or len(rest) // 5 != count:
                raise ValueError(f"{name}: count {count} does not match {len(rest) // 5} boxes")
            found[name] = count
        _COUNTS = found
    return _COUNTS


def rederive(item):
    name = item["provenance"]["source_id"]
    count = counts().get(name)
    if count is None:
        raise ValueError(f"missing {name}")
    return bin_of(count)


def build():
    buckets = defaultdict(list)
    for name, count in counts().items():
        label = bin_of(count)
        if label and (IMG / name).is_file():
            buckets[label].append(name)
    rng = random.Random(SEED)
    chosen = []
    for (label, _low, _high), n in zip(BINS, NEED):
        rng.shuffle(buckets[label])
        if len(buckets[label]) < n:
            raise SystemExit(f"{label} has {len(buckets[label])}, need {n}")
        chosen.extend((label, name) for name in buckets[label][:n])
    rng.shuffle(chosen)
    options = [name for name, _low, _high in BINS]
    out = []
    for i, (label, name) in enumerate(chosen):
        im = Image.open(IMG / name)
        rel = save_image(im, TASK, i)
        question, labels, expected = make_choice(
            "How many products are on this shelf?", options, label, f"{TASK}-{i}"
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
                "Grocery Dataset shelf images, gulvarol/grocerydataset",
                name,
                URL,
                "research only, not for commercial use",
                "annotation.txt product count",
                notes=str(counts()[name]),
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print(f"wrote {len(build())}")
