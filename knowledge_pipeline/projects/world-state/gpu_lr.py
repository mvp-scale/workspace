"""GPU softmax regression (sparse TF-IDF + dense features), same objective as sklearn LogisticRegression(C): C * sum(CE) + 0.5 * ||W||^2. 620x faster than sklearn on the topic head (L288)."""
import numpy as np, scipy.sparse as sp, torch
def _csr(X, dev): X = X.tocsr().astype(np.float32); return torch.sparse_csr_tensor(torch.tensor(X.indptr, dtype=torch.int64), torch.tensor(X.indices, dtype=torch.int64), torch.tensor(X.data), size=X.shape).to(dev)
def fit(Xs, Xd, y, n_classes, C=3.0, iters=300, dev="cuda"):
    Y = torch.tensor(y, device=dev); S = _csr(Xs, dev); D = torch.tensor(Xd, dtype=torch.float32, device=dev) if Xd is not None else None
    W = torch.zeros(Xs.shape[1], n_classes, device=dev, requires_grad=True); V = torch.zeros(Xd.shape[1], n_classes, device=dev, requires_grad=True) if Xd is not None else None; b = torch.zeros(n_classes, device=dev, requires_grad=True)
    ps = [p for p in (W, V, b) if p is not None]; opt = torch.optim.LBFGS(ps, lr=1, max_iter=iters, history_size=20, line_search_fn="strong_wolfe", tolerance_grad=1e-5, tolerance_change=1e-9)
    def closure():
        opt.zero_grad(); z = torch.sparse.mm(S, W) + b + (D @ V if D is not None else 0); L = C * torch.nn.functional.cross_entropy(z, Y, reduction="sum") + 0.5 * (W ** 2).sum() + (0.5 * (V ** 2).sum() if V is not None else 0); L.backward(); return L
    opt.step(closure); return (W.detach(), None if V is None else V.detach(), b.detach())
def predict(m, Xs, Xd, dev="cuda"):
    W, V, b = m; z = torch.sparse.mm(_csr(Xs, dev), W) + b
    if V is not None: z = z + torch.tensor(Xd, dtype=torch.float32, device=dev) @ V
    return torch.softmax(z, 1).cpu().numpy()

def fit_soft(Xs, Xd, Y, C=3.0, iters=300, dev="cuda"):
    """Same objective with SOFT targets Y (n x k rows summing to 1): C * sum(-Y log softmax) + 0.5 * ||W||^2."""
    Yt = torch.tensor(np.asarray(Y, dtype=np.float32), device=dev); k = Yt.shape[1]; S = _csr(Xs, dev); D = torch.tensor(Xd, dtype=torch.float32, device=dev) if Xd is not None else None
    W = torch.zeros(Xs.shape[1], k, device=dev, requires_grad=True); V = torch.zeros(Xd.shape[1], k, device=dev, requires_grad=True) if Xd is not None else None; b = torch.zeros(k, device=dev, requires_grad=True)
    ps = [p for p in (W, V, b) if p is not None]; opt = torch.optim.LBFGS(ps, lr=1, max_iter=iters, history_size=20, line_search_fn="strong_wolfe", tolerance_grad=1e-5, tolerance_change=1e-9)
    def closure():
        opt.zero_grad(); z = torch.sparse.mm(S, W) + b + (D @ V if D is not None else 0); L = C * -(Yt * torch.log_softmax(z, 1)).sum() + 0.5 * (W ** 2).sum() + (0.5 * (V ** 2).sum() if V is not None else 0); L.backward(); return L
    opt.step(closure); return (W.detach(), None if V is None else V.detach(), b.detach())
