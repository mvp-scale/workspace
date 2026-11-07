"""Whole-article topic reading (T42, L995 and L998): the same reader and heads, run over 64-piece windows of the article and the 49 topic probabilities averaged.
    from article_reader import read_article ; read_article(expert, title, body)"""
import re, numpy as np
from tokenizers import Tokenizer
def _soft(z): z = z - z.max(); p = np.exp(z); return p / p.sum()
class ArticleReader:
    def __init__(self, expert, cap=12):
        self.e = expert; self.cap = cap; self.tk = Tokenizer.from_file(expert.S["tok_path"]); self.tk.no_truncation()
    def windows(self, text, k=64):
        t = re.sub(r"\s+", " ", text); off = [o for o in self.tk.encode(t).offsets if o[1] > o[0]]; out = []
        for i in range(0, len(off), k):
            seg = off[i:i + k]; out.append(t[seg[0][0]:seg[-1][1]])
            if len(out) >= self.cap: break
        return out or [t]
    def read(self, title, body):
        S = self.e.S; W = self.windows(body); P = np.mean([_soft(self.e.student(title + ". " + w) @ S["t_W"].T + S["t_b"]) for w in W], axis=0)
        o2 = np.argsort(-P)[:2]; return {"answer": [S["topic_cl"][k] for k in o2], "confidence": float(P[o2].sum()), "windows": len(W)}
