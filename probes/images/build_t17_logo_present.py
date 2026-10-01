"""Logo photos. The brand is the COCO category name. One box per image."""
import json
import random
import sys
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_choice, provenance, save_image

SEED = 17
TASK = "t17_logo_present"
ROOT = Path("/workspace/data/sources/image-lab/logo-detection")
REPO = "https://huggingface.co/datasets/varun1212/logo-detection-dataset"
QUESTION = "Which brand logo is shown?"
_DATA = None

def coco():
    global _DATA
    if _DATA is None:
        _DATA = json.loads((ROOT / "annotations" / "train.json").read_text())
    return _DATA

def index():
    data = coco()
    cats = {c["id"]: c["name"] for c in data["categories"]}
    images = {im["id"]: im for im in data["images"]}
    by_brand = {}
    for ann in data["annotations"]:
        im = images[ann["image_id"]]
        name = cats[ann["category_id"]]
        by_brand.setdefault(name, []).append(im)
    return by_brand

def fetch(file_name):
    dest = ROOT / "images" / file_name
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = REPO + "/resolve/main/images/" + urllib.request.quote(file_name)
    req = urllib.request.Request(url, headers={"User-Agent": "image-lab-build"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        dest.write_bytes(resp.read())
    return dest

def select():
    rng = random.Random(SEED)
    brands = sorted(index())
    rng.shuffle(brands)
    chosen = []
    for brand in brands:
        ims = [im for im in index()[brand] if im.get("width", 0) >= 60]
        if not ims:
            continue
        rng.shuffle(ims)
        chosen.append((brand, ims[0]))
        if len(chosen) == 25:
            break
    if len(chosen) < 25:
        raise RuntimeError(f"only {len(chosen)} brands")
    return chosen

def rederive(item):
    file_name = item["provenance"]["source_id"]
    data = coco()
    images = {im["id"]: im for im in data["images"]}
    cats = {c["id"]: c["name"] for c in data["categories"]}
    hits = [cats[a["category_id"]] for a in data["annotations"] if images[a["image_id"]]["file_name"] == file_name]
    if len(hits) != 1:
        return None
    return hits[0]

def build():
    chosen = select()
    brands = [b for b, _im in chosen]
    rng = random.Random(SEED)
    out = []
    for n, (brand, im) in enumerate(chosen):
        others = [b for b in brands if b != brand]
        rng.shuffle(others)
        options = others[:3] + [brand]
        question, labels, expected = make_choice(QUESTION, options, brand, SEED + n)
        picture = Image.open(fetch(im["file_name"]))
        rel = save_image(picture, TASK, n)
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
                "varun1212/logo-detection-dataset, train.json",
                im["file_name"],
                REPO,
                "not stated, local use only",
                "categories.name",
                notes="categories.name",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out

if __name__ == "__main__":
    print("wrote", len(build()))
