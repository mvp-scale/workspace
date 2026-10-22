#!/bin/bash
# Build the Kaggle push dirs for a multi-head round (D-0038). Training rows only; refuses any test file.
#   newsreader/bitmob/mh/make_push.sh <round> <labels.jsonl>...      e.g. make_push.sh r1 data/clef-labels/train.jsonl data/clef-labels/country.jsonl
# Makes data/kaggle/mh_<round>/{ds,src}. Then: kaggle datasets create -p ds ; source tools/kaggle.env; tools/kaggle/watch.sh coreygorman/bitmob-mh-<round> data/kaggle/mh_<round>/out 50 60 data/kaggle/mh_<round>/src
set -e; R=$1; shift; W=/workspace; B=$W/data/kaggle/mh_$R; H=$W/newsreader/bitmob/mh
for f in "$@"; do case "$(basename $f)" in *test*) echo "refusing test file $f"; exit 2;; esac; done
rm -rf $B; mkdir -p $B/ds $B/src
$W/kev/.venv/bin/python $H/build_mh_data.py $B/ds "$@"
cat > $B/ds/dataset-metadata.json <<J
{"title": "bitmob-mh-train-$R", "id": "coreygorman/bitmob-mh-train-$R", "licenses": [{"name": "other"}], "isPrivate": true}
J
( cat $W/tools/kaggle/guard.py; grep -v PUSH-STRIP $H/mh_common.py; grep -v PUSH-STRIP $H/train_mh.py ) > $B/src/bitmob-mh-$R.py
cat > $B/src/kernel-metadata.json <<J
{"id": "coreygorman/bitmob-mh-$R", "title": "bitmob-mh-$R", "code_file": "bitmob-mh-$R.py", "language": "python", "kernel_type": "script", "is_private": true, "enable_gpu": true, "enable_tpu": false,
 "enable_internet": true, "keywords": ["gpu"], "dataset_sources": ["coreygorman/bitmob-mh-train-$R"], "kernel_sources": [], "competition_sources": [], "model_sources": [],
 "docker_image": "gcr.io/kaggle-private-byod/python@sha256:2757e0c7d1e0a9cb43da657b97e223c321a98f5014bdf64f44f2f6b083ad2b2f", "machine_shape": "NvidiaTeslaT4"}
J
python3 - <<P
import json,os; ids=set(json.load(open("$B/ds/keys.json"))["ids"]); t="$W/data/clef-labels/test.jsonl"
bad=[json.loads(l)["id"] for l in open(t) if l.strip() and json.loads(l)["id"] in ids] if os.path.exists(t) else []
assert not bad, f"frozen test ids in the dataset: {bad[:3]}"; print("ok: no frozen test id in", len(ids), "training rows")
P
echo "built $B (dataset ds/, kernel src/)"
