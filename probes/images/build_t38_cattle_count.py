"""UAV cattle photos. The count is the number of labelled rectangles."""
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

from huggingface_hub import hf_hub_download
from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_choice, provenance, save_image

TASK = "t38_cattle_count"
REPO = "Arvin26/cattle-detection"
SRC = Path("/workspace/data/sources/image-lab/cattle")
LABELS = SRC / "images and labels"
URL = "https://huggingface.co/datasets/Arvin26/cattle-detection"
SEED = 38
OPTIONS = ["1", "2-4", "5-12", "13 or more"]
NEED = {"1": 7, "2-4": 6, "5-12": 6, "13 or more": 6}
STEM = re.compile(r"^\d{8}_\d+m_\d+$")


def count_boxes(path):
    data = json.loads(Path(path).read_text())
    return sum(1 for shape in data.get("shapes") or [] if shape.get("shape_type") == "rectangle"), data


def bin_of(count):
    if count == 1:
        return "1"
    if 2 <= count <= 4:
        return "2-4"
    if 5 <= count <= 12:
        return "5-12"
    if count >= 13:
        return "13 or more"
    return None


def rederive(item):
    stem = item["provenance"]["source_id"]
    count, _ = count_boxes(LABELS / f"{stem}.json")
    return bin_of(count)


def select():
    rng = random.Random(SEED)
    buckets = defaultdict(list)
    for path in LABELS.glob("*.json"):
        if not STEM.fullmatch(path.stem):
            continue
        count, data = count_boxes(path)
        grade = bin_of(count)
        if grade is None:
            continue
        image_name = data.get("imagePath") or f"{path.stem}.JPG"
        parts = path.stem.split("_")
        group = "_".join(parts[:2]) if len(parts) >= 2 else path.stem
        frame = int(parts[-1]) if parts[-1].isdigit() else 0
        buckets[grade].append((group, frame, path.stem, image_name, count))
    chosen = []
    for grade in OPTIONS:
        pool = buckets[grade]
        rng.shuffle(pool)
        by_group = defaultdict(list)
        for item in pool:
            by_group[item[0]].append(item)
        groups = list(by_group)
        rng.shuffle(groups)
        picked = []
        frames = defaultdict(list)

        def consider(item, spaced):
            group, frame = item[0], item[1]
            if spaced and any(abs(frame - old) <= 8 for old in frames[group]):
                return False
            picked.append(item)
            frames[group].append(frame)
            return True

        while len(picked) < NEED[grade]:
            grew = False
            for group in groups:
                if len(picked) >= NEED[grade]:
                    break
                while by_group[group]:
                    item = by_group[group].pop(0)
                    if consider(item, True):
                        grew = True
                        break
            if not grew:
                break
        if len(picked) < NEED[grade]:
            rest = [item for group in groups for item in by_group[group]]
            rng.shuffle(rest)
            for item in rest:
                if len(picked) >= NEED[grade]:
                    break
                consider(item, False)
        if len(picked) < NEED[grade]:
            raise SystemExit(f"{grade} has {len(picked)}, need {NEED[grade]}")
        chosen.extend((grade, item) for item in picked)
    rng.shuffle(chosen)
    return chosen


def build():
    out = []
    for i, (grade, item) in enumerate(select()):
        _, _, stem, image_name, count = item
        local = Path(hf_hub_download(
            REPO, f"images and labels/{image_name}", repo_type="dataset", local_dir=SRC
        ))
        question, labels, expected = make_choice(
            "How many cattle are in this photo?", OPTIONS, grade, f"{TASK}-{i}"
        )
        rel = save_image(Image.open(local), TASK, i)
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
                "UAV cattle photos, Arvin26/cattle-detection",
                stem,
                URL,
                "not stated, local use only",
                "count of rectangle boxes in the LabelMe JSON",
                notes=f"cattle {count}",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print(f"wrote {len(build())}")
