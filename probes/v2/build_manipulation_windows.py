"""Build manipulation_windows.json (window-study set) from MentalManip (Wang et al., ACL 2024).
Raw: git clone https://github.com/audreycs/MentalManip -> /workspace/data/sources/mentalmanip/repo ; file mentalmanip_dataset/mentalmanip_con.csv (consensus). CC BY-NC 4.0.
Parser: the CSV stores each dialogue as one string, turns beginning with 'Person<k>:'. A new turn starts at every line-start match of
  ^(Person\\d+):\\s* ; continuation lines (no prefix) are appended to the current turn joined with a single space. Text whitespace is
  normalised (runs of whitespace -> one space). A dialogue is UNPARSEABLE (dropped, counted) if it does not start with a speaker prefix or has an empty turn.
Filters: 3<=turns<=12, len(raw dialogue text, normalised, joined with newlines)<=1400 chars; source_id not in manipulation_dialogue.jsonl;
  manipulative rows need non-empty consensus Technique (as in the existing probe set); non-manipulative rows any.
Sampling: random.Random(20260921) over ID-sorted lists, 100 per class. Output sorted by id after a seeded shuffle.
The label is DIALOGUE-LEVEL, not localised to any turn.
"""
import csv, json, random, re, collections
SRC='/workspace/data/sources/mentalmanip/repo/mentalmanip_dataset/mentalmanip_con.csv'
EXIST='/workspace/probes/v2/manipulation_dialogue.jsonl'
OUT='/workspace/probes/v2/manipulation_windows.json'
N=100
excl={json.loads(l)['provenance']['source_id'] for l in open(EXIST)}
PFX=re.compile(r'^(Person\d+):[ \t]*(.*)$')
def parse(s):
    turns=[]
    for line in s.strip().splitlines():
        line=line.strip()
        if not line: continue
        m=PFX.match(line)
        if m: turns.append({"speaker":m.group(1),"text":' '.join(m.group(2).split())})
        elif turns: turns[-1]["text"]=(turns[-1]["text"]+' '+' '.join(line.split())).strip()
        else: return None
    if not turns or any(not t["text"] for t in turns): return None
    return turns
rows=sorted(csv.DictReader(open(SRC,encoding='utf-8',newline='')),key=lambda r:r['ID'])
stat=collections.Counter(); pool={'1':[],'0':[]}
for r in rows:
    if r['ID'] in excl: stat['in_existing_probe']+=1; continue
    t=parse(r['Dialogue'])
    if t is None: stat['unparseable']+=1; continue
    if not 3<=len(t)<=12: stat['turns_out_of_range']+=1; continue
    if sum(len(x['speaker'])+2+len(x['text']) for x in t)+len(t)-1>1400: stat['too_long']+=1; continue
    if r['Manipulative']=='1' and not r['Technique'].strip(): stat['manip_no_technique']+=1; continue
    pool[r['Manipulative']].append((r,t))
rng=random.Random(20260921)
sel=rng.sample(pool['1'],N)+rng.sample(pool['0'],N); rng.shuffle(sel)
out=[]
for r,t in sel:
    out.append({"id":"mmwin-"+r['ID'],"source_id":r['ID'],"turns":t,"n_turns":len(t),"manipulative":r['Manipulative']=='1',
      "technique":[x.strip() for x in r['Technique'].split(',') if x.strip()],"vulnerability":[x.strip() for x in r['Vulnerability'].split(',') if x.strip()],
      "label_scope":"whole dialogue; not localised to any turn"})
out.sort(key=lambda d:d['id'])
doc={"name":"manipulation_windows","source":"MentalManip (Wang et al., ACL 2024), mentalmanip_con.csv","url":"https://github.com/audreycs/MentalManip","license":"CC BY-NC 4.0","retrieved":"2026-09-21","seed":20260921,
 "label_scope":"Labels, techniques and vulnerabilities apply to the whole dialogue, not to any individual turn or window.","filter_stats":dict(stat),"pool_sizes":{k:len(v) for k,v in pool.items()},"dialogues":out}
json.dump(doc,open(OUT,'w'),ensure_ascii=False,indent=1)
print(stat,doc['pool_sizes'],len(out),collections.Counter(d['n_turns'] for d in out))
