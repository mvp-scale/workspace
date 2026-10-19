"""Attack A1 (docs/value-indicators.md): one shared model across atoms, so rare atoms borrow from common ones. Four formulations, written before running:
  (a) pair model: logistic over [story vector, atom vector, story x atom] for every (story, atom) pair; atom vector = Glance encoding of its two wordings
  (b) multi-task network: story vector -> 256 hidden (ReLU, dropout 0.2) -> one output per atom, one network for all atoms
  (c) blend: the per-atom head's score averaged with (b)'s score (rank average within each atom)
  (d) outside idea, nearest neighbours: per atom, the similarity-weighted share of positives among the 25 most similar training stories
Story vector = Glance full story (the single head's input, so any gain is the sharing, not the features). Cross-fitted: 5 folds over the training
stories with the same fold seed as the baselines; test scored by the average of the five fold models. Scored by value_eval.py.
Run: models/embed-zs/.venv/bin/python -I newsreader/bitmob/attack_a1_shared.py"""
import sys, os, json, numpy as np, torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import value_eval as V
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold
from model2vec import StaticModel
torch.set_num_threads(8); torch.manual_seed(0)
G = np.load(f"{V.D}/features/glance_full.npy").astype(np.float32); G /= np.linalg.norm(G, axis=1, keepdims=True)
A = V.ATOMS; Yall = np.array([V.L[n]["agreed"] for n in A]).T.astype(np.float32)          # stories x atoms
QT = {}
for f in __import__("glob").glob("/workspace/newsreader/bitmob/batteries/evidence-v*.json"):
    for c in json.load(open(f))["concerns"]: QT[c["atom"]] = c["probes"]["a"] + " " + c["probes"]["b"]
FIRSTQ = {"civil_unrest|up": "report protests, riots or civil unrest; people marching or striking", "war_terror|up": "report armed conflict or terrorism; an attack, battle or escalation",
          "crime|up": "report a crime; a criminal act, arrest, charge or police investigation", "cyber_insecurity|up": "report a cyber risk; a hack, data breach, flaw or online scam"}
QT.update(FIRSTQ); pm = StaticModel.from_pretrained("minishlab/potion-base-32M")
Qv = pm.encode([QT[a].replace("{file}", "the story") for a in A]).astype(np.float32); Qv /= np.linalg.norm(Qv, axis=1, keepdims=True)
tr_idx = np.where(V.TRN)[0]; te_idx = np.where(V.test)[0]; folds = list(KFold(5, shuffle=True, random_state=0).split(tr_idx))
def cross(fit_predict):
    """fit_predict(train_rows, predict_rows) -> predictions (rows x atoms). Returns scores (stories x atoms): OOF on train, fold-average on test."""
    S = np.zeros((len(V.ids), len(A)), np.float32)
    for a, b in folds:
        p_b, p_t = fit_predict(tr_idx[a], [tr_idx[b], te_idx]); S[tr_idx[b]] = p_b; S[te_idx] += p_t / 5
    return S
# (a) pair model
def pair_fp(rows, outs):
    X = lambda r: np.hstack([np.repeat(G[r], len(A), 0), np.tile(Qv, (len(r), 1)), (np.repeat(G[r], len(A), 0) * np.tile(Qv, (len(r), 1)))])
    y = Yall[rows].reshape(-1); w = np.where(y > 0, (1 - y.mean()) / max(y.mean(), 1e-3), 1.0)
    m = LogisticRegression(C=2, max_iter=3000).fit(X(rows), y, sample_weight=w)
    return [m.predict_proba(X(r))[:, 1].reshape(len(r), len(A)) for r in outs]
# (b) multi-task network
def mt_fp(rows, outs, epochs=60):
    net = torch.nn.Sequential(torch.nn.Linear(G.shape[1], 256), torch.nn.ReLU(), torch.nn.Dropout(0.2), torch.nn.Linear(256, len(A)))
    X, Y = torch.tensor(G[rows]), torch.tensor(Yall[rows]); pw = torch.tensor(np.clip((1 - Yall[rows].mean(0)) / np.maximum(Yall[rows].mean(0), 1e-3), 1, 50))
    opt = torch.optim.AdamW(net.parameters(), lr=2e-3, weight_decay=1e-3); lossf = torch.nn.BCEWithLogitsLoss(pos_weight=pw)
    for ep in range(epochs):
        net.train(); perm = torch.randperm(len(rows))
        for i in range(0, len(rows), 64): b = perm[i:i + 64]; opt.zero_grad(); lossf(net(X[b]), Y[b]).backward(); opt.step()
    net.eval()
    with torch.no_grad(): return [torch.sigmoid(net(torch.tensor(G[r]))).numpy() for r in outs]
# (d) nearest neighbours
def knn_fp(rows, outs, k=25):
    res = []
    for r in outs:
        sim = G[r] @ G[rows].T; top = np.argsort(-sim, 1)[:, :k]; wt = np.take_along_axis(sim, top, 1).clip(0); wt /= wt.sum(1, keepdims=True) + 1e-9
        res.append(np.einsum("nk,nka->na", wt, Yall[rows][top]))
    return res
if __name__ == "__main__":
    print("training (a) pair model", flush=True); Sa = cross(pair_fp)
    print("training (b) multi-task network", flush=True); Sb = cross(mt_fp)
    print("training (d) nearest neighbours", flush=True); Sd = cross(knn_fp)
    rank = lambda x: np.argsort(np.argsort(x)) / max(1, len(x) - 1)
    single = {n: V.PP[n]["glance_full", "agreed"] for n in A}
    Sc = {n: (rank(single[n]) + rank(Sb[:, k])) / 2 for k, n in enumerate(A)}
    opts = {"A1a pair model": {n: Sa[:, k] for k, n in enumerate(A)}, "A1b multi-task network": {n: Sb[:, k] for k, n in enumerate(A)},
            "A1c blend (per-atom head + multi-task)": Sc, "A1d nearest neighbours": {n: Sd[:, k] for k, n in enumerate(A)}}
    np.savez(f"{V.D}/proof/a1-scores.npz", Sa=Sa, Sb=Sb, Sd=Sd)
    V.evaluate(opts, out_file=f"{V.D}/proof/a1-results.json")
