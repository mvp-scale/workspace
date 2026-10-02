"""Pilot set for retinal OCT (Kermany et al. 2018 test split, same source and labels as build_t43_retina.py).
RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE.   /workspace/kev/.venv/bin/python pilot_retina.py"""
import io, json, random
from collections import Counter
from pathlib import Path
import pyarrow.parquet as pq
from PIL import Image

PARQ = "/workspace/data/sources/image-lab/kermany-oct/test.parquet"
NAMES = {0: "CNV", 1: "DME", 2: "DRUSEN", 3: "NORMAL"}
QUESTION = "Which finding does this retinal OCT scan show?"
IMGDIR = Path("/workspace/data/image-lab/pilot/retina")
OUT = Path("/workspace/probes/images/pilots/retina.jsonl")
SEED = 4301
PER_CLASS = 25

t = pq.read_table(PARQ)
imgs, labs = t.column("image").to_pylist(), t.column("label").to_pylist()
rows = [(imgs[i]["path"], NAMES[labs[i]], imgs[i]["bytes"]) for i in range(t.num_rows)]
rng = random.Random(SEED)
chosen = []
for cls in NAMES.values():
    pool = sorted(r for r in rows if r[1] == cls)
    rng.shuffle(pool)
    seen, pick = set(), []
    for r in pool:
        pid = r[0].split("-")[1]
        if pid in seen:
            continue
        seen.add(pid); pick.append(r)
        if len(pick) == PER_CLASS:
            break
    chosen += pick
rng.shuffle(chosen)
IMGDIR.mkdir(parents=True, exist_ok=True)
out = []
for i, (path, cls, data) in enumerate(chosen):
    im = Image.open(io.BytesIO(data)).convert("RGB")
    orig = im.size
    if max(im.size) > 1536:
        s = 1536 / max(im.size); im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    p = IMGDIR / f"{i:03d}.jpg"; im.save(p, quality=88)
    order = list(NAMES.values()); random.Random(SEED * 1000 + i).shuffle(order)
    parts = path.rsplit(".", 1)[0].split("-")
    out.append({"id": f"retina-{i:03d}", "image": str(p),
                "question": {"type": "choice", "instructions": QUESTION, "criteria": {l: None for l in order}},
                "labels": order, "expected": cls, "source_id": path,
                "meta": {"label": cls, "patient_id": parts[1], "scan_index": parts[2],
                         "original_size": list(orig), "split": "test"}})
OUT.write_text("\n".join(json.dumps(r, sort_keys=True) for r in out) + "\n")
print(len(out), dict(Counter(r["expected"] for r in out)))
