"""Kerala road photos. The folder name is the pothole severity."""
import random
import sys
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download
from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_choice, provenance, save_image

TASK = "t37_road_damage"
REPO = "Arpitraj01/Pothole_classification"
SRC = Path("/workspace/data/sources/image-lab/pothole")
URL = "https://huggingface.co/datasets/Arpitraj01/Pothole_classification"
SEED = 37
OPTIONS = ["none", "low", "medium", "severe"]
NEED = {"none": 7, "low": 6, "medium": 6, "severe": 6}
SPLIT_RANK = {"test": 0, "val": 1, "train": 2}


def rederive(item):
    return Path(item["provenance"]["source_id"]).parent.name


def listed():
    files = HfApi().list_repo_files(REPO, repo_type="dataset")
    buckets = {name: {} for name in OPTIONS}
    for path in files:
        parts = Path(path).parts
        if len(parts) != 4 or parts[0] != "datasets":
            continue
        split, grade, filename = parts[1], parts[2], parts[3]
        if grade not in OPTIONS or split not in SPLIT_RANK:
            continue
        if Path(filename).suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        key = filename.lower()
        current = buckets[grade].get(key)
        if current is None or SPLIT_RANK[split] < SPLIT_RANK[current[0]]:
            buckets[grade][key] = (split, path)
    return buckets


def select():
    rng = random.Random(SEED)
    buckets = listed()
    chosen = []
    for grade in OPTIONS:
        pool = list(buckets[grade].values())
        rng.shuffle(pool)
        if len(pool) < NEED[grade]:
            raise SystemExit(f"{grade} has {len(pool)}, need {NEED[grade]}")
        chosen.extend((grade, path) for _, path in pool[:NEED[grade]])
    rng.shuffle(chosen)
    return chosen


def build():
    out = []
    for i, (grade, path) in enumerate(select()):
        local = Path(hf_hub_download(REPO, path, repo_type="dataset", local_dir=SRC))
        question, labels, expected = make_choice(
            "How severe is the pothole in this road photo?", OPTIONS, grade, f"{TASK}-{i}"
        )
        rel = save_image(Image.open(local), TASK, i)
        source_id = "/".join(Path(path).parts[1:])
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
                "Road photos from Kerala, Arpitraj01/Pothole_classification",
                source_id,
                URL,
                "MIT",
                "folder name",
                notes=grade,
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print(f"wrote {len(build())}")
