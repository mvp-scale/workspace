"""GSA lease scans from SignverOD. Yes when the box list includes the signature id."""
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_yesno, provenance, save_image

TASK = "t04_signature_present"
ROOT = Path("/workspace/data/sources/image-lab/signverod")
ANN = ROOT / "annotations.json"
LEGEND = ROOT / "labelmap.txt"
URL = "https://huggingface.co/datasets/ondrs/signverod"
QUESTION = "Is there a handwritten signature on this page?"

_ANN = None
_LEGEND = None


def legend():
    global _LEGEND
    if _LEGEND is None:
        names = {}
        for line in LEGEND.read_text(encoding="utf-8").splitlines():
            idx, name = line.split(None, 1)
            names[int(idx)] = name
        _LEGEND = names
    return _LEGEND


def signature_id():
    ids = [idx for idx, name in legend().items() if name == "signature"]
    if len(ids) != 1:
        raise RuntimeError(f"signature id not unique in labelmap: {ids}")
    return ids[0]


def records():
    global _ANN
    if _ANN is None:
        _ANN = json.loads(ANN.read_text(encoding="utf-8"))
    return _ANN


def by_path():
    return {row["path"]: row for row in records()}


def has_signature(row):
    return signature_id() in row["categories"]


def rederive(item):
    row = by_path().get(item["provenance"]["source_id"])
    if row is None:
        return None
    return "yes" if has_signature(row) else "no"


def build():
    chosen = records()
    yes = sum(1 for row in chosen if has_signature(row))
    if len(chosen) != 25 or yes != 13:
        raise SystemExit(f"need 25 pages with 13 signatures, found {len(chosen)} and {yes} yes")
    out = []
    for n, row in enumerate(chosen):
        im = Image.open(ROOT / "images" / row["path"])
        rel = save_image(im, TASK, n)
        present = has_signature(row)
        question, labels, expected = make_yesno(
            QUESTION,
            "A handwritten signature is on the page",
            "No handwritten signature is on the page",
            present,
        )
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
                "SignverOD GSA lease pages (ondrs/signverod)",
                row["path"],
                URL,
                "CC0-1.0",
                "objects.category named signature in labelmap.txt",
                notes="GSA scan; Kaggle card CC0-1.0, Hugging Face card Apache-2.0",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print(f"wrote {len(build())}")
