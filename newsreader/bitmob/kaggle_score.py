"""Score Kaggle-trained encoders locally on the frozen test (same test, labels and scoring as suite.py), CPU only.
  THREADS=6 kev/.venv/bin/python newsreader/bitmob/kaggle_score.py <run_dir> <model e5-base-v2|e5-large-v2> <area topic|type>
Writes data/suite_kaggle1/<model>/<area>.json + .npz. Fine-tune ran on Kaggle (fp16 weights saved), see ledger."""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import sys, json, time, collections, numpy as np, torch
from sklearn.model_selection import train_test_split
from sklearn.metrics import average_precision_score, f1_score
from transformers import AutoTokenizer, AutoModel
torch.set_num_threads(int(os.environ.get("THREADS", "6")))
run, mname, area = sys.argv[1:4]; SO = os.environ.get("SUITE_OUT", "suite_kaggle1"); sys.path.insert(0, os.path.dirname(__file__)); from progress import event; JOB = "kaggle:score"; W = "/workspace/data"; L = lambda f: [json.loads(l) for l in open(f)]
night = L(f"{W}/trainset/night1.jsonl"); tr_i, te_i = train_test_split(np.arange(len(night)), test_size=0.2, random_state=0)
test = [night[i] for i in te_i] + L(f"{W}/trainset/testA.jsonl"); Xs = [r["input"] for r in test]
if os.environ.get("OUTLET_PREFIX"):      # run 6: reader input = "source: <outlet> | " + input (item context, D-0015 fallback)
    import re; _o = lambda r: (r.get("outlet") or (r.get("source") if r.get("source") not in (None, "ccnews", "feed") else None) or r.get("feed") or (re.match(r"cc:https?://([^/]+)", r["id"]) or [0, "unknown"])[1]).replace("www.", "")
    Xs = [f"source: {_o(r)} | " + r["input"] for r in test]
d = f"{run}/{mname}/{area}"; keys = json.load(open(f"{d}/keys.json")); multi = area in ("type", "conditions")
event(JOB, "training", f"{mname} {area}: loading", pid=os.getpid())
tok = AutoTokenizer.from_pretrained(d); enc = AutoModel.from_pretrained(d).float().eval()
head = torch.nn.Linear(enc.config.hidden_size, len(keys)); head.load_state_dict({k: v.float() for k, v in torch.load(f"{d}/head.pt").items()})
def fwd(xs):
    b = tok(["query: " + x for x in xs], padding=True, truncation=True, max_length=int(os.environ.get("MAXLEN", "96")), return_tensors="pt"); h = enc(**b).last_hidden_state
    m = b["attention_mask"].unsqueeze(-1); return (h * m).sum(1) / m.sum(1)
def pred(xs):
    with torch.no_grad(): o = torch.cat([head(fwd(xs[j:j + 128])) for j in range(0, len(xs), 128)])
    return (torch.sigmoid(o) if multi else torch.softmax(o, 1)).numpy()
xs = Xs[:256]; t = time.time(); pred(xs); ms = round(1000 * (time.time() - t) / len(xs), 2); print("ms/story", ms, flush=True)
event(JOB, "scoring", f"{mname} {area}: scoring {len(Xs)} stories ({ms} ms/story)", pid=os.getpid()); t0 = time.time(); P = pred(Xs); print("scored", round((time.time() - t0) / 60, 1), "min", flush=True)
ix = {k: i for i, k in enumerate(keys)}; Y = np.zeros((len(test), len(keys)), bool)
keep = set(keys) - {"other"}
for j, r in enumerate(test):
    if area == "type": [Y.__setitem__((j, ix[k]), True) for k in keys if r["P"].get(f"g|{k}", 0) >= 0.5]
    elif area == "conditions": [Y.__setitem__((j, ix[k]), True) for k in r["target_keys"] if k in ix]
    else: f = r[area]; Y[j, ix[f if f in keep else "other"]] = True
if multi:
    ap = {k: float(average_precision_score(Y[:, i], P[:, i])) for i, k in enumerate(keys) if Y[:, i].sum() >= 3}
    sc = {"mean_AP": round(float(np.mean(list(ap.values()))), 4), "per_key_AP": {k: round(v, 4) for k, v in ap.items()}, "test_pos": {k: int(Y[:, i].sum()) for i, k in enumerate(keys)}}
else:
    y, pr = Y.argmax(1), P.argmax(1); sc = {"accuracy": round(float((y == pr).mean()), 4), "macroF1": round(float(f1_score(y, pr, average="macro")), 4)}
res = {"model": mname, "area": area, "kind": "multilabel" if multi else "multiclass", "keys": keys, "train": 12994, "test": len(test), "minutes": None, "ms_per_story": ms, "source": "kaggle fine-tune, e5ft recipe, fp16 weights"} | sc
out = f"{W}/{SO}/{mname}"; os.makedirs(out, exist_ok=True)
json.dump(res, open(f"{out}/{area}.json", "w"), indent=1); np.savez_compressed(f"{out}/{area}.npz", P=P.astype(np.float32), Y=Y, keys=np.array(keys), n_night=len(te_i)); print(sc if not multi else sc["mean_AP"])

event(JOB, "done", f"{mname} {area}: " + (f"mean AP {sc['mean_AP']}" if multi else f"accuracy {sc['accuracy']}") + f", {ms} ms/story", pid=os.getpid(), win=True)
