"""Atlas Dermatologico clinical photos (via Fitzpatrick17k) of four skin conditions. Answer = atlas diagnosis label."""
import csv
import random
import sys
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_choice, provenance, save_image

SEED = 48
TASK = "t48_wound_photo"
ROOT = Path("/workspace/data/sources/image-lab/fitz17k")
CSV_URL = "https://raw.githubusercontent.com/mattgroh/fitzpatrick17k/main/fitzpatrick17k.csv"
REPO = "https://github.com/mattgroh/fitzpatrick17k"
CLASSES = ["scabies", "tungiasis", "lichen planus", "psoriasis"]
TAKE = {"scabies": 7, "tungiasis": 6, "lichen planus": 6, "psoriasis": 6}
CANDIDATES = 12  # first 12 of the seeded shuffle per class are screened for privacy
# Skipped after a privacy screen of the 48 candidates: genital area (2), lower face / beard / eyes (3).
SKIP = {
    "0ff7c60fea8b55fd7f567d60cb7afe7c", "6c5f7848a7ecd6e62a949c13b05c05dd",
    "0a2a30d010c5b82ddabe4ae30c7ae3f2", "d6e48782569b4e90540e280e4b288562",
    "990d78eb61cc7e59bd11061bfa809895", "7395a68469f19821f29444f383abd041",
}

def rows():
    f = ROOT / "f.csv"
    if not f.is_file():
        ROOT.mkdir(parents=True, exist_ok=True)
        f.write_bytes(urllib.request.urlopen(CSV_URL, timeout=120).read())
    return list(csv.DictReader(open(f)))

def fetch(row):
    dest = ROOT / "img" / f"{row['md5hash']}.jpg"
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(row["url"], headers={"User-Agent": "Mozilla/5.0"})
    dest.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    return dest

def select():
    atlas = [r for r in rows() if "atlasdermatologico" in r["url"]]
    chosen = []
    for cls in CLASSES:
        pool = sorted((r for r in atlas if r["label"] == cls), key=lambda r: r["md5hash"])
        random.Random(SEED).shuffle(pool)
        ok = [r for r in pool[:CANDIDATES] if r["md5hash"] not in SKIP]
        if len(ok) < TAKE[cls]:
            raise RuntimeError(cls)
        chosen += ok[:TAKE[cls]]
    random.Random(SEED + 1).shuffle(chosen)
    return chosen

def rederive(item):
    h = item["provenance"]["source_id"]
    for r in rows():
        if r["md5hash"] == h:
            return r["label"]
    return None

def build():
    out = []
    for n, r in enumerate(select()):
        rel = save_image(Image.open(fetch(r)), TASK, n)
        q, labels, exp = make_choice(
            "Which skin condition does this clinical photograph show?", CLASSES, r["label"], SEED * 1000 + n)
        out.append({
            "id": f"{TASK}-{n:03d}", "family": TASK, "state": "An image is attached.",
            "images": [rel], "question": q, "labels": labels, "expected": exp,
            "split": "public", "group": None,
            "provenance": provenance(
                "Fitzpatrick17k (images and diagnosis labels from Atlas Dermatologico)", r["md5hash"],
                r["url"], "CC BY-NC-SA 3.0 (non-commercial; local testing only; images belong to the atlas)",
                "diagnosis label (column label) taken by Fitzpatrick17k from the atlas's own clinician-curated diagnosis; "
                f"nine_partition_label={r['nine_partition_label']}; fitzpatrick_scale={r['fitzpatrick_scale']}",
                notes="research benchmark, not for clinical use; skin conditions, not a wound-type task; repo " + REPO),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out

if __name__ == "__main__":
    print("wrote", len(build()))
