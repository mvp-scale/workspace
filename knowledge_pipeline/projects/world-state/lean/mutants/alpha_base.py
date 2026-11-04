import collections, itertools

def alpha(units, interval=False):
    """Krippendorff alpha. units: list of lists of values (missing already dropped). nominal by default."""
    o = collections.defaultdict(float); n = 0
    for u in units:
        m = len(u)
        if m < 2: continue
        for a, b in itertools.permutations(range(m), 2): o[(u[a], u[b])] += 1 / (m - 1)
        n += m
    if n < 2: return None
    nc = collections.defaultdict(float)
    for (a, b), v in o.items(): nc[a] += v
    d = (lambda a, b: (a - b) ** 2) if interval else (lambda a, b: 0 if a == b else 1)
    Do = sum(v * d(a, b) for (a, b), v in o.items()) / n
    De = sum(nc[a] * nc[b] * d(a, b) for a in nc for b in nc) / (n * (n - 1))
    return None if De == 0 else round(1 - Do / De, 3)
