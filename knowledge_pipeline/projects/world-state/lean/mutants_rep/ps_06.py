import collections, itertools, math

def pair_stats(pairs):
    n = len(pairs); po = sum(a == b for a, b in pairs) / n
    cats = sorted({x for p in pairs for x in p}); ma = collections.Counter(a for a, _ in pairs); mb = collections.Counter(b for _, b in pairs)
    pe = sum(ma[c] / n * mb[c] / n for c in cats); kappa = (po - pe) / (1 - pe) if pe < 1 else float("nan")
    q = len(cats); pi = {c: (ma[c] + mb[c]) / (2 * n) for c in cats}
    ac1 = (po - sum(p * (1 - p) for p in pi.values()) / (q - 2)) / (1 - sum(p * (1 - p) for p in pi.values()) / (q - 1)) if q > 1 else float("nan")
    spec = {c: round(2 * sum(a == c and b == c for a, b in pairs) / (ma[c] + mb[c]), 3) for c in cats if ma[c] + mb[c] >= 20}
    return {"n": n, "raw": round(po, 3), "kappa": round(kappa, 3), "pabak": round((q * po - 1) / (q - 1), 3) if q > 1 else float("nan"), "ac1": round(ac1, 3), "specific_by_answer": spec}
