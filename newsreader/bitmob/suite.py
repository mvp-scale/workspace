"""Model suite (T-0025): one candidate CPU reader on every area, same train and frozen test for all, results to data/suite/<model>/.

Train = night1 train part (80%, same split as F-0048) + round1 + round2; test = night1 held-out 2,000 + testA 9,997 (Jev labels, interim).
Areas: type (4 binary: happened, announced, opinion, forecast), topic (multi-class, topics with >= 20 train stories else other),
country (engine country, top 15 else other), conditions (binary per key with >= 30 train positives).
  CUDA_VISIBLE_DEVICES= models/embed-zs/.venv/bin/python newsreader/bitmob/suite.py <model> [area ...]
  models: tfidf e5 e5tfidf potion potion_ft setfit
Each run posts progress events (progress.py) and writes data/suite/<model>/<area>.json + .npz (test probabilities).
"""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""   # CPU only, by code (F-0071): set before any torch / setfit / sentence_transformers import
import sys, json, time, collections, numpy as np, torch
if torch.cuda.is_available(): raise SystemExit("suite.py is CPU-only: torch sees a GPU, refusing to run (F-0071)")
sys.path.insert(0, os.path.dirname(__file__)); from progress import event
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import average_precision_score, f1_score
from scipy.sparse import hstack, csr_matrix

MODEL, AREAS = sys.argv[1], sys.argv[2:] or ["type", "topic", "country", "conditions"]
W = "/workspace/data"; TAG = os.environ.get("SUITE_TAG", ""); OUT = f"{W}/suite{TAG}/{MODEL}"; os.makedirs(OUT, exist_ok=True); torch.set_num_threads(int(os.environ.get("THREADS", "4")))
L = lambda f: [json.loads(l) for l in open(f)]
night = L(f"{W}/trainset/night1.jsonl"); tr_i, te_i = train_test_split(np.arange(len(night)), test_size=0.2, random_state=0)
train = [night[i] for i in tr_i] + L(f"{W}/trainset/round1.jsonl") + L(f"{W}/trainset/round2.jsonl") + [r for n in filter(None, os.environ.get("EXTRA_TRAIN", "").split(",")) for r in L(f"{W}/trainset/{n}.jsonl")]
test = [night[i] for i in te_i] + L(f"{W}/trainset/testA.jsonl")
Xs_tr, Xs_te = [r["input"] for r in train], [r["input"] for r in test]
job = lambda a: f"{MODEL}:{a}"


def labels(area):
    if area == "type": keys = ["happened", "announced", "opinion", "forecast"]; f = lambda r: [k for k in keys if r["P"].get(f"g|{k}", 0) >= 0.5]; return "multilabel", keys, f
    if area == "conditions":
        c = collections.Counter(k for r in train for k in r["target_keys"]); keys = sorted(k for k, n in c.items() if n >= 30); return "multilabel", keys, lambda r: [k for k in r["target_keys"] if k in keys]
    field, top = ("topic", None) if area == "topic" else ("country", 15)
    c = collections.Counter(r[field] for r in train)
    keep = {k for k, n in c.items() if n >= 20} if top is None else {k for k, _ in c.most_common(top)}
    keys = sorted(keep) + ["other"]; return "multiclass", keys, lambda r: r[field] if r[field] in keep else "other"


def cache(name, fn):
    p = f"{W}/suite/cache-{name}.npy"
    if os.path.exists(p): return np.load(p)
    a = fn(); np.save(p, a); return a


def feats(kind):
    """Frozen features for train and test."""
    if kind == "tfidf":
        tf = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True).fit(Xs_tr); return tf.transform(Xs_tr), tf.transform(Xs_te)
    if kind == "e5":
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer("intfloat/e5-small-v2", device="cpu"); enc = lambda xs: m.encode(["query: " + x for x in xs], batch_size=128, normalize_embeddings=True, show_progress_bar=False)
        return cache("e5-train" + TAG, lambda: enc(Xs_tr)), cache("e5-test", lambda: enc(Xs_te))
    if kind == "potion":
        from model2vec import StaticModel
        m = StaticModel.from_pretrained("minishlab/potion-base-32M"); return cache("potion-train" + TAG, lambda: m.encode(Xs_tr)), cache("potion-test", lambda: m.encode(Xs_te))
    if kind == "e5tfidf":
        a, b = feats("e5"), feats("tfidf"); return hstack([csr_matrix(a[0]), b[0]]).tocsr(), hstack([csr_matrix(a[1]), b[1]]).tocsr()


