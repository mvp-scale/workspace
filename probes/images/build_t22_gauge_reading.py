"""Photographed water meters. The numeric reading is the value column."""
import csv
import math
import random
import re
from pathlib import Path

from huggingface_hub import hf_hub_download
from PIL import Image

import sys
sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import decoy_numbers, make_choice, provenance, save_image

TASK = "t22_gauge_reading"
REPO = "rsnogueira/Watermeter"
SRC = Path("/workspace/data/sources/image-lab/watermeter")
URL = "https://huggingface.co/datasets/rsnogueira/Watermeter"
SEED = 22
NAME = re.compile(r"^id_\d+_value_(\d+(?:_\d+)?)\.jpg$")
_INDEX = None


def reading_of(name):
    match = NAME.match(Path(name).name)
    if not match:
        raise ValueError(name)
    return match.group(1).replace("_", ".")


def index():
    global _INDEX
    if _INDEX is None:
        path = SRC / "metadata.csv"
        found = {}
        with path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                name = Path(row["photo_name"]).name
                text = reading_of(name)
                if math.isclose(float(text), float(row["value"]), rel_tol=1e-6, abs_tol=1e-3):
                    found[name] = text
        _INDEX = found
    return _INDEX


def rederive(item):
    return index()[item["provenance"]["source_id"]]


def select():
    rng = random.Random(SEED)
    items = list(index().items())
    rng.shuffle(items)
    seen = set()
    chosen = []
    for name, text in items:
        if text in seen:
            continue
        seen.add(text)
        chosen.append((name, text))
        if len(chosen) == 25:
            break
    if len(chosen) < 25:
        raise SystemExit(f"only {len(chosen)} distinct meter readings")
    return chosen


def build():
    SRC.mkdir(parents=True, exist_ok=True)
    if not (SRC / "metadata.csv").is_file():
        hf_hub_download(REPO, "metadata.csv", repo_type="dataset", local_dir=SRC)
    out = []
    for i, (name, text) in enumerate(select()):
        local = Path(hf_hub_download(REPO, f"images/{name}", repo_type="dataset", local_dir=SRC))
        options = [text, *decoy_numbers(text, 3, f"{TASK}-{i}")]
        question, labels, expected = make_choice(
            "What reading does this meter show?", options, text, f"{TASK}-{i}"
        )
        rel = save_image(Image.open(local), TASK, i)
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
                "Photographed water meters, rsnogueira/Watermeter",
                name,
                URL,
                "not stated, local use only",
                "metadata.csv value, matching the filename",
                notes=f"value {text}",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print(f"wrote {len(build())}")
