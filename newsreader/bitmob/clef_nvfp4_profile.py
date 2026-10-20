"""Where does the time go in alpha-x-ai's ClefVLLM wrapper? Times vLLM encode, the hidden-state copy, and the decision head separately.
Same 20 stories x 17 calls as clef_nvfp4_test.py. Does not modify the wrapper (subclass only).
Run: /workspace/models/cygnet-venv/bin/python newsreader/bitmob/clef_nvfp4_profile.py CHUNK UTIL TAG '{engine kwargs}'"""
import sys, os, json, time, torch
sys.path.insert(0, "/workspace/data/models/clef-flash-nvfp4-alpha")
os.environ.setdefault("WE_RULES", "rules_v2"); sys.path.insert(0, "/workspace/probes/world-engine")
import classify as C
from clef_vllm import ClefVLLM
CHUNK, UTIL, TAG = int(sys.argv[1]), float(sys.argv[2]), sys.argv[3]; ENG = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
LOG = "/workspace/data/clef-tune/tune.log"
def log(m): line = f"{time.strftime('%F %T')}  {m}"; print(line, flush=True); open(LOG, "a").write(line + "\n")
T = {"encode": 0.0, "copy": 0.0, "head": 0.0}
class Timed(ClefVLLM):
    def hidden_states(self, records, encoded):
        t = time.time(); outs = self.llm.encode([self._prompt(r, e) for r, e in zip(records, encoded)], pooling_task="token_embed", use_tqdm=False)
        torch.cuda.synchronize(); T["encode"] += time.time() - t
        t = time.time(); states = [o.outputs.data.to(self.device, torch.bfloat16) for o in outs]; torch.cuda.synchronize(); T["copy"] += time.time() - t
        return states
    def decide(self, encoded, hidden):
        t = time.time(); r = super().decide(encoded, hidden); torch.cuda.synchronize(); T["head"] += time.time() - t; return r
recs = [json.loads(l) for l in open("/workspace/data/newsreader/labels/clef-q4km.jsonl")][:20]
names = list(C.QS); reqs = []
for r in recs:
    state = f"News item (published 2026-10-19; today is 2026-10-19):\n{r['title']}. {r['text']}"
    for j in range(0, len(names), 20): reqs.append({"state": state, "questions": {k: {"type": "noul", "instructions": C.QS[k]} for k in names[j:j + 20]}})
clef = Timed("/workspace/data/models/clef-flash-nvfp4-alpha", gpu_memory_utilization=UTIL, **ENG)
clef.probabilities(reqs[:4]); T.update({k: 0.0 for k in T})
sample = clef.llm.encode([clef._prompt(reqs[0], clef.encode(reqs[0]))], pooling_task="token_embed", use_tqdm=False)[0].outputs.data
t0 = time.time()
for i in range(0, len(reqs), CHUNK): clef.probabilities(reqs[i:i + CHUNK])
el = time.time() - t0
log(f"[profile {TAG}] {json.dumps({'engine': ENG, 'chunk': CHUNK, 'util': UTIL, 'seconds': round(el, 1), 'stories_per_min': round(len(recs) / el * 60, 1), **{k: round(v, 1) for k, v in T.items()}, 'hidden_device': str(sample.device), 'hidden_dtype': str(sample.dtype), 'hidden_shape': list(sample.shape)})}")