def score(kind, keys, Y, P):
    if kind == "multilabel":
        ap = {k: float(average_precision_score(Y[:, i], P[:, i])) for i, k in enumerate(keys) if Y[:, i].sum() >= 3}
        return {"mean_AP": round(float(np.mean(list(ap.values()))), 4), "per_key_AP": {k: round(v, 4) for k, v in ap.items()},
                "test_pos": {k: int(Y[:, i].sum()) for i, k in enumerate(keys)}}
    y, pr = Y.argmax(1), P.argmax(1)
    return {"accuracy": round(float((y == pr).mean()), 4), "macroF1": round(float(f1_score(y, pr, average="macro")), 4)}


def ms_per_story(predict):
    xs = Xs_te[:256]; t = time.time(); predict(xs); return round(1000 * (time.time() - t) / len(xs), 2)


def run(area):
    kind, keys, lab = labels(area); t0 = time.time()
    Ytr = np.zeros((len(train), len(keys)), bool); Yte = np.zeros((len(test), len(keys)), bool); ix = {k: i for i, k in enumerate(keys)}
    for Y, rows in ((Ytr, train), (Yte, test)):
        for j, r in enumerate(rows):
            v = lab(r); [Y.__setitem__((j, ix[k]), True) for k in (v if isinstance(v, list) else [v])]
    event(job(area), "training", f"{len(keys)} labels, {len(train)} train / {len(test)} test", pid=os.getpid())
    if MODEL in ("tfidf", "e5", "e5tfidf", "potion"):
        Xtr, Xte = feats(MODEL); P = np.zeros(Yte.shape)
        if kind == "multilabel":
            for i, k in enumerate(keys):
                if Ytr[:, i].sum() < 2: continue
                P[:, i] = LogisticRegression(max_iter=3000, class_weight="balanced", C=2.0).fit(Xtr, Ytr[:, i]).predict_proba(Xte)[:, 1]
                if i % 10 == 9: event(job(area), "training", f"{i + 1}/{len(keys)} labels fitted", pid=os.getpid())
        else:
            clf = LogisticRegression(max_iter=3000, class_weight="balanced", C=2.0).fit(Xtr, Ytr.argmax(1)); P[:, clf.classes_] = clf.predict_proba(Xte)
        speed = {"tfidf": 0.1, "potion": None, "e5": None, "e5tfidf": None}.get(MODEL)
    else:
        P, speed = finetune(kind, keys, Ytr, area)
    event(job(area), "scoring", "scoring on the frozen test", pid=os.getpid())
    res = {"model": MODEL, "area": area, "kind": kind, "keys": keys, "train": len(train), "test": len(test), "minutes": round((time.time() - t0) / 60, 1), "ms_per_story": speed} | score(kind, keys, Yte, P)
    json.dump(res, open(f"{OUT}/{area}.json", "w"), indent=1)
    np.savez_compressed(f"{OUT}/{area}.npz", P=P.astype(np.float32), Y=Yte, keys=np.array(keys), n_night=len(te_i))
    head = f"mean AP {res['mean_AP']}" if kind == "multilabel" else f"accuracy {res['accuracy']}"
    event(job(area), "done", f"{head} ({res['minutes']} min)", pid=os.getpid(), win=True)


