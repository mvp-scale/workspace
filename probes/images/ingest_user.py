"""Turn /workspace/data/image-lab/user/<task_id>/ into a task jsonl. There are no photos yet; do not run this."""
import csv
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, "/workspace/probes/v2")
sys.path.insert(0, "/workspace/probes/images")
from _common import write
from _imgcommon import make_choice, make_yesno, provenance, save_image

USER = Path("/workspace/data/image-lab/user")
OUT = Path("/workspace/probes/images")

TASKS = {
    "t11_property_damage": {
        "kind": "yesno",
        "question": "Is there visible damage to the roof or walls?",
        "yes": "Damage to the roof or walls is visible",
        "no": "No damage to the roof or walls is visible",
        "answers": ["no", "yes"],
    },
    "t12_package_condition": {
        "kind": "choice",
        "question": "What is the condition of this package?",
        "answers": ["intact", "dented", "crushed", "open or torn"],
    },
    "t20_floor_hazard": {
        "kind": "yesno",
        "question": "Is there a spill or object on the floor that could cause a fall?",
        "yes": "A spill or object on the floor could cause a fall",
        "no": "The floor has no spill or object that could cause a fall",
        "answers": ["no", "yes"],
    },
    "t22_gauge_reading": {
        "kind": "choice_options",
        "question": "What value does the gauge show?",
    },
    "t25_room_type": {
        "kind": "choice",
        "question": "What kind of room or view is this?",
        "answers": ["kitchen", "bathroom", "bedroom", "living room", "exterior"],
    },
}

def load_csv(folder):
    path = folder / "labels.csv"
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows or not {"image", "question_id", "answer"} <= set(rows[0]):
        raise SystemExit("labels.csv needs columns image, question_id, answer")
    return rows

def build(task_id):
    spec = TASKS[task_id]
    folder = USER / task_id
    rows = load_csv(folder)
    out = []
    for n, row in enumerate(rows):
        image_path = folder / row["image"]
        if not image_path.is_file():
            raise SystemExit(f"missing photo {image_path}")
        answer = row["answer"].strip()
        if spec["kind"] == "yesno":
            if answer not in spec["answers"]:
                raise SystemExit(f"{row['image']}: answer must be no or yes")
            question, labels, expected = make_yesno(spec["question"], spec["yes"], spec["no"], answer == "yes")
        elif spec["kind"] == "choice":
            if answer not in spec["answers"]:
                raise SystemExit(f"{row['image']}: answer not in {spec['answers']}")
            question, labels, expected = make_choice(spec["question"], spec["answers"], answer, n)
        else:
            options = [part.strip() for part in (row.get("options") or "").split("|") if part.strip()]
            if len(options) != 4 or answer not in options or len(set(options)) != 4:
                raise SystemExit(f"{row['image']}: options must be four pipe-separated values including the answer")
            question, labels, expected = make_choice(spec["question"], options, answer, n)
        rel = save_image(Image.open(image_path), task_id, n)
        out.append({
            "id": f"{task_id}-{n:03d}",
            "family": task_id,
            "state": "An image is attached.",
            "images": [rel],
            "question": question,
            "labels": labels,
            "expected": expected,
            "split": "public",
            "group": None,
            "provenance": provenance(
                f"user folder {task_id}",
                row["image"],
                folder.as_uri(),
                "supplied by user",
                "supplied by user",
                notes=f"question_id={row['question_id']}",
            ),
        })
    write(OUT / f"{task_id}.jsonl", out)
    return out

def main():
    if len(sys.argv) != 2 or sys.argv[1] not in TASKS:
        raise SystemExit("usage: python ingest_user.py <task_id>")
    print("wrote", len(build(sys.argv[1])))

if __name__ == "__main__":
    main()
