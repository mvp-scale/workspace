"""F-0110 step 2 prep: tune-fit shortlist cut (95% of Clef trigger answers on 894 Clef-labelled tune rows, never test), apply to 300 fixed-seed frozen-test stories, write the Kaggle request file.
  CUDA_VISIBLE_DEVICES= /workspace/kev/.venv/bin/python newsreader/bitmob/mh/screen_real_prep.py"""
import os, sys, json, random, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import torch; torch.set_num_threads(8)
import classify as C
from mh_common import load, predict
OUT = "/workspace/data/diag/screen_real"; SEED = 20261022; N = 300; NCTRL = 30; REC = 0.95; TUNE = "/workspace/data/kaggle/mh_r6c1/tune"
R = [json.loads(l) for l in open("/workspace/data/clef-labels/test.jsonl")]
model, tok, K = load("/workspace/data/kaggle/mh_r6c1/out/mh"); model.cond_cuts = None
tt = json.load(open(f"{TUNE}/texts.json")); Z = np.load(f"{TUNE}/targets.npz"); keep = np.where(Z["w"] >= 4)[0]
HU = np.asarray(predict(model, tok, [tt[i] for i in keep])["cond"]); yc = Z["cond"][keep] >= C.ATTR_MIN
s = np.sort(HU[yc])[::-1]; thr = float(s[int(REC * len(s)) - 1]); print("tune-fit cut", thr)
idx = sorted(random.Random(SEED).sample(range(len(R)), N)); Rs = [R[i] for i in idx]
H = np.asarray(predict(model, tok, [r["state_text"] for r in Rs])["cond"]); A = [k.split("|") for k in K["cond"]]; flag = H >= thr
names = list(C.QS); rows = []
for n, r in enumerate(Rs):
    sk = {f"a|{d}|{dr}|{i}|{w}" for j, (d, dr, i) in enumerate(A) if flag[n, j] for w in (0, 1)}
    assert sk <= set(names)
    a = [k for k in names if k in sk]; blocks = [names[j:j + 20] for j in range(0, len(names), 20)]
    rows.append({"id": r["id"], "state": f"News item (published {r['day']}; today is {r['day']}):\n{r['state_text']}", "A": [a[j:j + 20] for j in range(0, len(a), 20)], "B": [b for b in blocks if sk & set(b)], "ctrl": n < NCTRL})
os.makedirs(OUT, exist_ok=True)
open(f"{OUT}/stories.jsonl", "w").write("".join(json.dumps(x) + "\n" for x in rows))
np.savez(f"{OUT}/prep.npz", idx=np.array(idx), H=H, flag=flag, thr=thr)
print("stories", len(rows), "shortlisted answers/story", flag.sum(1).mean(), "A calls/story", np.mean([len(x["A"]) for x in rows]), "B calls/story", np.mean([len(x["B"]) for x in rows]), "A q/story", np.mean([sum(map(len, x["A"])) for x in rows]), "B q/story", np.mean([sum(map(len, x["B"])) for x in rows]))
