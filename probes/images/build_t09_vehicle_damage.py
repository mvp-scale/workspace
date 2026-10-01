"""Car photos. Yes when the annotation lists a damage class. Parts-only images are the no set."""
import json
import random
import sys
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_yesno, provenance, save_image

SEED = 9
TASK = "t09_vehicle_damage"
ROOT = Path("/workspace/data/sources/image-lab/car-parts-damage")
REPO = "https://huggingface.co/datasets/DrBimmer/car-parts-and-damage-dataset"
DAMAGE = {
    "Dent", "Cracked", "Scratch", "Flaking", "Broken part",
    "Paint chip", "Missing part", "Corrosion",
}
PARTS = {
    "Windshield", "Back-windshield", "Front-window", "Back-window", "Front-door", "Back-door",
    "Front-wheel", "Back-wheel", "Front-bumper", "Back-bumper", "Headlight", "Tail-light",
    "Hood", "Trunk", "License-plate", "Mirror", "Roof", "Grille", "Rocker-panel",
    "Quarter-panel", "Fender",
}

def ann_files():
    return sorted(p for p in ROOT.rglob("*.json") if ".cache" not in p.parts)

def titles(path):
    data = json.loads(Path(path).read_text())
    return [o.get("classTitle") for o in (data.get("objects") or [])]

def answer_of(path):
    names = titles(path)
    if any(n not in DAMAGE and n not in PARTS for n in names):
        return None
    damaged = any(n in DAMAGE for n in names)
    parts = any(n in PARTS for n in names)
    if damaged and parts:
        return None
    if damaged:
        return True
    if parts:
        return False
    return None

def image_path(ann):
    rel = Path(ann).relative_to(ROOT).as_posix()
    if "/ann/" not in rel or not rel.endswith(".json"):
        raise ValueError(rel)
    return ROOT / rel.replace("/ann/", "/img/")[:-len(".json")]

def fetch(rel_posix):
    dest = ROOT / rel_posix
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = REPO + "/resolve/main/" + urllib.request.quote(rel_posix)
    req = urllib.request.Request(url, headers={"User-Agent": "image-lab-build"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        dest.write_bytes(resp.read())
    return dest

def select():
    yes, no = [], []
    for path in ann_files():
        ans = answer_of(path)
        if ans is True:
            yes.append(path)
        elif ans is False:
            no.append(path)
    rng = random.Random(SEED)
    rng.shuffle(yes)
    rng.shuffle(no)
    if len(yes) < 13 or len(no) < 12:
        raise RuntimeError(f"yes={len(yes)} no={len(no)}")
    return yes[:13] + no[:12]

def rederive(item):
    path = ROOT / item["provenance"]["source_id"]
    ans = answer_of(path)
    if ans is None:
        return None
    return "yes" if ans else "no"

def build():
    out = []
    for n, path in enumerate(select()):
        rel_ann = path.relative_to(ROOT).as_posix()
        img = image_path(path)
        rel_img = img.relative_to(ROOT).as_posix()
        im = Image.open(fetch(rel_img))
        rel = save_image(im, TASK, n)
        question, labels, expected = make_yesno(
            "Is this vehicle visibly damaged?",
            "The annotation includes at least one damage class",
            "The annotation includes no damage class",
            answer_of(path),
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
                "DrBimmer/car-parts-and-damage-dataset",
                rel_ann,
                REPO,
                "MIT",
                "presence of a damage classTitle",
                notes="presence of a damage classTitle",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out

if __name__ == "__main__":
    print("wrote", len(build()))
