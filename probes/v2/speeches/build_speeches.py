"""Builds speeches/*.json from raw files in /workspace/data/sources/speeches (see README.md)."""
import re, json, html
RAW='/workspace/data/sources/speeches/'
def split_sentences(par):
    par=' '.join(par.split())
    return [s for s in re.split(r'(?<=[.!?])(?:["”’\']?)\s+(?=["“‘\']?[A-Z])',par) if s]
# note: the lookbehind ends at the punctuation, so a closing quote stays attached only if not consumed; handled below
def split_sentences(par):
    par=' '.join(par.split())
    out=[];start=0
    for m in re.finditer(r'[.!?]["”’\']?\s+(?=["“‘\']?[A-Z])',par):
        out.append(par[start:m.end()].strip()); start=m.end()
    if par[start:].strip(): out.append(par[start:].strip())
    return out
def strip_html(s): return html.unescape(re.sub(r'<[^>]*>','',s))
def save(slug,meta,pars):
    d=dict(meta); d['paragraphs']=[split_sentences(p) for p in pars if p.strip()]
    json.dump(d,open(slug+'.json','w'),indent=1,ensure_ascii=False)
    print(slug,len(d['paragraphs']),sum(map(len,d['paragraphs'])))
# Gettysburg (Avalon, Bliss copy): single paragraph inside quotes
h=open(RAW+'gettyb.html',encoding='utf-8',errors='replace').read()
m=re.search(r'<p>\s*"?(Fourscore.*?)"?\s*</p>',h,re.S) or re.search(r'(Fourscore.*?perish from the earth\.)',h,re.S)
save('gettysburg-address',{"title":"Gettysburg Address","speaker":"Abraham Lincoln","year":1863,"source_url":"https://avalon.law.yale.edu/19th_century/gettyb.asp",
 "public_domain_basis":"Published 1863; author died 1865; US public domain (Yale Avalon Project transcription of the Bliss copy)."},[strip_html(m.group(1)).strip().strip('"')])
# FDR
h=open(RAW+'froos1.html',encoding='utf-8',errors='replace').read()
t=strip_html(h); lines=[l.strip() for l in t.splitlines()]
i=next(k for k,l in enumerate(lines) if l.startswith('SATURDAY, MARCH 4, 1933'))
pars=[]
for l in lines[i+1:]:
    if not l: continue
    if l.startswith('Inaugural Speeches Page') or l.startswith('20th Century Documents') or l.startswith('Avalon Home'): break
    pars.append(l)
save('fdr-first-inaugural',{"title":"First Inaugural Address","speaker":"Franklin D. Roosevelt","year":1933,"source_url":"https://avalon.law.yale.edu/20th_century/froos1.asp",
 "public_domain_basis":"Work of the US federal government (a President's official address), not eligible for copyright under 17 U.S.C. 105; Yale Avalon Project transcription."},pars)
# Julius Caesar 3.2 (Gutenberg #1522): Antony's own speeches only
L=open(RAW+'jc.txt',encoding='utf-8').read().splitlines()
s=next(k for k,l in enumerate(L) if l.startswith('Friends, Romans, countrymen'))-1
e=next(k for k in range(s,len(L)) if L[k].startswith('Take thou what course thou wilt'))
blocks=[];cur=None
for l in L[s:e+1]:
    if l.strip()=='ANTONY.': cur=[];blocks.append(cur);continue
    if re.match(r'^[A-Z][A-Z ]+\.$',l.strip()) or l.strip().startswith('['): cur=None;continue  # other speaker / stage direction
    if cur is not None and l.strip(): cur.append(l.strip())
# note: a stage-direction line ends the current block only if it appears at block start; inline ones are dropped
save('antony-funeral-oration',{"title":"Mark Antony's funeral oration (Julius Caesar, Act 3 Scene 2)","speaker":"Mark Antony (William Shakespeare, character)","year":1599,
 "source_url":"https://www.gutenberg.org/cache/epub/1522/pg1522.txt","public_domain_basis":"William Shakespeare died 1616; Project Gutenberg #1522 text (Gutenberg edition based on the public-domain Globe-type text). Only Antony's speech blocks are kept; citizens' lines and stage directions removed."},[' '.join(b) for b in blocks])
