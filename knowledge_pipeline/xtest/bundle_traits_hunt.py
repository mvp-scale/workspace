"""T36 step 4 part B: xtest bundle B13 for the 19 hunted traits. Each trait is asked only on its own 80 items (40 top ranked, 40 random), variant A wording of specs/traits_v0.json unchanged. 
    /workspace/kev/.venv/bin/python -I bundle_traits_hunt.py   (selection from runs/xtest/B13_selection.json)"""
import hashlib, json, os, sys
sys.path.insert(0, "/workspace/jevbench"); from jevbench.tasks import Task, write_jsonl, dataset_hash
W = "/workspace/knowledge_pipeline/projects/world-state"; OUT = f"{W}/runs/xtest/B13"; os.makedirs(OUT, exist_ok=True)
S = json.load(open(f"{W}/runs/xtest/B13_selection.json")); Q = {"t_" + x["id"]: x for x in json.load(open(f"{W}/specs/traits_v0.json"))["questions"]}
txt = {}
for p in ("data/pool_train.jsonl", "runs/pulse/queue_texts.jsonl"):
    for l in open(f"{W}/{p}", encoding="utf-8"):
        r = json.loads(l); txt[r["id"]] = r["text"]
tasks = []; items = {}; kind = {}
for t, v in S["selection"].items():
    for tag in ("top", "random"):
        for i in v[tag]:
            items[i] = txt[i]; kind[f"{t}:{i}"] = tag
            tasks.append(Task(id=f"{t}:{i}", family=t, state=txt[i], question={"type": "noul", "instructions": Q[t]["question"]}, labels=["no", "yes"], expected=None, split="private", group=f"{t}:{i}", provenance={"bundle": "B13", "variant": "A", "item": i, "stratum": tag}))
for t in tasks: t.validate()
write_jsonl(tasks, f"{OUT}/tasks_A.jsonl"); write_jsonl([], f"{OUT}/tasks_P.jsonl")
json.dump(kind, open(f"{OUT}/item_kind.json", "w"))
H = lambda s: hashlib.sha256(s.encode()).hexdigest()
b = {"id": "B13", "guideline_file": "specs/traits_v0.json", "n_items": len(items), "n_tasks": len(tasks), "fields": list(S["selection"]), "dataset_hash": {"A": dataset_hash(tasks)}, "guideline_sha256": H(open(f"{W}/specs/traits_v0.json").read()), "instruction_sha256": {"A": {t: H(Q[t]["question"]) for t in S["selection"]}}, "question_types": {t: "noul" for t in S["selection"]}, "selection": "40 top ranked by a leaf-embedding logistic ranker plus 40 random per trait (traits_hunt.py), enriched sample for reliability only", "decoding_contract": {"temperature": 0, "reasoning": "off or declared equal", "structured_output": "same label set for all"}}
json.dump(b, open(f"{OUT}/bundle.json", "w"), indent=1); print("B13", len(items), "distinct items,", len(tasks), "tasks,", len(S["selection"]), "traits")
