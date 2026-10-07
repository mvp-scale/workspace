import csv, json
T=[r['id'] for r in csv.DictReader(open('/workspace/probes/persona/rules_v2/domains.csv'))]
C=['happened','announced','forecast','opinion']
src=[l.rstrip('\n').split('|',1) for l in open(__file__.replace('build_stories.py','stories_src.txt')) if l.strip()]
out=[];n=0
for i,t in enumerate(T):
    c1=C[i%4];s1=(i//4)%2;v1=(i//3)%2;e1=(i//5)%2
    sp=[(c1,s1,v1,e1),(C[(i+2)%4],1-s1,1-v1,1-e1)]
    for k in range(2):
        topic,text=src[n]; assert topic==t,(topic,t); c,s,v,e=sp[k]
        out.append(dict(id=f"s{n+1:03d}",topic=t,text=text,cert=c,scope=['local','world'][s],valence=['bad','good'][v],effect=['large','small'][e])); n+=1
for topic,text in src[n:]:
    out.append(dict(id=f"s{len(out)+1:03d}",topic=topic.lower(),text=text,cert=None,scope=None,valence=topic.lower() if topic!='EXTRA' else None,effect=None)); 
json.dump(out,open('stories.json','w'),indent=1); print(len(out))
