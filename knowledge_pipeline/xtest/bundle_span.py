"""T40 step 2 part 2: bundle B15 from runs/xtest/B15_quotes.json. For every VALID quote two tasks per trait question: the quote alone (item id suffix |span) and a same-length random window of the same item (|rand). Same question wording as bundle_traits (variant A).
    /workspace/kev/.venv/bin/python -I bundle_span.py"""
import hashlib, json, os, sys
sys.path.insert(0, "/workspace/jevbench"); from jevbench.tasks import Task, write_jsonl, dataset_hash
W = "/workspace/knowledge_pipeline/projects/world-state"; BID = os.environ.get("SPAN_BUNDLE_ID", "B15"); OUT = f"{W}/runs/xtest/{BID}"; os.makedirs(OUT, exist_ok=True); QUOTES = os.environ.get("SPAN_OUT", "runs/xtest/B15_quotes.json")
Qs = json.load(open(f"{W}/{QUOTES}")); Q = ({t: v["question"] for t, v in json.load(open(os.environ["SPAN_QFILE"])).items()} if os.environ.get("SPAN_QFILE") else {"t_" + x["id"]: x["question"] for x in json.load(open(f"{W}/specs/traits_v0.json"))["questions"]})
tasks = []
for o in Qs:
    if not o["valid"]: continue
    for kind, state in (("span", o["quote"]), ("rand", o["control"])):
        iid = f"{o['item']}|{kind}"
        tasks.append(Task(id=f"{o['trait']}:{iid}", family=o["trait"], state=state, question={"type": "noul", "instructions": Q[o["trait"]]}, labels=["no", "yes"], expected=None, split="private", group=f"{o['trait']}:{iid}", provenance={"bundle": BID, "variant": "A", "item": iid, "stratum": kind}))
for t in tasks: t.validate()
write_jsonl(tasks, f"{OUT}/tasks_A.jsonl"); write_jsonl([], f"{OUT}/tasks_P.jsonl")
H = lambda s: hashlib.sha256(s.encode()).hexdigest(); F = sorted({o["trait"] for o in Qs})
b = {"id": BID, "guideline_file": "specs/traits_v0.json", "guideline_sha256": H(open(f"{W}/specs/traits_v0.json").read()), "n_tasks": len(tasks), "fields": F, "dataset_hash": {"A": dataset_hash(tasks), "P": None}, "instruction_sha256": {"A": {t: H(Q[t]) for t in F}}, "question_types": {t: "noul" for t in F}, "decoding_contract": {"temperature": 0, "reasoning": "off or declared equal", "structured_output": "same label set for all"}}
json.dump(b, open(f"{OUT}/bundle.json", "w"), indent=1); print(BID, len(tasks), "tasks", F)
