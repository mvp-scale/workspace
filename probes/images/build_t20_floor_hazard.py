"""HD10K test scene 1. A liquid-stain pixel or a solid-waste box is a hazard. Both empty is clean."""
import io
import random
import sys
import zipfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_yesno, provenance, save_image

TASK = "t20_floor_hazard"
ZIP = Path("/workspace/data/sources/image-lab/hd10k/HD10K_IROS2022.zip")
URL = "https://github.com/gaussianopensource/dl_active_cleaning"
SEED = 20
GAP_NS = 3_000_000_000
_FLAGS = None


def has_stain(png_bytes):
    im = Image.open(io.BytesIO(png_bytes))
    extrema = im.getextrema()
    if not extrema:
        return False
    if isinstance(extrema[0], tuple):
        return any(high > 0 for _low, high in extrema)
    return extrema[1] > 0


def timestamp_ns(stem):
    token = stem.split("-")[-1].replace("_keyframe", "")
    return int(token)


def flags():
    global _FLAGS
    if _FLAGS is None:
        z = zipfile.ZipFile(ZIP)
        names = [n for n in z.namelist() if not n.split("/")[-1].startswith("._")]
        images = [
            n for n in names
            if n.startswith("IROS2022_Dataset/test/images/scene_1/") and n.endswith(".jpg")
        ]
        masks = {
            Path(n).stem: n for n in names
            if n.startswith("IROS2022_Dataset/test/liquid_dirts_masks/") and n.endswith(".png")
        }
        boxes = {
            Path(n).stem: n for n in names
            if n.startswith("IROS2022_Dataset/test/solid_dirts_bboxes/") and n.endswith(".txt")
        }
        found = {}
        for name in images:
            stem = Path(name).stem
            text = z.read(boxes[stem]).decode("utf-8")
            hazard = has_stain(z.read(masks[stem])) or any(line.strip() for line in text.splitlines())
            found[name] = (hazard, timestamp_ns(stem))
        z.close()
        _FLAGS = found
    return _FLAGS


def rederive(item):
    name = item["provenance"]["source_id"]
    known = flags()
    if name not in known:
        raise ValueError(f"missing {name}")
    return "yes" if known[name][0] else "no"


def take(pool, n, used, rng):
    rng.shuffle(pool)
    chosen = []
    for name, ts in pool:
        if any(abs(ts - old) < GAP_NS for old in used):
            continue
        chosen.append(name)
        used.append(ts)
        if len(chosen) == n:
            return chosen
    raise SystemExit(f"could only space {len(chosen)} of {n}")


def build():
    if not ZIP.is_file():
        raise SystemExit(f"missing {ZIP}")
    known = flags()
    yes = [(name, ts) for name, (flag, ts) in known.items() if flag]
    no = [(name, ts) for name, (flag, ts) in known.items() if not flag]
    rng = random.Random(SEED)
    used = []
    no_names = take(no, 12, used, rng)
    yes_names = take(yes, 13, used, rng)
    chosen = [(True, name) for name in yes_names] + [(False, name) for name in no_names]
    rng.shuffle(chosen)
    z = zipfile.ZipFile(ZIP)
    out = []
    for i, (flag, name) in enumerate(chosen):
        im = Image.open(io.BytesIO(z.read(name)))
        rel = save_image(im, TASK, i)
        question, labels, expected = make_yesno(
            "Is there a spill or other dirt on this floor?",
            "The stain mask or the waste box file marks dirt.",
            "The stain mask and the waste box file are both empty.",
            flag,
        )
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
                "HD10K test scene 1, gaussianopensource/dl_active_cleaning",
                name,
                URL,
                "not stated, local use only",
                "liquid mask or solid-waste box file",
                notes="nonempty mask or box vs both empty",
            ),
        })
    z.close()
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out


if __name__ == "__main__":
    print(f"wrote {len(build())}")
