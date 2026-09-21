"""Build persuasion_appeals.jsonl from Persuasion for Good (Wang et al., ACL 2019).
Raw: git clone https://gitlab.com/ucdavisnlp/persuasionforgood -> /workspace/data/sources/p4g/repo
     (file data/AnnotatedData/300_dialog.xlsx, 300 annotated dialogues; annotation scheme data/persuader_scheme.docx). Licence: Apache-2.0 (repo LICENSE).
Rows: persuader (Role 0) sentence units, label = er_label_1 (most salient persuader label). Every persuader unit carries a label,
so the 'none' class is NOT unlabelled text: it is persuader units whose label is a non-strategy dialog act
(greeting, thank, acknowledgement, closing, you-are-welcome, off-task, praise-user, comment-partner).
Classes: credibility-appeal, emotion-appeal, logical-appeal, personal-story, foot-in-the-door, self-modeling, none.
Filters: 25<=len<=400 chars after whitespace normalisation (none class: 3<=len<=400, since acts are short), exact-duplicate texts dropped,
units with a second label (er_label_2) dropped (ambiguous). Sampling: random.Random(20260921), 20 per class, sorted before sampling.
Ids are p4g-<dialogue id>-<row index>.  xlsx read with stdlib reader _xlsx_min.py (openpyxl unavailable).
"""
import json, random, collections
import _xlsx_min
SRC='/workspace/data/sources/p4g/repo/data/AnnotatedData/300_dialog.xlsx'
OUT='/workspace/probes/v2/persuasion_appeals.jsonl'
N=20
NONE_ACTS={'greeting','thank','acknowledgement','closing','you-are-welcome','off-task','praise-user','comment-partner'}
STRAT=['credibility-appeal','emotion-appeal','logical-appeal','personal-story','foot-in-the-door','self-modeling']
CRIT={
 'credibility-appeal':"Uses credentials or facts about the organisation's record and impact (e.g. it is an international charity, highly ranked, checked online) to establish trust in it.",
 'emotion-appeal':"Tries to arouse emotion (empathy, sympathy, guilt, anger, storytelling to involve the listener) about the children's suffering to influence the listener.",
 'logical-appeal':"Uses reasoning or evidence: explains what the charity does or how a donation would make a tangible difference to children's health, education or safety.",
 'personal-story':"Persuades through the speaker's own story or a narrative example of someone's donation experience or of a beneficiary's outcome.",
 'foot-in-the-door':"Asks for or normalises a small donation (e.g. even a tiny amount helps) as a first, easy step towards agreeing to give.",
 'self-modeling':"Says the speaker will donate too (or match the donation), acting as a role model for the listener to follow.",
 'none':"No persuasion strategy: a greeting, thanks, acknowledgement, closing, praise or off-task remark with no persuasive appeal."}
Q={"type":"choice","instructions":"This sentence was said by a persuader trying to get someone to donate to the charity Save the Children. Which persuasion strategy, if any, does it use? Choose the single best label.",
   "criteria":CRIT}
LABELS=list(CRIT)
rows=_xlsx_min.read(SRC)[1:]
norm=lambda s:' '.join((s or '').split())
pool=collections.defaultdict(list); seen=set()
for a in rows:
    if a[2]!='0': continue
    a=a+['']*(9-len(a))
    lab,lab2=a[5],a[7]; t=norm(a[4])
    if lab2: continue
    cls=lab if lab in STRAT else ('none' if lab in NONE_ACTS else None)
    if not cls: continue
    lo=3 if cls=='none' else 25
    if not lo<=len(t)<=400 or t.lower() in seen: continue
    seen.add(t.lower()); pool[cls].append((f"p4g-{a[1]}-{a[0]}",t,lab,a[1]))
rng=random.Random(20260921); items=[]
for cls in LABELS:
    p=sorted(pool[cls]); items+= [(cls,)+q for q in rng.sample(p,N)]
    print(cls,len(p))
rng.shuffle(items)
with open(OUT,'w') as f:
    for cls,sid,t,orig,d in items:
        f.write(json.dumps({"id":"persuasion-"+sid,"family":"persuasion_appeals","state":t,"question":Q,"labels":LABELS,"expected":cls,"split":"public","group":None,
         "provenance":{"exclude_reason":None,"source":"Persuasion for Good (Wang et al., ACL 2019), AnnotatedData/300_dialog.xlsx, persuader er_label_1","url":"https://gitlab.com/ucdavisnlp/persuasionforgood","license":"Apache-2.0","retrieved":"2026-09-21","source_id":sid,
         "notes":f"original label={orig}; dialogue={d}; sentence-level unit shown without context"+("; none class = non-strategy dialog act" if cls=='none' else "")}},ensure_ascii=False)+'\n')
