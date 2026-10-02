"""Photographed electricity meters. The reading string is the label."""
import hashlib
import io
import random
import re
import sys
from pathlib import Path

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download
from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import decoy_numbers, make_choice, provenance, save_image

TASK = "t36_meter_reading"
REPO = "Praekelt/ElectricityMeterReadings1o4"
SRC = Path("/workspace/data/sources/image-lab/electricity-meters")
PARQUET = SRC / "data" / "train-00000-of-00001.parquet"
URL = "https://huggingface.co/datasets/Praekelt/ElectricityMeterReadings1o4"
SEED = 36
NUM = re.compile(r"^\d+(\.\d+)?$")
_INDEX = None


def table():
    rows = pq.read_table(PARQUET).to_pylist()
    for row in rows:
        raw = row["image"]["bytes"]
        row["_hash"] = hashlib.sha256(raw).hexdigest()
        row["_reading"] = (row.get("reading") or "").strip()
    return rows


def index():
    global _INDEX
    if _INDEX is None:
        _INDEX = {row["_hash"]: row["_reading"] for row in table() if NUM.fullmatch(row["_reading"])}
    return _INDEX


def rederive(item):
    return index()[item["provenance"]["source_id"]]


def select():
    rng = random.Random(SEED)
    rows = [row for row in table() if NUM.fullmatch(row["_reading"])]
    rng.shuffle(rows)
    seen = set()
    chosen = []
    for row in rows:
        if row["_reading"] in seen or row["_hash"] in seen:
            continue
        seen.add(row["_reading"])
        seen.add(row["_hash"])
        chosen.append(row)
        if len(chosen) == 25:
            break
    if len(chosen) < 25:
        raise SystemExit(f"only {len(chosen)} distinct electricity readings")
    return chosen


def build():
    if not PARQUET.is_file():
        hf_hub_download(REPO, "data/train-00000-of-00001.parquet", repo_type="dataset", local_dir=SRC)
    out = []
    for i, row in enumerate(select()):
        text = row["_reading"]
        options = [text, *decoy_numbers(text, 3, f"{TASK}-{i}")]
        question, labels, expected = make_choice(
            "What reading does this electricity meter show?", options, text, f"{TASK}-{i}"
        )
        rel = save_image(Image.open(io.BytesIO(row["image"]["bytes"])), TASK, i)
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
                "Photographed electricity meters, Praekelt/ElectricityMeterReadings1o4",
                row["_hash"],
                URL,
                "not stated, local use only",
                "reading",
                notes=f"reading {text}",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print(f"wrote {len(build())}")
