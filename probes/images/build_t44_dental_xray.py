"""Dental panoramic X-rays (DENTEX test split). Yes when the expert annotation has at least one caries (cürük) polygon."""
import io
import json
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

SEED = 44
TASK = "t44_dental_xray"
ROOT = Path("/workspace/data/sources/image-lab/dentex")
REPO = "https://huggingface.co/datasets/ibrahimhamamci/DENTEX"
ZIP_URL = REPO + "/resolve/main/DENTEX/test_data.zip"
ZIP = ROOT / "test_data.zip"
CARIES = "çürük"  # Turkish for caries; label strings look like "1-çürük-15" (quadrant-class-tooth)
EXCLUDE = set()  # image stems with readable personal data (none found)


def ensure_zip():
    if ZIP.is_file() and ZIP.stat().st_size > 0:
        return
    ROOT.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(ZIP_URL, headers={"User-Agent": "image-lab-build"})
    with urllib.request.urlopen(req, timeout=600) as r, open(ZIP, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)


def classes_of(label_json):
    out = []
    for sh in label_json["shapes"]:
        parts = sh["label"].split("-")
        out.append(parts[1] if len(parts) > 1 else sh["label"])
    return out


def answer_of(label_json):
    return CARIES in classes_of(label_json)


def stems(z):
    return sorted(n.split("/")[-1][:-5] for n in z.namelist() if n.startswith("disease/label/") and n.endswith(".json"))


def read_label(z, stem):
    return json.loads(z.read(f"disease/label/{stem}.json"))


def select(z):
    yes, no = [], []
    for s in stems(z):
        if s in EXCLUDE:
            continue
        (yes if answer_of(read_label(z, s)) else no).append(s)
    rng = random.Random(SEED)
    rng.shuffle(yes)
    rng.shuffle(no)
    if len(yes) < 13 or len(no) < 12:
        raise RuntimeError(f"yes={len(yes)} no={len(no)}")
    pick = yes[:13] + no[:12]
    rng.shuffle(pick)
    return pick


def rederive(item):
    with zipfile.ZipFile(ZIP) as z:
        return "yes" if answer_of(read_label(z, item["provenance"]["source_id"].split("/")[-1][:-5])) else "no"


def build():
    ensure_zip()
    out = []
    with zipfile.ZipFile(ZIP) as z:
        for n, stem in enumerate(select(z)):
            lab = read_label(z, stem)
            im = Image.open(io.BytesIO(z.read(f"disease/input/{stem}.png")))
            rel = save_image(im, TASK, n)
            question, labels, expected = make_yesno(
                "Is there a cavity (caries) visible on this dental X-ray?",
                "The expert annotation marks at least one caries (cürük) tooth",
                "The expert annotation marks no caries tooth",
                answer_of(lab),
            )
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
                    "DENTEX 2023 (ibrahimhamamci/DENTEX), test split, disease/label",
                    f"disease/label/{stem}.json",
                    REPO,
                    "CC-BY-NC-SA-4.0 (non-commercial; local testing only)",
                    "at least one polygon whose label class is cürük (caries) in the dataset's own expert annotation",
                    notes="research benchmark, not for clinical use; panoramic radiograph; non-commercial licence, local testing only",
                ),
            })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print("wrote", len(build()))
