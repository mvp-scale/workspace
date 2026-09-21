#!/usr/bin/env python3
"""Build phishing.jsonl from Hugging Face ealvaradob/phishing-dataset, texts.json (email + SMS portions only; no URLs/HTML).
Source: https://huggingface.co/datasets/ealvaradob/phishing-dataset (Apache-2.0), snapshot 55caf9af01ae498d68ff44886ff69a4b165eb54b
  huggingface_hub.snapshot_download('ealvaradob/phishing-dataset', repo_type='dataset') with HF_HOME=/workspace/data/sources/hf-cache
Upstream label: 1 = phishing (includes spam/smishing/scam), 0 = benign.
Cleaning: normalise whitespace; drop texts containing mojibake ('Â'); drop texts containing the words spam/ham/phish/smish
  (hint leakage); truncate at last sentence boundary (. ! ? followed by space) before 1200 chars if longer; drop if <40 chars after that.
Mechanical relevance filter on the positive class ONLY: text must match KEY (password, verify, login, suspended, prize, claim, beneficiary,
  inheritance, 'dear customer', ...) and must not match NOISE (unsubscribe, mortgage, pharmacy, penny stock, bulk-email ads ...), to favour credential/money/
  access lures over generic advertising spam (the upstream 'phishing' label includes much plain spam; first unfiltered draft was mostly drug/mortgage ads). Labels are never edited. Negatives: no filter beyond the above.
Strata (seed 20260921): label x {short<=300 chars (SMS-like), long (email-like)}, 16 each -> 64 items (32/32).
"""
import json, glob, random, re, sys
sys.path.insert(0, "/workspace/probes/v2")
from _common import write
SEED, PER = 20260921, 16
Q = "Is this message trying to get the recipient to hand over credentials, money or access through impersonation, pressure or deception?"
KEY = re.compile(r"password|passcode|\bpin\b|verify|verification|log ?in|sign ?in|suspend|unauthori[sz]ed|security (alert|team|department|check)|your account|bank account|paypal|ebay|\batm\b|beneficiar|inheritance|next of kin|wire transfer|prize|claim|winner|congratulations|you have won|won \$|£|confirm your|update your|urgent|dear (customer|user|member|friend|beloved)", re.I)
NOISE = re.compile(r"unsubscribe|mortgage|refinanc|pharmac|\brx\b|viagra|prozac|penny stock|otcbb|remove me|opt.?out|broadcast email|bulk email|email marketing|weight loss|casino|diploma", re.I)
BAD = re.compile(r"Â|\b(spam|ham|phish\w*|smish\w*)\b", re.I)
f = glob.glob("/workspace/data/sources/hf-cache/hub/datasets--ealvaradob--phishing-dataset/snapshots/*/texts.json")[0]
data = json.load(open(f, encoding="utf-8"))
def trunc(t):
    if len(t) <= 1200: return t
    cut = t[:1200]
    m = list(re.finditer(r"[.!?](?=\s)", cut))
    return cut[:m[-1].end()] if m else None
pools = {}
for i, r in enumerate(data):
    t = re.sub(r"\s+", " ", r["text"]).strip()
    if BAD.search(t): continue
    if r["label"] == 1 and (not KEY.search(t) or NOISE.search(t)): continue
    was_long = len(t) > 1200
    t = trunc(t)
    if not t or len(t) < 40: continue
    pools.setdefault((r["label"], "short" if len(t) <= 300 else "long"), {}).setdefault(t, (i, was_long))
rng = random.Random(SEED); out = []
for key in sorted(pools):
    for t in rng.sample(sorted(pools[key]), PER):
        i, wl = pools[key][t]
        out.append({"id": "phish-%05d" % i, "family": "deception", "state": t,
            "question": {"type": "noul", "instructions": Q, "criteria": {
                "true": "The message tries to obtain credentials, money or access through impersonation, pressure or deception",
                "false": "The message is a legitimate, non-deceptive communication"}},
            "labels": ["no", "yes"], "expected": "yes" if key[0] == 1 else "no", "split": "public", "group": None,
            "provenance": {"exclude_reason": None, "source": "ealvaradob/phishing-dataset texts.json (email+SMS)",
                "url": "https://huggingface.co/datasets/ealvaradob/phishing-dataset", "license": "Apache-2.0", "retrieved": "2026-09-21",
                "source_id": "texts.json index %d" % i, "notes": "stratum=%s/%s; truncated at sentence boundary=%s" % (key[0], key[1], wl)}})
random.Random(SEED + 1).shuffle(out)
write("/workspace/probes/v2/phishing.jsonl", out)
