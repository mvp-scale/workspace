#!/usr/bin/env python3
"""Extra labelled examples for the seven tone/text-type probe sets, built with each set's own labelling rule
(see probes/v2/build_*.py) from the same local sources, never including a probe item's text.

Used by probes/embed_curve.py to ask: with more examples than the ~80 a 5-fold split leaves, how close does each
embedding model get to Clef Flash and Jev? Up to CAP examples per class; seed 20260921.
iSarcasm and headlines draw from their TRAIN splits (the probe sets came from the test splits): same labelling, other rows.
Writes data/embed-zs/pools/<set>.jsonl rows {"text", "label": "yes"|"no"}.
"""
import csv, glob, json, os, random, re
from collections import Counter, defaultdict
from pathlib import Path

os.environ.setdefault("HF_HOME", "/workspace/data/sources/hf-cache")
PROBES, OUT, CAP, SEED = Path("/workspace/probes/v2"), Path("/workspace/data/embed-zs/pools"), 1000, 20260921
clean = lambda s: re.sub(r"\s+", " ", s).strip()
probe_texts = lambda s: {clean(json.loads(l)["state"]) for l in open(PROBES / f"{s}.jsonl")}


def save(name, pos, neg):
    held = probe_texts(name); rng = random.Random(SEED)
    pos = [t for t in dict.fromkeys(pos) if t not in held]; neg = [t for t in dict.fromkeys(neg) if t not in held]
    pos, neg = rng.sample(pos, min(CAP, len(pos))), rng.sample(neg, min(CAP, len(neg)))
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{name}.jsonl", "w") as f:
        for t in pos: f.write(json.dumps({"text": t, "label": "yes"}) + "\n")
        for t in neg: f.write(json.dumps({"text": t, "label": "no"}) + "\n")
    print(f"{name:<22} yes {len(pos):>5}  no {len(neg):>5}")


def goemotions():
    from datasets import load_dataset
    ds = load_dataset("google-research-datasets/go_emotions", "raw")["train"]; EMO = ds.column_names[9:]; ex = {}
    for r in ds:
        e = ex.setdefault(r["id"], {"text": r["text"], "unclear": False, "v": Counter()})
        e["unclear"] |= bool(r["example_very_unclear"])
        for k in EMO:
            if r[k]: e["v"][k] += 1
    for name, targets in (("emotion_fear", ["fear", "nervousness"]), ("emotion_anger", ["anger", "annoyance"])):
        pos, neg = [], defaultdict(list)
        for e in ex.values():
            t = clean(e["text"])
            if e["unclear"] or not 15 <= len(t) <= 250: continue
            tv = sum(e["v"][k] for k in targets)
            if tv == 0 and e["v"] and e["v"].most_common(1)[0][1] >= 2: neg[e["v"].most_common(1)[0][0]].append(t)
            elif tv >= 2: pos.append(t)
        rng = random.Random(SEED); strata = {k: rng.sample(v, len(v)) for k, v in sorted(neg.items())}; ns = []
        while len(ns) < 3 * CAP and any(strata.values()):  # stratified across the negatives' own labels, as the probe build does
            for k in sorted(strata):
                if strata[k]: ns.append(strata[k].pop())
        save(name, pos, ns)


def politeness():
    rows = [json.loads(l) for l in open("/workspace/data/sources/politeness/wikipedia-politeness-corpus/utterances.jsonl")]
    pos = [clean(r["text"]) for r in rows if r["meta"]["Binary"] == 1 and 20 <= len(clean(r["text"])) <= 300]
    neg = [clean(r["text"]) for r in rows if r["meta"]["Binary"] == -1 and 20 <= len(clean(r["text"])) <= 300]
    save("politeness_deference", pos, neg)


def threat():
    from datasets import load_dataset
    pos, neg = [], []
    for sp in ("train", "validation", "test"):
        d = load_dataset("google/civil_comments", split=sp)
        for t, th, tox in zip(d["text"], d["threat"], d["toxicity"]):
            if th >= 0.5 or (th == 0 and tox == 0):
                t = clean(t)
                if 15 <= len(t) <= 300: (pos if th >= 0.5 else neg).append(t)
    rng = random.Random(SEED); save("threat_civil", pos, rng.sample(neg, 20 * CAP))


def phishing():
    import importlib.util
    spec = importlib.util.spec_from_file_location("b", PROBES / "build_phishing.py"); src = open(PROBES / "build_phishing.py").read()
    KEY = re.compile(re.search(r'KEY = re.compile\(r"(.*?)", re.I\)', src).group(1), re.I)
    NOISE = re.compile(re.search(r'NOISE = re.compile\(r"(.*?)", re.I\)', src).group(1), re.I)
    BAD = re.compile(r"Â|\b(spam|ham|phish\w*|smish\w*)\b", re.I)
    data = json.load(open(glob.glob("/workspace/data/sources/hf-cache/hub/datasets--ealvaradob--phishing-dataset/snapshots/*/texts.json")[0]))
    def trunc(t):
        if len(t) <= 1200: return t
        m = list(re.finditer(r"[.!?](?=\s)", t[:1200])); return t[:1200][:m[-1].end()] if m else None
    pos, neg = [], []
    for r in data:
        t = clean(r["text"])
        if BAD.search(t) or (r["label"] == 1 and (not KEY.search(t) or NOISE.search(t))): continue
        t = trunc(t)
        if t and len(t) >= 40: (pos if r["label"] == 1 else neg).append(t)
    save("phishing", pos, neg)


def sarcasm():
    rows = list(csv.DictReader(open("/workspace/data/sources/isarcasm/iSarcasmEval/train/train.En.csv", encoding="utf-8")))
    ok = lambda t: 15 <= len(t) <= 300
    save("sarcasm_isarcasm", [clean(r["tweet"]) for r in rows if r["sarcastic"] == "1" and ok(clean(r["tweet"]))],
         [clean(r["tweet"]) for r in rows if r["sarcastic"] == "0" and ok(clean(r["tweet"]))])
    f = glob.glob("/workspace/data/sources/hf-cache/hub/datasets--raquiba--Sarcasm_News_Headline/snapshots/*/train.json")[0]
    rs = [json.loads(l) for l in open(f, encoding="utf-8")]
    save("sarcasm_headlines", [clean(r["headline"]) for r in rs if int(r["is_sarcastic"]) == 1 and ok(clean(r["headline"]))],
         [clean(r["headline"]) for r in rs if int(r["is_sarcastic"]) == 0 and ok(clean(r["headline"]))])


if __name__ == "__main__":
    politeness(); phishing(); sarcasm(); goemotions(); threat()
