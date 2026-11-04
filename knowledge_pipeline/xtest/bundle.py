"""xtest bundle builder (ledger L676, M1). Turns the frozen guideline file and an item file into jevbench Task records: ONE typed-question structure for every rater (noul or choice, instructions, criteria, exact labels, expected None). Instruction text and criteria are SLICED from the guideline by rule and asserted, never reworded by hand; the only text not from the guideline is the fixed question template per field, recorded in the bundle and hashed.
    python3 bundle.py --guideline specs/world_state_v3b_nosize_sonnet.json --items items.jsonl --design design.json --out runs/xtest/B1
Items: {"id","text"}. Design (optional): {"blind": false, "weights": {id: w}, "strata": {id: name}, "note": "..."}; without a design the bundle says blind:true is NOT claimed unless the caller passes --blind."""
import argparse, hashlib, json, os, re, sys
sys.path.insert(0, "/workspace/jevbench")
from jevbench.tasks import Task, write_jsonl, dataset_hash
H = lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest()
TEMPLATES = {  # the only hand-written text; same for every rater; PARAPHRASE is the meaning-preserving variant used for the sensitivity control
    "A": {"presence": "Under the conditions rule above, would the list of conditions for this item be non-empty? Answer yes or no.", "story": "Under the story_type rule above, which story type fits the main claim of this item?", "topic": "Under the topic rule above, which topic id is the best single fit for this item?", "which": "Under the conditions rule above, which single listed condition does this item report as having changed? Answer none if it reports none.", "direction": "Under the conditions rule above, did the condition this item reports change up, down, or is there none? Answer none if no listed condition changed.", "size": "Under the level rule above, how large is the change this item reports in a listed condition? Answer none if no listed condition changed.",
        "which_c": "Assume this item reports that one listed condition has already changed. Under the conditions rule above, which single listed condition is it?", "direction_c": "Assume this item reports that one listed condition has already changed. Under the conditions rule above, did it go up or down?", "size_c": "Assume this item reports that one listed condition has already changed. Under the level rule above, how large is the change?"},
    "P": {"presence": "Following the conditions rule given above, does this item report at least one listed condition that has already changed? Say yes or no.", "story": "Using the story_type rule given above, what is the story type of the main claim in this item?", "topic": "Using the topic rule given above, name the single topic id that fits this item best.", "which": "Following the conditions rule given above, name the one listed condition this item reports as already changed, or none.", "direction": "Following the conditions rule given above, state whether the reported condition moved up or down, or none if no listed condition changed.", "size": "Following the level rule given above, state the size of the reported change in a listed condition, or none if there is none.",
        "which_c": "Suppose this item reports that a listed condition has already changed. Following the conditions rule given above, name that one condition.", "direction_c": "Suppose this item reports that a listed condition has already changed. Following the conditions rule given above, state whether it moved up or down.", "size_c": "Suppose this item reports that a listed condition has already changed. Following the level rule given above, state how large the change is."},
}
def parse_guideline(g):
    L = g.split("\n"); one = lambda p: next(l for l in L if l.startswith(p))
    ti, ci = next(i for i, l in enumerate(L) if l.startswith("TOPICS")), next(i for i, l in enumerate(L) if l.startswith("CONDITIONS"))
    topics, conds = {}, {}
    for l in L[ti + 1:ci]:
        m = re.match(r"(\w+): (.*)", l)
        if m: topics[m.group(1)] = m.group(2).strip()
    last = ci
    for k in range(ci + 1, len(L)):
        m = re.match(r"(\w+): (.*?) \| up = (.*?) \| down = (.*)", L[k].strip())
        if m: conds[m.group(1)] = f"{m.group(2).strip()} Up: {m.group(3).strip()} Down: {m.group(4).strip()}"; last = k
    tail = "\n".join(l for l in L[last + 1:] if l.strip())
    assert len(topics) == 49 and len(conds) == 38, (len(topics), len(conds))
    st = one("story_type: "); m = re.search(r"'fact' if (.*?)\. 'forecast' if (.*?)\. 'opinion' if (.*?)\. 'unclear' only if (.*)", st); assert m, "story_type paragraph format changed"
    story = {"fact": m.group(1).strip(), "forecast": m.group(2).strip(), "opinion": m.group(3).strip(), "unclear": m.group(4).strip().rstrip(".")}
    cp = one("conditions: "); sents = [s.strip() for s in re.split(r"(?<=\.)\s+", cp[len("conditions: "):]) if s.strip()]
    none_s = next(x.strip() for x in re.split(r"(?<=\.)\s+", one("Be conservative.")) if "leave conditions empty" in x)
    dir_s = next(x.strip() for x in re.split(r"(?<=\.)\s+", cp[len("conditions: "):]) if "direction 'up' means" in x)
    lv = dict(re.findall(r"(\w+) = ([^;]+?)(?=;|$)", one("level: ")[len("level: how large the change is for the people affected: "):])); assert set(lv) == {"minor", "notable", "major", "severe", "extreme"}, lv
    return {"none_s": none_s, "dir_s": dir_s, "levels": {k: v.strip().rstrip(".") for k, v in lv.items()}, "intro": L[0].strip(), "topic_p": one("topic: "), "story_p": st, "cond_p": cp, "level_p": one("level: "), "cons_p": one("Be conservative."), "topics": topics, "conds": conds, "tail": tail, "story": story, "cond_yes": sents[0], "cond_no": " ".join(sents[1:3])}
