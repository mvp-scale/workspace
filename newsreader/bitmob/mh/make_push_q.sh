#!/bin/bash
# Queue Q3/Q4/Q5 (data/progress/queue.json). Builds data/kaggle/mh_q3, mh_q4, mh_q5 from the round-6 training rows (frozen test and tune rows absent). Does NOT launch. Never rm: existing dirs move aside.
#   q3 positive-story oversampling: stories holding a trigger (Clef >= 0.65) appear 3 times
#   q4 strong-only: positive = Clef >= 0.85; cells in 0.65-0.85 get weight 0 (not trained either way)
#   q5 graded: binary >= 0.65, cell weight 0.4 for 0.65-0.85, 1.0 above
set -e; W=/workspace; H=$W/newsreader/bitmob/mh; PY=$W/kev/.venv/bin/python; S=$W/data/kaggle/mh_r6c1/ds
[ -e $W/data/progress/STOP ] && { echo "STOP file set"; exit 3; }
for arm in q3 q4 q5; do
  B=$W/data/kaggle/mh_$arm; [ -e $B ] && mv $B $B.old.$(date +%s); mkdir -p $B/ds $B/src
  ARM=$arm S=$S D=$B/ds $PY - <<'P'
import os, json, numpy as np
S, D, arm = os.environ["S"], os.environ["D"], os.environ["ARM"]
Z = np.load(f"{S}/targets.npz"); Y = {k: Z[k] for k in Z.files}; texts = json.load(open(f"{S}/texts.json")); keys = json.load(open(f"{S}/keys.json")); c = Y["cond"]
Y["cond"] = (c >= (0.85 if arm == "q4" else 0.65)).astype(np.float32); pos = Y["cond"].sum(0); neg = len(c) - pos
Y["cond_pw"] = np.tile(np.clip(np.sqrt(neg / np.maximum(pos, 1)), 1, 20).astype(np.float32)[None, :], (len(c), 1))
if arm == "q4": Y["cond_cw"] = (~((c >= .65) & (c < .85))).astype(np.float32)
if arm == "q5": Y["cond_cw"] = np.where((c >= .65) & (c < .85), 0.4, 1.0).astype(np.float32)
if arm == "q3":
    rep = np.where((c >= .65).any(1))[0]; idx = np.concatenate([np.arange(len(c)), rep, rep])
    Y = {k: (v[idx] if getattr(v, "shape", ())[:1] == (len(c),) else v) for k, v in Y.items()}; texts = [texts[i] for i in idx]
    keys = dict(keys); keys["ids"] = [keys["ids"][i] for i in idx]
print(arm, "rows", len(texts), "positive cells", int(Y["cond"].sum()))
json.dump(texts, open(f"{D}/texts.json", "w")); json.dump(keys, open(f"{D}/keys.json", "w")); np.savez(f"{D}/targets.npz", **Y)
P
  cat > $B/ds/dataset-metadata.json <<J
{"title": "bitmob-mh-train-$arm", "id": "coreygorman/bitmob-mh-train-$arm", "licenses": [{"name": "other"}], "isPrivate": true}
J
  ( cat $W/tools/kaggle/guard.py; grep -v PUSH-STRIP $H/mh_common_b1.py; grep -v PUSH-STRIP $H/train_cond_q.py ) > $B/src/bitmob-mh-$arm.py
  sed -e "s/bitmob-mh-t3/bitmob-mh-$arm/g" -e "s#bitmob-mh-train-b1b#bitmob-mh-train-$arm#" $W/data/kaggle/mh_t3/src/kernel-metadata.json > $B/src/kernel-metadata.json
  $PY - <<P
import json, os
ids = set(json.load(open("$B/ds/keys.json"))["ids"]); test = set()
for f in ("test_in", "test", "test_noraw_partial"):
    p = "$W/data/clef-labels/%s.jsonl" % f
    if os.path.exists(p): test |= {json.loads(l)["id"] for l in open(p) if l.strip()}
tune = set(json.load(open("$W/data/kaggle/mh_r6c1/tune/keys.json"))["ids"])
assert not (ids & test) and not (ids & tune); src = open("$B/src/bitmob-mh-$arm.py").read(); assert "test_in" not in src and "clef-labels" not in src
print("$arm ok, no frozen-test or tune ids")
P
done
echo built
