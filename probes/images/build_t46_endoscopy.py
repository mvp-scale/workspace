"""Endoscopy stills from HyperKvasir labelled images (valid split). Pick one of four findings.
Label = the folder name of the dataset's own expert-labelled class. RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE."""
import random
import sys
import zipfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_choice, provenance, save_image

SEED = 46
TASK = "t46_endoscopy"
ZIP = Path("/workspace/data/sources/image-lab/hyper-kvasir/valid.zip")
URL = "https://huggingface.co/datasets/sahilur/hyper-kvasir-labeled-images"
QUESTION = "Which finding does this endoscopy image show?"
# option name -> source folders (exact HyperKvasir class folders), and how many of the 25
CLASSES = {
    "normal cecum": (["cecum"], 6),
    "polyp": (["polyps"], 7),
    "ulcerative colitis": (["ulcerative-colitis-grade-1", "ulcerative-colitis-grade-2", "ulcerative-colitis-grade-3"], 6),
    "esophagitis": (["esophagitis-a", "esophagitis-b-d"], 6),
}
FOLDER_TO_OPTION = {f: o for o, (fs, _) in CLASSES.items() for f in fs}


def members():
    with zipfile.ZipFile(ZIP) as z:
        return sorted(n for n in z.namelist() if n.endswith(".jpg"))


def answer_of(member):
    return FOLDER_TO_OPTION.get(member.split("/")[-2])


def select():
    names = members()
    rng = random.Random(SEED)
    chosen = []
    for opt, (folders, k) in CLASSES.items():
        pool = [n for n in names if n.split("/")[-2] in folders]
        rng.shuffle(pool)
        chosen += pool[:k]
    rng.shuffle(chosen)
    return chosen


def rederive(item):
    return answer_of(item["provenance"]["source_id"])


def build():
    out = []
    with zipfile.ZipFile(ZIP) as z:
        for n, member in enumerate(select()):
            with z.open(member) as fh:
                im = Image.open(fh)
                im.load()
            rel = save_image(im, TASK, n)
            question, labels, expected = make_choice(QUESTION, list(CLASSES), answer_of(member), SEED * 1000 + n)
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
                    "HyperKvasir labelled images (mirror sahilur/hyper-kvasir-labeled-images), valid.zip",
                    member,
                    URL,
                    "CC-BY-4.0",
                    "class folder assigned by experienced gastrointestinal endoscopists (HyperKvasir, Borgli et al. 2020)",
                    notes="research benchmark, not for clinical use. Class folder: " + member.split("/")[-2],
                ),
            })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print("wrote", len(build()))
