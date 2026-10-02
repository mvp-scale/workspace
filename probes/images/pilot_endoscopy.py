"""Endoscopy pilot (HyperKvasir valid.zip), 25 per class, seed 4601. RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE.
    /workspace/kev/.venv/bin/python pilot_endoscopy.py
"""
import io, json, random, sys, zipfile
from collections import Counter
from pathlib import Path
from PIL import Image

sys.path.insert(0, "/workspace/probes/images")
import build_t46_endoscopy as t46

OUT = Path("/workspace/probes/images/pilots/endoscopy.jsonl")
IMGDIR = Path("/workspace/data/image-lab/pilot/endoscopy")
SEED = 4601


def grade_of(folder):
    if folder.startswith("ulcerative-colitis-grade-"): return folder.rsplit("grade-", 1)[1]
    if folder == "esophagitis-a": return "A"
    if folder == "esophagitis-b-d": return "B-D"
    return None


def main():
    IMGDIR.mkdir(parents=True, exist_ok=True)
    names = t46.members()
    rng = random.Random(SEED)
    chosen = []
    for opt, (folders, _) in t46.CLASSES.items():
        pool = [n for n in names if n.split("/")[-2] in folders]
        rng.shuffle(pool)
        chosen += pool[:25]
    rng.shuffle(chosen)
    labels = list(t46.CLASSES)
    out = []
    with zipfile.ZipFile(t46.ZIP) as z:
        for i, m in enumerate(chosen):
            folder = m.split("/")[-2]; lab = t46.answer_of(m)
            im = Image.open(io.BytesIO(z.read(m))).convert("RGB")
            if max(im.size) > 1536:
                s = 1536 / max(im.size); im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
            p = IMGDIR / f"{i:03d}.jpg"; im.save(p, quality=88)
            order = list(labels); random.Random(SEED * 1000 + i).shuffle(order)
            out.append({"id": f"endoscopy-{i:03d}", "image": str(p),
                        "question": {"type": "choice", "instructions": t46.QUESTION, "criteria": {l: None for l in order}},
                        "labels": order, "expected": lab, "source_id": m,
                        "meta": {"class_folder": folder,
                                 "landmark": lab == "normal cecum",
                                 "kind": "landmark" if lab == "normal cecum" else "pathological finding",
                                 "upper_or_lower": "upper" if lab == "esophagitis" else "lower",
                                 "grade": grade_of(folder)}})
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(json.dumps(r, sort_keys=True) for r in out) + "\n")
    print(len(out), dict(Counter(r["expected"] for r in out)), dict(Counter(r["meta"]["class_folder"] for r in out)))


if __name__ == "__main__":
    main()
