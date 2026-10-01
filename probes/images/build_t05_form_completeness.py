"""Forms drawn by render_form. The label is the value passed into the drawing, replayed by seed."""
import random
import sys
from pathlib import Path

sys.path.insert(0, "/workspace/probes/vision")
sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from business import degrade, render_form
from _common import write
from _imgcommon import make_choice, make_yesno, provenance, save_image

SEED = 5
TASK = "t05_form_completeness"
TYPES = ["signed", "terms", "named", "two_or_more", "count"]
LEVELS = ["clean", "skew", "lowres", "scan"]
YES = {
    "signed": [True, True, True, False, False],
    "terms": [True, True, False, False, False],
    "named": [True, True, True, False, False],
    "two_or_more": [True, True, False, False, False],
}
URL = "file:///workspace/probes/vision/business.py"

def plan(i):
    return TYPES[i % 5], LEVELS[i % 4], i // 5

def realize(i):
    kind, level, occ = plan(i)
    for attempt in range(2000):
        rng = random.Random(f"{SEED}-{i}-{attempt}")
        kwargs = {}
        if kind in ("signed", "terms", "named"):
            kwargs[kind] = YES[kind][occ]
        im, fields = render_form(rng, **kwargs)
        if kind == "count" and fields["count"] != occ:
            continue
        if kind == "two_or_more" and ((fields["count"] >= 2) != YES[kind][occ]):
            continue
        return degrade(im, level, rng), fields, kind, level
    raise RuntimeError(f"no draw for item {i}")

def answer(kind, fields):
    if kind == "signed":
        return "yes" if fields["signed"] else "no"
    if kind == "terms":
        return "yes" if fields["terms"] else "no"
    if kind == "named":
        return "yes" if fields["named"] else "no"
    if kind == "two_or_more":
        return "yes" if fields["count"] >= 2 else "no"
    if kind == "count":
        return str(fields["count"])
    raise ValueError(kind)

def question_for(kind, fields):
    if kind == "signed":
        return make_yesno(
            "Has the form been signed?",
            "The signature box contains a signature",
            "The signature box is empty",
            fields["signed"],
        )
    if kind == "terms":
        return make_yesno(
            "Is the box for accepting the terms ticked?",
            "The terms checkbox is ticked",
            "The terms checkbox is empty",
            fields["terms"],
        )
    if kind == "named":
        return make_yesno(
            "Is the full name field filled in?",
            "A name is written on the full name line",
            "The full name line is blank",
            fields["named"],
        )
    if kind == "two_or_more":
        return make_yesno(
            "Are two or more checkboxes ticked?",
            "At least two checkboxes are ticked",
            "Fewer than two checkboxes are ticked",
            fields["count"] >= 2,
        )
    return make_choice(
        "How many checkboxes are ticked?",
        ["0", "1", "2", "3", "4"],
        str(fields["count"]),
        SEED + fields["count"],
    )

def rederive(item):
    i = int(str(item["provenance"]["source_id"]).split()[-1])
    _, fields, kind, _level = realize(i)
    return answer(kind, fields)

def build():
    out = []
    for i in range(25):
        im, fields, kind, level = realize(i)
        question, labels, expected = question_for(kind, fields)
        rel = save_image(im, TASK, i)
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
                "generated with render_form and degrade from probes/vision/business.py",
                f"item {i}",
                URL,
                "generated in this workspace",
                "generator value",
                notes=f"{kind} {level}",
            ),
        })
    write(Path(__file__).resolve().parent / f"{TASK}.jsonl", out)
    return out

if __name__ == "__main__":
    print("wrote", len(build()))
