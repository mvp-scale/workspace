"""Hard-hat photos. Yes when the dataset marks at least one head (no helmet)."""
import json
import random
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_yesno, provenance, save_image

SEED = 18
TASK = "t18_hard_hat_worn"
ROOT = Path("/workspace/data/sources/image-lab/hard-hat")
URL = "https://huggingface.co/datasets/Voxel51/hard-hat-detection"
_SAMPLES = None

def samples():
    global _SAMPLES
    if _SAMPLES is None:
        _SAMPLES = json.loads((ROOT / "samples.json").read_text())["samples"]
    return _SAMPLES

def labels_of(sample):
    return [d.get("label") for d in sample["ground_truth"]["detections"]]

def people(sample):
    return sum(1 for lab in labels_of(sample) if lab in ("head", "helmet"))

def missing_hat(sample):
    return any(lab == "head" for lab in labels_of(sample))

def by_path():
    return {s["filepath"]: s for s in samples()}

def select():
    yes, no = [], []
    for s in samples():
        if not 1 <= people(s) <= 3:
            continue
        (yes if missing_hat(s) else no).append(s["filepath"])
    rng = random.Random(SEED)
    rng.shuffle(yes)
    rng.shuffle(no)
    if len(yes) < 13 or len(no) < 12:
        raise RuntimeError(f"balance pool yes={len(yes)} no={len(no)}")
    return yes[:13] + no[:12]

def rederive(item):
    path = item["provenance"]["source_id"]
    sample = by_path()[path]
    if not 1 <= people(sample) <= 3:
        return None
    return "yes" if missing_hat(sample) else "no"

def build():
    paths = select()
    index = by_path()
    out = []
    for n, path in enumerate(paths):
        sample = index[path]
        im = Image.open(ROOT / path)
        rel = save_image(im, TASK, n)
        question, labels, expected = make_yesno(
            "Is there a person in this image who is NOT wearing a hard hat?",
            "At least one person is not wearing a hard hat",
            "No person is shown without a hard hat",
            missing_hat(sample),
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
                "Voxel51/hard-hat-detection",
                path,
                URL,
                "CC0-1.0",
                "at least one detection labelled head",
                notes="people = count of head and helmet labels, kept 1 to 3",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out

if __name__ == "__main__":
    print("wrote", len(build()))
