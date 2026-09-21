#!/usr/bin/env python3
"""Build politeness_deference.jsonl from the Stanford Politeness Corpus (Wikipedia talk-page requests),
Danescu-Niculescu-Mizil, Sudhof, Jurafsky, Leskovec, Potts (ACL 2013), ConvoKit release.
URL: https://zissou.infosci.cornell.edu/convokit/datasets/wikipedia-politeness-corpus/wikipedia-politeness-corpus.zip
     (docs https://convokit.cornell.edu/documentation/wiki_politeness.html), extracted to /workspace/data/sources/politeness/.
Licence: CC BY 4.0 (ConvoKit docs). Retrieved 2026-09-21. Read directly from utterances.jsonl (no convokit needed).
Labels: the corpus's own "Binary" field: +1 = top quartile of annotator politeness score (yes), -1 = bottom quartile (no); 0 (middle) dropped.
Filters: 20<=len<=300 after whitespace collapse, duplicate texts dropped. Seed 20260921, 50 per class random.sample.
"""
import json, random, re, sys
sys.path.insert(0, "/workspace/probes/v2")
from _common import write
SEED, N = 20260921, 50
def clean(s): return re.sub(r"\s+", " ", s).strip()
rows = [json.loads(l) for l in open("/workspace/data/sources/politeness/wikipedia-politeness-corpus/utterances.jsonl", encoding="utf-8")]
pool = {1: {}, -1: {}}
for r in rows:
    b = r["meta"]["Binary"]; t = clean(r["text"])
    if b in pool and 20 <= len(t) <= 300: pool[b].setdefault(t, r)
rng = random.Random(SEED)
print({k: len(v) for k, v in pool.items()})
out = []
for b, lab in ((1, "yes"), (-1, "no")):
    for t in rng.sample(sorted(pool[b]), N):
        r = pool[b][t]
        out.append({"id": "polite-%s" % r["id"], "family": "politeness_deference", "state": t,
            "question": {"type": "noul", "instructions": "Is the speaker being polite and deferential to the person they are addressing?",
                "criteria": {"true": "The speaker is polite and deferential (courteous, hedged, respectful request)", "false": "The speaker is impolite or blunt (curt, demanding, dismissive or rude)"}},
            "labels": ["no", "yes"], "expected": lab, "split": "public", "group": None,
            "provenance": {"exclude_reason": None, "source": "Stanford Politeness Corpus, Wikipedia requests (ConvoKit release)",
                "url": "https://convokit.cornell.edu/documentation/wiki_politeness.html", "license": "CC BY 4.0", "retrieved": "2026-09-21",
                "source_id": r["id"], "notes": "Binary=%d (top/bottom quartile of published score); Normalized Score=%.3f" % (b, r["meta"]["Normalized Score"])}})
random.Random(SEED + 1).shuffle(out)
write("/workspace/probes/v2/politeness_deference.jsonl", out)
