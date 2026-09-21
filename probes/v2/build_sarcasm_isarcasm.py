#!/usr/bin/env python3
"""Build sarcasm_isarcasm.jsonl (iSarcasmEval, SemEval-2022 Task 6, English task A, TEST split) and
sarcasm_headlines.jsonl (News Headlines Dataset for Sarcasm Detection v2, HF raquiba/Sarcasm_News_Headline test.json).
Sources:
  git clone https://github.com/iabufarha/iSarcasmEval  -> /workspace/data/sources/isarcasm/iSarcasmEval   (MIT)
  huggingface_hub.snapshot_download('raquiba/Sarcasm_News_Headline', repo_type='dataset') with HF_HOME=/workspace/data/sources/hf-cache
Sampling: seed 20260921; 40 per class (drop text >300 chars, <15 chars, or duplicate), random.sample per class.
Cleaning: strip/collapse whitespace only. Text otherwise verbatim.
"""
import csv, json, random, re, glob, sys
sys.path.insert(0, "/workspace/probes/v2")
from _common import write
SEED, N = 20260921, 40
def base(id_, state, yes, src, url, lic, sid, notes):
    return {"id": id_, "family": "subtext", "state": state,
        "question": {"type": "noul", "instructions": Q[id_.split("-")[0]],
            "criteria": {"true": "The speaker means the opposite of the literal words" if id_.startswith("isarc") else "The headline is satirical or sarcastic",
                         "false": "The speaker means what the words say" if id_.startswith("isarc") else "The headline is a straight news report"}},
        "labels": ["no", "yes"], "expected": "yes" if yes else "no", "split": "public", "group": None,
        "provenance": {"exclude_reason": None, "source": src, "url": url, "license": lic, "retrieved": "2026-09-21", "source_id": sid, "notes": notes}}
Q = {"isarc": "Does the speaker mean the opposite of what the words literally say?",
     "headl": "Is this headline satirical or sarcastic rather than a straight news report?"}
def clean(s): return re.sub(r"\s+", " ", s).strip()
def pick(pool, n, rng):
    return rng.sample(sorted(pool), n)

# iSarcasmEval
rng = random.Random(SEED)
rows = list(csv.DictReader(open("/workspace/data/sources/isarcasm/iSarcasmEval/test/task_A_En_test.csv", encoding="utf-8")))
pool = {1: {}, 0: {}}
for i, r in enumerate(rows):
    t = clean(r["text"])
    if 15 <= len(t) <= 300: pool[int(r["sarcastic"])].setdefault(t, i)
out = []
for lab in (0, 1):
    for t in pick(pool[lab].keys(), N, rng):
        out.append(base("isarc-%03d" % pool[lab][t], t, lab == 1, "iSarcasmEval (SemEval-2022 Task 6), English task A test, authors' own labels",
            "https://github.com/iabufarha/iSarcasmEval/blob/main/test/task_A_En_test.csv", "MIT", "task_A_En_test.csv row %d" % pool[lab][t],
            "Label = sarcastic column (tweet author's intent as labelled by the dataset authors' annotation)."))
random.Random(SEED + 1).shuffle(out)
write("/workspace/probes/v2/sarcasm_isarcasm.jsonl", out)

# Headlines
rng = random.Random(SEED)
f = glob.glob("/workspace/data/sources/hf-cache/hub/datasets--raquiba--Sarcasm_News_Headline/snapshots/*/test.json")[0]
pool = {1: {}, 0: {}}
for i, line in enumerate(open(f, encoding="utf-8")):
    r = json.loads(line); t = clean(r["headline"])
    if 15 <= len(t) <= 300: pool[int(r["is_sarcastic"])].setdefault(t, (i, r["article_link"]))
out = []
for lab in (0, 1):
    for t in pick(pool[lab].keys(), N, rng):
        i, link = pool[lab][t]
        out.append(base("headl-%05d" % i, t, lab == 1, "News Headlines Dataset for Sarcasm Detection v2 (Misra & Arora), HF raquiba/Sarcasm_News_Headline test.json",
            "https://huggingface.co/datasets/raquiba/Sarcasm_News_Headline", "CC0-1.0 (per Kaggle release; verify)", "test.json line %d; %s" % (i, link),
            "Label derives from publication (The Onion=1, HuffPost=0), not human intent annotation."))
random.Random(SEED + 1).shuffle(out)
write("/workspace/probes/v2/sarcasm_headlines.jsonl", out)
