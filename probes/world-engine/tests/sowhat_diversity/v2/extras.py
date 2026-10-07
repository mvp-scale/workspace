"""HARNESS-2 extras: anchor integrity, hook-family evenness, quiet shares, nulls. python3 extras.py -> extras.json in the diversity2 scratch dir.
Independent of the composer: re-reads the engine response of each story and re-derives every anchor from the numbers."""
import json, re, csv, collections, math
D='/tmp/claude-0/-workspace/cdb40569-0681-424f-99c4-07e70f2075c8/scratchpad/diversity2/'
R='/workspace/probes/persona/rules_v2/'
T1=json.load(open(D+'test1.json')); T2=json.load(open(D+'test2.json'))
LEX=list(csv.DictReader(open(R+'sowhat2_lexicon.csv')))
ACT={(r['id'],r['sign']):r['text'] for r in LEX if r['kind']=='act'}
HOOK={r['id']:r for r in csv.DictReader(open(R+'sowhat2_hooks.csv'))}
peak=lambda v: max(v,key=abs)
def round5(a): return math.floor(a+.5) if a<10 else math.floor(a/5+.5)*5
A1_MIN=2.0
import sys
STRICT=len(sys.argv)>1 and sys.argv[1]=='strict'
SUF='_strict' if STRICT else ''
def check(o,cache={}):
    """returns (ok, [problems]) for one output."""
    txt=(o['headline']+' '+(o['line2'] or ''))
    # the fixed unit "(out of) every 100 people" is a template constant, not a figure; STRICT mode counts it
    nums=re.findall(r'\d+',txt if STRICT else re.sub(r'(?i)\bevery 100\b','every hundred',txt)); a=o.get('anchor'); P=[]
    if not a:
        if nums: P.append('digits without an anchor: '+','.join(nums))
        return P
    if len(nums)>1: P.append('more than one digit-bearing figure: '+','.join(nums))
    if '%' in txt: P.append('percent sign')
    r=cache.setdefault(o['id'],json.load(open(D+o['id']+'.resp.json')))
    imp=r['impact']; hedged=o['cert'] in('forecast','opinion','unclear') or (o['cert']=='announced' and (o['weight'] or 1)<1)
    useIf=hedged and (o['weight'] or 1)<1
    nm=(imp.get('if_true') or {}).get('places') if useIf else imp['places']
    if nm is None: P.append('hedged story but no if_true in response'); return P
    dec=a['decision']; rows=[o['focus_id']]; ent=o['entry']
    if ent and ent not in rows: rows.append(ent)
    world='WORLD:world'
    shown=a['shown']
    exp_nums={str(shown)}
    if a['kind']=='multiple' and a.get('text') and 'more than 10' in a['text']: exp_nums={'10'}
    for n in nums:
        if n not in exp_nums: P.append(f'digit {n} does not trace to anchor shown value {shown}')
    if not nums: P.append('anchor present but no digit in text')
    if a['rule'] in('A1','A4'):
        if a['rule']!=('A4' if useIf else 'A1'): P.append(f"rule {a['rule']} but hedged-with-weight<1 is {useIf}")
        src=None
        for rid in rows:
            v=nm.get(rid,{}).get(dec)
            if v and abs(peak(v)-a['value_raw'])<0.006: src=(rid,peak(v)); break
        if not src: P.append(f"value {a['value_raw']} for {dec} not found as a peak at {rows} in {'if_true' if useIf else 'places'}")
        else:
            if abs(src[1])<A1_MIN: P.append(f'below threshold {A1_MIN}: {src[1]}')
            if round5(abs(src[1]))!=shown: P.append(f'shown {shown} != rounded {round5(abs(src[1]))}')
            # does the anchor say something the numbers do not support
            row=nm[src[0]]; top=max(row.items(),key=lambda kv:abs(peak(kv[1])))
            sign='down' if src[1]<0 else 'up'
            if ACT.get((dec,sign)) and ACT[(dec,sign)] not in txt: P.append(f'UNSUPPORTED: verb for {dec} {sign} ("{ACT.get((dec,sign))}") not in text')
            if abs(peak(top[1]))>0 and abs(src[1])<0.5*abs(peak(top[1])): P.append(f'UNSUPPORTED?: anchored decision {dec} {src[1]:+.2f} is under half the row\'s biggest move ({top[0]} {peak(top[1]):+.2f})')
            if hedged and useIf and not re.search(r'\b(would|could|may|will)\b',(a['text'] or '').replace('would not','').replace('could not','')): P.append('hedged anchor without a modal in the anchor wording')
            if not hedged and re.search(r'\b(would|could|may) (cut|spend|get|take|buy|move|loosen|rein|open|step|skip|switch|travel|save|borrow|check|speak|protest)',a['text'] or ''): P.append('modal wording on an unhedged anchor')
    elif a['rule']=='A3':
        wv=nm.get(world,{}).get(dec); found=None
        for rid in rows+[k for k in nm if k!=world]:
            v=nm.get(rid,{}).get(dec)
            if v and wv and abs(peak(wv))>0 and abs(abs(peak(v))/abs(peak(wv))-a['value_raw'])<0.011: found=(rid,peak(v),peak(wv)); break
        if not found: P.append(f"A3 ratio {a['value_raw']} for {dec} not reproducible from places")
        else:
            rp,wp=abs(found[1]),abs(found[2]);ra=rp/wp
            if ra<3: P.append(f'ratio {ra:.2f} under 3')
            if wp<0.25: P.append(f'world peak {wp:.2f} under 0.25')
            if rp<1: P.append(f'row peak {rp:.2f} under 1')
            if (found[1]<0)!=(found[2]<0): P.append('A3 row and world move in opposite directions')
    return P
