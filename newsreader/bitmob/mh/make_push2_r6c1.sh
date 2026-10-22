#!/bin/bash
# Round-2 Kaggle push dirs (D-0038/D-0042). Training rows only; the 15% tune rows stay LOCAL (data/kaggle/mh_<round>/tune), never uploaded; frozen test excluded by id and asserted absent.
#   newsreader/bitmob/mh/make_push2.sh <round> [--refit]        e.g. make_push2.sh r2 --refit
# --refit re-fits data/jev-labels/maps.json from the stories both teachers labelled (translate_jev_clef.py fit); without it the existing maps.json is used.
# Makes data/kaggle/mh_<round>/{ds,src,tune}. Then (captain):  see the printed commands.
set -e; R=$1; shift; W=/workspace; B=$W/data/kaggle/mh_$R; H=$W/newsreader/bitmob/mh; PY=$W/kev/.venv/bin/python
[ -e $W/data/progress/STOP ] && { echo "STOP file set: not building"; exit 3; }
if [ "$1" = "--refit" ] || [ ! -f $W/data/jev-labels/maps.json ]; then $PY $H/translate_jev_clef.py fit | tail -45; fi
rm -rf $B; mkdir -p $B/ds $B/src $B/tune
$PY $H/build_mh_data2.py $B/ds $B/tune
cat > $B/ds/dataset-metadata.json <<J
{"title": "bitmob-mh-train-$R", "id": "coreygorman/bitmob-mh-train-$R", "licenses": [{"name": "other"}], "isPrivate": true}
J
( cat $W/tools/kaggle/guard.py; grep -v PUSH-STRIP $H/mh_common.py; grep -v PUSH-STRIP $H/train_mh.py ) > $B/src/bitmob-mh-$R.py
cat > $B/src/kernel-metadata.json <<J
{"id": "coreygorman/bitmob-mh-$R", "title": "bitmob-mh-$R", "code_file": "bitmob-mh-$R.py", "language": "python", "kernel_type": "script", "is_private": true, "enable_gpu": true, "enable_tpu": false,
 "enable_internet": true, "keywords": ["gpu"], "dataset_sources": ["coreygorman/bitmob-mh-train-$R"], "kernel_sources": [], "competition_sources": [], "model_sources": [],
 "docker_image": "gcr.io/kaggle-private-byod/python@sha256:2757e0c7d1e0a9cb43da657b97e223c321a98f5014bdf64f44f2f6b083ad2b2f", "machine_shape": "NvidiaTeslaT4"}
J
$PY - <<P
import json,os,re
ids=set(json.load(open("$B/ds/keys.json"))["ids"]); test=set()
for f in ("test_in","test","test_noraw_partial"):
    p="$W/data/clef-labels/%s.jsonl"%f
    if os.path.exists(p): test|={json.loads(l)["id"] for l in open(p) if l.strip()}
tune=set(json.load(open("$B/tune/keys.json"))["ids"])
assert not (ids&test), "frozen test ids in the training dataset: %s"%sorted(ids&test)[:3]
assert not (ids&tune), "tune rows in the training dataset"
src=open("$B/src/bitmob-mh-$R.py").read(); assert "test_in" not in src and "clef-labels" not in src
print("ok: %d training rows, %d tune rows (local only), 0 frozen-test ids"%(len(ids),len(tune)))
P
N=$($PY -c "import json;print(len(json.load(open('$B/ds/keys.json'))['ids']))")
echo "estimate: $N rows x 15 epochs at ~205 rows/s (T4, round-1b measure) = $(( N*15/205/60 )) min; the trainer stops and saves at 36 min, guard 45 min"
echo "built $B"
echo "LAUNCH:  cd $W && source tools/kaggle.env && tools/.kaggle-venv/bin/kaggle datasets create -p $B/ds && sleep 25 && nohup tools/kaggle/watch.sh coreygorman/bitmob-mh-$R $B/out 50 60 $B/src > $B/watch.log 2>&1 &"
echo "AFTER:   CUDA_VISIBLE_DEVICES= $W/models/embed-zs/.venv/bin/python $H/tune_cuts.py $B/out/mh $B/tune   then   $W/models/embed-zs/.venv/bin/python $H/score_mh.py $B/out/mh <test snapshot> $B/score_$R.json"
