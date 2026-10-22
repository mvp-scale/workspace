"""HuffPost News Category pilot (F-0086; D-0023 rules). Quick test: e5tfidf (as suite.py builds it) on round-3 train + N mapped external rows, N in 0/5k/20k.
  CUDA_VISIBLE_DEVICES= THREADS=6 timeout 2400 models/embed-zs/.venv/bin/python -I newsreader/bitmob/news_category_pilot.py
Writes data/external/news_category/pilot_results.json (+ per-N test probabilities in the scratch dir given by PILOT_TMP)."""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import sys, json, collections, time, numpy as np, torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from progress import event
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import f1_score
from scipy.sparse import hstack, csr_matrix
torch.set_num_threads(int(os.environ.get("THREADS", "6")))
W = "/workspace/data"; EXT = f"{W}/external/news_category"; J = "pilot:news_category"
L = lambda f: [json.loads(l) for l in open(f)]
night = L(f"{W}/trainset/night1.jsonl"); tr_i, te_i = train_test_split(np.arange(len(night)), test_size=0.2, random_state=0)
train = [night[i] for i in tr_i] + L(f"{W}/trainset/round1.jsonl") + L(f"{W}/trainset/round2.jsonl") + [r for n in ("loop1", "loop2", "loop3") for r in L(f"{W}/trainset/{n}.jsonl")]
test = [night[i] for i in te_i] + L(f"{W}/trainset/testA.jsonl")
Xtr0, Xte = [r["input"] for r in train], [r["input"] for r in test]
E5TR = np.load(f"{W}/suite/cache-e5-train_r3.npy"); E5TE = np.load(f"{W}/suite/cache-e5-test.npy")
assert len(E5TR) == len(train) and len(E5TE) == len(test), (len(E5TR), len(train), len(E5TE), len(test))
event(J, "running", f"loaded {len(train)} train / {len(test)} test", pid=os.getpid())
# external: mapped rows only, text = headline + " " + short_description
mp = json.load(open(f"{EXT}/mapping.json")); mp.pop("_note")
ext = []
for l in open(f"{EXT}/data.json"):
    r = json.loads(l); m = mp.get(r["category"])
    if not m or not m["topic"]: continue
    h, d = str(r["headline"]).strip(), str(r["short_description"]).strip()
    if h and d: ext.append((f"{h} {d}", m["topic"]))
rng = np.random.RandomState(20261021)
bytopic = collections.defaultdict(list)
for i, (_, t) in enumerate(ext): bytopic[t].append(i)
def strat(pool, n):   # proportional to mapped topic counts, at least 1 per topic
    tot = sum(len(v) for v in pool.values()); out = {}
    for t, v in pool.items(): out[t] = list(rng.permutation(v)[:max(1, round(n * len(v) / tot))])
    return out
s20 = strat(bytopic, 20000); s5 = strat({t: v for t, v in s20.items()}, 5000)   # 5k is a stratified subset of the 20k
idx = {20000: sorted(i for v in s20.values() for i in v), 5000: sorted(i for v in s5.values() for i in v)}
cnt = {n: dict(collections.Counter(ext[i][1] for i in v)) for n, v in idx.items()}
alli = idx[20000]
from sentence_transformers import SentenceTransformer
m = SentenceTransformer("intfloat/e5-small-v2", device="cpu"); t0 = time.time()
event(J, "training", f"embedding {len(alli)} external rows", pid=os.getpid())
E5X = {}
for s in range(0, len(alli), 2000):
    ch = alli[s:s + 2000]; e = m.encode(["query: " + ext[i][0] for i in ch], batch_size=128, normalize_embeddings=True, show_progress_bar=False)
    for i, v in zip(ch, e): E5X[i] = v
    event(J, "training", f"embedded {s + len(ch)}/{len(alli)} ({time.time() - t0:.0f}s)", pid=os.getpid())

def run(n):
    sel = [] if n == 0 else idx[n]
    Xs = Xtr0 + [ext[i][0] for i in sel]; tops = [r["topic"] for r in train] + [ext[i][1] for i in sel]
    E = np.vstack([E5TR] + ([np.stack([E5X[i] for i in sel])] if sel else []))
    c = collections.Counter(tops); keep = {k for k, v in c.items() if v >= 20}; keys = sorted(keep) + ["other"]; ix = {k: i for i, k in enumerate(keys)}
    ytr = np.array([ix[t if t in keep else "other"] for t in tops]); yte = np.array([ix[r["topic"] if r["topic"] in keep else "other"] for r in test])
    tf = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True).fit(Xs)
    Xtr = hstack([csr_matrix(E), tf.transform(Xs)]).tocsr(); Xt = hstack([csr_matrix(E5TE), tf.transform(Xte)]).tocsr()
    clf = LogisticRegression(max_iter=3000, class_weight="balanced", C=2.0).fit(Xtr, ytr); P = np.zeros((len(test), len(keys))); P[:, clf.classes_] = clf.predict_proba(Xt)
    event(J, "training", f"N={n} fitted ({len(keys)} labels, {len(Xs)} train)", pid=os.getpid())
    return keys, yte, P
res = {}; os.makedirs(os.environ["PILOT_TMP"], exist_ok=True)
for n in (0, 5000, 20000):
    keys, y, P = run(n); res[n] = (keys, y, P)
    np.savez_compressed(f"{os.environ['PILOT_TMP']}/p{n}.npz", P=P.astype(np.float32), y=y, keys=np.array(keys))
    print(n, "acc", round(float((P.argmax(1) == y).mean()), 4), "F1", round(float(f1_score(y, P.argmax(1), average='macro')), 4), len(keys), flush=True)
json.dump({"counts": {str(n): c for n, c in cnt.items()}, "n_mapped_rows": len(ext)}, open(f"{EXT}/pilot_sample_counts.json", "w"), indent=1)
event(J, "done", "quick test done; analysis next", pid=os.getpid())
