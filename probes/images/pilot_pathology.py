"""Pilot set for the pathology patch task (PCam test shard 0): 50 tumour, 50 not, seed 4501, avoiding the rows t45 uses.
Images upscaled 96 -> 384 px (Lanczos). RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE.
    /workspace/kev/.venv/bin/python pilot_pathology.py
"""
import io, json, random, sys
from collections import Counter
from pathlib import Path
from PIL import Image

sys.path.insert(0, "/workspace/probes/images")
import build_t45_pathology_patch as t45

OUT = Path("/workspace/probes/images/pilots/pathology.jsonl")
IMGDIR = Path("/workspace/data/image-lab/pilot/pathology")


def stats(im):
    rgb = im.convert("RGB"); g = list(rgb.convert("L").getdata()); s = list(rgb.convert("HSV").getdata())
    n = len(g)
    return {"mean_brightness": round(sum(g) / n / 255, 4),
            "empty_fraction": round(sum(v >= 230 for v in g) / n, 4),
            "mean_saturation": round(sum(p[1] for p in s) / n / 255, 4)}


def main():
    lab = t45.labels(); used = set(t45.select())
    yes = [i for i, v in enumerate(lab) if v == 1 and i not in used]
    no = [i for i, v in enumerate(lab) if v == 0 and i not in used]
    rng = random.Random(4501)
    pick = rng.sample(yes, 50) + rng.sample(no, 50); rng.shuffle(pick)
    IMGDIR.mkdir(parents=True, exist_ok=True); OUT.parent.mkdir(exist_ok=True)
    rows = []
    for n, idx in enumerate(pick):
        row = t45.get_row(idx)
        im = Image.open(io.BytesIO(row["image"]["bytes"])).convert("RGB")
        meta = {"label": int(row["label"]), "original_width": im.width, "original_height": im.height, "row_index": idx, **stats(im)}
        p = IMGDIR / f"{n:03d}.jpg"
        im.resize((384, 384), Image.LANCZOS).save(p, quality=92)
        rows.append({"id": f"pathology-{n:03d}", "image": str(p),
                     "question": {"type": "noul", "instructions": "Does this lymph-node tissue patch contain tumour (metastasis)?"},
                     "labels": ["no", "yes"], "expected": "yes" if row["label"] == 1 else "no", "source_id": f"row {idx}", "meta": meta})
    OUT.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n")
    print(len(rows), dict(Counter(r["expected"] for r in rows)))


if __name__ == "__main__":
    main()
