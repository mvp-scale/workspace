"""Build nli_snli.jsonl from SNLI validation split (HF stanfordnlp/snli, CC BY-SA 4.0).
Original: https://nlp.stanford.edu/projects/snli/ . Seed 20260921, 30 per class.
Mapping: contradiction->contradicts, entailment->supports, neutral->neither. label -1 dropped."""
import os, json, random
os.environ.setdefault("HF_HOME","/workspace/data/sources/hf-cache")
from datasets import load_dataset
d=load_dataset("stanfordnlp/snli",split="validation")
MAP={0:"supports",1:"neither",2:"contradicts"}
CRIT={"contradicts":"Statement B cannot be true if statement A is true (they describe conflicting situations).",
 "supports":"If statement A is true, statement B must also be true (A entails B).",
 "neither":"Statement B might or might not be true given A; A neither guarantees nor rules it out."}
Q="How does statement B (the hypothesis) relate to statement A (the premise)?"
rng=random.Random(20260921); rows=[]
seen=set()
for lab,name in MAP.items():
    idx=[i for i,x in enumerate(d["label"]) if x==lab and len(d[i]["premise"])+len(d[i]["hypothesis"])<1200]
    idx=[i for i in idx if d[i]["premise"] not in seen or True]
    for i in rng.sample(idx,30):
        x=d[i]
        rows.append(dict(id=f"nli_snli-val-{i}",family="nli_snli",state=f"Statement A: {x['premise'].strip()}\nStatement B: {x['hypothesis'].strip()}",
         question={"type":"choice","instructions":Q,"criteria":CRIT},labels=list(CRIT),expected=name,split="public",group=None,
         provenance={"exclude_reason":None,"source":"SNLI (Bowman et al., 2015)","url":"https://huggingface.co/datasets/stanfordnlp/snli","license":"CC BY-SA 4.0",
         "retrieved":"2026-09-21","source_id":f"validation[{i}]","notes":"label map: entailment->supports, contradiction->contradicts, neutral->neither"}))
rng.shuffle(rows)
with open("/workspace/probes/v2/nli_snli.jsonl","w") as f:
    for r in rows: f.write(json.dumps(r,ensure_ascii=False)+"\n")
print(len(rows))
