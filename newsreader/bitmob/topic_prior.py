"""Topic prior correction: P_adj = P / prior^a (prior = train topic share), a fitted on the night1 held-out part (first n_night rows) by accuracy, scored on testA only. Also TP-3 count: topics with >=30 test positives whose recall < floor(n)=bar-1.96*sqrt(bar(1-bar)/n), bar 0.79 (rev 3 provisional TP-1).
  kev/.venv/bin/python newsreader/bitmob/topic_prior.py"""
import numpy as np, json, glob, os
W = "/workspace/data/"; ld = lambda p: np.load(W + p + ".npz", allow_pickle=True)
tf = ld("suite_r3/e5tfidf/topic"); Y = tf["Y"].argmax(1); nn = int(tf["n_night"]); keys = list(tf["keys"])
tr = [json.loads(l)["topic"] for l in open(W + "kaggle/ds_r4/train.jsonl")]; prior = np.array([max(1, sum(t == k for t in tr if True)) for k in keys], float)
if prior.sum() == 0: raise SystemExit("no prior")
prior /= prior.sum(); bar = 0.79
P = (ld("suite_kaggle7/e5b_ep3_lr3e-5/topic")["P"] + ld("suite_r5/e5tfidf/topic")["P"]) / 2      # r7 + tfidf r5 (D-0036)
def tp3(Q, rng):
    pred = Q.argmax(1); c = 0
    for j in range(len(keys)):
        m = Y[rng] == j; n = int(m.sum())
        if n >= 30 and (pred[rng][m] == j).mean() < bar - 1.96 * (bar * (1 - bar) / n) ** .5: c += 1
    return c
v, t = slice(0, nn), slice(nn, None)
for a in [0, .1, .2, .3, .4, .5, .7, 1.0]:
    Q = P / prior ** a; print(a, "night1 acc", round(float((Q[v].argmax(1) == Y[v]).mean()), 4), "testA acc", round(float((Q[t].argmax(1) == Y[t]).mean()), 4), "TP3 fails testA", tp3(Q, t))
