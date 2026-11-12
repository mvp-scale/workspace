"""What is ONE article about? Split the article's own text into sentences, embed each sentence (bge-small, CPU), cluster the sentences with HDBSCAN, name each group from that article's own words.
Nothing from other articles, no topic list. Output per article: sentences with their group, group words/exemplar/span, results at minimum group sizes 2 to 5, stability, and simple baselines.
    CUDA_VISIBLE_DEVICES= /workspace/models/embed-zs/.venv/bin/python article_topics.py -> runs/harvest/article_topics.json"""
import os, re, json, warnings, collections
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["CUDA_VISIBLE_DEVICES"] = ""; warnings.filterwarnings("ignore")
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.cluster import HDBSCAN
from sklearn.metrics import adjusted_rand_score as ARI
from sklearn.feature_extraction.text import CountVectorizer, ENGLISH_STOP_WORDS
N = 5000; R = [json.loads(l) for _, l in zip(range(N), open("runs/harvest/sample.jsonl"))]; X = [json.loads(l) for _, l in zip(range(N), open("runs/harvest/extract.jsonl"))]
STOP = list(ENGLISH_STOP_WORDS | set("said says say new year years time like just also told one get got going make way back could would may still even week day days last first two three according mr mrs ms".split()))
def split(text):
    cut = [m.end() for m in re.finditer(r"[.!?][\"”’)]?(?=\s+[A-Z0-9“\"‘'(])", text)]; s = []; a = 0  # the closing quote stays with its sentence
    for e in cut + [len(text)]:
        if text[a:e].strip(): s.append(text[a:e].strip())
        a = e
    out = []
    for x in s:  # glue very short fragments onto the previous sentence
        if out and len(x.split()) < 6: out[-1] += " " + x
        else: out.append(x)
    return out
def body_of(i):
    ti = re.sub(r"\s+", " ", R[i]["title"] or "").strip(); t = X[i]["text"]; return ti, (t[len(ti) + 2:] if t.startswith(ti) else t)
# choose 8 long articles with different reader topics, plus the Charlottesville article used earlier
cand = [i for i in range(N) if len(body_of(i)[1].split()) >= 700 and len(body_of(i)[0].split()) >= 5 and 40 <= len(split(body_of(i)[1])) <= 90]
walk0 = json.load(open("runs/harvest/topic_shape_walk.json"))["articles"][0]["idx"]; seen = set(); pick = [walk0] if walk0 in cand else []
for i in cand:
    t = X[i]["reader"]["topic_top2"][0]
    if t in seen or i in pick: continue
    seen.add(t); pick.append(i)
    if len(pick) == 9: break
m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 256
enc = lambda xs: m.encode(xs, batch_size=32, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True).astype(np.float32)
def label_words(sents, lab, topn=6):
    """Words from THIS article only: for each group, words common in its sentences and rare in the article's other sentences."""
    ids = sorted(set(l for l in lab if l >= 0)); docs = [" ".join(s for s, l in zip(sents, lab) if l == c) for c in ids] + [" ".join(s for s, l in zip(sents, lab) if l < 0) or "x"]
    cv = CountVectorizer(stop_words=STOP, token_pattern=r"[A-Za-z][A-Za-z]{2,}", lowercase=True); M = cv.fit_transform(docs).toarray().astype(float); voc = np.array(cv.get_feature_names_out())
    tf = M / np.maximum(M.sum(axis=1, keepdims=True), 1); df = (M > 0).sum(axis=0); sc = tf * np.log(1 + len(docs) / df)
    return {c: [{"word": str(voc[j]), "times": int(M[k, j])} for j in np.argsort(-sc[k])[:topn] if M[k, j] > 0] for k, c in enumerate(ids)}
out = []
for i in pick:
    title, body = body_of(i); sents = split(body); E = enc(sents); te = enc([title])[0]; cen = E.mean(axis=0); cen /= np.linalg.norm(cen); centre_order = np.argsort(-(E @ cen))
    runs = {}
    for mcs in (2, 3, 4, 5):
        h = HDBSCAN(min_cluster_size=mcs, min_samples=2, copy=True).fit(E); lab = h.labels_; k = int(lab.max()) + 1; words = label_words(sents, lab) if k else {}
        groups = []
        for c in range(k):
            idx = np.where(lab == c)[0]; sub = E[idx]; mean_sim = (sub @ sub.T).mean(axis=1); ex = int(idx[np.argmax(mean_sim)]); cc = sub.mean(axis=0); cc /= np.linalg.norm(cc)
            groups.append({"id": c, "sentences": [int(j) for j in idx], "n_sentences": int(len(idx)), "n_words": int(sum(len(sents[j].split()) for j in idx)), "first": int(idx.min()), "last": int(idx.max()), "exemplar": ex, "words": words.get(c, []), "title_similarity": round(float(te @ cc), 3), "inside_similarity": round(float((sub @ sub.T)[np.triu_indices(len(idx), 1)].mean()) if len(idx) > 1 else 1.0, 3)})
        runs[str(mcs)] = {"clusters": k, "noise_share": round(float((lab < 0).mean()), 3), "labels": [int(l) for l in lab], "membership": [round(float(p), 2) for p in h.probabilities_], "groups": sorted(groups, key=lambda g: -g["n_words"])}
    stab = {k: round(float(ARI(runs["3"]["labels"], runs[k]["labels"])), 3) for k in runs if k != "3"}
    tw = collections.Counter(w for w in re.findall(r"[A-Za-z][A-Za-z]{2,}", body.lower()) if w not in STOP); kw = [{"word": w, "times": n} for w, n in tw.most_common(8)]
    out.append({"idx": int(i), "title": title, "domain": R[i]["domain"], "words": len(body.split()), "sentences": sents, "title_to_sentence_similarity": [round(float(v), 3) for v in E @ te], "centre_sentence_order": [int(j) for j in centre_order[:5]], "runs": runs, "stability_ari_vs_3": stab, "baseline_top_words": kw})
    r3 = runs["3"]; print(f"{title[:50]:50} {len(sents):3} sents | m=3: {r3['clusters']} groups, noise {r3['noise_share']:.2f} | ARI vs 3: {stab}")
json.dump({"v": "article-topics-v0", "model": "BAAI/bge-small-en-v1.5 (CPU)", "method": "sentences of one article, HDBSCAN min_samples 2, eom, euclidean on unit vectors", "articles": out}, open("runs/harvest/article_topics.json", "w"), indent=1)
