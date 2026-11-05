"""T36 natural prevalence confirmation (bundle B16): the 11 candidate traits asked on ONE shared random sample of 800 natural queue items (DEVQ) that are not in the 150 item B4 panel set. Variant A wording of specs/traits_v1_candidates.json unchanged.
    /workspace/kev/.venv/bin/python -I bundle_traits_natural.py"""
import hashlib, json, os, random, sys
sys.path.insert(0, "/workspace/jevbench"); from jevbench.tasks import Task, write_jsonl, dataset_hash
W = "/workspace/knowledge_pipeline/projects/world-state"; OUT = f"{W}/runs/xtest/B16"; os.makedirs(OUT, exist_ok=True)
CAND = ["t_x013v1", "t_x031v1"]
Q = {t: {"question": v["question"]} for t, v in json.load(open(f"{W}/specs/traits_v1_candidates.json")).items()}
b4 = {json.loads(l)["id"] for l in open(f"{W}/runs/xtest/B4/items.jsonl")}
txt = {r["id"]: r["text"] for r in map(json.loads, open(f"{W}/runs/pulse/queue_texts.jsonl"))}
devq = [json.loads(l)["id"] for l in open(f"{W}/runs/pulse/devq_items.jsonl")]
pool = sorted(i for i in devq if i in txt and i not in b4); random.Random(20261107).shuffle(pool); ids = pool[:800]
assert not (set(ids) & b4) and len(set(ids)) == 800
tasks = [Task(id=f"{t}:{i}", family=t, state=txt[i], question={"type": "noul", "instructions": Q[t]["question"]}, labels=["no", "yes"], expected=None, split="private", group=f"{t}:{i}", provenance={"bundle": "B16", "variant": "A", "item": i, "stratum": "natural"}) for t in CAND for i in ids]
for t in tasks: t.validate()
write_jsonl(tasks, f"{OUT}/tasks_A.jsonl"); write_jsonl([], f"{OUT}/tasks_P.jsonl")
with open(f"{OUT}/items.jsonl", "w") as f:
    for i in ids: f.write(json.dumps({"id": i, "text": txt[i]}) + "\n")
H = lambda s: hashlib.sha256(s.encode()).hexdigest()
b = {"id": "B16", "guideline_file": "specs/traits_v1_candidates.json", "guideline_sha256": H(open(f"{W}/specs/traits_v1_candidates.json").read()), "n_items": 800, "n_tasks": len(tasks), "fields": CAND, "dataset_hash": {"A": dataset_hash(tasks), "P": None}, "instruction_sha256": {"A": {t: H(Q[t]["question"]) for t in CAND}}, "question_types": {t: "noul" for t in CAND}, "selection": "800 random DEVQ items excluding the 150 B4 items, seed 20261107", "decoding_contract": {"temperature": 0, "reasoning": "off or declared equal", "structured_output": "same label set for all"}}
json.dump(b, open(f"{OUT}/bundle.json", "w"), indent=1); print("B16", len(ids), "items x", len(CAND), "traits =", len(tasks), "tasks")
