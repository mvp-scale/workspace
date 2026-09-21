#!/usr/bin/env python3
"""Build emotion_fear.jsonl and emotion_anger.jsonl from GoEmotions RAW (Demszky et al. 2020, ACL).
Source: https://huggingface.co/datasets/google-research-datasets/go_emotions (config "raw"; Apache-2.0),
        retrieved 2026-09-21 via datasets.load_dataset with HF_HOME=/workspace/data/sources/hf-cache.
Raw = one row per (example, rater). Per example we count raters and per-emotion votes.
 yes: >=2 raters chose fear or nervousness (anger or annoyance for the anger set).
 no : NO rater chose any of the target emotions, and >=2 raters agree on some other label (incl. neutral)
      (so the negative has a documented, different, agreed label); examples flagged example_very_unclear excluded.
Filters: 15<=len(text)<=250 after whitespace collapse; duplicate texts dropped. Text is verbatim (incl. [NAME]/[RELIGION] tokens).
Sampling: seed 20260921, N=50 per class; positives sampled at random, negatives sampled round-robin
across their modal-label strata (stratified) so no single emotion dominates.
"""
import json, random, re, sys, os
from collections import defaultdict, Counter
os.environ.setdefault("HF_HOME", "/workspace/data/sources/hf-cache")
sys.path.insert(0, "/workspace/probes/v2")
from _common import write
from datasets import load_dataset
SEED, N = 20260921, 50
ds = load_dataset("google-research-datasets/go_emotions", "raw")["train"]
EMO = [c for c in ds.column_names[9:]]
ex = {}
for r in ds:
    e = ex.setdefault(r["id"], {"text": r["text"], "n": 0, "unclear": False, "v": Counter()})
    e["n"] += 1; e["unclear"] |= bool(r["example_very_unclear"])
    for k in EMO:
        if r[k]: e["v"][k] += 1
def clean(s): return re.sub(r"\s+", " ", s).strip()
SETS = {"fear": (["fear", "nervousness"], "Is the speaker expressing fear or nervousness?",
                 "The speaker expresses fear, anxiety or nervousness", "The speaker expresses something other than fear or nervousness"),
        "anger": (["anger", "annoyance"], "Is the speaker expressing anger or annoyance?",
                  "The speaker expresses anger or annoyance", "The speaker expresses something other than anger or annoyance")}
for name, (targets, q, t, f) in SETS.items():
    rng = random.Random(SEED)
    pos, neg, seen = [], defaultdict(list), set()
    for id_ in sorted(ex):
        e = ex[id_]; tx = clean(e["text"])
        if e["unclear"] or not 15 <= len(tx) <= 250 or tx in seen: continue
        tv = {k: e["v"][k] for k in targets}
        if sum(tv.values()) == 0:
            top, c = e["v"].most_common(1)[0] if e["v"] else (None, 0)
            if c >= 2: neg[top].append((id_, tx, e)); seen.add(tx)
        elif sum(tv.values()) >= 2:
            pos.append((id_, tx, e)); seen.add(tx)
    print(name, "positives available:", len(pos), "negatives available:", sum(map(len, neg.values())), {k: len(v) for k, v in neg.items()})
    ps = rng.sample(pos, N)
    strata = {k: rng.sample(v, len(v)) for k, v in sorted(neg.items())}
    ns = []
    while len(ns) < N:
        for k in sorted(strata):
            if strata[k] and len(ns) < N: ns.append(strata[k].pop())
    out = []
    for lab, items in (("yes", ps), ("no", ns)):
        for id_, tx, e in items:
            votes = {k: v for k, v in sorted(e["v"].items())}
            out.append({"id": "goemo-%s-%s" % (name, id_), "family": "emotion_" + name, "state": tx,
                "question": {"type": "noul", "instructions": q, "criteria": {"true": t, "false": f}},
                "labels": ["no", "yes"], "expected": lab, "split": "public", "group": None,
                "provenance": {"exclude_reason": None, "source": "GoEmotions raw (Demszky et al. 2020), Reddit comments, crowd rater votes",
                    "url": "https://huggingface.co/datasets/google-research-datasets/go_emotions", "license": "Apache-2.0",
                    "retrieved": "2026-09-21", "source_id": id_,
                    "notes": "raters=%d; rater votes per emotion=%s" % (e["n"], json.dumps(votes))}})
    random.Random(SEED + 1).shuffle(out)
    write("/workspace/probes/v2/emotion_%s.jsonl" % name, out)
