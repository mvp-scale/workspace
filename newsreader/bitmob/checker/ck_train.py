"""Checker trainer (Kaggle 2xT4 or CPU dry run). Data dir has pairs.npz, stories.json, questions.json. Soft-target BCE, per-pair weight.
  python ck_train.py [--data D] [--out D] [--repo intfloat/e5-small-v2] [--epochs 4] [--bs 64] [--lr 5e-5] [--max_rows N]"""
import os, sys, json, time, glob, argparse
import numpy as np, torch
from transformers import AutoTokenizer
from ck_common import *      # PUSH-STRIP
from guard import guard, beat      # PUSH-STRIP
ap = argparse.ArgumentParser(); ap.add_argument("--data"); ap.add_argument("--out"); ap.add_argument("--repo", default="intfloat/e5-small-v2"); ap.add_argument("--epochs", type=int, default=4); ap.add_argument("--bs", type=int, default=64)
ap.add_argument("--lr", type=float, default=5e-5); ap.add_argument("--max_rows", type=int, default=0); ap.add_argument("--max_min", type=int, default=50); ap.add_argument("--stop_min", type=float, default=40)
a = ap.parse_args([] if os.path.exists("/kaggle") else None)
if os.path.exists("/kaggle"): a.data = a.data or os.path.dirname(glob.glob("/kaggle/input/**/pairs.npz", recursive=True)[0]); a.out = a.out or "/kaggle/working/ck"
guard(max_min=a.max_min, idle_min=8)
dev = "cuda" if torch.cuda.is_available() else "cpu"; ng = torch.cuda.device_count(); print("device", dev, ng, flush=True)
Z = np.load(f"{a.data}/pairs.npz"); st = json.load(open(f"{a.data}/stories.json")); qs = json.load(open(f"{a.data}/questions.json"))
s, q, t, w = Z["s"], Z["q"], Z["t"], Z["w"]; N = len(s) if not a.max_rows else min(a.max_rows, len(s))
tok = AutoTokenizer.from_pretrained(a.repo); model = Checker(repo=a.repo).to(dev); net = torch.nn.DataParallel(model) if ng > 1 else model
opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01); spe = (N + a.bs - 1) // a.bs; steps = a.epochs * spe
sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda i: min(1, (i + 1) / 100) * max(0.0, 1 - i / steps)); amp = dev == "cuda"; scaler = torch.cuda.amp.GradScaler(enabled=amp)
t0 = time.time(); step = 0; stop = False; print("pairs", N, "steps", steps, flush=True); B = torch.nn.functional.binary_cross_entropy_with_logits
for ep in range(a.epochs):
    model.train(); perm = np.random.RandomState(ep).permutation(N)
    for i in range(0, N, a.bs):
        ix = perm[i:i + a.bs]; ids, mask = ck_tokenise(tok, [ck_text(qs[q[j]], st[s[j]]) for j in ix], dev)
        with torch.autocast(dev, dtype=torch.float16, enabled=amp): z = net(ids, mask)
        yt = torch.tensor(t[ix], device=dev); ww = torch.tensor(w[ix], device=dev); loss = (B(z.float(), yt, reduction="none") * ww).sum() / ww.sum()
        opt.zero_grad(); scaler.scale(loss).backward(); scaler.unscale_(opt); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); scaler.step(opt); scaler.update(); sched.step(); step += 1
        if step % 50 == 0 or step == 1: print(f"ep {ep + 1} step {step}/{steps} loss {loss.item():.4f} t={time.time() - t0:.0f}s", flush=True)
        beat(f"step {step}")
        if (time.time() - t0) / 60 > a.stop_min: print("time budget reached at step", step, flush=True); stop = True; break
    if stop: break
if a.out: ck_save(model, tok, a.out); print("saved", a.out, flush=True)
print("DONE", round((time.time() - t0) / 60, 2), "min", flush=True)
