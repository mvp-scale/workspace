"""One article, four levels (beats): title, first sentence, first 250 words, full article. Each beat is embedded whole (the full article as the mean of 250-word chunks). Every paragraph and every sentence of the article is then given its similarity to each beat, plus its HDBSCAN group at its own piece size.
Only this article's own text is used (bge-small, CPU).
    CUDA_VISIBLE_DEVICES= /workspace/models/embed-zs/.venv/bin/python article_levels.py -> runs/harvest/article_levels.json"""
import os, re, json, warnings
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["CUDA_VISIBLE_DEVICES"] = ""; warnings.filterwarnings("ignore")
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.cluster import HDBSCAN
B = json.load(open("runs/harvest/article_beats.json")); RW = B["raw"]; body = RW["body"]; cut = RW["slice_250_ends_at_char"]; sents = B["all_sentences"]
paras = [p.strip() for p in body.split("\n") if p.strip()]
m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 256
enc = lambda xs: m.encode(xs, batch_size=32, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True).astype(np.float32)
words = body.split(); chunks = [" ".join(words[a:a + 250]) for a in range(0, len(words), 250)]
unit = lambda v: v / np.linalg.norm(v)
beat_text = {"title": RW["title"], "first_sentence": RW["first_sentence"], "first_250_words": body[:cut]}
V = {k: enc([t])[0] for k, t in beat_text.items()}; V["full_article"] = unit(enc(chunks).mean(axis=0))
names = ["title", "first_sentence", "first_250_words", "full_article"]
matrix = [[round(float(V[a] @ V[b]), 3) for b in names] for a in names]
def level(pieces):
    E = enc(pieces); lab = HDBSCAN(min_cluster_size=3, min_samples=2, copy=True).fit_predict(E); rows = []
    gids = sorted(set(int(g) for g in lab if g >= 0), key=lambda g: -int((lab == g).sum())); letter = {g: chr(65 + k) for k, g in enumerate(gids)}  # A is the largest group
    for i, (t, e) in enumerate(zip(pieces, E)):
        rows.append({"i": i, "text": t, "words": len(t.split()), "group": int(lab[i]), "letter": letter.get(int(lab[i])), "sim": {k: round(float(e @ V[k]), 3) for k in names}})
    groups = []
    for g in gids:
        idx = np.where(lab == g)[0]; sub = E[idx]; sm = sub @ sub.T; central = int(idx[np.argmax(sm.mean(axis=1))]); within = float(sm[np.triu_indices(len(idx), 1)].mean())
        groups.append({"letter": letter[int(g)], "n": int(len(idx)), "first": int(idx.min()), "last": int(idx.max()), "central": central, "within_similarity": round(within, 3), "members": [int(j) for j in idx]})
    return rows, int(lab.max()) + 1, round(float((lab < 0).mean()), 3), groups
P, pg, pn, PG = level(paras); S, sg, sn, SG = level(sents)
# where does each piece sit relative to the 250-word cut? (character offsets)
def offsets(pieces, rows):
    pos = 0
    for r in rows:
        k = body.find(r["text"][:40], pos); r["start_char"] = k if k >= 0 else None; r["in_first_250"] = (k >= 0 and k < cut); pos = max(pos, k if k >= 0 else pos)
offsets(paras, P); offsets(sents, S)
for G_, rows_ in ((PG, P), (SG, S)):
    for g in G_: g["inside_first_250"] = int(sum(1 for j in g["members"] if rows_[j]["in_first_250"]))
top = {lv: {k: [r["i"] for r in sorted(rows, key=lambda r: -r["sim"][k])[:5]] for k in names} for lv, rows in (("paragraphs", P), ("sentences", S))}
inside = {lv: {k: sum(1 for i in top[lv][k] if rows[i]["in_first_250"]) for k in names} for lv, rows in (("paragraphs", P), ("sentences", S))}
json.dump({"v": "article-levels-v0", "model": "BAAI/bge-small-en-v1.5 (CPU)", "idx": B["idx"], "raw": RW, "beat_names": names, "beat_matrix": matrix, "full_article_vector": "mean of " + str(len(chunks)) + " chunks of up to 250 words", "paragraphs": {"groups": pg, "noise": pn, "rows": P, "group_table": PG}, "sentences": {"groups": sg, "noise": sn, "rows": S, "group_table": SG}, "top5": top, "top5_inside_first_250": inside}, open("runs/harvest/article_levels.json", "w"), indent=1)
print("matrix (rows/cols: title, first sentence, first 250, full):"); [print(" ", r) for r in matrix]; print([(g["letter"], g["n"], g["first"], g["last"], g["inside_first_250"]) for g in SG]); print("paragraph groups", pg, "noise", pn, "| sentence groups", sg, "noise", sn); print("top5 inside first 250:", inside)
