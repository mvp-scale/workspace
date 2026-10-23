#!/bin/bash
# Build the Kaggle push dirs for the checker: data/kaggle/ck_<tag>/{ds,src}. Training rows only (asserted in ck_build.py). Usage: make_push_ck.sh <tag> <repo>
set -e; T=$1; REPO=${2:-intfloat/e5-small-v2}; W=/workspace; B=$W/data/kaggle/ck_$T; H=$W/newsreader/bitmob/checker
[ -e $W/data/progress/STOP ] && { echo "STOP file set"; exit 3; }
mkdir -p $B/ds $B/src; cp $W/data/checker/pairs/{pairs.npz,stories.json,questions.json} $B/ds/
cat > $B/ds/dataset-metadata.json <<J
{"title": "bitmob-ck-train-$T", "id": "coreygorman/bitmob-ck-train-$T", "licenses": [{"name": "other"}], "isPrivate": true}
J
( cat $W/tools/kaggle/guard.py; grep -v PUSH-STRIP $H/ck_common.py; grep -v PUSH-STRIP $H/ck_train.py | sed "s#default=\"intfloat/e5-small-v2\"#default=\"$REPO\"#" ) > $B/src/bitmob-ck-$T.py
cat > $B/src/kernel-metadata.json <<J
{"id": "coreygorman/bitmob-ck-$T", "title": "bitmob-ck-$T", "code_file": "bitmob-ck-$T.py", "language": "python", "kernel_type": "script", "is_private": true, "enable_gpu": true, "enable_tpu": false,
 "enable_internet": true, "keywords": ["gpu"], "dataset_sources": ["coreygorman/bitmob-ck-train-$T"], "kernel_sources": [], "competition_sources": [], "model_sources": [],
 "docker_image": "gcr.io/kaggle-private-byod/python@sha256:2757e0c7d1e0a9cb43da657b97e223c321a98f5014bdf64f44f2f6b083ad2b2f", "machine_shape": "NvidiaTeslaT4"}
J
grep -c "import \*\|from ck_common\|from guard" $B/src/bitmob-ck-$T.py || true
echo built $B
