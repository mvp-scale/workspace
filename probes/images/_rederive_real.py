"""Recompute an expected answer from the label file saved next to the download."""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

SRC = Path("/workspace/data/sources/image-lab")


def _yolo(path):
    counts = Counter()
    text = path.read_text() if path.is_file() and path.stat().st_size else ""
    for line in text.splitlines():
        parts = line.split()
        if parts and parts[0].isdigit():
            counts[int(parts[0])] += 1
    return counts


def parking(item):
    stem = item["provenance"]["source_id"]
    free = _yolo(SRC / "pklot" / "data" / "labels" / "valid" / f"{stem}.txt")[0]
    if free <= 10:
        return "0-10"
    if free <= 30:
        return "11-30"
    if free <= 60:
        return "31-60"
    return "61 or more"


def herd(item):
    stem = Path(item["provenance"]["source_id"]).stem
    total = sum(_yolo(SRC / "sheep-goats" / "train" / "labels" / f"{stem}.txt").values())
    if total == 0:
        return "0"
    if total <= 5:
        return "1-5"
    if total <= 15:
        return "6-15"
    return "16 or more"


def pigs(item):
    image_id = item["provenance"]["source_id"]
    standing = 0
    with (SRC / "pigs" / "viewpoint_aware_pig_posture_recognition" / "train.csv").open(newline="") as f:
        for row in csv.DictReader(f):
            if row["image_id"] == image_id and int(row["class_id"]) == 3:
                standing += 1
    if standing >= 3:
        return "3 or more"
    return str(standing)


def doors(item):
    stem = item["provenance"]["source_id"]
    n = _yolo(SRC / "cubicasa" / "labels" / "val" / f"{stem}.txt")[1]
    if n <= 3:
        return "0-3"
    if n <= 6:
        return "4-6"
    if n <= 9:
        return "7-9"
    return "10 or more"


def damage(item):
    image_id = item["provenance"]["source_id"]
    rows = json.loads((SRC / "crisismmd" / "damage" / "test.json").read_text())
    show = {
        "little_or_no_damage": "little or no damage",
        "mild_damage": "mild damage",
        "severe_damage": "severe damage",
    }
    for row in rows:
        if row["image_id"] == image_id:
            return show[row["label"]]
    raise KeyError(image_id)
