"""Shared pieces for the multi-head reader (D-0038): head layout, model, loss, text prep. Used by train_mh.py (Kaggle), score_mh.py and the serving rewrite.
One shared e5-base-v2 encoder (mean pooling, 'query: ' prefix, max_length 96) and one linear head per group. keys.json (written by build_mh_data.py) fixes every head's output names."""
import numpy as np, torch, torch.nn.functional as F
MAXLEN = 96
# head -> (kind, loss weight). sigmoid: multi-label BCE with soft targets. softmax: soft-target cross-entropy. sev: 39 groups of 5 levels, masked soft CE.
HEADS = {"gate": ("sigmoid", 1.0), "scope": ("sigmoid", 0.5), "cond": ("sigmoid", 2.0), "topic_c": ("softmax", 1.0), "topic_y": ("sigmoid", 1.0),
         "region": ("softmax", 0.5), "country": ("softmax", 1.0), "expected": ("sigmoid", 1.0), "done": ("sigmoid", 0.5), "severity": ("sev", 0.5)}
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
    """y: dict of tensors; masks: expected_mask (N,78), done_mask (N,), sev_mask (N,39). Returns total, per-head dict."""
    L = {}
    L["gate"] = F.binary_cross_entropy_with_logits(out["gate"], y["gate"]); L["scope"] = F.binary_cross_entropy_with_logits(out["scope"], y["scope"])
    L["cond"] = F.binary_cross_entropy_with_logits(out["cond"], y["cond"]); L["topic_y"] = F.binary_cross_entropy_with_logits(out["topic_y"], y["topic_y"])
    for h in ("topic_c", "region", "country"): L[h] = -(y[h] * F.log_softmax(out[h], -1)).sum(-1).mean()
    m = y["expected_mask"]; L["expected"] = (F.binary_cross_entropy_with_logits(out["expected"], y["expected"], reduction="none") * m).sum() / m.sum().clamp(min=1)
    m = y["done_mask"]; L["done"] = (F.binary_cross_entropy_with_logits(out["done"][:, 0], y["done"], reduction="none") * m).sum() / m.sum().clamp(min=1)
    m = y["sev_mask"]; ce = -(y["severity"] * F.log_softmax(out["severity"], -1)).sum(-1); L["severity"] = (ce * m).sum() / m.sum().clamp(min=1)
    return sum(HEADS[h][1] * v for h, v in L.items()), {h: float(v) for h, v in L.items()}


def tokenise(tok, texts, device="cpu"):
    b = tok(["query: " + t for t in texts], padding=True, truncation=True, max_length=MAXLEN, return_tensors="pt"); return b["input_ids"].to(device), b["attention_mask"].to(device)


def predict(model, tok, texts, device="cpu", bs=32):
    """-> dict head -> numpy probabilities (sigmoid / softmax; severity (N,39,5) softmax)."""
    model.eval(); res = {h: [] for h in HEADS}
    with torch.inference_mode():
        for s in range(0, len(texts), bs):
            ids, mask = tokenise(tok, texts[s:s + bs], device); out = model(ids, mask)
            for h, o in out.items(): res[h].append((torch.sigmoid(o) if HEADS[h][0] == "sigmoid" else torch.softmax(o, -1)).cpu().numpy())
    return {h: np.concatenate(v) for h, v in res.items()}


def save(model, tok, out_dir, keys):
    import os, json
    os.makedirs(f"{out_dir}/encoder", exist_ok=True); model.enc.save_pretrained(f"{out_dir}/encoder"); tok.save_pretrained(f"{out_dir}/encoder")
    for h, lin in model.heads.items():
        os.makedirs(f"{out_dir}/{h}", exist_ok=True); torch.save({k: v.half().cpu() for k, v in lin.state_dict().items()}, f"{out_dir}/{h}/head.pt"); json.dump(keys[h], open(f"{out_dir}/{h}/keys.json", "w"))
    json.dump(keys, open(f"{out_dir}/keys.json", "w"))


def load(model_dir, device="cpu"):
    import json
    from transformers import AutoModel, AutoTokenizer
    keys = json.load(open(f"{model_dir}/keys.json")); tok = AutoTokenizer.from_pretrained(f"{model_dir}/encoder")
    m = MH(keys, encoder=AutoModel.from_pretrained(f"{model_dir}/encoder").float())
    for h, lin in m.heads.items(): lin.load_state_dict({k: v.float() for k, v in torch.load(f"{model_dir}/{h}/head.pt").items()})
    return m.to(device).eval(), tok, keys
