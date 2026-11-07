"""T41 hunt (bundle B22): five sparse traits, each asked on 80 keyword ranked items + 40 random items from the unlabelled pool, wordings of specs/traits_r1b_candidates.json unchanged. Pre-registered after L908.
    /workspace/kev/.venv/bin/python -I bundle_traits_r1_hunt.py"""
import hashlib, json, os, random, re, sys
sys.path.insert(0, "/workspace/jevbench"); from jevbench.tasks import Task, write_jsonl, dataset_hash
W = "/workspace/knowledge_pipeline/projects/world-state"; OUT = f"{W}/runs/xtest/B22"; os.makedirs(OUT, exist_ok=True)
KW = {
    "t_x024r1": r"\b(agreement|agreed|deal|ceasefire|cease-fire|truce|settlement|settled|signed|treaty|accord|pact)\b",
    "t_x026r1": r"\b(damage[sd]?|destroyed|collapsed|collapse|flooded|bridge|power lines?|outage|razed|wrecked|rubble|infrastructure)\b",
    "t_x027r1": r"\b(shortage[s]?|short of|scarcity|ran out|run out|famine|rationing|rationed|blackout|no (?:food|water|fuel|electricity))\b",
    "t_x028r1": r"\b(outbreak|epidemic|pandemic|contaminat\w+|e\. ?coli|salmonella|listeria|cholera|measles|virus spreads?|cases (?:rise|rose|surge))\b",
    "t_x030r1": r"\b(riot[s]?|looting|looted|clashes|clashed|coup|unrest|tear gas|curfew|stormed|ransacked)\b",
}
Q = {t: {"question": v["question"]} for t, v in json.load(open(f"{W}/specs/traits_r1b_candidates.json")).items() if t in KW}
b18 = {json.loads(l)["id"] for l in open(f"{W}/runs/xtest/B18/items.jsonl")}
txt = {}
for p in ("data/pool_train.jsonl", "runs/pulse/queue_texts.jsonl"):
    for l in open(f"{W}/{p}", encoding="utf-8"):
        r = json.loads(l); txt[r["id"]] = r["text"]
pool = sorted(i for i in txt if i not in b18); rng = random.Random(20261105); tasks = []; items = {}; sel = {}
for t, pat in KW.items():
    rx = re.compile(pat, re.I); score = {i: len(rx.findall(txt[i])) for i in pool}
    hits = [i for i in pool if score[i] > 0]; hits.sort(key=lambda i: (-score[i], i)); top = hits[:80]; tset = set(top)
    rnd = rng.sample([i for i in pool if i not in tset], 40); sel[t] = {"top": top, "random": rnd, "keyword_hit_items_in_pool": len(hits)}
    for kind, ids in (("top", top), ("random", rnd)):
        for i in ids:
            items[i] = txt[i]
            tasks.append(Task(id=f"{t}:{i}", family=t, state=txt[i], question={"type": "noul", "instructions": Q[t]["question"]}, labels=["no", "yes"], expected=None, split="private", group=f"{t}:{i}", provenance={"bundle": "B22", "variant": "A", "item": i, "stratum": kind}))
for t in tasks: t.validate()
write_jsonl(tasks, f"{OUT}/tasks_A.jsonl"); write_jsonl([], f"{OUT}/tasks_P.jsonl")
with open(f"{OUT}/items.jsonl", "w") as f:
    for i, x in items.items(): f.write(json.dumps({"id": i, "text": x}) + "\n")
json.dump(sel, open(f"{OUT}/selection.json", "w"))
H = lambda s: hashlib.sha256(s.encode()).hexdigest(); F = list(KW)
b = {"id": "B22", "guideline_file": "specs/traits_r1b_candidates.json", "guideline_sha256": H(open(f"{W}/specs/traits_r1b_candidates.json").read()), "n_items": len(items), "n_tasks": len(tasks), "fields": F, "dataset_hash": {"A": dataset_hash(tasks), "P": None}, "instruction_sha256": {"A": {t: H(Q[t]["question"]) for t in F}}, "question_types": {t: "noul" for t in F}, "selection": "80 keyword ranked + 40 random unlabelled pool items per trait, seed 20261105, B18 items excluded", "decoding_contract": {"temperature": 0, "reasoning": "off or declared equal", "structured_output": "same label set for all"}}
json.dump(b, open(f"{OUT}/bundle.json", "w"), indent=1); print("B22", len(items), "items,", len(tasks), "tasks;", {t: v["keyword_hit_items_in_pool"] for t, v in sel.items()})
