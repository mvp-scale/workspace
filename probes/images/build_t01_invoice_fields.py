"""Photographed invoices. The total string in the annotation file is the answer."""
import json
import random
import re
import sys
import zipfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import decoy_numbers, make_choice, provenance, save_image

TASK = "t01_invoice_fields"
ROOT = Path("/workspace/data/sources/image-lab/cruz-invoices")
ANN = ROOT / "annotations"
ZIP = ROOT / "1_Images.zip"
URL = "https://zenodo.org/records/7213544"
SEED = 1
QUESTION = "What is the total amount on this invoice?"
TOTAL_RE = re.compile(r"\d+(?:[.,]\d+)?")


def annotation(stem):
    return json.loads((ANN / f"{stem}.txt").read_text(encoding="utf-8"))


def total_of(stem):
    value = annotation(stem).get("total")
    if isinstance(value, str) and TOTAL_RE.fullmatch(value):
        return value
    return None


def pool():
    rows = []
    for path in sorted(ANN.glob("*.txt")):
        total = total_of(path.stem)
        if total:
            rows.append((path.stem, total))
    return rows


def choose():
    rng = random.Random(SEED)
    rows = pool()
    rng.shuffle(rows)
    seen, chosen = set(), []
    for stem, total in rows:
        if total in seen:
            continue
        seen.add(total)
        chosen.append((stem, total))
        if len(chosen) == 25:
            break
    if len(chosen) < 25:
        raise SystemExit(f"only {len(chosen)} distinct totals")
    return chosen


def open_image(stem):
    folder = ROOT / "images"
    for ext in (".jpg", ".jpeg", ".png"):
        path = folder / f"{stem}{ext}"
        if path.is_file():
            return Image.open(path), path.name
    if not ZIP.is_file():
        raise FileNotFoundError(stem)
    with zipfile.ZipFile(ZIP) as zf:
        for name in zf.namelist():
            if Path(name).stem == stem and Path(name).suffix.lower() in {".jpg", ".jpeg", ".png"}:
                with zf.open(name) as handle:
                    return Image.open(handle).copy(), Path(name).name
    raise FileNotFoundError(stem)


def rederive(item):
    stem = Path(item["provenance"]["source_id"]).stem
    return total_of(stem)


def build():
    chosen = choose()
    out = []
    for n, (stem, total) in enumerate(chosen):
        im, name = open_image(stem)
        rel = save_image(im, TASK, n)
        options = decoy_numbers(total, 3, SEED + n) + [total]
        question, labels, expected = make_choice(QUESTION, options, total, f"{TASK}-{n}")
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
                "Cruz and Castelli personal invoices and receipts (Zenodo 7213544)",
                name,
                URL,
                "CC-BY-4.0",
                "annotation total",
                notes="annotation total",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print(f"wrote {len(build())}")
