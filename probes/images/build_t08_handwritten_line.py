"""IAM lines. The text is the sample's assistant field, used only when it is under 60 characters."""
import json
import random
import sys
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_choice, provenance, save_image

SEED = 8
TASK = "t08_handwritten_line"
ROOT = Path("/workspace/data/sources/image-lab/iam-handwriting")
REPO = "https://huggingface.co/datasets/Voxel51/iam_handwriting_finevision"
QUESTION = "Which text is written in the image?"
_SAMPLES = None

def samples():
    global _SAMPLES
    if _SAMPLES is None:
        _SAMPLES = json.loads((ROOT / "samples.json").read_text())["samples"]
    return _SAMPLES

def text_of(sample):
    a = sample.get("assistant")
    if isinstance(a, str) and a.strip() == a and "\n" not in a and len(a) < 60:
        return a
    return None

def fetch(rel):
    dest = ROOT / rel
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = REPO + "/resolve/main/" + urllib.request.quote(rel)
    req = urllib.request.Request(url, headers={"User-Agent": "image-lab-build"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        dest.write_bytes(resp.read())
    return dest

def pool():
    rows = []
    seen = set()
    for s in samples():
        text = text_of(s)
        if not text or text in seen:
            continue
        seen.add(text)
        rows.append(s)
    return rows

def select():
    rng = random.Random(SEED)
    rows = pool()
    rng.shuffle(rows)
    if len(rows) < 28:
        raise RuntimeError(f"only {len(rows)} short lines")
    return rows[:25], rows

def rederive(item):
    name = item["provenance"]["source_id"]
    for s in samples():
        if s["filepath"] == name:
            return text_of(s)
    return None

def build():
    chosen, all_rows = select()
    texts = [text_of(s) for s in all_rows]
    rng = random.Random(SEED)
    out = []
    for n, sample in enumerate(chosen):
        text = text_of(sample)
        decoys = [t for t in texts if t != text]
        rng.shuffle(decoys)
        options = decoys[:3] + [text]
        question, labels, expected = make_choice(QUESTION, options, text, SEED + n)
        im = Image.open(fetch(sample["filepath"]))
        rel = save_image(im, TASK, n)
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
                "Voxel51/iam_handwriting_finevision",
                sample["filepath"],
                REPO,
                "cc (version not stated), local use only",
                "assistant",
                notes="assistant",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out

if __name__ == "__main__":
    print("wrote", len(build()))
