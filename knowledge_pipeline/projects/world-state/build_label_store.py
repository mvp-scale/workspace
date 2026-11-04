"""T21: one label store. Every labels.jsonl under runs/ (world-state labels: topic, story_type, conditions) becomes rows (item_id, labeller, model, prompt_version, run, topic, story_type, n_conditions, kinds). Writes runs/label_store/labels.jsonl and coverage.json. Read-only on sources; no item text. python3 build_label_store.py"""
import json, glob, os, collections
LV = {"minor": 0, "notable": 1, "major": 2, "severe": 3, "extreme": 4}
os.makedirs("runs/label_store", exist_ok=True); rows = 0; cov = collections.defaultdict(set); per = collections.Counter(); seen = set()
with open("runs/label_store/labels.jsonl", "w") as out:
    for f in sorted(glob.glob("runs/**/labels.jsonl", recursive=True)):
        if "label_store" in f: continue
        run = f.rsplit("/", 1)[0]
        for l in open(f):
            try: r = json.loads(l)
            except Exception: continue
            lab = r.get("label") or {}; pv = r.get("provenance") or {}
            if "story_type" not in lab or "topic" not in lab: continue
            model = pv.get("model", "?"); fam = "sonnet" if "sonnet" in model else "haiku" if "haiku" in model else "gemma" if "gemma" in model.lower() else "qwen" if "qwen" in model.lower() else "other"
            key = (r["item_id"], model, pv.get("prompt_version", "?"), run)
            if key in seen: continue
            seen.add(key); c = lab.get("conditions") or []
            out.write(json.dumps({"item_id": r["item_id"], "family": fam, "model": model, "version": pv.get("prompt_version", "?"), "run": run, "topic": lab["topic"], "story_type": lab["story_type"], "n_conditions": len(c), "kinds": [x.get("condition") for x in c], "max_level": max([LV.get(x.get("level"), 0) for x in c], default=-1)}) + "\n")
            rows += 1; cov[(fam, pv.get("prompt_version", "?"))].add(r["item_id"]); per[(fam, pv.get("prompt_version", "?"))] += 1
summ = {f"{k[0]}|{k[1]}": {"rows": per[k], "items": len(v)} for k, v in cov.items()}
items = collections.defaultdict(set)
for (fam, v), s in cov.items():
    for i in s: items[i].add(fam)
both = sum(1 for s in items.values() if "sonnet" in s and "haiku" in s)
json.dump({"rows": rows, "items": len(items), "sonnet_items": sum(1 for s in items.values() if "sonnet" in s), "haiku_items": sum(1 for s in items.values() if "haiku" in s), "sonnet_and_haiku": both, "by_labeller_version": summ}, open("runs/label_store/coverage.json", "w"), indent=1)
print(rows, "rows;", len(items), "items;", "sonnet", sum(1 for s in items.values() if "sonnet" in s), "haiku", sum(1 for s in items.values() if "haiku" in s), "both", both)
for k, v in sorted(summ.items(), key=lambda kv: -kv[1]["items"])[:14]: print(f"  {k:34s} items {v['items']:6d}")
