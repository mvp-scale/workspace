"""A1b second formulation (pre-registered in docs/value-indicators.md): the multi-task network with inputs Glance full + Glance lead + Scholar lead
(each unit-normalised), five seeds averaged, same cross-fitting and scorer. Also as a fourth all-agree jury voter."""
import sys, os, numpy as np, torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import value_eval as V
import attack_a1_shared as S1
n_ = lambda X: X / np.linalg.norm(X, axis=1, keepdims=True)
F = f"{V.D}/features"; G3 = np.hstack([n_(np.load(f"{F}/glance_full.npy")), n_(np.load(f"{F}/glance_lead.npy")), n_(np.load(f"{F}/scholar_lead.npy"))]).astype(np.float32)
def mt(rows, outs, seed, epochs=60):
    torch.manual_seed(seed); A = V.ATOMS
    net = torch.nn.Sequential(torch.nn.Linear(G3.shape[1], 256), torch.nn.ReLU(), torch.nn.Dropout(0.2), torch.nn.Linear(256, len(A)))
    X, Y = torch.tensor(G3[rows]), torch.tensor(S1.Yall[rows]); pw = torch.tensor(np.clip((1 - S1.Yall[rows].mean(0)) / np.maximum(S1.Yall[rows].mean(0), 1e-3), 1, 50))
    opt = torch.optim.AdamW(net.parameters(), lr=2e-3, weight_decay=1e-3); lossf = torch.nn.BCEWithLogitsLoss(pos_weight=pw)
    for ep in range(epochs):
        net.train(); perm = torch.randperm(len(rows))
        for i in range(0, len(rows), 64): b = perm[i:i + 64]; opt.zero_grad(); lossf(net(X[b]), Y[b]).backward(); opt.step()
    net.eval()
    with torch.no_grad(): return [torch.sigmoid(net(torch.tensor(G3[r]))).numpy() for r in outs]
Sg = sum(S1.cross(lambda r, o, s=s: mt(r, o, s)) for s in range(5)) / 5
Sb1 = sum(S1.cross(lambda r, o, s=s: S1.mt_fp(r, o) if not torch.manual_seed(100 + s) is None else None) for s in range(5)) / 5
np.savez(f"{V.D}/proof/a1b2-scores.npz", Sg=Sg, Sb1=Sb1)
opts = {"A1b multi-task, Glance only, 5 seeds": {n: Sb1[:, k] for k, n in enumerate(V.ATOMS)}, "A1b'' multi-task, Glance+lead+Scholar lead, 5 seeds": {n: Sg[:, k] for k, n in enumerate(V.ATOMS)}}
# as a fourth voter in the jury (its own best-F1 cut on training scores)
from sklearn.metrics import f1_score
jp = V.jury_preds().copy()
for k, n in enumerate(V.ATOMS):
    s = Sg[:, k]; lab = V.L[n]["agreed"]; c = max(np.linspace(.02, .98, 49), key=lambda t: f1_score(lab[V.TRN], s[V.TRN] >= t))
    for j, d in enumerate(V.DS): jp[j, k] &= s[V.test] >= V.shift(c, d)
opts["jury + A1b'' as 4th voter"] = jp
V.evaluate(opts, out_file=f"{V.D}/proof/a1b2-results.json")