def instructions(P, field, tpl):
    base = field[:-2] if field.endswith("_c") else field
    if base == "presence": body = [P["intro"], P["cond_p"], P["cons_p"], "CONDITIONS (id: meaning, up, down)\n" + "\n".join(f"{k}: {v}" for k, v in P["conds"].items()), P["tail"]]
    elif base == "story": body = [P["intro"], P["story_p"]]
    elif base == "topic": body = [P["intro"], P["topic_p"]]
    elif base in ("which", "direction"): body = [P["intro"], P["cond_p"], P["cons_p"], "CONDITIONS (id: meaning, up, down)\n" + "\n".join(f"{k}: {v}" for k, v in P["conds"].items()), P["tail"]]
    elif base == "size": body = [P["intro"], P["cond_p"], P["level_p"], P["cons_p"]]
    else: raise ValueError(field)
    return "\n\n".join(body) + "\n\n" + tpl[field]
FIELDS_ALL = ("presence", "story", "topic", "which", "direction", "size", "which_c", "direction_c", "size_c")
def build(guideline_path, items_path, out, design=None, blind=False, fields=("presence", "story", "topic")):
    spec = json.load(open(guideline_path)); g = spec["guideline"]; g = "\n".join(g) if isinstance(g, list) else str(g); P = parse_guideline(g)
    items = [json.loads(l) for l in open(items_path)]; os.makedirs(out, exist_ok=True); tasks = {"A": [], "P": []}
    crit = {"presence": {"true": P["cond_yes"], "false": P["cond_no"]}, "story": P["story"], "topic": P["topics"]}
    crit.update({"which": {**P["conds"], "none": P["none_s"]}, "direction": {"up": re.search(r"'up' means (.*?); 'down'", P["dir_s"]).group(1), "down": re.search(r"'down' means (.*?)\.?$", P["dir_s"]).group(1), "none": P["none_s"]}, "size": {**P["levels"], "none": P["none_s"]}})
    labels = {"presence": ["no", "yes"], "story": list(P["story"]), "topic": list(P["topics"]), "which": list(P["conds"]) + ["none"], "direction": ["up", "down", "none"], "size": list(P["levels"]) + ["none"]}; qtype = {"presence": "noul", **{f: "choice" for f in FIELDS_ALL if f != "presence"}}
    for f in ("which", "direction", "size"): crit[f + "_c"] = {k: v for k, v in crit[f].items() if k != "none"}; labels[f + "_c"] = [x for x in labels[f] if x != "none"]
    for v in "AP":
        for f in fields:
            ins = instructions(P, f, TEMPLATES[v])
            for it in items:
                tasks[v].append(Task(id=f"{f}:{it['id']}", family=f, state=it["text"], question={"type": qtype[f], "instructions": ins, "criteria": crit[f]}, labels=labels[f], expected=None, split="private", group=f"{f}:{it['id']}", provenance={"bundle": os.path.basename(out), "variant": v, "item": it["id"], "stratum": (design or {}).get("strata", {}).get(it["id"])}))
    for v in tasks:
        for t in tasks[v]: t.validate()
        write_jsonl(tasks[v], f"{out}/tasks_{v}.jsonl")
    bundle = {"id": os.path.basename(out), "guideline_file": guideline_path, "guideline_sha256": H(g), "items_file": items_path, "items_sha256": H(open(items_path).read()), "n_items": len(items),
              "templates_sha256": {v: H(json.dumps(TEMPLATES[v], sort_keys=True)) for v in TEMPLATES}, "instruction_sha256": {v: {f: H(instructions(P, f, TEMPLATES[v])) for f in fields} for v in "AP"},
              "dataset_hash": {v: dataset_hash(tasks[v]) for v in tasks}, "question_types": qtype, "labels_n": {f: len(labels[f]) for f in fields}, "fields": list(fields),
              "decoding_contract": {"temperature": 0, "reasoning": "off or declared equal", "structured_output": "same label set for all; schema where supported, declared where not"},
              "selection": {"blind": bool(blind), "design": design or None}}
    json.dump(bundle, open(f"{out}/bundle.json", "w"), indent=1); return bundle
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--guideline", required=True); ap.add_argument("--items", required=True); ap.add_argument("--out", required=True); ap.add_argument("--design"); ap.add_argument("--blind", action="store_true"); ap.add_argument("--fields", nargs="+", default=["presence", "story", "topic"]); a = ap.parse_args()
    b = build(a.guideline, a.items, a.out, json.load(open(a.design)) if a.design else None, a.blind, tuple(a.fields)); print(json.dumps({k: b[k] for k in ("id", "n_items", "guideline_sha256", "dataset_hash", "labels_n")}, indent=1))
