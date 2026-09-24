"""Build mmlu_<subject>.jsonl (57 files, one per MMLU subject) from the MMLU test split
(HF cais/mmlu, MIT licence). Hendrycks et al. 2021, "Measuring Massive Multitask Language
Understanding". Full test split, no sampling: 14,042 items total across 57 subjects.
Each item keeps its four original options, lettered A-D, matching the site's own
"read the model's own answer-letter scores" technique."""
import os, json
os.environ.setdefault("HF_HOME", "/workspace/data/sources/hf-cache")
from datasets import get_dataset_config_names, load_dataset

LETTERS = ["A", "B", "C", "D"]
RETRIEVED = "2026-09-23"
SOURCE = "MMLU (Hendrycks, Burns, Basart, Zou, Mazeika, Song, Steinhardt, 2021), \"Measuring Massive Multitask Language Understanding\", ICLR 2021"
URL = "https://huggingface.co/datasets/cais/mmlu"

subjects = [s for s in get_dataset_config_names("cais/mmlu") if s not in ("all", "auxiliary_train")]
total = 0
for subject in sorted(subjects):
    d = load_dataset("cais/mmlu", subject, split="test")
    rows = []
    for i, x in enumerate(d):
        choices = x["choices"]
        if len(choices) != 4:
            continue  # every MMLU item has exactly 4 options; defensive skip if that ever isn't true
        letter = LETTERS[x["answer"]]
        crit = dict(zip(LETTERS, [c.strip() for c in choices]))
        rows.append(dict(
            id=f"mmlu_{subject}-test-{i}", family=f"mmlu_{subject}", state=x["question"].strip(),
            question={"type": "choice", "instructions": "Which option is correct?", "criteria": crit},
            labels=LETTERS, expected=letter, split="public", group=None,
            provenance={"exclude_reason": None, "source": SOURCE, "url": URL, "license": "MIT",
                        "retrieved": RETRIEVED, "source_id": f"test[{i}]", "notes": f"subject: {subject}"}))
    with open(f"/workspace/probes/v2/mmlu_{subject}.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    total += len(rows)
    print(f"{subject}: {len(rows)}")
print(f"TOTAL: {total} items across {len(subjects)} subjects")
