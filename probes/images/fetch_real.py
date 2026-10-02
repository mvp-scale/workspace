"""Pull 25 real, already-labelled images for each function above the line.

Sources stay under data/sources/image-lab/<name>/. Resized copies go to
data/image-lab/images/<task>/. Does not download a whole multi-GB repo.
"""
import io
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download
from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_choice, provenance, save_image

API = HfApi()
SRC = Path("/workspace/data/sources/image-lab")
HERE = Path("/workspace/probes/images")
N = 25


def names(repo, path):
    return [x.path for x in API.list_repo_tree(repo, path_in_repo=path, repo_type="dataset", recursive=False)]


def grab(repo, path, dest):
    dest.mkdir(parents=True, exist_ok=True)
    return Path(hf_hub_download(repo, path, repo_type="dataset", local_dir=dest))


def yolo_counts(text):
    counts = Counter()
    for line in text.splitlines():
        parts = line.split()
        if parts and parts[0].isdigit():
            counts[int(parts[0])] += 1
    return counts


def pick_bins(buckets, seed, order):
    rng = random.Random(seed)
    for key in buckets:
        rng.shuffle(buckets[key])
    base, extra = divmod(N, len(order))
    chosen = []
    for i, key in enumerate(order):
        need = base + (1 if i < extra else 0)
        have = buckets.get(key) or []
        if len(have) < need:
            raise SystemExit(f"{seed}: bin {key} has {len(have)}, need {need}")
        chosen.extend((key, item) for item in have[:need])
    rng.shuffle(chosen)
    return chosen


def record(task, index, rel, question, options, expected, source, source_id, url, license, origin, notes):
    q, opts, _ = make_choice(question, options, expected, seed=f"{task}-{index}")
    return {
        "id": f"{task}-{index:03d}",
        "family": task,
        "state": "An image is attached.",
        "images": [rel],
        "question": q,
        "labels": opts,
        "expected": expected,
        "split": "public",
        "group": None,
        "provenance": provenance(source, source_id, url, license, origin, notes),
    }


def parking():
    repo = "dronefreak/PKLot"
    task = "t26_parking_free"
    root = SRC / "pklot"
    label_paths = names(repo, "data/labels/valid")
    rng = random.Random(26)
    sample = rng.sample(label_paths, 400)
    bins = {"0-10": [], "11-30": [], "31-60": [], "61 or more": []}
    for path in sample:
        local = grab(repo, path, root)
        text = local.read_text()
        free = yolo_counts(text)[0]
        if free <= 10:
            key = "0-10"
        elif free <= 30:
            key = "11-30"
        elif free <= 60:
            key = "31-60"
        else:
            key = "61 or more"
        bins[key].append((path, free))
    order = ["0-10", "11-30", "31-60", "61 or more"]
    rows = []
    for i, (key, (path, free)) in enumerate(pick_bins(bins, 26, order)):
        stem = Path(path).stem
        img = grab(repo, f"data/images/valid/{stem}.jpg", root)
        rel = save_image(Image.open(img), task, i)
        rows.append(record(
            task, i, rel,
            "How many labelled parking spaces in this frame are free?",
            order, key,
            "PKLot (UFPR), valid split, via dronefreak/PKLot",
            stem, "https://huggingface.co/datasets/dronefreak/PKLot",
            "CC-BY-4.0", "human box, class vacant",
            f"free spaces {free}; vacant is class 0 in data.yaml",
        ))
    write(HERE / f"{task}.jsonl", rows)
    print(task, Counter(r["expected"] for r in rows))


def herd():
    repo = "AGRARIAN/greek_sheep_goats_dataset"
    task = "t27_herd_count"
    root = SRC / "sheep-goats"
    frames = defaultdict(list)
    for path in names(repo, "train/images"):
        stem = Path(path).stem
        frame, _patch = stem.rsplit("_", 1)
        frames[frame].append(path)
    rng = random.Random(27)
    frame_ids = list(frames)
    rng.shuffle(frame_ids)
    bins = {"0": [], "1-5": [], "6-15": [], "16 or more": []}
    order = list(bins)
    for frame in frame_ids:
        path = sorted(frames[frame])[0]
        label = "train/labels/" + Path(path).stem + ".txt"
        local = grab(repo, label, root)
        text = local.read_text() if local.stat().st_size else ""
        total = sum(yolo_counts(text).values())
        key = "0" if total == 0 else "1-5" if total <= 5 else "6-15" if total <= 15 else "16 or more"
        bins[key].append((path, total))
        if all(len(bins[k]) >= 8 for k in order):
            break
    rows = []
    for i, (key, (path, total)) in enumerate(pick_bins(bins, 27, order)):
        img = grab(repo, path, root)
        rel = save_image(Image.open(img), task, i)
        rows.append(record(
            task, i, rel,
            "How many sheep and goats are in this drone frame?",
            order, key,
            "AGRARIAN greek sheep and goats, train frames",
            Path(path).name, "https://huggingface.co/datasets/AGRARIAN/greek_sheep_goats_dataset",
            "Apache-2.0", "human box",
            f"animals {total}; one patch of frame {Path(path).stem.rsplit('_', 1)[0]}",
        ))
    write(HERE / f"{task}.jsonl", rows)
    print(task, Counter(r["expected"] for r in rows))


