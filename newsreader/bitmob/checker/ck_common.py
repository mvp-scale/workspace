"""CPU checker (F-0110): a small cross-encoder that reads "query: <question> || <story>" for ONE attribute / gate question / expected-impact question and predicts Clef's probability.
Shared by the Kaggle trainer and local scoring. Clef is only the teacher (soft targets); serving is CPU only."""
import numpy as np, torch
MAXLEN = 192; QCHARS = 300


def ck_text(q, story):
    return f"query: {q[:QCHARS]} || {story}"


class Checker(torch.nn.Module):
    def __init__(self, repo="intfloat/e5-small-v2", encoder=None):
        super().__init__()
        from transformers import AutoModel
        self.enc = encoder or AutoModel.from_pretrained(repo); self.head = torch.nn.Linear(self.enc.config.hidden_size, 1)

    def forward(self, ids, mask):
        h = self.enc(input_ids=ids, attention_mask=mask).last_hidden_state; m = mask.unsqueeze(-1).to(h.dtype)
        return self.head(((h * m).sum(1) / m.sum(1)).float())[:, 0]


def ck_tokenise(tok, texts, device="cpu"):
    b = tok(texts, padding=True, truncation=True, max_length=MAXLEN, return_tensors="pt"); return b["input_ids"].to(device), b["attention_mask"].to(device)


def ck_predict(model, tok, texts, bs=64, device="cpu"):
    model.eval(); out = []
    with torch.inference_mode():
        order = np.argsort([len(t) for t in texts]); res = np.zeros(len(texts), np.float32)      # length-sorted batches = less padding
        for s in range(0, len(texts), bs):
            ix = order[s:s + bs]; ids, mask = ck_tokenise(tok, [texts[i] for i in ix], device); res[ix] = torch.sigmoid(model(ids, mask)).cpu().numpy()
    return res


def ck_save(model, tok, d):
    import os; os.makedirs(d, exist_ok=True); model.enc.save_pretrained(f"{d}/encoder"); tok.save_pretrained(f"{d}/encoder"); torch.save({k: v.float().cpu() for k, v in model.head.state_dict().items()}, f"{d}/head.pt")


def ck_load(d):
    from transformers import AutoModel, AutoTokenizer
    m = Checker(encoder=AutoModel.from_pretrained(f"{d}/encoder").float()); m.head.load_state_dict(torch.load(f"{d}/head.pt")); return m.eval(), AutoTokenizer.from_pretrained(f"{d}/encoder")
