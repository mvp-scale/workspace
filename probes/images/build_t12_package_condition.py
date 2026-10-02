"""Cardboard boxes. The test/good or test/bad folder is the label."""
import random
import re
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_yesno, provenance, save_image

TASK = "t12_package_condition"
ROOT = Path("/workspace/data/sources/image-lab/cardboard-box")
REPO = "Gabriel8/cardboard-box-anomaly-detection"
URL = "https://huggingface.co/datasets/Gabriel8/cardboard-box-anomaly-detection"
SEED = 12
BOX = re.compile(r"box(\d+)")


def box_id(name):
    match = BOX.search(Path(name).name)
    if not match:
        raise ValueError(name)
    return match.group(1)


def folder_of(rel):
    return Path(rel).parent.name


def answer_of(rel):
    path = ROOT / rel
    if not path.is_file() or path.stat().st_size <= 0:
        raise ValueError(rel)
    folder = path.parent.name
    if folder == "bad":
        return True
    if folder == "good":
        return False
    raise ValueError(folder)


def rederive(item):
    return "yes" if answer_of(item["provenance"]["source_id"]) else "no"


def remote_files():
    from huggingface_hub import HfApi

    files = HfApi().list_repo_files(REPO, repo_type="dataset")
    return [name for name in files if name.startswith("test/") and name.lower().endswith((".jpg", ".jpeg", ".png"))]


def select(files):
    pools = {"good": {}, "bad": {}}
    for name in files:
        folder = folder_of(name)
        if folder not in pools:
            continue
        pools[folder].setdefault(box_id(name), []).append(name)
    overlap = set(pools["good"]) & set(pools["bad"])
    if overlap:
        raise SystemExit(f"box ids in both folders: {sorted(overlap)[:8]}")
    rng = random.Random(SEED)
    chosen = []
    for folder, n in (("bad", 13), ("good", 12)):
        ids = sorted(pools[folder])
        rng.shuffle(ids)
        if len(ids) < n:
            raise SystemExit(f"{folder} boxes {len(ids)}, need {n}")
        for bid in ids[:n]:
            shots = sorted(pools[folder][bid])
            rng.shuffle(shots)
            chosen.append(shots[0])
    rng.shuffle(chosen)
    return chosen


def fetch(rel):
    dest = ROOT / rel
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    from huggingface_hub import hf_hub_download

    hf_hub_download(repo_id=REPO, filename=rel, repo_type="dataset", local_dir=str(ROOT))
    if not dest.is_file():
        raise FileNotFoundError(rel)
    return dest


def build():
    chosen = select(remote_files())
    out = []
    for i, rel_img in enumerate(chosen):
        im = Image.open(fetch(rel_img))
        rel = save_image(im, TASK, i)
        question, labels, expected = make_yesno(
            "Is this cardboard box defective?",
            "The image file is in the bad folder.",
            "The image file is in the good folder.",
            answer_of(rel_img),
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
                "CC BY-NC-SA 4.0. Local use.",
                "good or bad folder",
                notes=folder_of(rel_img),
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print(f"wrote {len(build())}")
