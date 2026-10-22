#!/bin/bash
# F-0110: build Kaggle push dirs for the screen-then-check real-Clef run (frozen-test stories only; never rm). Based on kaggle_label_push.sh:  of a slice of an input list (D-0038, D-0040). Test and train datasets are kept separate; a test dataset is never a training input.
#   newsreader/bitmob/kaggle_label_push.sh <input.jsonl> <offset> <n> <name> <dataset-name> [train|test] [workers=4] [label-min=33] [guard-min=45]
# offset: row index into the input; a NEGATIVE offset -K counts from the END (rows[len-K-n : len-K]), so the captain can work downward from the end.
# Skips ids already labelled (any data/clef-labels/*.jsonl that is not an *_in file). kind=train refuses any frozen-test id; kind=test accepts only test_in ids.
# Output convention (copy from the kernel output dir): data/clef-labels/kaggle_<name>.jsonl
# Does NOT launch. Launch (check data/progress/STOP absent first!):
#   kaggle datasets create -p $B/ds ; source tools/kaggle.env ; tools/kaggle/watch.sh coreygorman/bitmob-screenk-<name> $B/out 50 60 $B/src
set -e; IN=$1; OFF=$2; N=$3; NAME=$4; DS=$5; KIND=${6:-train}; WK=${7:-4}; LM=${8:-33}; GM=${9:-45}; W=/workspace; B=$W/data/kaggle/screen_$NAME
[ -e $W/data/progress/STOP ] && { echo "STOP file present: not building"; exit 3; }
[ -e $B ] && mv $B $B.old.$(date +%s); mkdir -p $B/ds $B/src $B/pkg/probes/persona $B/pkg/probes/world-engine/data $B/pkg/demo $B/pkg/newsreader/bitmob
python3 - <<P
import json
rows=[l for l in open("$IN") if l.strip()]; test={json.loads(l)["id"] for l in open("$W/data/clef-labels/test_in.jsonl")}
ids=[json.loads(r)["id"] for r in rows]; assert ids and set(ids)<=test and len(set(ids))==len(ids), "non-test id in the test dataset"
open("$B/ds/stories.jsonl","w").write("".join(r if r.endswith("\\n") else r+"\\n" for r in rows)); json.dump(ids,open("$B/ids.json","w")); print("ok:",len(rows),"frozen-test stories")
P
P=$W/probes/persona; cp -r $P/rules $P/rules_v2 $B/pkg/probes/persona/; cp $P/personas.py $P/offline.py $P/rules.py $P/world_model.py $B/pkg/probes/persona/
cp $W/probes/world-engine/classify.py $B/pkg/probes/world-engine/; cp $W/probes/world-engine/data/countries_world100.csv $B/pkg/probes/world-engine/data/
cat > $B/pkg/demo/backends.py <<'S'
import os
BACKENDS = {"clef-flash-q4km": {"url": "http://127.0.0.1:" + os.environ.get("CLEF_PORT", "8018"), "key": "", "model": ""}}
def name(bid): return bid
S
cat > $B/pkg/newsreader/bitmob/progress.py <<'S'
def event(job, state, msg, pid=None, win=False, **kw): print("[event]", job, state, msg, flush=True)
S
cp $W/newsreader/bitmob/screen_real_run.py $B/pkg/newsreader/bitmob/
tar czf $B/ds/pkg.tar.gz -C $B/pkg . ; mv $B/pkg /tmp/pkg_$$_old 2>/dev/null || true
cat > $B/ds/dataset-metadata.json <<J
{"title": "$DS", "id": "coreygorman/$DS", "licenses": [{"name": "other"}], "isPrivate": true}
J
( cat $W/tools/kaggle/guard.py; sed -e "s/__NAME__/$NAME/" -e "s/__WORKERS__/$WK/" -e "s/__LABELMIN__/$LM/" -e "s/__MAXMIN__/$GM/" $W/newsreader/bitmob/kaggle_screen_kernel.py ) > $B/src/bitmob-screenk-$NAME.py
cat > $B/src/kernel-metadata.json <<J
{"id": "coreygorman/bitmob-screenk-$NAME", "title": "bitmob-screenk-$NAME", "code_file": "bitmob-screenk-$NAME.py", "language": "python", "kernel_type": "script", "is_private": true, "enable_gpu": true, "enable_tpu": false,
 "enable_internet": true, "keywords": ["gpu"], "dataset_sources": ["coreygorman/$DS"], "kernel_sources": [], "competition_sources": [], "model_sources": [],
 "docker_image": "gcr.io/kaggle-private-byod/python@sha256:2757e0c7d1e0a9cb43da657b97e223c321a98f5014bdf64f44f2f6b083ad2b2f", "machine_shape": "NvidiaTeslaT4"}
J
echo "built $B"
