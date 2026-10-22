"""Shared pieces for the multi-head reader (D-0038): head layout, model, loss, text prep. Used by train_mh.py (Kaggle), score_mh.py and the serving rewrite.
One shared e5-base-v2 encoder (mean pooling, 'query: ' prefix, max_length 96) and one linear head per group. keys.json (written by build_mh_data.py) fixes every head's output names."""
import numpy as np, torch, torch.nn.functional as F
MAXLEN = 96
# head -> (kind, loss weight). sigmoid: multi-label BCE with soft targets. softmax: soft-target cross-entropy. sev: 39 groups of 5 levels, masked soft CE.
HEADS = {"gate": ("sigmoid", 1.0), "scope": ("sigmoid", 0.5), "cond": ("sigmoid", 2.0), "topic_c": ("softmax", 1.0), "topic_y": ("sigmoid", 1.0),
         "region": ("softmax", 0.5), "country": ("softmax", 1.0), "expected": ("sigmoid", 2.0), "done": ("sigmoid", 0.5), "severity": ("sev", 0.5)}
SEV_LEVELS = 5


def head_size(h, keys):
    return len(keys[h]) * SEV_LEVELS if HEADS[h][0] == "sev" else len(keys[h])


class MH(torch.nn.Module):
    def __init__(self, keys, repo="intfloat/e5-base-v2", encoder=None):
        super().__init__()
        from transformers import AutoModel
        self.enc = encoder or AutoModel.from_pretrained(repo); self.keys = keys; hs = self.enc.config.hidden_size
        self.heads = torch.nn.ModuleDict({h: torch.nn.Linear(hs, head_size(h, keys)) for h in HEADS})

    def pooled(self, ids, mask):
        h = self.enc(input_ids=ids, attention_mask=mask).last_hidden_state; m = mask.unsqueeze(-1).to(h.dtype)
        return ((h * m).sum(1) / m.sum(1)).float()

    def forward(self, ids, mask):
        z = self.pooled(ids, mask); out = {}
        for h, lin in self.heads.items():
            o = lin(z); out[h] = o.view(o.shape[0], -1, SEV_LEVELS) if HEADS[h][0] == "sev" else o
        return out


def loss_fn(out, y):
    """y: dict of tensors. Optional per-row masks m_<head> (N,) and row weight w (N,) (round 2: a row trains only the heads its labels cover; Clef rows weigh more).
    Without them (round 1 data) every row trains every head with weight 1, as before. expected_mask (N,78), done_mask (N,), sev_mask (N,39) as in round 1."""
    L = {}; N = out["gate"].shape[0]; one = out["gate"].new_ones(N); w = y.get("w", one)
    def rm(l, head):      # per-row loss l (N,), row mask for the head, row weight -> weighted mean over rows that train this head
        m = y.get("m_" + head, one) * w; return (l * m).sum() / m.sum().clamp(min=1e-6)
    B = F.binary_cross_entropy_with_logits
    L["gate"] = rm(B(out["gate"], y["gate"], reduction="none").mean(-1), "gate"); L["scope"] = rm(B(out["scope"], y["scope"], reduction="none").mean(-1), "scope")
    L["cond"] = rm(B(out["cond"], y["cond"], reduction="none").mean(-1), "cond"); L["topic_y"] = rm(B(out["topic_y"], y["topic_y"], reduction="none").mean(-1), "topic_y")
    for h in ("topic_c", "region", "country"): L[h] = rm(-(y[h] * F.log_softmax(out[h], -1)).sum(-1), h)
    m = y["expected_mask"] * w[:, None]; L["expected"] = (B(out["expected"], y["expected"], reduction="none") * m).sum() / m.sum().clamp(min=1)
    m = y["done_mask"] * w; L["done"] = (B(out["done"][:, 0], y["done"], reduction="none") * m).sum() / m.sum().clamp(min=1)
    m = y["sev_mask"] * w[:, None]; ce = -(y["severity"] * F.log_softmax(out["severity"], -1)).sum(-1); L["severity"] = (ce * m).sum() / m.sum().clamp(min=1)
    return sum(HEADS[h][1] * v for h, v in L.items()), {h: float(v) for h, v in L.items()}


ATTR_MIN = 0.65      # classify.ATTR_MIN: the engine fires a reading when the mean of an attribute's two wordings is >= this


