"""CO-2 style count: outlets (>=60 test stories) whose country agreement with Jev is below floor(n)=bar-1.96*sqrt(bar(1-bar)/n), bar 0.89 (rev 3 provisional CO-1). Test = night1 held-out + testA (same order as suite npz).
  kev/.venv/bin/python newsreader/bitmob/outlet_floor.py <npz path under data/ without .npz> [...]"""
import sys, json, collections, numpy as np
from sklearn.model_selection import train_test_split
W = "/workspace/data/"; L = lambda f: [json.loads(l) for l in open(f)]; night = L(W + "trainset/night1.jsonl"); _, te = train_test_split(np.arange(len(night)), test_size=0.2, random_state=0)
test = [night[i] for i in te] + L(W + "trainset/testA.jsonl"); bar = 0.89
for p in sys.argv[1:]:
    z = np.load(W + p + ".npz", allow_pickle=True); P = z["P"]
    if "+" in p: pass
    ok = P.argmax(1) == z["Y"].argmax(1); d = collections.defaultdict(list)
    for r, o in zip(test, ok): d[r["outlet"]].append(o)
    fails = sorted((round(float(np.mean(v)), 3), k, len(v)) for k, v in d.items() if len(v) >= 60 and np.mean(v) < bar - 1.96 * (bar * (1 - bar) / len(v)) ** .5)
    print(p, "outlets", sum(len(v) >= 60 for v in d.values()), "below floor", len(fails), fails[:10])
