"""HAM10000 dermatoscopic images. Answer = the dataset's dx column, only rows with dx_type == histo.
RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE."""
import csv
import random
import sys
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_choice, provenance, save_image

SEED = 40
TASK = "t40_skin_lesion"
ROOT = Path("/workspace/data/sources/image-lab/ham10000")
MIRROR = "https://huggingface.co/datasets/ShiroOnigami23/skin-cancer-ham10000-dataset"
OWNER = "https://doi.org/10.7910/DVN/DBW86T"
NAMES = {
    "nv": "melanocytic nevus",
    "mel": "melanoma",
    "bkl": "benign keratosis",
    "bcc": "basal cell carcinoma",
}
PER_CLASS = {"nv": 6, "mel": 6, "bkl": 6, "bcc": 7}
QUESTION = "Which diagnosis best describes this skin lesion?"


def rows():
    with open(ROOT / "HAM10000_metadata.csv", newline="") as f:
        return list(csv.DictReader(f))


def label_of(row):
    if row["dx_type"] != "histo" or row["dx"] not in NAMES:
        return None
    return NAMES[row["dx"]]


def fetch(image_id):
    for part in ("part_1", "part_2"):
        rel = f"HAM10000_images_{part}/{image_id}.jpg"
        dest = ROOT / rel
        if dest.is_file() and dest.stat().st_size > 0:
            return dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(f"{MIRROR}/resolve/main/{rel}", headers={"User-Agent": "image-lab-build"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                dest.write_bytes(resp.read())
            return dest
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
    raise RuntimeError(image_id)


def select():
    allrows = rows()
    count = {}
    for r in allrows:
        count[r["lesion_id"]] = count.get(r["lesion_id"], 0) + 1
    by = {k: [] for k in NAMES}
    for r in allrows:
        if label_of(r) and count[r["lesion_id"]] == 1:  # one image per lesion, no near-duplicates
            by[r["dx"]].append(r)
    rng = random.Random(SEED)
    chosen = []
    for k in sorted(NAMES):
        by[k].sort(key=lambda r: r["image_id"])
        rng.shuffle(by[k])
        chosen += by[k][:PER_CLASS[k]]
    rng.shuffle(chosen)
    return chosen


def rederive(item):
    iid = item["provenance"]["source_id"]
    for r in rows():
        if r["image_id"] == iid:
            return label_of(r)
    return None


def build():
    out = []
    for n, r in enumerate(select()):
        rel = save_image(Image.open(fetch(r["image_id"])), TASK, n)
        label = label_of(r)
        question, labels, expected = make_choice(QUESTION, list(NAMES.values()), label, SEED * 1000 + n)
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
                "HAM10000 (Tschandl et al. 2018), file mirror ShiroOnigami23/skin-cancer-ham10000-dataset",
                r["image_id"],
                OWNER,
                "CC-BY-NC-4.0 (non-commercial; local testing only)",
                f"dx column = {r['dx']}, dx_type = histo (pathology-confirmed)",
                notes="research benchmark, not for clinical use; non-commercial licence, local testing only; "
                      f"lesion {r['lesion_id']}, site {r['localization']}, age {r['age']}, sex {r['sex']}",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print("wrote", len(build()))