def run(items,label):
    outs=[]; anch=[o for o in items if o.get('anchor')]
    digit_no_anchor=[o for o in items if not o.get('anchor') and re.search(r'\d',o['headline']+' '+(o['line2'] or ''))]
    bad=[]
    for o in items:
        p=check(o)
        if p: bad.append(dict(id=o['id'],focus=o['focus'],headline=o['headline'],line2=o['line2'],problems=p))
    return dict(label=label,n=len(items),with_anchor=len(anch),anchor_share=round(len(anch)/len(items),4),in_headline=sum(o['anchor']['where']=='headline' for o in anch),
      rules=collections.Counter(o['anchor']['rule'] for o in anch).most_common(),
      statements_with_problems=len(bad),problems=bad,digit_without_anchor=len(digit_no_anchor),
      unsupported=[b for b in bad if any(p.startswith('UNSUPPORTED') for p in b['problems'])],
      stories_with_unsupported_anchor=len({b['id'] for b in bad if any(p.startswith('UNSUPPORTED') for p in b['problems'])}))
w=[o for o in T1['outputs'] if o['focus']=='world']
res=dict(world=run(w,'world'),all=run(T1['outputs'],'all foci'))
# hook families
def fam(items):
    fc=collections.Counter(o['family'] for o in items); out={}
    for f,c in fc.most_common():
        its=[o for o in items if o['family']==f]; hc=collections.Counter(o['hook'] for o in its)
        bc=collections.Counter(o['body'] for o in its)
        out[f]=dict(n=c,share=round(c/len(items),3),distinct_hooks=len(hc),top_hook=hc.most_common(1)[0],top_hook_share=round(hc.most_common(1)[0][1]/c,3),distinct_bodies=len(bc),top_body=bc.most_common(1)[0],hooks=hc.most_common(6))
    return out
