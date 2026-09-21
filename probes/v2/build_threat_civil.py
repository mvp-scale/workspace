#!/usr/bin/env python3
"""Build threat_civil.jsonl from Jigsaw Civil Comments (Borkan et al. 2019), HF google/civil_comments (CC0-1.0),
https://huggingface.co/datasets/google/civil_comments, retrieved 2026-09-21 (HF_HOME=/workspace/data/sources/hf-cache).
All splits (train+validation+test) pooled. Scores are fractions of crowd raters.
 yes: threat >= 0.5.   no: threat == 0 AND toxicity == 0.
Filters: 15<=len(text)<=300 after whitespace collapse, duplicate texts dropped. Seed 20260921, up to 50 per class (all yes if fewer).
The number of qualifying positives is printed and recorded in threat_civil.md.
"""
import os, random, re, sys
os.environ.setdefault("HF_HOME", "/workspace/data/sources/hf-cache")
sys.path.insert(0, "/workspace/probes/v2")
from _common import write
from datasets import load_dataset
SEED, N = 20260921, 50
def clean(s): return re.sub(r"\s+", " ", s).strip()
pos, neg = {}, {}
raw_pos = 0
for sp in ("train", "validation", "test"):
    d = load_dataset("google/civil_comments", split=sp)
    for i, (t, th, tox) in enumerate(zip(d["text"], d["threat"], d["toxicity"])):
        if th >= 0.5:
            raw_pos += 1
            tx = clean(t)
            if 15 <= len(tx) <= 300: pos.setdefault(tx, (sp, i, th, tox))
        elif th == 0 and tox == 0:
            tx = clean(t)
            if 15 <= len(tx) <= 300: neg.setdefault(tx, (sp, i, th, tox))
print("raw threat>=0.5:", raw_pos, "usable unique:", len(pos), "negatives usable:", len(neg))
rng = random.Random(SEED)
n = min(N, len(pos))
sel = [("yes", t, pos[t]) for t in rng.sample(sorted(pos), n)] + [("no", t, neg[t]) for t in rng.sample(sorted(neg), n)]
out = []
for lab, t, (sp, i, th, tox) in sel:
    out.append({"id": "civil-%s-%d" % (sp, i), "family": "threat", "state": t,
        "question": {"type": "noul", "instructions": "Does this text threaten to harm the listener?",
            "criteria": {"true": "The text threatens violence or harm to the person addressed", "false": "The text contains no threat"}},
        "labels": ["no", "yes"], "expected": lab, "split": "public", "group": None,
        "provenance": {"exclude_reason": None, "source": "Jigsaw Civil Comments (news-site comments, crowd-rated)",
            "url": "https://huggingface.co/datasets/google/civil_comments", "license": "CC0-1.0", "retrieved": "2026-09-21",
            "source_id": "%s[%d]" % (sp, i), "notes": "threat=%.3f toxicity=%.3f" % (th, tox)}})
random.Random(SEED + 1).shuffle(out)
write("/workspace/probes/v2/threat_civil.jsonl", out)
