"""Near-duplicate leakage check (playbook 00 section 13, test T07). Usage (from projects/world-state): python3 leakage_check.py
Near-duplicate = Jaccard of word 4-gram shingle sets >= 0.8, or equal normalised headline (text before the first '. ')."""
import json, re, collections, hashlib
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
norm = lambda t: re.sub(r"[^a-z0-9 ]+", " ", t.lower()).split()
def sh(t):
    w = norm(t); return {hash(" ".join(w[i:i + 4])) for i in range(max(len(w) - 3, 1))}
head = lambda t: " ".join(norm(t.split(". ")[0]))
pool = J("data/pool_train.jsonl"); P = [sh(r["text"]) for r in pool]; PH = collections.defaultdict(list)
for k, r in enumerate(pool): PH[head(r["text"])].append(k)
idx = collections.defaultdict(list)
for k, s in enumerate(P):
    for h in s: idx[h].append(k)
def near(S, skip=None):
    cnt = collections.Counter()
    for h in S:
        for k in idx.get(h, ()): cnt[k] += 1
    best = 0.0
    for k, c in cnt.items():
        if skip is not None and k == skip: continue
        j = c / (len(S) + len(P[k]) - c); best = max(best, j)
    return best
out = {}
for name, path in (("sealed", "runs/pulse/sealed_items.jsonl"), ("devq", "runs/pulse/devq_items.jsonl")):
    items = J(path); flagged = []; same_head = 0
    for r in items:
        s = sh(r["text"]); b = near(s); h = head(r["text"]) in PH
        same_head += h
        if b >= 0.8 or h: flagged.append({"id": r["id"], "jaccard": round(b, 3), "same_headline": h})
    # within-set duplicates
    S2 = [(r["id"], sh(r["text"]), head(r["text"])) for r in items]; seen = {}; within = []
    ii = collections.defaultdict(list)
    for n, (i, s, hh) in enumerate(S2):
        cand = collections.Counter()
        for x in s:
            for m in ii.get(x, ()): cand[m] += 1
        dup = any(c / (len(s) + len(S2[m][1]) - c) >= 0.8 for m, c in cand.items()) or hh in seen
        if dup: within.append(i)
        seen.setdefault(hh, i)
        for x in s: ii[x].append(n)
    out[name] = {"n": len(items), "vs_training_flagged": len(flagged), "vs_training_rate": round(len(flagged) / len(items), 4), "same_headline_in_pool": same_head, "within_set_duplicates": len(within), "within_rate": round(len(within) / len(items), 4), "flagged_ids": [f["id"] for f in flagged], "within_ids": within}
    print(name, {k: v for k, v in out[name].items() if "ids" not in k})
json.dump(out, open("runs/pulse/leakage_check.json", "w"), indent=1)
