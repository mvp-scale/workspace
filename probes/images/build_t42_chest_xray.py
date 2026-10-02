"""Pediatric chest X-rays (Kermany et al.). Yes = PNEUMONIA label, no = NORMAL. Research benchmark, not for clinical use."""
import io
import random
import re
import sys
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_yesno, provenance, save_image

SEED = 42
TASK = "t42_chest_xray"
SRC = Path("/workspace/data/sources/image-lab/chest-xray-kermany/data/test-00000-of-00001.parquet")
URL = "https://huggingface.co/datasets/hf-vision/chest-xray-pneumonia"


def rows():
    t = pq.read_table(SRC)
    return [(i, r["image"]["path"], r["label"]) for i, r in enumerate(t.to_pylist())]


def patient(path):
    m = re.match(r"(person\d+)_", path) or re.match(r"IM-(\d+)-", path) or re.match(r"NORMAL2-IM-(\d+)-", path)
    return m.group(1) if m else path


def select():
    allr = rows()
    rng = random.Random(SEED)
    rng.shuffle(allr)
    seen, yes_b, yes_v, no = set(), [], [], []
    for r in allr:
        p = patient(r[1])
        if p in seen:
            continue
        seen.add(p)
        if r[2] == 0:
            no.append(r)
        elif "_bacteria_" in r[1]:
            yes_b.append(r)
        elif "_virus_" in r[1]:
            yes_v.append(r)
    chosen = yes_b[:7] + yes_v[:6] + no[:12]
    random.Random(SEED + 1).shuffle(chosen)
    return chosen


def rederive(item):
    idx = int(item["provenance"]["source_id"].split("row ")[1].split(" ")[0])
    r = pq.read_table(SRC).slice(idx, 1).to_pylist()[0]
    return "yes" if r["label"] == 1 else "no"


def build():
    table = pq.read_table(SRC).to_pylist()
    out = []
    for n, (idx, path, label) in enumerate(select()):
        im = Image.open(io.BytesIO(table[idx]["image"]["bytes"]))
        rel = save_image(im, TASK, n)
        q, labels, exp = make_yesno(
            "Does this chest X-ray show pneumonia or another abnormality?",
            "The dataset label is PNEUMONIA",
            "The dataset label is NORMAL",
            label == 1,
        )
        out.append({
            "id": f"{TASK}-{n:03d}", "family": TASK, "state": "An image is attached.", "images": [rel],
            "question": q, "labels": labels, "expected": exp, "split": "public", "group": None,
            "provenance": provenance(
                "Kermany et al. pediatric chest X-ray (hf-vision/chest-xray-pneumonia mirror), test split",
                f"row {idx} file {path}", URL, "CC-BY-4.0 (as stated on the HF mirror card)",
                "diagnosis graded by two expert physicians, evaluation set checked by a third (Kermany et al., Cell 2018)",
                notes="research benchmark, not for clinical use; pediatric AP films, ages 1-5, Guangzhou",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print("wrote", len(build()))
