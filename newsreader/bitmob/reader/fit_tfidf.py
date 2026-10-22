"""D-0037: refit the e5tfidf half of each BitMob reader (frozen e5-small embedding + tf-idf 1-2gram -> logistic regression, as suite.py e5tfidf)
on the ds_r5 / ds_r8 TRAIN rows and save it for serving. Also writes its frozen-test probabilities (same test order as suite.py) for scoring/blending.
  THREADS=8 kev/.venv/bin/python newsreader/bitmob/reader/fit_tfidf.py   -> data/bitmob-integration/models/tfidf_<area>.joblib, data/bitmob-integration/tfidf_test_<area>.npz"""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import json, sys, time, joblib, numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse import hstack, csr_matrix
W = "/workspace/data"; OUT = f"{W}/bitmob-integration"; L = lambda f: [json.loads(l) for l in open(f)]
import torch; torch.set_num_threads(int(os.environ.get("THREADS", "8")))
r5 = L(f"{W}/kaggle/ds_r5/train.jsonl"); r8 = {r["id"]: r for r in L(f"{W}/kaggle/ds_r8/train.jsonl")}; K5 = json.load(open(f"{W}/kaggle/ds_r5/keys.json")); K8 = json.load(open(f"{W}/kaggle/ds_r8/keys.json"))
X = [r["text"] for r in r5]
night = L(f"{W}/trainset/night1.jsonl"); _, te_i = train_test_split(np.arange(len(night)), test_size=0.2, random_state=0)
test = [night[i] for i in te_i] + L(f"{W}/trainset/testA.jsonl"); Xt = [r["input"] for r in test]
from sentence_transformers import SentenceTransformer
m = SentenceTransformer("intfloat/e5-small-v2", device="cpu"); enc = lambda xs: m.encode(["query: " + x for x in xs], batch_size=128, normalize_embeddings=True, show_progress_bar=False)
t = time.time(); Etr = enc(X); print("embed train", round(time.time() - t), "s", flush=True)
Ete = np.load(f"{W}/suite/cache-e5-test.npy"); assert len(Ete) == len(Xt), (Ete.shape, len(Xt))
tf = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True).fit(X)
Ftr = hstack([csr_matrix(Etr), tf.transform(X)]).tocsr(); Fte = hstack([csr_matrix(Ete), tf.transform(Xt)]).tocsr()
joblib.dump(tf, f"{OUT}/models/tfidf_vectorizer.joblib")
def fit_multi(Y, name):
    cls = []; P = np.zeros((Fte.shape[0], Y.shape[1]), np.float32)
    for i in range(Y.shape[1]):
        if Y[:, i].sum() < 2: cls.append(None); continue
        lr = LogisticRegression(max_iter=3000, class_weight="balanced", C=2.0).fit(Ftr, Y[:, i]); cls.append(lr); P[:, i] = lr.predict_proba(Fte)[:, 1]
    joblib.dump(cls, f"{OUT}/models/tfidf_{name}.joblib"); return P
def fit_cls(y, nk, name):
    lr = LogisticRegression(max_iter=3000, class_weight="balanced", C=2.0).fit(Ftr, y); P = np.zeros((Fte.shape[0], nk), np.float32); P[:, lr.classes_] = lr.predict_proba(Fte)
    joblib.dump(lr, f"{OUT}/models/tfidf_{name}.joblib"); return P
res = {}
tk = K5["topic_keys"]; y = np.array([tk.index(r["topic"]) for r in r5]); res["topic"] = fit_cls(y, len(tk), "topic"); print("topic", flush=True)
res["conditions"] = fit_multi(np.array([r["cond"] for r in r5], bool), "conditions"); print("conditions", flush=True)
ck = K8["country_keys"]; y = np.array([ck.index(r8[r["id"]]["country"]) for r in r5]); res["country"] = fit_cls(y, len(ck), "country"); print("country", flush=True)
res["heads"] = fit_multi(np.array([r8[r["id"]]["heads"] for r in r5], bool), "heads"); print("heads", flush=True)
for a, P in res.items(): np.savez_compressed(f"{OUT}/tfidf_test_{a}.npz", P=P, n_night=len(te_i))
print("done")
