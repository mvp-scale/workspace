"""T20 step 0 (ledger L435): carve DEV2 and SEALED item lists from the never-used test-period items. Writes ids, and for DEV2 the item file for Sonnet labelling. SEALED gets ids and a SHA-256 only; its labels are made at step 4.
    python3 make_sets.py     (CPU, no hosted calls)"""
import json, glob, hashlib, random, re, numpy as np, pathlib
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
pool = {r["id"]: r for r in J("data/pool_train.jsonl")}; old = {}; sn = {}
for f in glob.glob("runs/p7/chunk*/labels.jsonl"):
    for r in J(f): old[r["item_id"]] = r["label"]
for f in glob.glob("runs/p7b/*/labels.jsonl"):
    for r in J(f): sn[r["item_id"]] = r["label"]
for f in glob.glob("runs/p6/sonnet/*.jsonl"):
    for r in J(f):
        if "item_id" in r: sn.setdefault(r["item_id"], r.get("label"))
oi = sorted(old); dto = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dto, kind="stable"); o = o[dto[o] != ""]
test = [oi[k] for k in np.array_split(o, 5)[4]]; tset = set(test); start = min(pool[i]["date"] for i in test)
trn = [i for i in old if i not in tset and pool[i]["date"] and pool[i]["date"] < start]
norm = lambda t: re.sub(r"\W+", " ", t.lower()).strip(); h = lambda i: hashlib.sha256(norm(pool[i]["text"]).encode()).hexdigest()
seen = {h(i) for i in trn} | {h(i) for i in test if i in sn}; near = set(pathlib.Path("runs/p4/exclude_near_dups_of_test.txt").read_text().split())
cand = []; dup = 0
for i in sorted(test):
    if i in sn or i in near: continue
    k = h(i)
    if k in seen: dup += 1; continue
    seen.add(k); cand.append(i)
random.Random(20261101).shuffle(cand); sealed, dev2 = cand[:1500], cand[1500:]
out = pathlib.Path("runs/pulse"); out.mkdir(exist_ok=True)
(out / "dev2_items.jsonl").write_text("".join(json.dumps(pool[i]) + "\n" for i in dev2)); (out / "dev2_ids.txt").write_text("\n".join(dev2) + "\n"); (out / "sealed_ids.txt").write_text("\n".join(sealed) + "\n")
sha = hashlib.sha256(("\n".join(sealed) + "\n").encode()).hexdigest()
info = {"test_period_items": len(test), "test_start": start, "train_items": len(trn), "sonnet_labelled_total": len(sn), "sonnet_in_test_period": sum(i in sn for i in test), "candidates_after_dedup": len(cand), "exact_text_twins_dropped": dup, "dev2": len(dev2), "sealed": len(sealed), "sealed_ids_sha256": sha, "dev2_date_range": [min(pool[i]["date"] for i in dev2), max(pool[i]["date"] for i in dev2)], "sealed_date_range": [min(pool[i]["date"] for i in sealed), max(pool[i]["date"] for i in sealed)]}
(out / "sets.json").write_text(json.dumps(info, indent=1)); print(json.dumps(info, indent=1))
