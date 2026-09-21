#!/usr/bin/env python3
"""Build checklist_contractnli.jsonl from ContractNLI test+dev (seeded, deterministic)."""
import json, random, re, collections
SRC = '/workspace/data/sources/contractnli/contract-nli/'
OUT = '/workspace/probes/v2/'
SEED, PER_LABEL, MAXC, TARGET = 20260921, 24, 1450, 1200
rng = random.Random(SEED)
lab = json.load(open(SRC + 'test.json'))['labels']
hyps = {k: {"short_description": v["short_description"], "hypothesis": v["hypothesis"]} for k, v in sorted(lab.items(), key=lambda kv: int(kv[0].split('-')[1]))}
json.dump(hyps, open(OUT + 'checklist_hypotheses.json', 'w'), indent=1, ensure_ascii=False)
LAB = {'Entailment': 'entailed', 'Contradiction': 'contradicted', 'NotMentioned': 'not_mentioned'}
norm = lambda s: re.sub(r'\s+', ' ', s).strip()

def window(doc, lo, hi):
    """Grow contiguous span range [lo,hi] with neighbouring sentences up to TARGET chars. Returns text, (lo,hi)."""
    sp = doc['spans']; T = doc['text']
    ln = lambda a, b: norm(T[sp[a][0]:sp[b][1]])
    left = True
    while True:
        moved = False
        for side in (('l', 'r') if left else ('r', 'l')):
            a, b = (lo - 1, hi) if side == 'l' else (lo, hi + 1)
            if a >= 0 and b < len(sp) and len(ln(a, b)) <= TARGET:
                lo, hi = a, b; moved = True; break
        left = not left
        if not moved: break
    return ln(lo, hi), (lo, hi)

def cands():
    out = {'entailed': [], 'contradicted': [], 'not_mentioned': []}
    for split in ('test', 'dev'):
        for doc in json.load(open(SRC + split + '.json'))['documents']:
            sp = doc['spans']; T = doc['text']
            ann = doc['annotation_sets'][0]['annotations']
            for h, a in ann.items():
                l = LAB[a['choice']]
                if l != 'not_mentioned':
                    ev = sorted(a['spans'])
                    if len(norm(T[sp[ev[0]][0]:sp[ev[-1]][1]])) > 1300: continue  # all evidence must fit
                    lo, hi = ev[0], ev[-1]
                    tgt = None
                else:
                    # window centred on annotated evidence for ANOTHER hypothesis (topical but not evidence for h)
                    others = [s for h2, a2 in ann.items() if h2 != h and a2['spans'] for s in a2['spans']]
                    if not others: continue
                    c = rng.choice(sorted(others)); lo = hi = c
                    if len(norm(T[sp[c][0]:sp[c][1]])) > 1300: continue
                text, (a0, b0) = window(doc, lo, hi)
                if len(text) > MAXC or len(text) < 150: continue
                out[l].append(dict(doc=doc, h=h, text=text, lo=a0, hi=b0, split=split, ev=a['spans']))
    return out

C = cands()
rows = []
for l in ('entailed', 'contradicted', 'not_mentioned'):
    pool = C[l]; rng.shuffle(pool)
    byh = collections.defaultdict(list)
    for c in pool: byh[c['h']].append(c)
    hs = sorted(byh); rng.shuffle(hs)
    perdoc = collections.Counter(); chosen = []
    while len(chosen) < PER_LABEL and any(byh.values()):
        for h in hs:
            while byh[h]:
                c = byh[h].pop()
                if perdoc[c['doc']['id']] < 2:
                    perdoc[c['doc']['id']] += 1; chosen.append(c); break
            if len(chosen) >= PER_LABEL: break
    for c in chosen:
        h = hyps[c['h']]
        rows.append({
            "id": f"cnli-{c['split']}-{c['doc']['id']}-{c['h']}",
            "family": "checklist_contractnli",
            "state": c['text'],
            "question": {"type": "choice",
                         "instructions": "Does this contract text say the following? " + h['hypothesis'] + " Answer entailed if the text supports it, contradicted if the text says the opposite, or not_mentioned if the text does not address it.",
                         "criteria": {"entailed": "The contract text supports the statement.",
                                      "contradicted": "The contract text says something that conflicts with the statement.",
                                      "not_mentioned": "The contract text neither supports nor contradicts the statement."}},
            "labels": ["entailed", "contradicted", "not_mentioned"],
            "expected": l,
            "split": "public", "group": None,
            "provenance": {"exclude_reason": None, "source": "ContractNLI (Koreeda & Manning 2021)",
                           "url": "https://stanfordnlp.github.io/contract-nli/", "license": "CC BY 4.0",
                           "retrieved": "2026-09-21", "source_id": f"{c['split']}/doc{c['doc']['id']}/{c['h']}",
                           "notes": f"hypothesis {c['h']} ({h['short_description']}); file {c['doc']['file_name']}; window = spans {c['lo']}-{c['hi']} of document (whitespace-collapsed); evidence spans {c['ev']}"}})
rng.shuffle(rows)
with open(OUT + 'checklist_contractnli.jsonl', 'w') as f:
    for r in rows: f.write(json.dumps(r, ensure_ascii=False) + '\n')
print(len(rows), collections.Counter(r['expected'] for r in rows))
print(collections.Counter((r['expected'], r['provenance']['notes'].split(' ')[1]) for r in rows))
print('hyps', len({r['provenance']['notes'].split(' ')[1] for r in rows}), 'maxlen', max(len(r['state']) for r in rows))
