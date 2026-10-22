"""D-0037 run8 dataset: ds_r5 train rows (frozen test ids already excluded) + full country label + recent/scope binary heads (Jev P >= 0.5).
  kev/.venv/bin/python newsreader/bitmob/build_ds_r8.py"""
import json, glob, collections, os
W = "/workspace/data"; rows = {}
for f in glob.glob(f"{W}/trainset/*.jsonl"):
    for l in open(f):
        try: r = json.loads(l)
        except Exception: continue
        if "id" in r and isinstance(r.get("P"), dict): rows.setdefault(r["id"], r)
ds = [json.loads(l) for l in open(f"{W}/kaggle/ds_r5/train.jsonl")]
# frozen test must be absent
from sklearn.model_selection import train_test_split; import numpy as np
night = [json.loads(l) for l in open(f"{W}/trainset/night1.jsonl")]; _, te = train_test_split(np.arange(len(night)), test_size=0.2, random_state=0)
test_ids = {night[i]["id"] for i in te} | {json.loads(l)["id"] for l in open(f"{W}/trainset/testA.jsonl")}
HEADS = {"recent": "x|recent", "national": "s|national", "local": "s|local", "new": "s|new"}
c = collections.Counter(rows[d["id"]]["country"] for d in ds)
keep = sorted(k for k, n in c.items() if n >= 10); to_other = {k: n for k, n in c.items() if n < 10}
out = []
for d in ds:
    assert d["id"] not in test_ids
    r = rows[d["id"]]; P = r["P"]
    out.append({"id": d["id"], "text": d["text"], "country": r["country"] if r["country"] in keep else "other", "country_raw": r["country"],
                "heads": [int(P.get(HEADS[k], 0) >= 0.5) for k in HEADS]})
keys = {"country_keys": keep + ["other"], "head_keys": list(HEADS)}
os.makedirs(f"{W}/kaggle/ds_r8", exist_ok=True)
open(f"{W}/kaggle/ds_r8/train.jsonl", "w").write("".join(json.dumps(r) + "\n" for r in out)); json.dump(keys, open(f"{W}/kaggle/ds_r8/keys.json", "w"))
json.dump({"classes_ge10": len(keep), "countries_lt10_mapped_to_other": to_other, "rows_to_other": sum(to_other.values()), "n": len(out)}, open(f"{W}/kaggle/ds_r8/country_fallback.json", "w"), indent=1)
json.dump({"title": "bitmob-train-r8", "id": "coreygorman/bitmob-train-r8", "licenses": [{"name": "other"}], "isPrivate": True}, open(f"{W}/kaggle/ds_r8/dataset-metadata.json", "w"))
print(len(out), "rows;", len(keep), "country classes + other;", sum(to_other.values()), "rows in", len(to_other), "small countries ->other")