def calibrate_pivot(p, cuts, pivot):
    """Monotone map sending each key's tuned cut to the engine's own bar `pivot` ([0,c] -> [0,pivot], [c,1] -> [pivot,1]); cuts None = no-op."""
    if cuts is None: return p
    c = np.clip(np.asarray(cuts, np.float32), 0.01, 0.99)[None, :]
    return np.where(p <= c, pivot * p / c, pivot + (1 - pivot) * (p - c) / (1 - c)).astype(np.float32)


def calibrate_cond(p, cuts):
    """Per-attribute monotone map p -> p' with the tuned cut c sent to ATTR_MIN: [0,c] -> [0,.65], [c,1] -> [.65,1]. cuts: array (n_attr,) or None (no-op, round-1 models)."""
    if cuts is None: return p
    c = np.clip(np.asarray(cuts, np.float32), 0.01, 0.99)[None, :]
    return np.where(p <= c, ATTR_MIN * p / c, ATTR_MIN + (1 - ATTR_MIN) * (p - c) / (1 - c)).astype(np.float32)


def tokenise(tok, texts, device="cpu"):
    b = tok(["query: " + t for t in texts], padding=True, truncation=True, max_length=MAXLEN, return_tensors="pt"); return b["input_ids"].to(device), b["attention_mask"].to(device)


def predict(model, tok, texts, device="cpu", bs=32):
    """-> dict head -> numpy probabilities (sigmoid / softmax; severity (N,39,5) softmax)."""
    model.eval(); res = {h: [] for h in HEADS}
    with torch.inference_mode():
        for s in range(0, len(texts), bs):
            ids, mask = tokenise(tok, texts[s:s + bs], device); out = model(ids, mask)
            for h, o in out.items(): res[h].append((torch.sigmoid(o) if HEADS[h][0] == "sigmoid" else torch.softmax(o, -1)).cpu().numpy())
    res = {h: np.concatenate(v) for h, v in res.items()}
    cuts = getattr(model, "cond_cuts", None)
    if cuts is not None: res["cond"] = calibrate_cond(res["cond"], cuts)      # the engine's own 0.65 bar then means "above the tuned cut"
    gc = getattr(model, "gate_cuts", None)
    if gc is not None:      # per-question gate cuts (round 4): each tuned cut maps to the engine's own bar for that question
        for k, (c, pv) in gc.items(): j = model.keys["gate"].index(k); res["gate"][:, j] = calibrate_pivot(res["gate"][:, j:j + 1], np.array([c], np.float32), pv)[:, 0]
    ec = getattr(model, "exp_cuts", None)
    if ec is not None: res["expected"] = calibrate_pivot(res["expected"], ec, 0.5)      # engine's EXPECT_MIN .5 then means "above the tuned cut" (round 4)
    return res


def save(model, tok, out_dir, keys):
    import os, json
    os.makedirs(f"{out_dir}/encoder", exist_ok=True); model.enc.save_pretrained(f"{out_dir}/encoder"); tok.save_pretrained(f"{out_dir}/encoder")
    for h, lin in model.heads.items():
        os.makedirs(f"{out_dir}/{h}", exist_ok=True); torch.save({k: v.half().cpu() for k, v in lin.state_dict().items()}, f"{out_dir}/{h}/head.pt"); json.dump(keys[h], open(f"{out_dir}/{h}/keys.json", "w"))
    json.dump(keys, open(f"{out_dir}/keys.json", "w"))


def load(model_dir, device="cpu"):
    import json, os
    from transformers import AutoModel, AutoTokenizer
    keys = json.load(open(f"{model_dir}/keys.json")); tok = AutoTokenizer.from_pretrained(f"{model_dir}/encoder")
    m = MH(keys, encoder=AutoModel.from_pretrained(f"{model_dir}/encoder").float())
    for h, lin in m.heads.items(): lin.load_state_dict({k: v.float() for k, v in torch.load(f"{model_dir}/{h}/head.pt").items()})
    cp = f"{model_dir}/cuts.json"      # written by tune_cuts.py; absent for round-1 models = no calibration
    cj = json.load(open(cp)) if os.path.exists(cp) else {}
    m.cond_cuts = np.array(cj["cond_cuts"], np.float32) if "cond_cuts" in cj else None
    m.gate_cuts = {k: (v, cj["gate_cuts_pivots"][k]) for k, v in cj["gate_cuts"].items()} if "gate_cuts" in cj else None
    m.exp_cuts = np.array(cj["exp_cuts"], np.float32) if "exp_cuts" in cj else None
    return m.to(device).eval(), tok, keys
