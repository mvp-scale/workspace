"""Synthetic cheques. The amount is metadata text.amount_in_numbers, not a reading of the image."""
import json
import random
import re
import sys
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import decoy_numbers, make_choice, provenance, save_image

SEED = 6
TASK = "t06_cheque_amount"
ROOT = Path("/workspace/data/sources/image-lab/ocr-synthetic-cheque")
META = ROOT / "metadata.jsonl"
REPO = "https://huggingface.co/datasets/alpha-brain/ocr-synthetic-cheque-datatset"
_ROWS = None

def rows():
    global _ROWS
    if _ROWS is None:
        _ROWS = [json.loads(line) for line in META.read_text().splitlines() if line.strip()]
    return _ROWS

def amount_of(row):
    text = row.get("text") or {}
    amt = text.get("amount_in_numbers")
    if isinstance(amt, str) and re.fullmatch(r"\d+\.\d+", amt):
        return amt
    return None

def select():
    seen, good = set(), []
    for row in rows():
        amt = amount_of(row)
        name = row.get("file_name") or ""
        if amt is None or ".." in name or not name.endswith((".jpg", ".jpeg", ".png")):
            continue
        if amt in seen:
            continue
        seen.add(amt)
        good.append(row)
    rng = random.Random(SEED)
    rng.shuffle(good)
    if len(good) < 25:
        raise RuntimeError(f"only {len(good)} cheques with a numeric amount")
    return good[:25]

def fetch(file_name):
    dest = ROOT / file_name
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{REPO}/resolve/main/{file_name}"
    req = urllib.request.Request(url, headers={"User-Agent": "image-lab-build"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        dest.write_bytes(resp.read())
    return dest

def rederive(item):
    name = item["provenance"]["source_id"]
    for row in rows():
        if row.get("file_name") == name:
            return amount_of(row)
    return None

def build():
    chosen = select()
    out = []
    for n, row in enumerate(chosen):
        amt = amount_of(row)
        im = Image.open(fetch(row["file_name"]))
        rel = save_image(im, TASK, n)
        options = decoy_numbers(amt, 3, SEED + n) + [amt]
        question, labels, expected = make_choice("What is the amount on this cheque?", options, amt, SEED + n)
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
                "alpha-brain/ocr-synthetic-cheque-datatset",
                row["file_name"],
                REPO,
                "not stated, local use only",
                "text.amount_in_numbers",
                notes="text.amount_in_numbers",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out

if __name__ == "__main__":
    print("wrote", len(build()))
