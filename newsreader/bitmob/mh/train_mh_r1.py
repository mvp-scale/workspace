"""Multi-head trainer (D-0038): ONE shared encoder, ten heads (mh_common.HEADS). Runs on Kaggle (private, training data only) or on CPU for the dry run.
  python train_mh.py [--data DIR] [--out DIR] [--epochs 3] [--max_rows N] [--bs 32] [--max_steps N] [--repo intfloat/e5-base-v2]
On Kaggle the data dir is found under /kaggle/input and out is /kaggle/working/mh. make_push.sh concatenates guard.py + mh_common.py + this file (lines carrying the strip marker are removed)."""
import os, sys, json, time, glob, argparse
import numpy as np, torch
from transformers import AutoTokenizer
from mh_common import *      # PUSH-STRIP
from guard import guard, beat      # PUSH-STRIP
ap = argparse.ArgumentParser(); ap.add_argument("--data"); ap.add_argument("--out"); ap.add_argument("--epochs", type=int, default=3); ap.add_argument("--max_rows", type=int, default=0)
ap.add_argument("--bs", type=int, default=32); ap.add_argument("--max_steps", type=int, default=0); ap.add_argument("--repo", default="intfloat/e5-base-v2"); ap.add_argument("--lr", type=float, default=3e-5)
ap.add_argument("--max_min", type=int, default=45); ap.add_argument("--threads", type=int, default=0)
a = ap.parse_args([] if os.path.exists("/kaggle") else None)
if os.path.exists("/kaggle"): a.data = a.data or os.path.dirname(glob.glob("/kaggle/input/**/targets.npz", recursive=True)[0]); a.out = a.out or "/kaggle/working/mh"
guard(max_min=a.max_min, idle_min=8)
dev = "cuda" if torch.cuda.is_available() else "cpu"; print("device", dev, flush=True)
if a.threads: torch.set_num_threads(a.threads)
texts = json.load(open(f"{a.data}/texts.json")); keys = json.load(open(f"{a.data}/keys.json")); Z = np.load(f"{a.data}/targets.npz"); Y = {k: Z[k] for k in Z.files}
N = len(texts) if not a.max_rows else min(a.max_rows, len(texts)); tok = AutoTokenizer.from_pretrained(a.repo); model = MH(keys, repo=a.repo).to(dev)
opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01); spe = (N + a.bs - 1) // a.bs; steps = a.max_steps or a.epochs * spe
sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1, (s + 1) / 50) * max(0.0, 1 - s / steps)); amp = dev == "cuda"; scaler = torch.cuda.amp.GradScaler(enabled=amp)
t0 = time.time(); step = 0; print("rows", N, "steps", steps, {h: head_size(h, keys) for h in HEADS}, flush=True)
for ep in range(a.epochs):
    model.train(); perm = np.random.RandomState(ep).permutation(N)
    for s in range(0, N, a.bs):
        ix = perm[s:s + a.bs]; ids, mask = tokenise(tok, [texts[i] for i in ix], dev)
        y = {k: torch.tensor(v[ix], device=dev) for k, v in Y.items()}
        with torch.autocast(dev, dtype=torch.float16, enabled=amp): out = model(ids, mask)
        loss, per = loss_fn({h: o.float() for h, o in out.items()}, y)
        opt.zero_grad(); scaler.scale(loss).backward(); scaler.unscale_(opt); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); scaler.step(opt); scaler.update(); sched.step(); step += 1
        if step % 20 == 0 or step == 1: print(f"ep {ep + 1} step {step}/{steps} loss {loss.item():.4f} " + " ".join(f"{h}={v:.3f}" for h, v in per.items()) + f" t={time.time() - t0:.0f}s", flush=True)
        beat(f"step {step}")
        if a.max_steps and step >= a.max_steps: break
    if a.max_steps and step >= a.max_steps: break
if a.out:
    model.enc.half() if amp else None; save(model, tok, a.out, keys); print("saved", a.out, flush=True)
print("DONE", round((time.time() - t0) / 60, 2), "min", flush=True)
