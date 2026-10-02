"""Pilot sets of 100 images for the layered method (skin, dental, chest). Not lab tasks: they live in
/workspace/data/image-lab/pilot/<name>/ and probes/images/pilots/<name>.jsonl, and reuse the same sources and label rules as t40, t44, t42.
RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE.

    /workspace/kev/.venv/bin/python pilots.py skin dental chest
"""
import io, json, random, sys, zipfile
from pathlib import Path
from PIL import Image

sys.path.insert(0, "/workspace/probes/images")
import build_t40_skin_lesion as skin
import build_t44_dental_xray as dental
import build_t42_chest_xray as chest
import pyarrow.parquet as pq

OUTDIR = Path("/workspace/probes/images/pilots")
IMGDIR = Path("/workspace/data/image-lab/pilot")


def save(im, name, i):
    d = IMGDIR / name; d.mkdir(parents=True, exist_ok=True)
    im = im.convert("RGB")
    if max(im.size) > 1536:
        s = 1536 / max(im.size); im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    p = d / f"{i:03d}.jpg"; im.save(p, quality=88)
    return str(p)


def pick_q(question, labels, expected, seed):
    r = random.Random(seed); order = list(labels); r.shuffle(order)
    return {"type": "choice", "instructions": question, "criteria": {l: None for l in order}}, order


def build_skin():
    rows = skin.rows(); cnt = {}
    for r in rows: cnt[r["lesion_id"]] = cnt.get(r["lesion_id"], 0) + 1
    by = {k: [] for k in skin.NAMES}
    for r in rows:
        if skin.label_of(r) and cnt[r["lesion_id"]] == 1: by[r["dx"]].append(r)
    rng = random.Random(4001); chosen = []
    for k in sorted(skin.NAMES):
        by[k].sort(key=lambda r: r["image_id"]); rng.shuffle(by[k]); chosen += by[k][:25]
    rng.shuffle(chosen); out = []
    for i, r in enumerate(chosen):
        lab = skin.label_of(r); q, order = pick_q(skin.QUESTION, list(skin.NAMES.values()), lab, 4000 + i)
        out.append({"id": f"skin-{i:03d}", "image": save(Image.open(skin.fetch(r["image_id"])), "skin", i), "question": q, "labels": order, "expected": lab, "source_id": r["image_id"]})
    return out


def build_dental():
    skin_zip = dental.ZIP
    with zipfile.ZipFile(skin_zip) as z:
        yes, no = [], []
        for s in dental.stems(z): (yes if dental.answer_of(dental.read_label(z, s)) else no).append(s)
        rng = random.Random(4401); rng.shuffle(yes); rng.shuffle(no)
        n = min(50, len(yes), len(no)); pick = yes[:n] + no[:n]; rng.shuffle(pick); out = []
        for i, s in enumerate(pick):
            lab = "yes" if dental.answer_of(dental.read_label(z, s)) else "no"
            out.append({"id": f"dental-{i:03d}", "image": save(Image.open(io.BytesIO(z.read(f"disease/input/{s}.png"))), "dental", i),
                        "question": {"type": "noul", "instructions": "Is there a cavity (caries) visible on this dental X-ray?"}, "labels": ["no", "yes"], "expected": lab, "source_id": s})
    return out


def build_chest():
    table = pq.read_table(chest.SRC).to_pylist(); allr = chest.rows(); rng = random.Random(4201); rng.shuffle(allr)
    seen, yes, no = set(), [], []
    for r in allr:
        p = chest.patient(r[1])
        if p in seen: continue
        seen.add(p); (no if r[2] == 0 else yes).append(r)
    n = min(50, len(yes), len(no)); pick = yes[:n] + no[:n]; rng.shuffle(pick); out = []
    for i, (idx, path, label) in enumerate(pick):
        out.append({"id": f"chest-{i:03d}", "image": save(Image.open(io.BytesIO(table[idx]["image"]["bytes"])), "chest", i),
                    "question": {"type": "noul", "instructions": "Does this chest X-ray show pneumonia or another abnormality?"}, "labels": ["no", "yes"], "expected": "yes" if label == 1 else "no", "source_id": path})
    return out


if __name__ == "__main__":
    OUTDIR.mkdir(exist_ok=True)
    for name in sys.argv[1:]:
        rows = {"skin": build_skin, "dental": build_dental, "chest": build_chest}[name]()
        (OUTDIR / f"{name}.jsonl").write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n")
        from collections import Counter
        print(name, len(rows), dict(Counter(r["expected"] for r in rows)))
