#!/bin/bash
# 1-3-1 series 2, solution B1 (R-0186): from-scratch A/B of the multi-head reader. SAME rows, SAME recipe (15 epochs, e5-base-v2, lr 5e-5), only the condition target differs.
#   arm a = control: soft Clef value (as round 6).  arm b = B1: binary trigger (Clef attribute mean >= 0.65) with per-key pos_weight clip(sqrt(neg/pos), 1, 20).
# Data = data/kaggle/mh_r6c1/ds (training rows only; frozen test and tune rows asserted absent). Builds data/kaggle/mh_b1a, mh_b1b. Does NOT launch. Never rm: an existing dir is moved aside.
set -e; W=/workspace; H=$W/newsreader/bitmob/mh; PY=$W/kev/.venv/bin/python
[ -e $W/data/progress/STOP ] && { echo "STOP file set: not building"; exit 3; }
for arm in a b; do
  B=$W/data/kaggle/mh_b1$arm; [ -e $B ] && mv $B $B.old.$(date +%s); mkdir -p $B/ds $B/src
  cp $W/data/kaggle/mh_r6c1/ds/texts.json $W/data/kaggle/mh_r6c1/ds/keys.json $B/ds/
  ARM=$arm SRC=$W/data/kaggle/mh_r6c1/ds/targets.npz DST=$B/ds/targets.npz $PY - <<'P'
import os, numpy as np
Z = np.load(os.environ["SRC"]); Y = {k: Z[k] for k in Z.files}
if os.environ["ARM"] == "b":
    c = Y["cond"]; b = (c >= 0.65).astype(np.float32); pos = b.sum(0); neg = len(b) - pos
    Y["cond"] = b; Y["cond_pw"] = np.tile(np.clip(np.sqrt(neg / np.maximum(pos, 1)), 1, 20).astype(np.float32)[None, :], (len(b), 1))
    print("arm b: binary cond targets, trigger cells", int(pos.sum()), "pos_weight range", float(Y["cond_pw"][0].min()), float(Y["cond_pw"][0].max()))
else: print("arm a: soft cond targets unchanged")
np.savez(os.environ["DST"], **Y)
P
  cat > $B/ds/dataset-metadata.json <<J
{"title": "bitmob-mh-train-b1$arm", "id": "coreygorman/bitmob-mh-train-b1$arm", "licenses": [{"name": "other"}], "isPrivate": true}
J
  ( cat $W/tools/kaggle/guard.py; grep -v PUSH-STRIP $H/mh_common_b1.py; grep -v PUSH-STRIP $H/train_mh_b1.py ) > $B/src/bitmob-mh-b1$arm.py
  cat > $B/src/kernel-metadata.json <<J
{"id": "coreygorman/bitmob-mh-b1$arm", "title": "bitmob-mh-b1$arm", "code_file": "bitmob-mh-b1$arm.py", "language": "python", "kernel_type": "script", "is_private": true, "enable_gpu": true, "enable_tpu": false,
 "enable_internet": true, "keywords": ["gpu"], "dataset_sources": ["coreygorman/bitmob-mh-train-b1$arm"], "kernel_sources": [], "competition_sources": [], "model_sources": [],
 "docker_image": "gcr.io/kaggle-private-byod/python@sha256:2757e0c7d1e0a9cb43da657b97e223c321a98f5014bdf64f44f2f6b083ad2b2f", "machine_shape": "NvidiaTeslaT4"}
J
  $PY - <<P
import json, os
ids = set(json.load(open("$B/ds/keys.json"))["ids"]); test = set()
for f in ("test_in", "test", "test_noraw_partial"):
    p = "$W/data/clef-labels/%s.jsonl" % f
    if os.path.exists(p): test |= {json.loads(l)["id"] for l in open(p) if l.strip()}
tune = set(json.load(open("$W/data/kaggle/mh_r6c1/tune/keys.json"))["ids"])
assert not (ids & test), "frozen test ids in the training dataset"; assert not (ids & tune), "tune rows in the training dataset"
src = open("$B/src/bitmob-mh-b1$arm.py").read(); assert "test_in" not in src and "clef-labels" not in src
print("arm $arm ok: %d training rows, 0 frozen-test ids, 0 tune ids" % len(ids))
P
done
echo built
