"""T41 round 1b (bundle B21): six revised trait wordings (specs/traits_r1b_candidates.json) on the SAME 800 natural items as B16 (same seed). Variant A, wording unchanged.
    /workspace/kev/.venv/bin/python -I bundle_traits_r1.py"""
import hashlib, json, os, random, sys
sys.path.insert(0, "/workspace/jevbench"); from jevbench.tasks import Task, write_jsonl, dataset_hash
W = "/workspace/knowledge_pipeline/projects/world-state"; OUT = f"{W}/runs/xtest/B21"; os.makedirs(OUT, exist_ok=True)
CAND = ["t_x019r1","t_x012r1","t_x020r1","t_x024r1","t_x026r1","t_x027r1","t_x030r1","t_x028r1"]
Q = {t: {"question": v["question"]} for t, v in json.load(open(f"{W}/specs/traits_r1b_candidates.json")).items()}
b4 = {json.loads(l)["id"] for l in open(f"{W}/runs/xtest/B4/items.jsonl")}
txt = {r["id"]: r["text"] for r in map(json.loads, open(f"{W}/runs/pulse/queue_texts.jsonl"))}
devq = [json.loads(l)["id"] for l in open(f"{W}/runs/pulse/devq_items.jsonl")]
pool = sorted(i for i in devq if i in txt and i not in b4); random.Random(20261107).shuffle(pool); ids = pool[:800]
assert not (set(ids) & b4) and len(set(ids)) == 800
tasks = [Task(id=f"{t}:{i}", family=t, state=txt[i], question={"type": "noul", "instructions": Q[t]["question"]}, labels=["no", "yes"], expected=None, split="private", group=f"{t}:{i}", provenance={"bundle": "B21", "variant": "A", "item": i, "stratum": "natural"}) for t in CAND for i in ids]
for t in tasks: t.validate()
write_jsonl(tasks, f"{OUT}/tasks_A.jsonl"); write_jsonl([], f"{OUT}/tasks_P.jsonl")
with open(f"{OUT}/items.jsonl", "w") as f:
    for i in ids: f.write(json.dumps({"id": i, "text": txt[i]}) + "\n")
H = lambda s: hashlib.sha256(s.encode()).hexdigest()
b = {"id": "B21", "guideline_file": "specs/traits_r1b_candidates.json", "guideline_sha256": H(open(f"{W}/specs/traits_r1b_candidates.json").read()), "n_items": 800, "n_tasks": len(tasks), "fields": CAND, "dataset_hash": {"A": dataset_hash(tasks), "P": None}, "instruction_sha256": {"A": {t: H(Q[t]["question"]) for t in CAND}}, "question_types": {t: "noul" for t in CAND}, "selection": "same 800 items as B16 and B18 (DEVQ, excluding B4, seed 20261107)", "decoding_contract": {"temperature": 0, "reasoning": "off or declared equal", "structured_output": "same label set for all"}}
json.dump(b, open(f"{OUT}/bundle.json", "w"), indent=1); print("B21", len(ids), "items x", len(CAND), "traits =", len(tasks), "tasks")
