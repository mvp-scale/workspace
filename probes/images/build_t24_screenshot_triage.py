"""ScreenSpot-v2 screenshots. The file labels the pointed-at target as icon or text."""
import json
import random
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_yesno, provenance, save_image

TASK = "t24_screenshot_triage"
SRC = Path("/workspace/data/sources/image-lab/screenspot")
ZIP = SRC / "screenspotv2_image.zip"
URL = "https://huggingface.co/datasets/OS-Copilot/ScreenSpot-v2"
SEED = 24
JSONS = [
    "screenspot_desktop_v2.json",
    "screenspot_mobile_v2.json",
    "screenspot_web_v2.json",
]
_INDEX = None


def records():
    rows = []
    for name in JSONS:
        rows.extend(json.loads((SRC / name).read_text()))
    return rows


def index():
    global _INDEX
    if _INDEX is None:
        found = defaultdict(set)
        for row in records():
            if row.get("data_type") in {"icon", "text"}:
                found[(row["img_filename"], row["instruction"])].add(row["data_type"])
        _INDEX = found
    return _INDEX


def rederive(item):
    image_name, instruction = json.loads(item["provenance"]["source_id"])
    kinds = index()[(image_name, instruction)]
    if kinds == {"icon"}:
        return "yes"
    if kinds == {"text"}:
        return "no"
    raise KeyError(item["provenance"]["source_id"])


def spread(rows, count, rng):
    by_source = defaultdict(list)
    for row in rows:
        by_source[row["data_source"]].append(row)
    keys = list(by_source)
    rng.shuffle(keys)
    picked = []
    while len(picked) < count:
        grew = False
        for key in keys:
            if by_source[key] and len(picked) < count:
                picked.append(by_source[key].pop())
                grew = True
        if not grew:
            break
    if len(picked) < count:
        raise SystemExit(f"only {len(picked)} screenshots, need {count}")
    return picked


def select():
    rng = random.Random(SEED)
    by_image = defaultdict(list)
    for row in records():
        key = (row["img_filename"], row["instruction"])
        if index()[key] <= {"icon", "text"} and len(index()[key]) == 1:
            by_image[row["img_filename"]].append(row)
    one_each = []
    for rows in by_image.values():
        kinds = {row["data_type"] for row in rows}
        if len(kinds) != 1:
            continue
        rng.shuffle(rows)
        one_each.append(rows[0])
    icons = [row for row in one_each if row["data_type"] == "icon"]
    texts = [row for row in one_each if row["data_type"] == "text"]
    rng.shuffle(icons)
    rng.shuffle(texts)
    chosen = spread(icons, 13, rng) + spread(texts, 12, rng)
    rng.shuffle(chosen)
    return chosen


def build():
    names = set(zipfile.ZipFile(ZIP).namelist())
    out_dir = SRC / "picked"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = []
    with zipfile.ZipFile(ZIP) as archive:
        for i, row in enumerate(select()):
            member = f"screenspotv2_image/{row['img_filename']}"
            if member not in names:
                raise SystemExit(f"missing {member}")
            target = out_dir / row["img_filename"]
            if not target.is_file():
                target.write_bytes(archive.read(member))
            instruction = row["instruction"]
            question, labels, expected = make_yesno(
                f'The instruction is: "{instruction}". Is that target an icon?',
                "The target is an icon.",
                "The target is text.",
                row["data_type"] == "icon",
            )
            rel = save_image(Image.open(target), TASK, i)
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
                    "OS screenshots, OS-Copilot/ScreenSpot-v2",
                    json.dumps([row["img_filename"], instruction], ensure_ascii=False),
                    URL,
                    "Apache-2.0",
                    "data_type",
                    notes=f"{row['data_type']}; {row['data_source']}",
                ),
            })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print(f"wrote {len(build())}")
