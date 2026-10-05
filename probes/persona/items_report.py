import json
import numpy as np
from scipy.stats import spearmanr
from personas import gen
R = json.load(open("/workspace/data/persona-lab/items.json")); n = 400; pers = [gen(s) for s in range(1, n + 1)]
rng = np.random.default_rng(0)
lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))
def z(x): return (x - x.mean(0)) / (x.std(0) + 1e-9)
rho = lambda a, b: float(spearmanr(a, b)[0])
print(f"{'trait':8s} {'sat%':>5s} {'alpha':>6s} {'split':>6s} {'rho1':>6s} {'rho2':>6s} {'rho4':>6s} {'rho6':>6s} {'rho10':>6s} {'weak1%':>7s}")
ok = {}
for t, rows in R.items():
    P = np.array(rows); Z = z(lg(P)); lat = np.array([p["latent"][t] for p in pers])
    sat = float(np.mean((P < .05) | (P > .95))) * 100
    k = Z.shape[1]; alpha = k / (k - 1) * (1 - Z.var(0, ddof=1).sum() / Z.sum(1).var(ddof=1))
    a, b = Z[:, ::2].mean(1), Z[:, 1::2].mean(1); sh = np.corrcoef(a, b)[0, 1]; sb = 2 * sh / (1 + sh)
    single = [rho(Z[:, j], lat) for j in range(k)]
    def sub(m): return float(np.mean([rho(Z[:, rng.choice(k, m, replace=False)].mean(1), lat) for _ in range(200)]))
    r = {m: sub(m) for m in (2, 4, 6, 10)}
    print(f"{t:8s} {sat:5.0f} {alpha:6.2f} {sb:6.2f} {np.mean(single):6.2f} {r[2]:6.2f} {r[4]:6.2f} {r[6]:6.2f} {r[10]:6.2f} {100*np.mean(np.array(single)<.4):7.0f}")
    # flag rule
    sd = Z.std(1); flag = sd > np.quantile(sd, .9); score = Z.mean(1)
    # error vs hidden trait: rank-based residual
    rk = lambda x: np.argsort(np.argsort(x)) / (len(x) - 1)
    err = np.abs(rk(score) - rk(lat))
    ok[t] = dict(alpha=alpha, sb=sb, r1=float(np.mean(single)), r6=r[6], r10=r[10], sat=sat, ferr=float(err[flag].mean()), uerr=float(err[~flag].mean()))
print("\nR1 alpha>=.80 & split>=.80:", {t: v["alpha"] >= .8 and v["sb"] >= .8 for t, v in ok.items()})
print("R2 rho10>=.80:", {t: v["r10"] >= .8 for t, v in ok.items()}, "| gain over single item >= .10 where single < .75:", {t: (v["r10"] - v["r1"] >= .10) for t, v in ok.items() if v["r1"] < .75})
print("R3 rho6 within .03 of rho10:", {t: abs(v["r10"] - v["r6"]) <= .03 for t, v in ok.items()})
print("R4 any trait with >50% saturated:", {t: round(v["sat"]) for t, v in ok.items() if v["sat"] > 50})
print("flag rule: mean rank error flagged vs unflagged:", {t: (round(v["ferr"], 2), round(v["uerr"], 2)) for t, v in ok.items()})
