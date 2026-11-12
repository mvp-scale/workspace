"""One article, four beats: title, first sentence, first 250 words, whole article. Each beat is cut into its own pieces and embedded (bge-small, CPU).
HDBSCAN runs on the beats that have enough pieces (first 250 words, whole article). The whole-article groups are the article's concepts; every piece of every beat is placed against them, so the flow (concepts present in all beats) and the variants (concepts in some beats only) can be read off.
Only this article's own text is used.
    CUDA_VISIBLE_DEVICES= /workspace/models/embed-zs/.venv/bin/python article_beats.py -> runs/harvest/article_beats.json"""
import os, re, json, warnings, collections
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["CUDA_VISIBLE_DEVICES"] = ""; warnings.filterwarnings("ignore")
import numpy as np, spacy
from sentence_transformers import SentenceTransformer
from sklearn.cluster import HDBSCAN
from sklearn.metrics import adjusted_rand_score as ARI
from sklearn.feature_extraction.text import CountVectorizer, ENGLISH_STOP_WORDS
A = json.load(open("runs/harvest/article_topics.json"))["articles"][0]; title = A["title"]; sents = A["sentences"]
STOP = list(ENGLISH_STOP_WORDS | set("said says say new year years time like just also told one get got going make way back could would may still even week day days last first two three according mr mrs ms did think want".split()))
nlp = spacy.load("en_core_web_sm"); m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 256
enc = lambda xs: m.encode(xs, batch_size=32, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True).astype(np.float32)
def chunks(text):
    d = nlp(text); out = []
    for c in d.noun_chunks:
        t = re.sub(r"^(the|a|an|its|their|his|her|our|your|my)\s+", "", c.text.strip(), flags=re.I)
        if len(t) > 2 and t.lower() not in ("you", "it", "i", "we", "they", "he", "she", "that", "this"): out.append(t)
    return out
# beats
b1 = [title] + chunks(title)  # the whole headline, then its phrases
b2s = sents[0]; b2 = [b2s] + chunks(b2s)
cum = 0; b3i = []
for i, s in enumerate(sents):
    cum += len(s.split())
    if cum > 250: break
    b3i.append(i)
b3 = [sents[i] for i in b3i]; b4 = list(sents)
E1, E2, E3, E4 = enc(b1), enc(b2), enc(b3), enc(b4)
def words_for(texts, lab, topn=6):
    ids = sorted(set(l for l in lab if l >= 0)); docs = [" ".join(t for t, l in zip(texts, lab) if l == c) for c in ids] + [" ".join(t for t, l in zip(texts, lab) if l < 0) or "x"]
    cv = CountVectorizer(stop_words=STOP, token_pattern=r"[A-Za-z][A-Za-z]{2,}", lowercase=True); M = cv.fit_transform(docs).toarray().astype(float); voc = np.array(cv.get_feature_names_out()); tf = M / np.maximum(M.sum(axis=1, keepdims=True), 1); df = (M > 0).sum(axis=0); sc = tf * np.log(1 + len(docs) / df)
    return {c: [{"word": str(voc[j]), "times": int(M[k, j])} for j in np.argsort(-sc[k])[:topn] if M[k, j] > 0] for k, c in enumerate(ids)}
def hdb(E, mcs, ms): h = HDBSCAN(min_cluster_size=mcs, min_samples=ms, copy=True).fit(E); return h.labels_, h.probabilities_
# concepts = whole-article groups
lab4, pr4 = hdb(E4, 3, 2); ids = sorted(set(l for l in lab4 if l >= 0)); cw = words_for(b4, lab4)
cent = {}; concepts = []
for c in ids:
    idx = np.where(lab4 == c)[0]; v = E4[idx].mean(axis=0); v /= np.linalg.norm(v); cent[c] = v; sub = E4[idx]; ex = int(idx[np.argmax((sub @ sub.T).mean(axis=1))])
    concepts.append({"id": int(c), "n_sentences": int(len(idx)), "n_words": int(sum(len(b4[j].split()) for j in idx)), "sentences": [int(j) for j in idx], "words": cw.get(c, []), "exemplar": b4[ex], "exemplar_idx": ex, "first": int(idx.min()), "last": int(idx.max())})
