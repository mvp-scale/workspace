"""Destination section: how many stories in the extract records appear at more than one publisher.
Pre-registered at ledger L1051. A = near-duplicate text (word 5-shingles, Jaccard >= 0.5, different domain).
B = same story in other words (>= 3 shared PERSON/ORG/GPE names, dates within 3 days, different domain).
    python3 multi_publisher.py   (from projects/world-state)"""
import json, re, itertools, datetime as dt
from collections import defaultdict
R = [json.loads(l) for l in open("runs/harvest/extract.jsonl", encoding="utf-8")]
def day(r):
    try: return dt.date.fromisoformat((r["source"].get("date") or "")[:10])
    except Exception: return None
def shingles(t):
    w = re.findall(r"[a-z0-9']+", t.lower()); return {" ".join(w[i:i+5]) for i in range(max(len(w)-4, 0))}
def names(r): return {e[0].lower() for e in r["entities"]["items"] if e[1] in ("PERSON", "ORG", "GPE")}
S = [shingles(r["text"]) for r in R]; N = [names(r) for r in R]; D = [day(r) for r in R]; DOM = [r["source"]["domain"] for r in R]
# inverted indexes so we do not compare all pairs
idx_s = defaultdict(set); idx_n = defaultdict(set)
for i, s in enumerate(S):
    for x in s: idx_s[x].add(i)
for i, n in enumerate(N):
    for x in n: idx_n[x].add(i)
def pairs(idx, minshare):
    cnt = defaultdict(int)
    for ids in idx.values():
        if len(ids) > 40: continue
        for a, b in itertools.combinations(sorted(ids), 2): cnt[(a, b)] += 1
    return {p for p, c in cnt.items() if c >= minshare}
A = set(); B = set()
for a, b in pairs(idx_s, 3):
    if DOM[a] == DOM[b]: continue
    j = len(S[a] & S[b]) / max(len(S[a] | S[b]), 1)
    if j >= 0.5: A.add((a, b))
for a, b in pairs(idx_n, 3):
    if DOM[a] == DOM[b] or D[a] is None or D[b] is None or abs((D[a]-D[b]).days) > 3: continue
    if len(N[a] & N[b]) >= 3: B.add((a, b))
def clusters(P):
    par = {}
    def f(x):
        while par.setdefault(x, x) != x: par[x] = par[par[x]]; x = par[x]
        return x
    for a, b in P: par[f(a)] = f(b)
    g = defaultdict(set)
    for x in list(par): g[f(x)].add(x)
    return [sorted(v) for v in g.values() if len({DOM[i] for i in v}) >= 2]
out = {"n_records": len(R), "A_clusters": clusters(A), "B_clusters": clusters(B)}
out["A_count"] = len(out["A_clusters"]); out["B_count"] = len(out["B_clusters"])
json.dump(out, open("runs/harvest/multi_publisher.json", "w"))
print("A", out["A_count"], "B", out["B_count"])
for k in ("A_clusters", "B_clusters"):
    for c in sorted(out[k], key=lambda c: -len(c))[:6]:
        print(k[0], len(c), [DOM[i] for i in c][:5], "|", R[c[0]]["text"][:90].replace("\n", " "))
