"""Indoor scene test split. Four rooms. There is no exterior class in this set."""
import random
import sys
import zipfile
from collections import defaultdict
from io import BytesIO
from pathlib import Path

from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_choice, provenance, save_image

TASK = "t25_room_type"
ZIP = Path("/workspace/data/sources/image-lab/indoor-scene/data/test.zip")
URL = "https://huggingface.co/datasets/keremberke/indoor-scene-classification"
SEED = 25
# The test zip has kitchen and livingroom, and not bathroom or bedroom.
# dining_room and pantry are the other two room folders with enough photos.
ROOMS = {"kitchen": "kitchen", "livingroom": "living room", "dining_room": "dining room", "pantry": "pantry"}
NEED = {"kitchen": 7, "livingroom": 6, "dining_room": 6, "pantry": 6}


def members():
    buckets = defaultdict(list)
    with zipfile.ZipFile(ZIP) as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            parts = Path(name).parts
            if len(parts) < 2:
                continue
            folder = parts[-2]
            if folder in ROOMS and name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                buckets[folder].append(name)
    return buckets


def rederive(item):
    folder = item["provenance"]["source_id"].split("/", 1)[0]
    if folder not in ROOMS:
        raise ValueError(f"unknown folder {folder}")
    return ROOMS[folder]


def build():
    if not ZIP.is_file():
        raise SystemExit(f"missing {ZIP}")
    buckets = members()
    rng = random.Random(SEED)
    chosen = []
    for folder, n in NEED.items():
        names = buckets[folder]
        rng.shuffle(names)
        if len(names) < n:
            raise SystemExit(f"{folder} has {len(names)} in the test zip, need {n}. counts={ {k: len(v) for k, v in buckets.items()} }")
        chosen.extend((folder, name) for name in names[:n])
    rng.shuffle(chosen)
    options = list(dict.fromkeys(ROOMS.values()))
    out = []
    with zipfile.ZipFile(ZIP) as zf:
        for i, (folder, name) in enumerate(chosen):
            im = Image.open(BytesIO(zf.read(name)))
            rel = save_image(im, TASK, i)
            answer = ROOMS[folder]
            question, labels, expected = make_choice(
                "What kind of room is this?", options, answer, f"{TASK}-{i}"
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
                    "MIT Indoor scenes, keremberke/indoor-scene-classification test",
                    f"{folder}/{Path(name).name}",
                    URL,
                    "export README says MIT; original indoor-scene terms apply, local use",
                    "folder name",
                    notes=folder,
                ),
            })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print(f"wrote {len(build())}")
