"""Build fallacy_logic.jsonl from LOGIC (Jin et al. 2022), edu_dev.csv + edu_test.csv.
Raw: /workspace/data/sources/logic/ (downloaded from
https://raw.githubusercontent.com/causalNLP/logical-fallacy/main/data/{edu_dev,edu_test}.csv).
Deterministic: seed 20260921, 15 items per type, stratified."""
import os, re, json, random, subprocess
import pandas as pd
RAW="/workspace/data/sources/logic"; BASE="https://raw.githubusercontent.com/causalNLP/logical-fallacy/main/data/"
os.makedirs(RAW,exist_ok=True)
for s in ("edu_dev","edu_test"):
    p=f"{RAW}/{s}.csv"
    if not os.path.exists(p): subprocess.check_call(["curl","-sL","-o",p,BASE+s+".csv"])
CRIT={
 "ad hominem":"attacks the person making an argument (their character, circumstances or motives) instead of addressing the argument itself",
 "ad populum":"claims something is true or right because many people believe it or do it, or appeals to what the crowd or a group favours",
 "appeal to emotion":"tries to persuade by manipulating the reader's feelings (pity, fear, guilt, anger) in place of giving valid reasons",
 "false causality":"assumes that because one event followed or coincided with another, the first caused the second (or asserts a causal link without support)",
 "false dilemma":"presents only two (or a few) options as if they were the only ones, ignoring other possibilities",
 "faulty generalization":"draws a broad conclusion about a whole group or class from a small, unrepresentative or insufficient sample",
 "circular reasoning":"uses the claim it is trying to prove as its own premise, so the argument only restates its conclusion",
 "fallacy of credibility":"relies on the supposed authority, status or reputation of a speaker or source rather than on evidence for the claim",
}
QN="Which type of logical fallacy does the passage commit?"
INS=QN+" Choose the single best-fitting type."
df=pd.concat([pd.read_csv(f"{RAW}/{s}.csv").assign(split=s) for s in ("edu_dev","edu_test")],ignore_index=True)
df["idx"]=df.groupby("split").cumcount()
def clean(t):
    t=re.sub(r"\s*\n?\s*Is an example of\.*\s*$","",str(t)).strip()
    return re.sub(r"[ \t]+"," ",t)
df["text"]=df.source_article.map(clean)
df=df[(df.text.str.len()>0)&(df.text.str.len()<=1500)].drop_duplicates("text")
rng=random.Random(20260921); rows=[]
for lab in CRIT:
    sub=df[df.updated_label==lab].sort_values(["split","idx"])
    picks=rng.sample(list(sub.itertuples()),15)
    for r in picks:
        rows.append(dict(id=f"fallacy_logic-{r.split}-{r.idx}",family="fallacy_logic",state=r.text,
          question={"type":"choice","instructions":INS,"criteria":CRIT},labels=list(CRIT),expected=lab,split="public",group=None,
          provenance={"exclude_reason":None,"source":"LOGIC (Jin et al., 2022, Logical Fallacy Detection)","url":"https://github.com/causalNLP/logical-fallacy",
          "license":"no licence declared in repo (research dataset); see fallacy_logic.md","retrieved":"2026-09-21","source_id":f"{r.split}.csv row {r.idx}",
          "notes":"trailing 'Is an example of....' prompt stripped where present"}))
rng.shuffle(rows)
with open("/workspace/probes/v2/fallacy_logic.jsonl","w") as f:
    for r in rows: f.write(json.dumps(r,ensure_ascii=False)+"\n")
print(len(rows))
