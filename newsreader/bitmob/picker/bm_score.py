"""BitMob (mh_r4) condition score for a jsonl of {id,state_text}. usage: bm_score.py in.jsonl out.npy"""
import os, sys, json
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ.setdefault("WORLD_GPU", "0")
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import numpy as np, torch
from mh_common import load, predict
torch.set_num_threads(8)
R=[json.loads(l) for l in open(sys.argv[1])]
model, tok, K = load("/workspace/data/kaggle/mh_r4/out/mh"); model.cond_cuts = None
H = predict(model, tok, [r["state_text"] for r in R])["cond"]
np.save(sys.argv[2], H.max(1))
