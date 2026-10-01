"""CountBench: the blank in the caption is the dataset's number field. Local use only."""
import io
import random
import re
import sys
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_choice, provenance, save_image

SEED = 14
TASK = "t14_count_items"
SRC = next(Path("/workspace/data/sources/image-lab/countbench/data").glob("*.parquet"))
URL = "https://huggingface.co/datasets/nielsr/countbench"
WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}
_TABLE = None

def table():
    global _TABLE
    if _TABLE is None:
        _TABLE = pq.read_table(SRC).to_pylist()
    return _TABLE

def match_span(text, num):
    return re.search(rf"\b({WORDS[num]}|{num})\b", text or "", re.I)

def masked(text, num):
    m = match_span(text, num)
    if not m:
        return None
    return text[:m.start()] + "___" + text[m.end():]

def eligible():
    by_n = {n: [] for n in range(2, 11)}
    for i, row in enumerate(table()):
        num = row.get("number")
        img = row.get("image")
        if num not in WORDS or not img or not img.get("bytes"):
            continue
        if masked(row.get("text") or "", num) is None:
            continue
        by_n[num].append(i)
    return by_n

def select():
    rng = random.Random(SEED)
    order = list(range(2, 11))
    rng.shuffle(order)
    by_n = eligible()
    for n in by_n:
        rng.shuffle(by_n[n])
    chosen = []
    for rank, n in enumerate(order):
        need = 3 if rank < 7 else 2
        if len(by_n[n]) < need:
            raise RuntimeError(f"number {n} has {len(by_n[n])} rows, need {need}")
        chosen.extend((i, n) for i in by_n[n][:need])
    chosen.sort(key=lambda pair: (pair[1], pair[0]))
    return chosen

def rederive(item):
    idx = int(str(item["provenance"]["source_id"]).split()[-1])
    row = table()[idx]
    num = row["number"]
    if masked(row.get("text") or "", num) is None:
        return None
    return str(num)

def build():
    chosen = select()
    out = []
    for n, (i, num) in enumerate(chosen):
        row = table()[i]
        question_text = (
            'A caption for this photo reads: "'
            + masked(row["text"], num)
            + '". Which number belongs in the blank?'
        )
        options = [str(x) for x in range(2, 11)]
        question, labels, expected = make_choice(question_text, options, str(num), SEED + i)
        im = Image.open(io.BytesIO(row["image"]["bytes"]))
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
                "CountBench (Paiss et al.), train split",
                f"row {i}",
                URL,
                "not stated, local use only",
                "number",
                notes="number",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out

if __name__ == "__main__":
    print("wrote", len(build()))
