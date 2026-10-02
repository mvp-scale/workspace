"""Concrete photos. Positive and Negative are the folder names in test.zip."""
import random
import sys
import zipfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_yesno, provenance, save_image

TASK = "t11_property_damage"
ROOT = Path("/workspace/data/sources/image-lab/concrete-crack")
ZIP = ROOT / "data" / "test.zip"
URL = "https://huggingface.co/datasets/mohammadnajeeb/concrete_crack_images"
SEED = 11
YES_FOLDER = "Positive"
NO_FOLDER = "Negative"


def members():
    with zipfile.ZipFile(ZIP) as archive:
        return [name for name in archive.namelist() if name.lower().endswith(".jpg")]


def folder_of(member):
    parts = member.split("/")
    if len(parts) < 2:
        raise ValueError(member)
    return parts[-2]


def answer_of(member):
    if member not in set(members_cached()):
        raise ValueError(member)
    folder = folder_of(member)
    if folder == YES_FOLDER:
        return True
    if folder == NO_FOLDER:
        return False
    raise ValueError(folder)


_MEMBERS = None


def members_cached():
    global _MEMBERS
    if _MEMBERS is None:
        _MEMBERS = set(members())
    return _MEMBERS


def rederive(item):
    member = item["provenance"]["source_id"]
    return "yes" if answer_of(member) else "no"


def select():
    yes, no = [], []
    for name in members():
        folder = folder_of(name)
        if folder == YES_FOLDER:
            yes.append(name)
        elif folder == NO_FOLDER:
            no.append(name)
    rng = random.Random(SEED)
    rng.shuffle(yes)
    rng.shuffle(no)
    if len(yes) < 13 or len(no) < 12:
        raise SystemExit(f"yes={len(yes)} no={len(no)}")
    chosen = yes[:13] + no[:12]
    rng.shuffle(chosen)
    return chosen


def build():
    if not ZIP.is_file():
        raise SystemExit(f"missing {ZIP}")
    out = []
    with zipfile.ZipFile(ZIP) as archive:
        chosen = select()
        for i, member in enumerate(chosen):
            im = Image.open(archive.open(member))
            rel = save_image(im, TASK, i)
            question, labels, expected = make_yesno(
                "Is there a crack in this concrete?",
                "The image is in the Positive folder, the positive crack class.",
                "The image is in the Negative folder, the negative crack class.",
                answer_of(member),
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
                    "mohammadnajeeb/concrete_crack_images",
                    member,
                    URL,
                    "CC BY 4.0",
                    "Positive or Negative folder in test.zip",
                    notes=folder_of(member),
                ),
            })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print(f"wrote {len(build())}")
