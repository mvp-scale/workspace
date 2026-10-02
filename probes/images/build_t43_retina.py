"""Retinal OCT B-scans (Kermany et al. 2018, test split). Pick-one: CNV / DME / drusen / normal.
RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE."""
import io
import random
import sys
import urllib.request
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_choice, provenance, save_image

SEED = 43
TASK = "t43_retina"
ROOT = Path("/workspace/data/sources/image-lab/kermany-oct")
PARQ = ROOT / "test.parquet"
REPO = "https://huggingface.co/datasets/zacharielegault/Kermany2017-OCT"
NAMES = {0: "CNV", 1: "DME", 2: "DRUSEN", 3: "NORMAL"}
OPTIONS = {
    "CNV": "choroidal neovascularization (neovascular AMD)",
    "DME": "diabetic macular edema",
    "DRUSEN": "drusen (early AMD)",
    "NORMAL": "normal retina",
}
QUESTION = "Which finding does this retinal OCT scan show?"
PER_CLASS = {"CNV": 7, "DME": 6, "DRUSEN": 6, "NORMAL": 6}


def table():
    if not PARQ.is_file() or PARQ.stat().st_size == 0:
        ROOT.mkdir(parents=True, exist_ok=True)
        url = REPO + "/resolve/main/data/test-00000-of-00001.parquet"
        req = urllib.request.Request(url, headers={"User-Agent": "image-lab-build"})
        with urllib.request.urlopen(req, timeout=300) as r:
            PARQ.write_bytes(r.read())
    return pq.read_table(PARQ)


def rows():
    t = table()
    imgs = t.column("image").to_pylist()
    labs = t.column("label").to_pylist()
    return [(i, imgs[i]["path"], NAMES[labs[i]], imgs[i]["bytes"]) for i in range(t.num_rows)]


def select():
    allr = rows()
    rng = random.Random(SEED)
    chosen = []
    for cls, n in PER_CLASS.items():
        pool = sorted(r for r in allr if r[2] == cls)
        rng.shuffle(pool)
        seen, pick = set(), []
        for r in pool:  # one scan per patient id
            pid = r[1].split("-")[1]
            if pid in seen:
                continue
            seen.add(pid)
            pick.append(r)
            if len(pick) == n:
                break
        chosen += pick
    rng.shuffle(chosen)
    return chosen


def rederive(item):
    fname = item["provenance"]["source_id"]
    for _, path, cls, _ in rows():
        if path == fname:
            return cls
    return None


def build():
    out = []
    for n, (idx, path, cls, data) in enumerate(select()):
        rel = save_image(Image.open(io.BytesIO(data)), TASK, n)
        question, labels, expected = make_choice(QUESTION, list(OPTIONS), cls, SEED * 1000 + n)
        question["criteria"] = {k: OPTIONS[k] for k in labels}
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
                "Kermany et al. 2018 retinal OCT (zacharielegault/Kermany2017-OCT mirror), test split",
                path,
                REPO,
                "CC-BY-4.0 (as stated on the mirror card; original on Mendeley Data rscbjbr9sj)",
                "class in the dataset's own label column, graded by expert ophthalmologists (test split verified by independent graders)",
                notes="research benchmark, not for clinical use",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print("wrote", len(build()))