concepts.sort(key=lambda c: -c["n_words"])
own = np.array([E4[i] @ cent[lab4[i]] for i in range(len(b4)) if lab4[i] >= 0]); tau = round(float(np.percentile(own, 10)), 3)
def place(v):
    s = {c: float(v @ cent[c]) for c in ids}; c = max(s, key=s.get); return (int(c), round(s[c], 3)) if s[c] >= tau else (None, round(s[c], 3)), {int(k): round(x, 3) for k, x in s.items()}
def beat(pieces, E, labs=None):
    out = []
    for k, (t, v) in enumerate(zip(pieces, E)):
        (c, sim), allsim = place(v); out.append({"text": t, "concept": c, "similarity": sim, "own_group": (int(labs[k]) if labs is not None else None)})
    return out
lab3, pr3 = hdb(E3, 2, 1)
beats = {"title": {"what": "the headline, then its phrases", "pieces": beat(b1, E1), "hdbscan": None},
         "first_sentence": {"what": "the first sentence, then its phrases", "pieces": beat(b2, E2), "hdbscan": None},
         "first_250_words": {"what": "the sentences inside the first 250 words", "pieces": beat(b3, E3, lab3), "hdbscan": {"min_cluster_size": 2, "min_samples": 1, "groups": int(lab3.max()) + 1, "noise": round(float((lab3 < 0).mean()), 3)}},
         "whole_article": {"what": "every sentence of the article", "pieces": beat(b4, E4, lab4), "hdbscan": {"min_cluster_size": 3, "min_samples": 2, "groups": int(lab4.max()) + 1, "noise": round(float((lab4 < 0).mean()), 3)}}}
flow = []
for c in concepts:
    row = {"concept": c["id"], "title": [p["text"] for p in beats["title"]["pieces"] if p["concept"] == c["id"]], "first_sentence": [p["text"] for p in beats["first_sentence"]["pieces"] if p["concept"] == c["id"]], "first_250_words": sum(1 for p in beats["first_250_words"]["pieces"] if p["concept"] == c["id"]), "whole_article": sum(1 for p in beats["whole_article"]["pieces"] if p["concept"] == c["id"])}
    row["beats_present"] = sum([bool(row["title"]), bool(row["first_sentence"]), row["first_250_words"] > 0, row["whole_article"] > 0]); flow.append(row)
# stability of the two clustered beats across minimum group sizes
stab = {}
for nm, E, base_m in (("first_250_words", E3, 2), ("whole_article", E4, 3)):
    runs = {}; base = hdb(E, base_m, 1 if nm == "first_250_words" else 2)[0]
    for mcs in (2, 3, 4, 5):
        l = hdb(E, mcs, 1 if nm == "first_250_words" else 2)[0]; runs[str(mcs)] = {"groups": int(l.max()) + 1, "noise": round(float((l < 0).mean()), 3), "ari_vs_chosen": round(float(ARI(base, l)), 3)}
    stab[nm] = runs
_raw = [json.loads(l) for _, l in zip(range(A["idx"] + 1), open("runs/harvest/sample.jsonl"))][A["idx"]]["text"]; _ms = list(re.finditer(r"\S+", _raw)); _off = _ms[249].end() if len(_ms) >= 250 else len(_raw)
raw = {"title": title, "body": _raw, "first_sentence": sents[0], "words_in_body": len(_ms), "slice_250_ends_at_char": _off}
out = {"v": "article-beats-v1", "raw": raw, "idx": A["idx"], "title": title, "domain": A["domain"], "model": "BAAI/bge-small-en-v1.5 (CPU)", "placement_threshold": tau, "placement_rule": "a piece joins the concept whose centre it is closest to, if its similarity is at least the 10th percentile of how close the concept's own sentences are to their centre", "beats": beats, "concepts": concepts, "flow": flow, "stability": stab, "all_sentences": b4}
json.dump(out, open("runs/harvest/article_beats.json", "w"), indent=1)
print("tau", tau, "| concepts", [(c["id"], c["n_sentences"], [w["word"] for w in c["words"][:3]]) for c in concepts])
for r in flow: print(r["concept"], "beats", r["beats_present"], "| title", r["title"], "| first sent", r["first_sentence"], "| 250w", r["first_250_words"], "| whole", r["whole_article"])
print("title pieces:", [(p["text"], p["concept"], p["similarity"]) for p in beats["title"]["pieces"]]); print("first sentence pieces:", [(p["text"][:40], p["concept"], p["similarity"]) for p in beats["first_sentence"]["pieces"]]); print(stab)
