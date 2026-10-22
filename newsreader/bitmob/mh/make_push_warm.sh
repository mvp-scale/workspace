#!/bin/bash
# Round-6 WARM-START push dirs (D-0038). New Clef rows + a replay sample of the previous training set; the previous model goes up as a 2nd private dataset; the kernel warm-starts from it.
#   newsreader/bitmob/mh/make_push_warm.sh <round> <prev_model_dir> <new_label_files...> [--replay N]      e.g. make_push_warm.sh r6c1 data/kaggle/mh_r5/out/mh data/clef-labels/r6_c1.jsonl --replay 6000
# Makes data/kaggle/mh_<round>/{ds,prev,src,tune}. Tune rows stay LOCAL (the previous round's tune set, unchanged). Frozen test asserted absent. Warm defaults in the kernel: 3 epochs, lr 2e-5, trainer stop 36 min, guard 45 min.
# Single T4 is used: ~8,000 rows x 3 epochs at ~205 rows/s = ~2 min of training; DataParallel would add risk for no needed gain (boot ~3 min dominates, total about 0.1 GPU h).
set -e; R=$1; PREV=$2; shift 2; W=/workspace; B=$W/data/kaggle/mh_$R; H=$W/newsreader/bitmob/mh; PY=$W/kev/.venv/bin/python
[ -e $W/data/progress/STOP ] && { echo "STOP file set: not building"; exit 3; }
FILES=(); REPLAY=6000; BASE=${WARM_BASE:-$W/data/kaggle/mh_r5}
while [ $# -gt 0 ]; do case "$1" in --replay) REPLAY=$2; shift 2;; --base) BASE=$2; shift 2;; *) FILES+=("$1"); shift;; esac; done
[ ${#FILES[@]} -gt 0 ] || { echo "no new label files"; exit 2; }
for f in "${FILES[@]}"; do case "$(basename $f)" in *test*) echo "refusing test file $f"; exit 2;; esac; done
rm -rf $B; mkdir -p $B/ds $B/prev $B/src
$PY $H/build_warm.py $B/ds $B/tune --new "${FILES[@]}" --replay $REPLAY --base $BASE
cat > $B/ds/dataset-metadata.json <<J
{"title": "bitmob-mh-train-$R", "id": "coreygorman/bitmob-mh-train-$R", "licenses": [{"name": "other"}], "isPrivate": true}
J
# previous model as its own private dataset (no tune scratch files)
mkdir -p $B/prev/mh; cp -r "$PREV/." $B/prev/mh/; rm -f $B/prev/mh/tune_raw_*
cat > $B/prev/dataset-metadata.json <<J
{"title": "bitmob-mh-prev-$R", "id": "coreygorman/bitmob-mh-prev-$R", "licenses": [{"name": "other"}], "isPrivate": true}
J
( cat $W/tools/kaggle/guard.py; grep -v PUSH-STRIP $H/mh_common.py; grep -v PUSH-STRIP $H/train_mh.py | sed 's/"--epochs", type=int, default=15/"--epochs", type=int, default=3/; s/"--lr", type=float, default=5e-5/"--lr", type=float, default=2e-5/' ) > $B/src/bitmob-mh-$R.py
grep -q 'default=3)' $B/src/bitmob-mh-$R.py && grep -q 'default=2e-5' $B/src/bitmob-mh-$R.py || { echo "warm defaults not applied"; exit 4; }
cat > $B/src/kernel-metadata.json <<J
{"id": "coreygorman/bitmob-mh-$R", "title": "bitmob-mh-$R", "code_file": "bitmob-mh-$R.py", "language": "python", "kernel_type": "script", "is_private": true, "enable_gpu": true, "enable_tpu": false,
 "enable_internet": true, "keywords": ["gpu"], "dataset_sources": ["coreygorman/bitmob-mh-train-$R", "coreygorman/bitmob-mh-prev-$R"], "kernel_sources": [], "competition_sources": [], "model_sources": [],
 "docker_image": "gcr.io/kaggle-private-byod/python@sha256:2757e0c7d1e0a9cb43da657b97e223c321a98f5014bdf64f44f2f6b083ad2b2f", "machine_shape": "NvidiaTeslaT4"}
J
$PY - <<P
import json,os
ids=set(json.load(open("$B/ds/keys.json"))["ids"]); test=set()
for f in ("test_in","test","test_noraw_partial"):
    p="$W/data/clef-labels/%s.jsonl"%f
    if os.path.exists(p): test|={json.loads(l)["id"] for l in open(p) if l.strip()}
tune=set(json.load(open("$B/tune/keys.json"))["ids"])
assert not (ids&test), "frozen test ids in the warm training dataset: %s"%sorted(ids&test)[:3]
assert not (ids&tune), "tune rows in the warm training dataset"
src=open("$B/src/bitmob-mh-$R.py").read(); assert "test_in" not in src and "clef-labels" not in src
print("ok: %d warm training rows, %d tune rows (local only), 0 frozen-test ids"%(len(ids),len(tune)))
P
N=$($PY -c "import json;print(len(json.load(open('$B/ds/keys.json'))['ids']))")
echo "estimate: $N rows x 3 epochs at ~205 rows/s (T4) = $(( N*3/205 )) s of training + ~3 min boot/load = about 0.1 GPU h"
echo "built $B"
echo "LAUNCH:  cd $W && source tools/kaggle.env && K=tools/.kaggle-venv/bin/kaggle && \$K datasets create -p $B/ds && \$K datasets create -p $B/prev --dir-mode zip && sleep 30 && nohup tools/kaggle/watch.sh coreygorman/bitmob-mh-$R $B/out 30 60 $B/src > $B/watch.log 2>&1 &"
echo "AFTER:   $H/after_warm.sh $R [prev_score_json]"
