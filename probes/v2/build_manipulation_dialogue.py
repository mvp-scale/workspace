"""Build manipulation_dialogue.jsonl from MentalManip (Wang et al., ACL 2024).
Raw: git clone https://github.com/audreycs/MentalManip -> /workspace/data/sources/mentalmanip/repo
Uses mentalmanip_dataset/mentalmanip_con.csv (consensus: all 3 annotators agree on the manipulation label).
Filters: dialogue <= 1400 chars (no truncation performed); manipulative rows must have a non-empty consensus Technique.
Sampling: random.Random(20260921), 40 per class, manipulative stratified round-robin over primary technique string.
"""
import csv, json, random, collections
SRC='/workspace/data/sources/mentalmanip/repo/mentalmanip_dataset/mentalmanip_con.csv'
OUT='/workspace/probes/v2/manipulation_dialogue.jsonl'
N=40
rows=list(csv.DictReader(open(SRC,encoding='utf-8',newline='')))
clean=lambda s:'\n'.join(' '.join(l.split()) for l in s.strip().splitlines() if l.strip())
rng=random.Random(20260921)
pos=[r for r in rows if r['Manipulative']=='1' and r['Technique'].strip() and len(clean(r['Dialogue']))<=1400]
neg=[r for r in rows if r['Manipulative']=='0' and len(clean(r['Dialogue']))<=1400]
neg.sort(key=lambda r:r['ID']); pos.sort(key=lambda r:r['ID'])
neg=rng.sample(neg,N)
by=collections.defaultdict(list)
for r in pos: by[r['Technique']].append(r)
for v in by.values(): rng.shuffle(v)
keys=sorted(by); rng.shuffle(keys); sel=[]
while len(sel)<N:
    for k in keys:
        if by[k] and len(sel)<N: sel.append(by[k].pop())
items=sel+neg; rng.shuffle(items)
Q={"type":"noul","instructions":"Does one speaker in this dialogue try to manipulate the other, that is, use language to influence, alter, or control the other person's psychological state or perception for the manipulator's benefit?",
 "criteria":{"true":"One speaker uses language to influence, alter, or control the other's psychological state or perception for the manipulator's own benefit.","false":"No speaker tries to manipulate the other; the conversation is ordinary."}}
with open(OUT,'w') as f:
    for r in items:
        y=r['Manipulative']=='1'
        f.write(json.dumps({"id":"mentalmanip-"+r['ID'],"family":"manipulation_dialogue","state":clean(r['Dialogue']),"question":Q,"labels":["no","yes"],"expected":"yes" if y else "no","split":"public","group":None,
         "provenance":{"exclude_reason":None,"source":"MentalManip (Wang et al., ACL 2024), mentalmanip_con.csv","url":"https://github.com/audreycs/MentalManip","license":"CC BY-NC 4.0","retrieved":"2026-09-21","source_id":r['ID'],
         "notes":f"consensus label; technique={r['Technique'] or 'none'}; vulnerability={r['Vulnerability'] or 'none'}; no truncation (dialogues <=1400 chars only)"}})+'\n')
print(collections.Counter(i['Manipulative'] for i in items))
