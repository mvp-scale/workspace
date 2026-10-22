"""Score run8 (country 69-class, scope/recent heads) locally on CPU on the frozen test. Same test, order and fp32 forward as kaggle_score.py.
  THREADS=8 models/embed-zs/.venv/bin/python newsreader/bitmob/reader/score_r8.py <country|heads>  -> data/suite_kaggle8/e5-base-v2/<area>.npz"""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import sys, json, time, numpy as np, torch
from sklearn.model_selection import train_test_split
from transformers import AutoTokenizer, AutoModel
torch.set_num_threads(int(os.environ.get("THREADS", "8"))); area = sys.argv[1]; W = "/workspace/data"; L = lambda f: [json.loads(l) for l in open(f)]
sys.path.insert(0, "/workspace/newsreader/bitmob"); from progress import event
night = L(f"{W}/trainset/night1.jsonl"); _, te_i = train_test_split(np.arange(len(night)), test_size=0.2, random_state=0)
test = [night[i] for i in te_i] + L(f"{W}/trainset/testA.jsonl"); Xs = [r["input"] for r in test]
d = f"{os.environ.get('RUN8', W + '/kaggle/run8')}/e5-base-v2/{area}"; keys = json.load(open(f"{d}/keys.json")); multi = area == "heads"
tok = AutoTokenizer.from_pretrained(d); enc = AutoModel.from_pretrained(d).float().eval(); head = torch.nn.Linear(enc.config.hidden_size, len(keys)); head.load_state_dict({k: v.float() for k, v in torch.load(f"{d}/head.pt").items()})
def fwd(xs):
    b = tok(["query: " + x for x in xs], padding=True, truncation=True, max_length=96, return_tensors="pt"); h = enc(**b).last_hidden_state; m = b["attention_mask"].unsqueeze(-1); return (h * m).sum(1) / m.sum(1)
def pred(xs):
    with torch.no_grad(): o = torch.cat([head(fwd(xs[j:j + 128])) for j in range(0, len(xs), 128)])
    return (torch.sigmoid(o) if multi else torch.softmax(o, 1)).numpy()
J = f"kaggle8:score:{area}"; event(J, "scoring", f"scoring {len(Xs)} stories", pid=os.getpid()); t0 = time.time(); P = pred(Xs); print("scored", round((time.time() - t0) / 60, 1), "min", flush=True)
out = f"{W}/suite_kaggle8/e5-base-v2"; os.makedirs(out, exist_ok=True); np.savez_compressed(f"{out}/{area}.npz", P=P.astype(np.float32), keys=np.array(keys), n_night=len(te_i))
event(J, "done", f"{area} test probabilities written", pid=os.getpid(), win=True)
