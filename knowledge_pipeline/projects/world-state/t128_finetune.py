"""T128: fine-tune a small encoder (bge-small) on the engine's own readings (the 1736 stories plus the T126 extension), presence and direction heads, headline plus two sentences, CPU. Test = grouped fold 0 (crc32 of the headline, mod 5); 10 percent of the training stories form the dev set that picks the epoch; the sparse word-count heads are trained and scored on the same split for comparison.
    EPOCHS=6 LIMIT=<stories, 0 = all> OUT=<folder> /workspace/models/embed-zs/.venv/bin/python -u t128_finetune.py -> <OUT>/t128_finetune.json"""
import os, json, re, collections, pathlib, time, zlib, random
import numpy as np, torch
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from scipy.sparse import hstack
from transformers import AutoTokenizer, AutoModel
torch.set_num_threads(int(os.environ.get("THREADS", 12))); torch.manual_seed(7); random.seed(7)
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t128")); OUT.mkdir(parents=True, exist_ok=True); T0 = time.time(); EP = int(os.environ.get("EPOCHS", 6)); LIM = int(os.environ.get("LIMIT", 0))
nk = lambda t: re.sub(r"\W+", " ", t.lower()).strip()
short = lambda t, b: (t.strip() + ". " + " ".join(re.split(r"(?<=[.!?])\s+", b.strip())[:2])).strip()
eng = {}
for fn in ("clef-q4km.jsonl", "clef-q4km-w3.jsonl", "clef-q4km-ext.jsonl"):
    p = "/workspace/data/newsreader/labels/" + fn
    if os.path.exists(p):
        for l in open(p):
            r = json.loads(l)
            if "title" in r: eng.setdefault(r["id"], r)
E = list(eng.values())[: LIM or None]
def etext(r):
    b = re.sub(r"^#.*?\n", "", r["text"].strip(), count=1).strip(); return short(r["title"], re.sub(r"^Published\s*", "", b))
tx = [etext(r) for r in E]; ep = np.array([1 if r.get("readings") else 0 for r in E], float); dm = np.zeros(len(E)); dy = np.zeros(len(E))
for k, r in enumerate(E):
    w = collections.Counter()
    for x in r.get("readings") or []: w[x["direction"]] += x.get("strength", 1.0)
    if w["up"] != w["down"] and max(w, key=w.get) in ("up", "down"): dm[k] = 1; dy[k] = 1 if w["up"] > w["down"] else 0
key = [zlib.crc32(nk(r["title"]).encode()) for r in E]
te = [i for i in range(len(E)) if key[i] % 5 == 0]; rest = [i for i in range(len(E)) if key[i] % 5 != 0]; dv = [i for i in rest if (key[i] // 5) % 10 == 0]; tr = [i for i in rest if i not in set(dv)]
print(f"stories {len(E)}: train {len(tr)} dev {len(dv)} test {len(te)}", flush=True)
tok = AutoTokenizer.from_pretrained("BAAI/bge-small-en-v1.5"); enc = AutoModel.from_pretrained("BAAI/bge-small-en-v1.5")
head = torch.nn.Linear(enc.config.hidden_size, 2)
def fwd(ids):
    b = tok([tx[i] for i in ids], padding=True, truncation=True, max_length=64, return_tensors="pt"); return head(enc(**b).last_hidden_state[:, 0])
def predict(ids):
    enc.eval(); o = []
    with torch.no_grad():
        for a in range(0, len(ids), 64): o.append(torch.sigmoid(fwd(ids[a:a + 64])).numpy())
    return np.vstack(o)
def sc(ids, P):
    m = [j for j, i in enumerate(ids) if dm[i]]; yd = dy[[ids[j] for j in m]]
    return {"presence_auroc": float(roc_auc_score(ep[ids], P[:, 0])), "direction_auroc": float(roc_auc_score(yd, P[m, 1])), "direction_accuracy": float(((P[m, 1] >= 0.5) == yd).mean())}
opt = torch.optim.AdamW(list(enc.parameters()) + list(head.parameters()), lr=5e-5, weight_decay=0.01); steps = EP * ((len(tr) + 31) // 32)
sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / 20) * max(0.0, 1 - s / steps)); pw = torch.tensor((1 - ep[tr].mean()) / max(ep[tr].mean(), 1e-6)).float()
curve = []; best = None
for e in range(1, EP + 1):
    enc.train(); order = tr[:]; random.shuffle(order); tl = 0
    for a in range(0, len(order), 32):
        ids = order[a:a + 32]; lg = fwd(ids); y = torch.tensor(np.stack([ep[ids], dy[ids]], 1)).float()
        lp = torch.nn.functional.binary_cross_entropy_with_logits(lg[:, 0], y[:, 0], pos_weight=pw); mk = torch.tensor(dm[ids]).float()
        ld = (torch.nn.functional.binary_cross_entropy_with_logits(lg[:, 1], y[:, 1], reduction="none") * mk).sum() / mk.sum().clamp(min=1)
        loss = lp + ld; opt.zero_grad(); loss.backward(); opt.step(); sched.step(); tl += float(loss) * len(ids)
    dsc = sc(dv, predict(dv)); tsc = sc(te, predict(te)); pt = {"epoch": e, "train_loss": round(tl / len(tr), 4), "dev_presence_auroc": round(dsc["presence_auroc"], 4), "dev_direction_auroc": round(dsc["direction_auroc"], 4), "test_presence_auroc": round(tsc["presence_auroc"], 4)}
    curve.append(pt); crit = dsc["presence_auroc"] + dsc["direction_auroc"]
    if best is None or crit > best[0]: best = (crit, e, tsc)
    print(pt, round(time.time() - T0), flush=True)
    json.dump({"curve": curve, "partial": True}, open(OUT / "t128_finetune.json", "w"))
w = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True, max_features=60000); c = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=5, sublinear_tf=True, max_features=60000); trn = tr + dv
Xa = hstack([w.fit_transform([tx[i] for i in trn]), c.fit_transform([tx[i] for i in trn])]).tocsr(); Xe = hstack([w.transform([tx[i] for i in te]), c.transform([tx[i] for i in te])]).tocsr()
pp = LogisticRegression(C=4.0, max_iter=400, class_weight="balanced").fit(Xa, ep[trn]).predict_proba(Xe)[:, 1]; dtr = [j for j, i in enumerate(trn) if dm[i]]
pdv = LogisticRegression(C=4.0, max_iter=400, class_weight="balanced").fit(Xa[dtr], dy[[trn[j] for j in dtr]]).predict_proba(Xe)[:, 1]; Ps = np.stack([pp, pdv], 1); sp = sc(te, Ps)
maj = float(max(dy[[i for i in te if dm[i]]].mean(), 1 - dy[[i for i in te if dm[i]]].mean()))
res = {"stories": len(E), "train": len(tr), "dev": len(dv), "test": len(te), "epochs": EP, "best_epoch_by_dev": best[1], "finetuned": {k: round(v, 4) for k, v in best[2].items()}, "sparse_same_split": {k: round(v, 4) for k, v in sp.items()}, "direction_majority_on_test": round(maj, 4), "curve": curve,
       "note": "Test = grouped fold 0 of the engine stories; epoch chosen on a 10 percent dev split of the training stories, never on test; reference is the engine's stored reading (agreement, not accuracy)."}
res["seconds"] = round(time.time() - T0); json.dump(res, open(OUT / "t128_finetune.json", "w"), indent=1); print(json.dumps({k: res[k] for k in ("finetuned", "sparse_same_split", "best_epoch_by_dev", "seconds")}))
