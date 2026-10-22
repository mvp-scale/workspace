#!/bin/bash
# After a warm Kaggle run returns: tune cuts (conditions, then reading head), score the 2,000 frozen-test stories, print one line vs the previous score file. CPU only.
#   newsreader/bitmob/mh/after_warm.sh <round> [prev_score_json]     (default prev: the newest other data/kaggle/mh_*/score_*.json)
set -e; R=$1; W=/workspace; B=$W/data/kaggle/mh_$R; H=$W/newsreader/bitmob/mh; PY=$W/models/embed-zs/.venv/bin/python
SP=/tmp/claude-0/-workspace/56bd04e1-c166-41e7-b6b1-a8834c019bd6/scratchpad; T=$SP/test_2000.jsonl; mkdir -p $SP; [ -f $T ] || cp $W/data/clef-labels/test.jsonl $T
export CUDA_VISIBLE_DEVICES= WORLD_GPU=0 WE_RULES=rules_v2
[ -d $B/out/mh ] || { echo "no model at $B/out/mh"; exit 2; }
$PY $H/tune_cuts.py $B/out/mh $B/tune 2>&1 | grep -A3 '"on_tune"' | tr -d '\n ' ; echo
$PY $H/tune_reading.py $B/out/mh $B/tune 2>&1 | grep -A2 on_tune_combined | tr -d '\n '; echo
$PY $H/score_mh.py $B/out/mh $T $B/score_$R.json --threads 8 ${NTEST:+--n $NTEST} > /dev/null 2>&1
PREV=${2:-$(ls -t $W/data/kaggle/mh_*/score_*.json | grep -v "/score_$R.json" | head -1)}
$PY - <<P
import json
n=json.load(open("$B/score_$R.json")); o=json.load(open("$PREV"))
def v(d,k):
    x=d[k]["value"]; return x if not isinstance(x,dict) else (x.get("TPR") if k=="P-0017" else x.get("share_AP>=.7"))
names={"P-0016":"gate","P-0017":"conditions TPR","P-0018":"topics","P-0019":"country","P-0020":"expected","P-0021":"severity"}
print("n=%d  %s  | prev %s"%(n["meta"]["n"]," ".join("%s %.3f%s"%(names[k],v(n,k),"*" if n[k]["pass"] else "") for k in names),"$PREV".split("/")[-2]))
print("conditions FPR %.5f (limit .001)  delta TPR vs prev %+.3f   (* = passes)"%(n["P-0017"]["value"]["FPR"], v(n,"P-0017")-v(o,"P-0017")))
P
