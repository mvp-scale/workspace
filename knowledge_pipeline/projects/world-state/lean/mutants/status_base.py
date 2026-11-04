import collections, itertools

def status(u):
    c = collections.Counter(u).most_common(); top = c[0][1]
    return "unanimous" if top == len(u) else ("majority" if top > len(u) / 2 else "split")
