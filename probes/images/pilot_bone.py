"""Pilot set of 100 FracAtlas images (50 fractured, 50 not) for the layered method. RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE.
Same source and clean rule as build_t41_bone_fracture.py; seed 4101. Run: /workspace/kev/.venv/bin/python pilot_bone.py"""
import json, random, sys
from collections import Counter
from pathlib import Path
from PIL import Image

sys.path.insert(0, "/workspace/probes/images")
import build_t41_bone_fracture as b

OUT = Path("/workspace/probes/images/pilots/bone.jsonl")
IMGDIR = Path("/workspace/data/image-lab/pilot/bone")
INTS = ("hand", "leg", "hip", "shoulder", "mixed", "hardware", "multiscan", "fractured", "fracture_count", "frontal", "lateral", "oblique")


def main():
    rng = random.Random(4101)
    pool = [r for r in b.rows() if b.clean(r)]
    picked = []
    for flag in (True, False):
        c = [r for r in pool if b.answer_of(r) == flag]
        rng.shuffle(c)
        good = []
        for r in c:
            if b.readable(r): good.append(r)
            if len(good) == 50: break
        picked += good
    rng.shuffle(picked)
    IMGDIR.mkdir(parents=True, exist_ok=True)
    out = []
    for i, r in enumerate(picked):
        im = Image.open(b.img_path(r)).convert("RGB")
        if max(im.size) > 1536:
            s = 1536 / max(im.size); im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        p = IMGDIR / f"{i:03d}.jpg"; im.save(p, quality=88)
        meta = {k: int(r[k]) for k in INTS}
        meta["body_part"] = b.part_of(r)
        meta["views"] = "+".join(b.view_of(r))
        out.append({"id": f"bone-{i:03d}", "image": str(p),
                    "question": {"type": "noul", "instructions": "Does this X-ray show a fracture?"},
                    "labels": ["no", "yes"], "expected": "yes" if b.answer_of(r) else "no",
                    "source_id": r["image_id"], "meta": meta})
    OUT.write_text("\n".join(json.dumps(r, sort_keys=True) for r in out) + "\n")
    print(len(out), dict(Counter(r["expected"] for r in out)), dict(Counter(r["meta"]["body_part"] for r in out)))


if __name__ == "__main__":
    main()
