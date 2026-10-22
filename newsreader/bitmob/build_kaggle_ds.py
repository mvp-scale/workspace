"""Build the private Kaggle training dataset (train rows only; frozen test ids asserted absent). train r3 dataset + extra loop files.
  kev/.venv/bin/python newsreader/bitmob/build_kaggle_ds.py <base_dir with train.jsonl,keys.json> <out_dir> <trainset name>... [--holdout N]   (--holdout: last N rows go to heldout.jsonl for calibration, not trained on)"""
import sys, json, os
base, out = sys.argv[1:3]; names = [a for a in sys.argv[3:] if not a.startswith("--")]; HO = int(sys.argv[sys.argv.index("--holdout") + 1]) if "--holdout" in sys.argv else 0
if HO: names = [n for n in names if n != str(HO)]
W = "/workspace/data/trainset"; L = lambda f: [json.loads(l) for l in open(f)]
rows = L(f"{base}/train.jsonl"); K = json.load(open(f"{base}/keys.json")); ci = {k: i for i, k in enumerate(K["cond_keys"])}; keep = set(K["country_keys"]) - {"other"}
test_ids = {r["id"] for r in L(f"{W}/testA.jsonl")}; night = L(f"{W}/night1.jsonl")
from sklearn.model_selection import train_test_split; import numpy as np
_, te = train_test_split(np.arange(len(night)), test_size=0.2, random_state=0); test_ids |= {night[i]["id"] for i in te}
have = {r["id"] for r in rows}
for n in names:
    for r in L(f"{W}/{n}.jsonl"):
        if r["id"] in have: continue
        assert r["id"] not in test_ids
        c = [0] * len(ci)
        for k in r["target_keys"]:
            if k in ci: c[ci[k]] = 1
        rows.append({"id": r["id"], "text": r["input"], "topic": r["topic"], "type": [int(r["P"].get(f"g|{k}", 0) >= 0.5) for k in K["type_keys"]], "country": r["country"] if r["country"] in keep else "other", "cond": c}); have.add(r["id"])
assert not ({r["id"] for r in rows} & test_ids)
os.makedirs(out, exist_ok=True)
if HO: ho, rows = rows[-HO:], rows[:-HO]; open(f"{out}/heldout.jsonl", "w").write("".join(json.dumps(r) + "\n" for r in ho))
open(f"{out}/train.jsonl", "w").write("".join(json.dumps(r) + "\n" for r in rows)); json.dump(K, open(f"{out}/keys.json", "w")); print(len(rows), "train rows")
