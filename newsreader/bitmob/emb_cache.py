"""e5 embedding cache keyed by story id + model (round speed-up, D-0013). data/emb_cache/<model>.json (id -> row) + <model>.npy (float32).
  from emb_cache import EmbCache; c = EmbCache("e5-small-v2"); E = c.get(ids, texts, encode_fn); c.save()"""
import os, json, numpy as np
D = "/workspace/data/emb_cache"
class EmbCache:
    def __init__(self, model):
        os.makedirs(D, exist_ok=True); self.j, self.n = f"{D}/{model}.json", f"{D}/{model}.npy"
        self.idx = json.load(open(self.j)) if os.path.exists(self.j) else {}; self.E = np.load(self.n) if os.path.exists(self.n) else np.zeros((0, 384), np.float32)
        self.hits = self.miss = 0
    def get(self, ids, texts, encode, chunk=4096):
        need = [i for i, k in enumerate(ids) if k not in self.idx]; self.hits += len(ids) - len(need); self.miss += len(need)
        for s in range(0, len(need), chunk):
            part = need[s:s + chunk]; new = np.asarray(encode([texts[i] for i in part]), np.float32)
            for i in part: self.idx[ids[i]] = len(self.idx)
            self.E = np.vstack([self.E, new]); self.save()
        return self.E[[self.idx[k] for k in ids]]
    def save(self):
        np.save(self.n, self.E); json.dump(self.idx, open(self.j, "w"))
