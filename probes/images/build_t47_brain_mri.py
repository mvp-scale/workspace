"""Brain MRI slices. Answer = the dataset's own class label (glioma / meningioma / pituitary / no tumour)."""
import io
import random
import sys
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_choice, provenance, save_image

SEED = 47
TASK = "t47_brain_mri"
PQ = Path("/workspace/data/sources/image-lab/brain-mri-aiomar/data/test-00000-of-00001.parquet")
REPO = "https://huggingface.co/datasets/AIOmarRehan/Brain_Tumor_MRI_Dataset"
NAMES = {0: "glioma", 1: "meningioma", 2: "no tumour", 3: "pituitary tumour"}
PER_CLASS = {0: 6, 1: 6, 2: 7, 3: 6}
QUESTION = "Which type of brain tumour is shown, if any?"
NOTE = ("research benchmark, not for clinical use. Mirror is the Kaggle 'Brain Tumor MRI' set (Figshare + SARTAJ + Br35H); "
        "card says some SARTAJ glioma labels were wrong and were replaced from Figshare.")

_rows = None

def rows():
    global _rows
    if _rows is None:
        _rows = pq.read_table(PQ).to_pylist()
    return _rows

def select():
    rs = rows()
    rng = random.Random(SEED)
    picked = []
    for cls, n in PER_CLASS.items():
        idx = [i for i, r in enumerate(rs) if r["label"] == cls and Image.open(io.BytesIO(r["image"]["bytes"])).size[0] >= 200]
        rng.shuffle(idx)
        picked += idx[:n]
    rng.shuffle(picked)
    return picked

def rederive(item):
    i = int(item["provenance"]["source_id"].split()[2])
    return NAMES[rows()[i]["label"]]

def build():
    rs = rows()
    out = []
    for n, i in enumerate(select()):
        r = rs[i]
        rel = save_image(Image.open(io.BytesIO(r["image"]["bytes"])), TASK, n)
        question, labels, expected = make_choice(QUESTION, list(NAMES.values()), NAMES[r["label"]], SEED * 1000 + n)
        out.append({
            "id": f"{TASK}-{n:03d}", "family": TASK, "state": "An image is attached.",
            "images": [rel], "question": question, "labels": labels, "expected": expected,
            "split": "public", "group": None,
            "provenance": provenance(
                "AIOmarRehan/Brain_Tumor_MRI_Dataset (test split)",
                f"test row {i} ({r['image'].get('path')})", REPO, "CC0-1.0 (as stated on the mirror card)",
                "dataset class label (class_label column 'label'), from Figshare/SARTAJ/Br35H sources", notes=NOTE),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out

if __name__ == "__main__":
    print("wrote", len(build()))
