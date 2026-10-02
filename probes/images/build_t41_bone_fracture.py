"""FracAtlas radiographs. Yes when dataset.csv says fractured=1 (radiologist-annotated). Single body part, no hardware."""
import csv
import random
import sys
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_yesno, provenance, save_image

SEED = 41
TASK = "t41_bone_fracture"
ROOT = Path("/workspace/data/sources/image-lab/fracatlas")
ZIP_URL = "https://ndownloader.figshare.com/files/65518038"
PAGE = "https://figshare.com/articles/dataset/The_dataset/22363012"
PARTS = ["hand", "leg", "hip", "shoulder"]
YES_PER_PART = {"hand": 4, "leg": 3, "hip": 3, "shoulder": 3}   # 13
NO_PER_PART = {"hand": 3, "leg": 3, "hip": 3, "shoulder": 3}    # 12
EXCLUDE = set()  # image ids skipped for readable burned-in text (filled after review)


def ensure():
    csv_path = ROOT / "FracAtlas" / "dataset.csv"
    if csv_path.is_file():
        return
    ROOT.mkdir(parents=True, exist_ok=True)
    z = ROOT / "FracAtlas.zip"
    if not z.is_file():
        urllib.request.urlretrieve(ZIP_URL, z)
    zipfile.ZipFile(z).extractall(ROOT)


def rows():
    ensure()
    with open(ROOT / "FracAtlas" / "dataset.csv", newline="") as f:
        return sorted(csv.DictReader(f), key=lambda r: r["image_id"])


def part_of(r):
    ps = [p for p in PARTS if r[p] == "1"]
    return ps[0] if len(ps) == 1 else None


def clean(r):
    return (r["mixed"] == "0" and r["hardware"] == "0" and r["multiscan"] == "0"
            and part_of(r) and r["image_id"] not in EXCLUDE)


def answer_of(r):
    return r["fractured"] == "1"


def img_path(r):
    sub = "Fractured" if answer_of(r) else "Non_fractured"
    return ROOT / "FracAtlas" / "images" / sub / r["image_id"]


def readable(r):
    try:
        with Image.open(img_path(r)) as im:
            im.load()
        return True
    except Exception:
        return False


def select():
    rng = random.Random(SEED)
    pool = [r for r in rows() if clean(r)]
    out = []
    for flag, quota in ((True, YES_PER_PART), (False, NO_PER_PART)):
        for p in PARTS:
            c = [r for r in pool if answer_of(r) == flag and part_of(r) == p]
            rng.shuffle(c)
            c = [r for r in c[:quota[p] + 6] if readable(r)]
            if len(c) < quota[p]:
                raise RuntimeError((flag, p, len(c)))
            out += c[:quota[p]]
    rng.shuffle(out)
    return out


def rederive(item):
    sid = item["provenance"]["source_id"]
    for r in rows():
        if r["image_id"] == sid:
            return "yes" if answer_of(r) else "no"
    return None


def view_of(r):
    return [v for v in ("frontal", "lateral", "oblique") if r[v] == "1"]


def build():
    out = []
    for n, r in enumerate(select()):
        rel = save_image(Image.open(img_path(r)), TASK, n)
        q, labels, expected = make_yesno(
            "Does this X-ray show a fracture?",
            "The dataset's radiologist annotation marks a fracture (fractured=1)",
            "The dataset's annotation marks no fracture (fractured=0)",
            answer_of(r),
        )
        p = provenance(
            "FracAtlas (Abedeen et al., Sci Data 2023), figshare",
            r["image_id"], PAGE, "CC BY 4.0",
            "dataset.csv column 'fractured', annotated by radiologists per the Scientific Data paper",
            notes="research benchmark, not for clinical use. body_part=%s; views=%s; fracture_count=%s"
                  % (part_of(r), "+".join(view_of(r)), r["fracture_count"]),
        )
        out.append({
            "id": f"{TASK}-{n:03d}", "family": TASK, "state": "An image is attached.",
            "images": [rel], "question": q, "labels": labels, "expected": expected,
            "split": "public", "group": None, "provenance": p,
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print("wrote", len(build()))
