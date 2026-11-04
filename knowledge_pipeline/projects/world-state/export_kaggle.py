"""P8 export: runs/*/labels.jsonl -> a training set (train/dev) with a manifest. Local only; the upload to a PRIVATE Kaggle dataset is a separate, asked step.
usage: export_kaggle.py <out_dir> <label_dir>...   Splits by hash of the item id (90/10). Never includes the frozen test, its near-duplicates, or items without a label."""
import hashlib, json, pathlib, sys, collections
H = pathlib.Path(__file__).resolve().parent; out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
test = {r.get("id") or r.get("item_id") for r in J(H / "data/pilot300.jsonl")}; bad = set((H / "runs/p4/exclude_near_dups_of_test.txt").read_text().split())
pool = {r["id"]: r for r in J(H / "data/pool_train.jsonl")}; rows, seen, skipped = [], set(), collections.Counter()
for d in sys.argv[2:]:
    for r in J(pathlib.Path(d) / "labels.jsonl"):
        i = r["item_id"]
        if i in seen: skipped["duplicate"] += 1; continue
        if i in test or i in bad: skipped["test_or_near_dup"] += 1; continue
        if i not in pool: skipped["not_in_pool"] += 1; continue
        seen.add(i); L = r["label"]
        rows.append({"id": i, "text": pool[i]["text"], "topic": L["topic"], "story_type": L["story_type"], "claim": L.get("claim"), "conditions": L["conditions"],
                     "teacher": r["provenance"]["model"], "prompt_version": r["provenance"]["prompt_version"]})
dev = lambda i: int(hashlib.sha256(i.encode()).hexdigest(), 16) % 10 == 0
split = {"train": [r for r in rows if not dev(r["id"])], "dev": [r for r in rows if dev(r["id"])]}; files = {}
for k, v in split.items():
    p = out / f"{k}.jsonl"; p.write_text("".join(json.dumps(r) + "\n" for r in v)); files[k] = {"items": len(v), "sha8x2": hashlib.sha256(p.read_bytes()).hexdigest()[:16]}
cc = collections.Counter(c["condition"] for r in rows for c in r["conditions"])
m = {"items": len(rows), "files": files, "skipped": dict(skipped), "overlap_with_frozen_test": len({r["id"] for r in rows} & test), "overlap_with_near_dups": len({r["id"] for r in rows} & bad),
     "teachers": sorted({r["teacher"] for r in rows}), "prompt_versions": sorted({r["prompt_version"] for r in rows}), "per_condition": dict(cc.most_common())}
(out / "manifest.json").write_text(json.dumps(m, indent=1)); print(json.dumps({k: v for k, v in m.items() if k != "per_condition"}, indent=1))
