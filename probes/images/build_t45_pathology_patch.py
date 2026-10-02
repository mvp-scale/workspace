"""PatchCamelyon test shard 0. Yes when the dataset label says the centre 32x32 px region holds tumour."""
import io
import random
import sys
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_yesno, provenance, save_image

SEED = 45
TASK = "t45_pathology_patch"
ROOT = Path("/workspace/data/sources/image-lab/pcam")
FILE = ROOT / "test-00000-of-00002.parquet"
REPO = "https://huggingface.co/datasets/dpdl-benchmark/patch_camelyon"
URL = REPO + "/resolve/main/data/test-00000-of-00002.parquet"


def fetch():
    if FILE.is_file() and FILE.stat().st_size > 0:
        return FILE
    import urllib.request
    ROOT.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(URL, headers={"User-Agent": "image-lab-build"})
    with urllib.request.urlopen(req, timeout=600) as r:
        FILE.write_bytes(r.read())
    return FILE


def labels():
    return pq.ParquetFile(fetch()).read(columns=["label"]).column("label").to_pylist()


def select():
    lab = labels()
    yes = [i for i, v in enumerate(lab) if v == 1]
    no = [i for i, v in enumerate(lab) if v == 0]
    rng = random.Random(SEED)
    yes = rng.sample(yes, 13)
    no = rng.sample(no, 12)
    rows = yes + no
    rng.shuffle(rows)
    return rows


def get_row(idx):
    pf = pq.ParquetFile(fetch())
    start = 0
    for g in range(pf.num_row_groups):
        n = pf.metadata.row_group(g).num_rows
        if idx < start + n:
            return pf.read_row_group(g).slice(idx - start, 1).to_pylist()[0]
        start += n
    raise IndexError(idx)


def rederive(item):
    idx = int(item["provenance"]["source_id"].split("row ")[1])
    return "yes" if get_row(idx)["label"] == 1 else "no"


def build():
    out = []
    for n, idx in enumerate(select()):
        row = get_row(idx)
        im = Image.open(io.BytesIO(row["image"]["bytes"]))
        rel = save_image(im, TASK, n)
        question, labs, expected = make_yesno(
            "Does this lymph-node tissue patch contain tumour (metastasis)?",
            "The dataset label says the centre 32x32 px region contains tumour",
            "The dataset label says the centre 32x32 px region contains no tumour",
            row["label"] == 1,
        )
        out.append({
            "id": f"{TASK}-{n:03d}",
            "family": TASK,
            "state": "An image is attached.",
            "images": [rel],
            "question": question,
            "labels": labs,
            "expected": expected,
            "split": "public",
            "group": None,
            "provenance": provenance(
                "PatchCamelyon (PCam), test split, mirror dpdl-benchmark/patch_camelyon",
                f"{FILE.name} row {idx}",
                "https://github.com/basveeling/pcam",
                "CC0-1.0 (as stated by the PCam owner)",
                "PCam binary label, derived from CAMELYON16 pathologist lesion annotations; patch-level",
                notes="research benchmark, not for clinical use. 96x96 px patch, saved at native size. "
                      "Label refers to centre 32x32 px only.",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print("wrote", len(build()))
