"""Single-class CarDD photos. The one damage label in samples.json is the answer."""
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_choice, provenance, save_image

TASK = "t10_damaged_part"
ROOT = Path("/workspace/data/sources/image-lab/cardd")
SAMPLES = ROOT / "samples.json"
REPO = "harpreetsahota/CarDD"
URL = "https://huggingface.co/datasets/harpreetsahota/CarDD"
CLASSES = ["dent", "glass shatter", "scratch", "tire flat"]
NEED = [6, 6, 7, 6]
SEED = 10


def load_samples():
    data = json.loads(SAMPLES.read_text())
    return data["samples"]


_INDEX = None


def index():
    global _INDEX
    if _INDEX is None:
        _INDEX = {row["filepath"]: row for row in load_samples()}
    return _INDEX


def class_of(row):
    labels = {d["label"] for d in row["detections"]["detections"]}
    if len(labels) != 1:
        return None
    name = next(iter(labels))
    if name not in CLASSES:
        return None
    return name


def rederive(item):
    row = index().get(item["provenance"]["source_id"])
    if row is None:
        raise ValueError(item["provenance"]["source_id"])
    return class_of(row)


def fetch(rel):
    dest = ROOT / rel
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    from huggingface_hub import hf_hub_download

    hf_hub_download(repo_id=REPO, filename=rel, repo_type="dataset", local_dir=str(ROOT))
    if not dest.is_file():
        raise FileNotFoundError(rel)
    return dest


def select():
    buckets = defaultdict(list)
    for row in load_samples():
        name = class_of(row)
        if name is not None:
            buckets[name].append(row["filepath"])
    rng = random.Random(SEED)
    chosen = []
    for name, n in zip(CLASSES, NEED):
        pool = buckets[name]
        rng.shuffle(pool)
        if len(pool) < n:
            raise SystemExit(f"{name} has {len(pool)} single-class images, need {n}")
        chosen.extend(pool[:n])
    rng.shuffle(chosen)
    return chosen


def build():
    out = []
    for i, rel_img in enumerate(select()):
        im = Image.open(fetch(rel_img))
        rel = save_image(im, TASK, i)
        answer = class_of(index()[rel_img])
        question, labels, expected = make_choice(
            "Which damage type is visible in this photo?",
            CLASSES,
            answer,
            f"{TASK}-{i}",
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
                REPO,
                rel_img,
                URL,
                "Flickr and Shutterstock terms, non-commercial research and education. Local use.",
                "single detections label",
                notes=answer,
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print(f"wrote {len(build())}")
