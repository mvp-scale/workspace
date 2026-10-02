"""Brain MRI pilot (task t47). RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE.
    /workspace/kev/.venv/bin/python pilot_brain.py
"""
import io, json, random, sys
from collections import Counter
from pathlib import Path
from PIL import Image, ImageStat

sys.path.insert(0, "/workspace/probes/images")
import build_t47_brain_mri as t47

OUT = Path("/workspace/probes/images/pilots/brain.jsonl")
IMGDIR = Path("/workspace/data/image-lab/pilot/brain")
GROUP = {"glioma": "intra-axial", "meningioma": "extra-axial", "pituitary tumour": "extra-axial", "no tumour": "none"}


def main():
    rs = t47.rows()
    used = set(t47.select())
    rng = random.Random(4701)
    chosen = []
    for cls, name in t47.NAMES.items():
        idx = [i for i, r in enumerate(rs) if r["label"] == cls]
        fresh = [i for i in idx if i not in used]; old = [i for i in idx if i in used]
        rng.shuffle(fresh); rng.shuffle(old)
        chosen += (fresh + old)[:25]
    rng.shuffle(chosen)
    IMGDIR.mkdir(parents=True, exist_ok=True)
    out = []
    for n, i in enumerate(chosen):
        r = rs[i]; lab = t47.NAMES[r["label"]]
        im = Image.open(io.BytesIO(r["image"]["bytes"]))
        w, h, mode = im.width, im.height, im.mode
        rgb = im.convert("RGB")
        gray = rgb.convert("L")
        bright = ImageStat.Stat(gray).mean[0] / 255.0
        is_gray = mode in ("L", "I", "I;16", "LA") or all(
            a == b == c for a, b, c in list(rgb.resize((32, 32)).getdata()))
        if max(rgb.size) > 1536:
            s = 1536 / max(rgb.size); rgb = rgb.resize((round(w * s), round(h * s)), Image.LANCZOS)
        p = IMGDIR / f"{n:03d}.jpg"; rgb.save(p, quality=88)
        order = list(t47.NAMES.values()); random.Random(4700 + n).shuffle(order)
        out.append({"id": f"brain-{n:03d}", "image": str(p),
                    "question": {"type": "choice", "instructions": t47.QUESTION, "criteria": {l: None for l in order}},
                    "labels": order, "expected": lab, "source_id": i,
                    "meta": {"label": lab, "original_width": w, "original_height": h, "original_mode": mode,
                             "is_grayscale": bool(is_gray), "mean_brightness": round(bright, 4),
                             "has_tumour": lab != "no tumour", "tumour_group": GROUP[lab]}})
    OUT.write_text("\n".join(json.dumps(x, sort_keys=True) for x in out) + "\n")
    print(len(out), dict(Counter(x["expected"] for x in out)), "overlap with t47:", len(set(chosen) & used))


if __name__ == "__main__":
    main()
