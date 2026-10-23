"""Run raw BitMob (no cuts) once on train Clef rows (ds w>=4), tune Clef rows (w>=4) and the 2,000 frozen-test stories; cache cond/gate/expected/reading + per-story ms.
  CUDA_VISIBLE_DEVICES= kev/.venv/bin/python newsreader/bitmob/checker/bm_cache.py"""
import os, sys, json, time, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import torch; torch.set_num_threads(8)
from mh_common import load, predict
B = "/workspace/data/kaggle/mh_r6c1"; O = "/workspace/data/checker"
model, tok, K = load(f"{B}/out/mh")
for a in ("cond_cuts", "gate_cuts", "exp_cuts", "reading_cuts"): setattr(model, a, None)
test = [json.loads(l) for l in open("/workspace/data/clef-labels/test.jsonl")]; TID = {r["id"] for r in test}
for name, d in (("train", f"{B}/ds"), ("tune", f"{B}/tune")):
    tt = json.load(open(f"{d}/texts.json")); ids = json.load(open(f"{d}/keys.json"))["ids"]; Z = np.load(f"{d}/targets.npz"); keep = np.where(Z["w"] >= 4)[0]
    assert not (TID & {ids[i] for i in keep}), "test id"
    t0 = time.time(); H = predict(model, tok, [tt[i] for i in keep]); print(name, len(keep), "rows", round((time.time() - t0) / len(keep) * 1000, 1), "ms/story", flush=True)
    np.savez_compressed(f"{O}/bm_{name}.npz", keep=keep, ids=np.array([ids[i] for i in keep]), cond=H["cond"], gate=H["gate"], expected=H["expected"], reading=H["reading"], y_cond=Z["cond"][keep], y_gate=Z["gate"][keep], y_exp=Z["expected"][keep], y_expm=Z["expected_mask"][keep])
t0 = time.time(); H = predict(model, tok, [r["state_text"] for r in test]); dt = time.time() - t0; print("test", len(test), round(dt / len(test) * 1000, 1), "ms/story", flush=True)
np.savez_compressed(f"{O}/bm_test.npz", cond=H["cond"], gate=H["gate"], expected=H["expected"], reading=H["reading"], bm_ms=dt / len(test) * 1000)