def pigs():
    import csv
    repo = "anilbhujel/viewpoint-aware-pig-posture-recognition"
    task = "t28_pigs_standing"
    root = SRC / "pigs"
    csv_path = grab(repo, "viewpoint_aware_pig_posture_recognition/train.csv", root)
    groups = defaultdict(list)
    with csv_path.open(newline="") as f:
        for row in csv.DictReader(f):
            groups[row["image_id"]].append(int(row["class_id"]))
    bins = {"0": [], "1": [], "2": [], "3 or more": []}
    for image_id, classes in groups.items():
        standing = sum(1 for c in classes if c == 3)
        key = "3 or more" if standing >= 3 else str(standing)
        bins[key].append((image_id, standing))
    order = ["0", "1", "2", "3 or more"]
    print("pig bin pools", {k: len(v) for k, v in bins.items()})
    rows = []
    for i, (key, (image_id, standing)) in enumerate(pick_bins(bins, 28, order)):
        img = grab(repo, f"viewpoint_aware_pig_posture_recognition/train_images/{image_id}", root)
        rel = save_image(Image.open(img), task, i)
        rows.append(record(
            task, i, rel,
            "How many pigs in this pen are standing?",
            order, key,
            "Viewpoint-aware pig posture, train split",
            image_id, "https://huggingface.co/datasets/anilbhujel/viewpoint-aware-pig-posture-recognition",
            "CC-BY-4.0", "human box and posture",
            f"standing {standing}; class 3 is Standing",
        ))
    write(HERE / f"{task}.jsonl", rows)
    print(task, Counter(r["expected"] for r in rows))


def doors():
    repo = "v1nz/cubicasa5k-yolo"
    task = "t29_floorplan_doors"
    root = SRC / "cubicasa"
    bins = {"0-3": [], "4-6": [], "7-9": [], "10 or more": []}
    order = list(bins)
    for path in names(repo, "labels/val"):
        local = grab(repo, path, root)
        doors = yolo_counts(local.read_text())[1]
        key = "0-3" if doors <= 3 else "4-6" if doors <= 6 else "7-9" if doors <= 9 else "10 or more"
        bins[key].append((Path(path).stem, doors))
    print("door bin pools", {k: len(v) for k, v in bins.items()})
    rows = []
    for i, (key, (stem, doors)) in enumerate(pick_bins(bins, 29, order)):
        img = grab(repo, f"images/val/{stem}.png", root)
        rel = save_image(Image.open(img), task, i)
        rows.append(record(
            task, i, rel,
            "How many doors does this floor plan show?",
            order, key,
            "CubiCasa5K floor plans, val split, via v1nz/cubicasa5k-yolo",
            stem, "https://huggingface.co/datasets/v1nz/cubicasa5k-yolo",
            "CC BY-NC-SA 4.0 (upstream Zenodo; hub card says CC BY-NC 4.0). Local use.",
            "human polygon, class door",
            f"doors {doors}; class 1 is door",
        ))
    write(HERE / f"{task}.jsonl", rows)
    print(task, Counter(r["expected"] for r in rows))


def damage():
    repo = "QCRI/CrisisMMD"
    task = "t30_damage_severity"
    root = SRC / "crisismmd"
    raw = json.loads(grab(repo, "damage/test.json", root).read_text())
    options = ["little or no damage", "mild damage", "severe damage"]
    show = {
        "little_or_no_damage": "little or no damage",
        "mild_damage": "mild damage",
        "severe_damage": "severe damage",
    }
    bins = defaultdict(list)
    for row in raw:
        bins[show[row["label"]]].append(row)
    rows = []
    for i, (key, src) in enumerate(pick_bins(dict(bins), 30, options)):
        img = grab(repo, src["image_path"], root)
        rel = save_image(Image.open(img), task, i)
        rows.append(record(
            task, i, rel,
            "How severe is the damage to buildings or infrastructure in this photo?",
            options, key,
            "CrisisMMD damage task, test split",
            src["image_id"], "https://huggingface.co/datasets/QCRI/CrisisMMD",
            "CC BY-NC-SA 4.0. Local use.",
            "human image label",
            f"label {src['label']}; event {src['event_name']}; tweet text not stored",
        ))
    write(HERE / f"{task}.jsonl", rows)
    print(task, Counter(r["expected"] for r in rows))


if __name__ == "__main__":
    which = sys.argv[1:] or ["parking", "herd", "pigs", "doors", "damage"]
    for name in which:
        globals()[name]()
