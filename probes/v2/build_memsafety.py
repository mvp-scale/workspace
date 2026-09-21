#!/usr/bin/env python3
"""Build memsafety probe set from NIST SARD Juliet Test Suite for C/C++ v1.3 (public domain).
Source page: https://samate.nist.gov/SARD/test-suites/112
Zip: https://samate.nist.gov/SARD/downloads/test-suites/2017-10-01-juliet-test-suite-for-c-cplusplus-v1-3.zip
Extract to /workspace/data/sources/juliet/ (gives C/testcases/...). Seed 20260921.
Per CWE: 8 test cases (single-file, flow variant 01; variant 02 fills in if fewer than 8 distinct bases),
each yields the _bad function (yes) and one randomly chosen good function (goodG2B/goodB2G/good1..) (no).
Sanitising: comments stripped, 'static' removed from signature, lone ';' lines removed, functions renamed target_function / helper_N, identifiers or string
literals containing bad/good/CWE/flaw replaced, harness (main, *_good/_bad wrappers) dropped, whitespace normalised.
"""
import re, json, random, glob, os, zipfile
ROOT = '/workspace/data/sources/juliet/C/testcases'
ZIP = '/workspace/data/sources/juliet/2017-10-01-juliet-test-suite-for-c-cplusplus-v1-3.zip'
URL = 'https://samate.nist.gov/SARD/test-suites/112'
OUT = '/workspace/probes/v2/memsafety.jsonl'
CWES = {'121':'CWE121_Stack_Based_Buffer_Overflow','122':'CWE122_Heap_Based_Buffer_Overflow',
 '124':'CWE124_Buffer_Underwrite','126':'CWE126_Buffer_Overread','127':'CWE127_Buffer_Underread',
 '401':'CWE401_Memory_Leak','415':'CWE415_Double_Free','416':'CWE416_Use_After_Free',
 '457':'CWE457_Use_of_Uninitialized_Variable','476':'CWE476_NULL_Pointer_Dereference'}
PAIRS = 8
Q = ("Does this C function contain a memory-safety bug (out-of-bounds read or write, use after free, "
     "double free, null-pointer dereference, or leaked or uninitialised memory)?")
CRIT = {"true": "The function contains at least one memory-safety bug that can occur when it runs: an out-of-bounds read or write, use after free, double free, null-pointer dereference, or leaked or uninitialised memory.",
        "false": "The function is memory-safe: all buffer accesses are in bounds, memory is freed exactly once and not used afterwards, pointers are checked or valid before dereference, allocations are released and variables are initialised before use."}
INSTR = "Read the C function and decide whether it contains a memory-safety bug."

def strip_comments(s):
    out=[];i=0;n=len(s)
    while i<n:
        if s.startswith('/*',i):
            j=s.find('*/',i+2); i=n if j<0 else j+2; out.append(' ')
        elif s.startswith('//',i):
            j=s.find('\n',i); i=n if j<0 else j
        elif s[i]=='"':
            j=i+1
            while j<n and s[j]!='"':
                j+=2 if s[j]=='\\' else 1
            out.append(s[i:j+1]); i=j+1
        elif s[i]=="'":
            j=i+1
            while j<n and s[j]!="'":
                j+=2 if s[j]=='\\' else 1
            out.append(s[i:j+1]); i=j+1
        else:
            out.append(s[i]); i+=1
    return ''.join(out)

FUNC = re.compile(r'^(?:static\s+)?[\w\s\*]+?\b(\w+)\s*\([^)]*\)\s*\n\{.*?\n\}\s*$', re.S|re.M)
def functions(src):
    """return {name: text} for top-level functions (column-0 signature and closing brace)."""
    res={}
    for m in re.finditer(r'^((?:static )?\w[\w \*]*?\b(\w+)\s*\([^;{]*?\))\s*\n\{\n.*?\n\}$', src, re.S|re.M):
        res[m.group(2)] = m.group(0)
    return res

