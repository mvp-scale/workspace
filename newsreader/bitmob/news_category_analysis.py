"""Paired analysis for the News Category pilot: python3 -I news_category_analysis.py <tmp dir> -> data/external/news_category/pilot_results.json"""
import sys, json, numpy as np
from sklearn.metrics import f1_score
T = sys.argv[1]; W = "/workspace/data"; rng = np.random.RandomState(7)
ft = np.load(f"{W}/suite_r3/e5ft/topic.npz", allow_pickle=True); base = np.load(f"{W}/suite_r3/ensemble/topic.npz", allow_pickle=True)
D = {n: np.load(f"{T}/p{n}.npz") for n in (0, 5000, 20000)}
y0 = D[0]["y"]; k0 = list(D[0]["keys"]); print("N=0 keys equal r3 e5ft keys:", k0 == list(ft["keys"]), "y equal:", (ft["Y"].argmax(1) == y0).all())
def pred(n, ens):
    k = list(D[n]["keys"]); P = D[n]["P"]
    if not ens: return k, P
    kk = list(ft["keys"]); Pf = np.zeros_like(P)   # e5ft fixed at round 3, aligned to this key set (new keys get 0)
    for j, key in enumerate(kk):
        if key in k: Pf[:, k.index(key)] = ft["P"][:, j]
    return k, (P + Pf) / 2
def labelmap(n):   # test label as name, so key sets can differ
    k = list(D[n]["keys"]); return np.array(k)[D[n]["y"]]
ytrue0 = labelmap(0); out = {"keys_by_N": {str(n): len(D[n]["keys"]) for n in D}}
B = 2000; N = len(ytrue0); bi = rng.randint(0, N, (B, N))
def f1s(yt, yp, labels): return f1_score(yt, yp, labels=labels, average=None, zero_division=0)
for ens in (False, True):
    nm = "ensemble_proxy" if ens else "e5tfidf"; k, P = pred(0, ens); p0 = np.array(k)[P.argmax(1)]; c0 = (p0 == ytrue0)
    out[nm] = {"acc_N0": round(float(c0.mean()), 4)}
    for n in (5000, 20000):
        k, P = pred(n, ens); pn = np.array(k)[P.argmax(1)]; yt = labelmap(n); cn = (pn == yt)
        d = cn.astype(float) - c0.astype(float); boot = d[bi].mean(1)
        # macro F1 over the N=0 label set (other collapses unseen labels)
        labs = k0
        def mf(yt_, p_): return f1_score(yt_, p_, labels=labs, average="macro", zero_division=0)
        ytn = np.where(np.isin(yt, labs), yt, "other"); pnn = np.where(np.isin(pn, labs), pn, "other")
        mb = np.array([mf(ytrue0[b], p0[b]) for b in bi[:300]]); mn = np.array([mf(ytn[b], pnn[b]) for b in bi[:300]])
        out[nm][str(n)] = {"acc": round(float(cn.mean()), 4), "dAcc": round(float(d.mean()), 4), "ci95": [round(float(np.percentile(boot, 2.5)), 4), round(float(np.percentile(boot, 97.5)), 4)],
                           "dMacroF1": round(float(mf(ytn, pnn) - mf(ytrue0, p0)), 4), "dMacroF1_ci95_300boot": [round(float(np.percentile(mn - mb, 2.5)), 4), round(float(np.percentile(mn - mb, 97.5)), 4)]}
        if not ens:
            # 10 most-confused topics at N=0 (off-diagonal errors involving the topic as true or predicted)
            from collections import Counter
            conf = Counter((a, b) for a, b in zip(ytrue0, p0) if a != b); tc = Counter()
            for (a, b), v in conf.items(): tc[a] += v; tc[b] += v
            top10 = [t for t, _ in tc.most_common(10)]; f0 = dict(zip(labs, f1s(ytrue0, p0, labs))); fn = dict(zip(labs, f1s(ytn, pnn, labs)))
            out[nm][str(n)]["per_topic_dF1_top10_confused"] = {t: [round(float(f0[t]), 3), round(float(fn[t]), 3), round(float(fn[t] - f0[t]), 3)] for t in top10}
            pairs = [("culture_leisure", "other"), ("elections_politics", "governance_corruption"), ("crime_policing", "terrorism_violence"), ("courts_rulings", "crime_policing")]
            def pc(yt_, p_, a, b): return int(((yt_ == a) & (p_ == b)).sum() + ((yt_ == b) & (p_ == a)).sum())
            out[nm][str(n)]["pair_confusions_N0_to_N"] = {f"{a}/{b}": [pc(ytrue0, p0, a, b), pc(ytn, pnn, a, b)] for a, b in pairs}
            out[nm]["top10_confused"] = top10
json.dump(out, open("/workspace/data/external/news_category/pilot_results.json", "w"), indent=1); print(json.dumps(out, indent=1))
