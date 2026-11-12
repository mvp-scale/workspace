"""T73 stage 2: GLiNER medium v2.1 (threshold 0.5, the T68 label set) over the unique sentences of the 563 pairs. Run in the ner_gliner venv, CPU.
    /workspace/data/venvs/ner_gliner/bin/python t73_gliner.py -> runs/pulse/t73_entities.json"""
import os, json, time
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ["TOKENIZERS_PARALLELISM"] = "false"
from gliner import GLiNER
sents = json.load(open(os.environ.get("T73DIR", "runs/pulse") + "/t73_sentences.json")); m = GLiNER.from_pretrained("urchade/gliner_medium-v2.1")
lab = ["person", "organization", "location", "event", "product", "building", "art work", "other entity"]; out = {}; t0 = time.time()
for k, s in enumerate(sents):
    out[s] = sorted({e["text"] for e in m.predict_entities(s, lab, threshold=0.5)})
    if k % 500 == 0: print(k, len(sents), f"{time.time() - t0:.0f}s", flush=True)
json.dump(out, open(os.environ.get("T73DIR", "runs/pulse") + "/t73_entities.json", "w")); print("done", len(out), f"{time.time() - t0:.0f}s")