BAD_ID = re.compile(r'\b\w*(?:bad|good|CWE|flaw)\w*\b', re.I)
def sanitize(text, own_name):
    t = strip_comments(text)
    t = re.sub(r'"[^"\n]*(?:good|bad|cwe|flaw)[^"\n]*"', '"text"', t, flags=re.I)
    ids = {}
    def rep(m):
        w=m.group(0)
        if w==own_name: return 'target_function'
        if w not in ids: ids[w]='helper_%d'%(len(ids)+1)
        return ids[w]
    # protect string literals
    parts = re.split(r'("(?:[^"\\\n]|\\.)*")', t)
    parts = [p if p.startswith('"') else BAD_ID.sub(rep,p) for p in parts]
    t=''.join(parts)
    t = re.sub(r'[ \t]+\n','\n',t)
    t = re.sub(r'\n{2,}','\n',t).strip()
    t = re.sub(r'^static\s+','',t)                      # good funcs are static, bad are not: neutralise
    t = re.sub(r'\n[ \t]*;[ \t]*(?=\n)', '', t)      # drop lone empty-statement lines (Juliet good-sink filler)
    return t

def main():
    if not os.path.isdir(ROOT):
        zipfile.ZipFile(ZIP).extractall('/workspace/data/sources/juliet')
    rng = random.Random(20260921)
    rows=[]
    for cwe, d in CWES.items():
        cands=[]
        for var in ('01','02'):
            fs = sorted(f for f in glob.glob(f'{ROOT}/{d}/**/*_{var}.c', recursive=True))
            cands += fs
        ok=[]
        for f in cands:
            src=open(f,encoding='latin-1').read()
            fn=functions(src)
            bad=[k for k in fn if k.endswith('_bad')]
            good=[k for k in fn if re.search(r'good(G2B|B2G|\d|)\w*$',k) and not k.endswith('_good')]
            if len(bad)!=1 or not good: continue
            texts={}
            base=os.path.basename(f)
            bt=sanitize(fn[bad[0]],bad[0])
            if len(bt)>1500 or BAD_ID.search(bt.replace('target_function','')): continue
            goods=[(g,sanitize(fn[g],g)) for g in good]
            goods=[(g,t) for g,t in goods if len(t)<=1500 and not BAD_ID.search(t.replace('target_function',''))]
            if not goods: continue
            key=re.sub(r'_\d\d\.c$','',base)
            ok.append((key,f,bad[0],bt,goods))
        seen=set(); pool=[]
        for var in ('01','02'):
            for it in ok:
                if it[1].endswith(f'_{var}.c') and it[0] not in seen:
                    seen.add(it[0]); pool.append((var,it))
        r1=[x for v,x in pool if v=='01']; r2=[x for v,x in pool if v=='02']
        rng.shuffle(r1); rng.shuffle(r2)
        sel=(r1+r2)[:PAIRS]
        for key,f,bname,bt,goods in sel:
            g,gt=goods[rng.randrange(len(goods))]
            base=os.path.basename(f)
            gid=f'memsafety_cwe{cwe}_{len(rows)//2:03d}'
            rel=os.path.relpath(f,'/workspace/data/sources/juliet')
            for kind,txt,exp,fname in (('bad',bt,'yes',bname),('good',gt,'no',g)):
                rows.append({"id":f"{gid}_{'b' if kind=='bad' else 'g'}","family":"memsafety",
                 "state":txt,
                 "question":{"type":"noul","instructions":INSTR+" "+Q,"criteria":CRIT},
                 "labels":["no","yes"],"expected":exp,"split":"public","group":gid,
                 "provenance":{"exclude_reason":None,"source":"NIST SARD Juliet Test Suite for C/C++ v1.3","url":URL,
                  "license":"public domain (US Government work, NIST SARD)","retrieved":"2026-09-21",
                  "source_id":f"{base}::{fname}",
                  "notes":f"CWE-{cwe}; variant {'bad' if kind=='bad' else re.sub(r'^.*?_(good\\w*)$',r'\\1',fname)}; sanitised (comments stripped, identifiers renamed)"}})
    with open(OUT,'w') as fh:
        for r in rows: fh.write(json.dumps(r)+'\n')
    print(len(rows))
main()
