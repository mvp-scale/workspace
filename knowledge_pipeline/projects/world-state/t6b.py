exec(open("t6_answerable.py").read().split("conf = np.maximum")[0])
conf = np.maximum(p, 1 - p); yh = (p > 0.5).astype(int)
v = np.array([i in sn for i in ids]); ix = np.where(v)[0]
sy = np.array([1 if (ids[k] in sn and sn[ids[k]]["conditions"]) else 0 for k in range(len(ids))])
def curve(metric):
    o = ix[np.argsort(-conf[ix])]; return {f"{int(c*100)}%": round(float(metric(o[:int(len(o)*c)])), 3) for c in (1.0, .8, .6, .5, .4, .3, .2, .1)}
res = {"student_vs_sonnet": curve(lambda s: (yh[s] == sy[s]).mean()), "student_vs_haiku": curve(lambda s: (yh[s] == y[s]).mean()), "sonnet_positive_rate_on_slice": curve(lambda s: sy[s].mean())}
json.dump(res, open(H0 / "runs/structure/t6b.json", "w"), indent=1); print(json.dumps(res, indent=1))
o = ix[np.argsort(-conf[ix])]; a = (yh[o] == sy[o]); k = len(o) // 2
print("exact", a.mean(), a[:k].mean(), a[:k].mean() - a.mean(), "always-absent", 1 - sy[o].mean(), 1 - sy[o[:k]].mean())