res['families_world']=fam(w); res['families_all']=fam(T1['outputs']); res['families_test2']=fam(T2['outputs'])
bc=collections.Counter(o['body'] for o in w); res['top_body_world']=bc.most_common(5); res['top_body_share_world']=round(bc.most_common(1)[0][1]/len(w),4)
bca=collections.Counter(o['body'] for o in T1['outputs']); res['top_body_share_all']=round(bca.most_common(1)[0][1]/len(T1['outputs']),4)
# quiet
def quiet(items,n_stories):
    q=[o for o in items if o['lead']=='quiet']; qs=collections.Counter(o['family'] for o in q)
    nonvague=[o for o in q if o['family'] not in('NOTHING','QUIET_VAGUE')]
    noimp=[o for o in items if o['family'] in('NOTHING','QUIET_VAGUE')]
    sent=collections.Counter(o['headline'] for o in q)
    return dict(quiet=len(q),quiet_share=round(len(q)/len(items),4),by_family=qs.most_common(),quiet_excl_noimpact_over_all=round(len(nonvague)/len(items),4),quiet_excl_noimpact_over_counted=round(len(nonvague)/(len(items)-len(noimp)),4),no_impact_stories=len(noimp),
      max_repeat_one_sentence=sent.most_common(1)[0][1] if sent else 0,top_repeats=sent.most_common(4))
res['quiet_world']=quiet(w,len(w)); res['quiet_all']=quiet(T1['outputs'],0); res['quiet_test2']=quiet(T2['outputs'],0)
# trigger clause in non-vague quiet: all quiet outputs contain trigger beat?  approximated by beats list
nq=[o for o in w if o['lead']=='quiet' and o['family'] not in('NOTHING','QUIET_VAGUE')]
res['quiet_nonvague_has_trigger_beat']=dict(n=len(nq),with_trigger_beat=sum(any(b['kind']=='trigger' and b.get('text') for b in o['beats']) for o in nq))
# hushed soft word, headline lengths, stock tails
soft=[r['text'] for r in LEX if r['kind']=='soft']; res['soft_words_in_lexicon']=len(soft)
hu=[o for o in w if o['register']=='hushed']
res['hushed']=dict(n=len(hu),with_soft=sum(any(s.lower() in o['headline'].lower() for s in soft) for o in hu))
stock=["Elsewhere, barely a ripple","Little changes elsewhere","A tiny shift that reaches","Fades slowly","no decision moves enough to matter"]
for k,v in (('world',w),('all',T1['outputs']),('test2',T2['outputs'])):
    res['stock_tail_'+k]=sum(any(s in o['headline']+' '+(o['line2'] or '') for s in stock) for o in v)
    res['headline_over_22_'+k]=sum(len(o['headline'].split())>22 for o in v)
    res['line2_over_14_'+k]=sum(len(o['line2'].split())>14 for o in v if o['line2'])
res['nulls']=dict(test1_fails=T1['fails'],test2_null=T2['null_count'])
res['banned_hits']=dict(world=sum(bool(o['banned']) for o in w),all=sum(bool(o['banned']) for o in T1['outputs']),test2=sum(bool(o['banned']) for o in T2['outputs']))
res['banned_examples']=[(o['id'],o['headline'],o['banned']) for o in T1['outputs'] if o['banned']][:10]
# test2 digits
res['test2_digits']=sum(bool(re.search(r'\d',o['headline']+' '+(o['line2'] or ''))) for o in T2['outputs'])
res['test2_multi_digit']=sum(len(re.findall(r'\d+',o['headline']+' '+(o['line2'] or '')))>1 for o in T2['outputs'])
json.dump(res,open(D+'extras'+SUF+'.json','w'),indent=1,default=list)
for k in('world','all'): print(k,{x:res[k][x] for x in('n','with_anchor','anchor_share','in_headline','statements_with_problems','digit_without_anchor','stories_with_unsupported_anchor')})
print('quiet',res['quiet_world']); print('banned',res['banned_hits'],'stock',res['stock_tail_world'],res['stock_tail_all'],res['stock_tail_test2'])