def finetune(kind, keys, Ytr, area):
    """potion_ft: model2vec StaticModelForClassification; setfit: SetFit with the e5-small body."""
    if MODEL == "potion_ft":
        from model2vec.train import StaticModelForClassification
        clf = StaticModelForClassification.from_pretrained(model_name="minishlab/potion-base-32M")
        ytr = [[k for k, v in zip(keys, row) if v] for row in Ytr] if kind == "multilabel" else [keys[i] for i in Ytr.argmax(1)]
        clf.fit(Xs_tr, ytr, max_epochs=int(os.environ.get("EPOCHS", "20")), early_stopping_patience=3)
        P = np.asarray(clf.predict_proba(Xs_te)); order = [list(clf.classes_).index(k) if k in list(clf.classes_) else -1 for k in keys]
        P = np.stack([P[:, o] if o >= 0 else np.zeros(len(Xs_te)) for o in order], 1)
        return P, ms_per_story(lambda xs: clf.predict_proba(xs))
    if MODEL == "setfit":
        from setfit import SetFitModel, Trainer, TrainingArguments
        from datasets import Dataset
        multi = kind == "multilabel"
        m = SetFitModel.from_pretrained("intfloat/e5-small-v2", multi_target_strategy="one-vs-rest" if multi else None, labels=None if multi else keys)
        ytr = [list(map(int, row)) for row in Ytr] if multi else list(Ytr.argmax(1))
        args = TrainingArguments(batch_size=32, num_epochs=1, max_steps=int(os.environ.get("STEPS", "1500")), num_iterations=None)
        from transformers import TrainerCallback
        class Pace(TrainerCallback):   # post s/step after ~20 steps; stop early so the run fits BUDGET_S (default 2400 s)
            t0 = None; limit = None
            def on_step_end(self, a, state, control, **kw):
                if self.t0 is None: self.t0 = time.time(); return
                if state.global_step == 20:
                    spp = (time.time() - self.t0) / 19; self.limit = int(float(os.environ.get("BUDGET_S", "2400")) / spp)
                    event(job(area), "training", f"measured {spp:.2f} s/step; will run {min(self.limit, a.max_steps)} of {a.max_steps} steps", pid=os.getpid())
                if self.limit and state.global_step >= self.limit: control.should_training_stop = True
                if state.global_step % 100 == 0: event(job(area), "training", f"step {state.global_step}/{a.max_steps}", pid=os.getpid())
        Trainer(model=m, args=args, callbacks=[Pace()], train_dataset=Dataset.from_dict({"text": ["query: " + x for x in Xs_tr], "label": ytr})).train()
        P = np.asarray(m.predict_proba(["query: " + x for x in Xs_te]))
        if multi and P.ndim == 3: P = P[:, :, 1]
        return P, ms_per_story(lambda xs: m.predict_proba(["query: " + x for x in xs]))
    if MODEL == "e5ft":   # as finetune_conditions.py: mean-pooled e5-small + linear head, 2 epochs, max 96 tokens
        from transformers import AutoTokenizer, AutoModel
        tok = AutoTokenizer.from_pretrained("intfloat/e5-small-v2"); enc = AutoModel.from_pretrained("intfloat/e5-small-v2")
        head = torch.nn.Linear(enc.config.hidden_size, len(keys)); multi = kind == "multilabel"
        opt = torch.optim.AdamW(list(enc.parameters()) + list(head.parameters()), lr=3e-5)
        pos = torch.tensor(Ytr.sum(0), dtype=torch.float); pw = ((len(Ytr) - pos) / pos.clamp(min=1)).clamp(max=50)
        lossf = torch.nn.BCEWithLogitsLoss(pos_weight=pw) if multi else torch.nn.CrossEntropyLoss()
        fwd = lambda xs: (lambda b, h: (h * b["attention_mask"].unsqueeze(-1)).sum(1) / b["attention_mask"].sum(1, keepdim=True))(*(lambda b: (b, enc(**b).last_hidden_state))(tok(["query: " + x for x in xs], padding=True, truncation=True, max_length=96, return_tensors="pt")))
        n, E = len(Xs_tr), int(os.environ.get("EPOCHS", "2"))
        for ep in range(E):
            enc.train(); perm = np.random.RandomState(ep).permutation(n)
            for s in range(0, n, 32):
                ix = perm[s:s + 32]; out = head(fwd([Xs_tr[i] for i in ix]))
                y = torch.tensor(Ytr[ix], dtype=torch.float) if multi else torch.tensor(Ytr[ix].argmax(1))
                loss = lossf(out, y); opt.zero_grad(); loss.backward(); opt.step()
                if (s // 32) % 50 == 0: event(job(area), "training", f"epoch {ep + 1}/{E}, {s}/{n} stories, loss {loss.item():.3f}", pid=os.getpid())
        enc.eval()
        def pred(xs):
            with torch.no_grad():
                o = torch.cat([head(fwd(xs[j:j + 128])) for j in range(0, len(xs), 128)])
            return (torch.sigmoid(o) if multi else torch.softmax(o, 1)).numpy()
        return pred(Xs_te), ms_per_story(pred)
    raise SystemExit(f"unknown model {MODEL}")


for a in AREAS:
    event(job(a), "queued", "waiting to start", pid=os.getpid())
for a in AREAS:
    try: run(a)
    except Exception as e: event(job(a), "failed", f"{type(e).__name__}: {str(e)[:200]}", pid=os.getpid()); raise
