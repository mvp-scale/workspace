#!/usr/bin/env python3
"""Validate probes/persona/rules_v2 (standard library only). Exit 1 on any failure."""
import csv, os, sys
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
V2 = os.path.join(HERE, 'rules_v2')
V1 = os.path.join(HERE, 'rules')
LEVELS = {0.2, 0.5, 0.8}
POLITICAL = {'econ_orientation', 'cultural_orientation', 'group_identity', 'religiosity'}
fails = []; notes = []
def load(name, d=V2):
    p = os.path.join(d, name)
    if not os.path.exists(p): return []
    with open(p, newline='') as f: return list(csv.DictReader(f))
def check(ok, msg):
    if not ok: fails.append(msg)
def split(s): return [x.strip() for x in (s or '').split(';') if x.strip()]
def words(s): return len((s or '').split())

res = load('resources.csv'); dials = load('dials.csv'); doms = load('domains.csv'); els = load('elements.csv')
decs = load('decisions.csv'); grid = load('grid.csv'); dw = load('decision_weights.csv'); ties = load('dial_ties.csv'); idmap = load('id_map.csv')
layers = {'resource': res, 'dial': dials, 'domain': doms, 'element': els, 'decision': decs}

# counts
exp = {'resource': 26, 'dial': 39, 'domain': 49, 'element': 47, 'decision': 20}
for k, n in exp.items(): check(len(layers[k]) == n, f'{k} count {len(layers[k])} != {n}')
# unique ids
for k, rows in layers.items():
    c = Counter(r['id'] for r in rows)
    check(all(v == 1 for v in c.values()), f'duplicate ids in {k}: {[i for i, v in c.items() if v > 1]}')
# no id across layers
owner = defaultdict(list)
for k, rows in layers.items():
    for r in rows: owner[r['id']].append(k)
shared = {i: l for i, l in owner.items() if len(l) > 1}
check(not shared, f'ids shared across layers: {shared}')
for i in ('health_status', 'debt_burden', 'minerals_materials'):
    check(owner.get(i) == ['element'] if i != 'minerals_materials' else owner.get(i) == ['resource'], f'collision id {i} wrong owner {owner.get(i)}')
notes.append('collisions fixed: health_status=%s debt_burden=%s minerals_materials=%s' % (owner.get('health_status'), owner.get('debt_burden'), owner.get('minerals_materials')))

RES = {r['id'] for r in res}; DIAL = {r['id']: r for r in dials}; TOP = {r['id']: r for r in doms}
EL = {r['id']: r for r in els}; DEC = {r['id'] for r in decs}
# optimism
check('optimism' not in DIAL, "optimism present as a dial row")
check('optimism' in EL and EL['optimism']['kind'] == 'state', 'optimism must be a state')
check([r for r in dials if r['kind'] == 'outcome'] == [], "no outcome-kind dial row expected (outlook is an engine readout, documented in README)")
readme = open(os.path.join(V2, 'README.md')).read() if os.path.exists(os.path.join(V2, 'README.md')) else ''
check('outlook' in readme, 'README must document the outlook readout')
# columns
check(list(dials[0].keys())[:7] == ['id', 'name', 'kind', 'definition', 'half_life_ticks', 'grounding_series', 'status'] and 'resource_id' in dials[0] and 'up_means' in dials[0], 'dials columns')
check(all(r['kind'] in ('trait', 'state', 'derived') for r in els), 'element kinds')
# dials -> resource
for r in dials:
    check(r['resource_id'] in RES, f"dial {r['id']} resource_id {r['resource_id']!r} missing")
    check(bool(r['up_means']), f"dial {r['id']} has no up_means")
# topics
route = {}
for t in doms:
    ds = split(t['dials']); route[t['id']] = ds
    if t['id'] == 'other':
        check(not ds, 'other must have no dials'); continue
    check(1 <= len(ds) <= 3, f"topic {t['id']} has {len(ds)} dials")
    for d in ds: check(d in DIAL, f"topic {t['id']} dangling dial {d}")
    derived = []
    for d in ds:
        r = DIAL.get(d, {}).get('resource_id')
        if r and r not in derived: derived.append(r)
    check(split(t['resources']) == derived, f"topic {t['id']} resources not derived from dials")
check('other' in TOP, "'other' row missing")
reach = {d for ds in route.values() for d in ds}
declared = sorted(d for d, r in DIAL.items() if d not in reach)
undeclared = [d for d in declared if DIAL[d]['kind'] == 'condition']
notes.append('conditions reached by no topic (declared, kind != condition): %s' % declared)
check(not undeclared, f'conditions unreachable and undeclared: {undeclared}')

# grid
cond_in = defaultdict(list)
for g in grid:
    s = float(g['strength']); e = g['element_id']; d = g['dial_id']
    check(e in EL, f'grid dangling element {e}'); check(d in DIAL, f'grid dangling dial {d}')
    check(abs(s) in LEVELS, f'grid {e}<-{d} strength {s} off scale')
    check(g['status'].startswith('guess'), f'grid {e}<-{d} status')
    if g['moderated_by']: check(g['moderated_by'] in EL, f"grid {e} moderated_by dangling {g['moderated_by']}")
    need = abs(s) >= 0.8 or s < 0 or 'contested' in g['status'] or d == 'migration_flow'
    check(not need or g['why'].strip(), f'grid {e}<-{d} needs why')
    check(not g['why'] or words(g['why']) <= 15, f'grid {e}<-{d} why >15 words')
    check(e in EL and EL[e]['kind'] == 'state', f'grid links into non-moving element {e}')
    cond_in[e].append(d)
check(len(grid) == len({(g['element_id'], g['dial_id']) for g in grid}), 'duplicate grid pair')
moving = [e for e, r in EL.items() if r['kind'] == 'state']
for e in moving:
    check(1 <= len(cond_in[e]) <= 4, f'moving state {e} has {len(cond_in[e])} condition links')
# ties
out = Counter()
for t in ties:
    s = float(t['strength']); out[t['from_dial']] += 1
    check(t['from_dial'] in DIAL and t['to_dial'] in DIAL, f"tie dangling {t['from_dial']}->{t['to_dial']}")
    check(abs(s) in LEVELS, 'tie strength off scale'); check(t['why'].strip() and words(t['why']) <= 15, f"tie {t['from_dial']} why")
check(len(ties) <= 12, f'{len(ties)} ties > 12'); check(all(v <= 1 for v in out.values()), 'more than 1 outgoing tie from a condition')
# every condition useful downstream
feeds = {g['dial_id'] for g in grid} | {t['from_dial'] for t in ties}
dead = [d for d, r in DIAL.items() if d not in feeds and r['kind'] == 'condition']
check(not dead, f'conditions feeding no state or tie: {dead}')
# decision weights
inputs = defaultdict(list); per_state = defaultdict(set)
for w in dw:
    s = float(w['weight']); d = w['decision_id']; e = w['element_id']
    check(d in DEC, f'dw dangling decision {d}'); check(e in EL, f'dw dangling element {e}')
    check(abs(s) in LEVELS, f'dw {d}<-{e} off scale'); check(w['status'].startswith('guess'), f'dw {d}<-{e} status')
    need = abs(s) >= 0.8 or s < 0 or 'contested' in w['why'] or e in POLITICAL
    check(not need or w['why'].strip(), f'dw {d}<-{e} needs why')
    check(not w['why'] or words(w['why']) <= 15, f'dw {d}<-{e} why >15 words')
    inputs[d].append(e); per_state[e].add(d)
check(len(dw) == len({(w['decision_id'], w['element_id']) for w in dw}), 'duplicate dw pair')
for d in DEC:
    n = len(inputs[d]); check(4 <= n <= 6, f'decision {d} has {n} inputs (need 4..6)')
for e, ds in per_state.items(): check(len(ds) <= 4, f'state {e} feeds {len(ds)} decisions (>4)')
unlinked = sorted(e for e in EL if e not in per_state)
notes.append('states with no decision link (flagged): %s' % unlinked)
check(not unlinked, f'states with no decision link: {unlinked}')
# fixed elements have no incoming condition links
# totals
tc = sum(len(v) for v in route.values())
total = tc + len(ties) + len(grid) + len(dw)
check(total <= 375, f'total links {total} > 375')
notes.append(f'links: topic->condition {tc}, condition->condition {len(ties)}, condition->state {len(grid)}, state->decision {len(dw)}, total {total}')
# id_map
seen = defaultdict(set)
for m in idmap:
    check(m['action'] in ('keep', 'rename', 'merge', 'split', 'retire', 'new'), f"id_map action {m['action']}")
    seen[m['layer']].add(m['old_id'])
    for n in split(m['new_ids']):
        if n.startswith('outlook'): continue
        check(n in layers.get(m['layer'], []) or any(n == r['id'] for r in layers[m['layer']]), f"id_map {m['old_id']}-> {n} not in v2 {m['layer']}")
v1files = {'dial': 'dials.csv', 'domain': 'domains.csv', 'element': 'elements.csv', 'decision': 'decisions.csv', 'resource': 'resources.csv'}
for layer, fn in v1files.items():
    for r in load(fn, V1): check(r['id'] in seen[layer], f"id_map missing v1 {layer} {r['id']}")
topic_new = {n for m in idmap if m['layer'] == 'domain' for n in split(m['new_ids'])}
check(set(TOP) <= topic_new, f'topics not in id_map: {sorted(set(TOP)-topic_new)}')


# ---- banks: full coverage of v2 ids; every question non-empty and ends with '?' ----
def bank_checks():
    da = load('dial_attributes.csv') + load('dial_attributes_extra.csv')
    conds = {i for i, r in DIAL.items()}
    for d in conds:
        for dr in ('up', 'down'):
            n = sum(1 for r in da if r['dial_id'] == d and r['direction'] == dr)
            check(n >= 2, f'dial_attributes: {d} {dr} has {n} attributes (need >=2)')
    check({r['dial_id'] for r in da} <= conds, 'dial_attributes: unknown dial id')
    for r in da:
        check(r['attribute'].strip() and r['attribute'] != 'todo' and r['definition'].strip(), f"dial_attributes: {r['dial_id']} {r['direction']} blank attribute/definition")
        qs = (r['question_1'], r['question_2'])
        check(all(q.strip().endswith('.') and '?' not in q and len(q.strip()) > 10 for q in qs), f"dial_attributes: {r['dial_id']}/{r['attribute']} must be a statement ending with '.' and no '?'")
        check(qs[0] != qs[1], f"dial_attributes: {r['dial_id']}/{r['attribute']} two questions identical")
    ip = load('impact_phrases.csv'); cond = {i for i, r in DIAL.items() if r['kind'] in ('condition', 'media')}
    check({r['dial_id'] for r in ip} == cond and len(ip) == len(cond), 'impact_phrases: need exactly one row per condition-kind and media-kind dial (a missing row made classify.severity raise KeyError)')
    check(all(r['up'].strip() and r['down'].strip() for r in ip), 'impact_phrases: blank phrase')
    dp = load('decision_phrases.csv')
    check({r['decision_id'] for r in dp} == DEC and len(dp) == len(DEC), 'decision_phrases: need exactly one row per decision')
    check(all(r['up'].strip() and r['down'].strip() for r in dp), 'decision_phrases: blank phrase')
    eq = load('element_questions.csv')
    for e, r in EL.items():
        n = sum(1 for q in eq if q['element_id'] == e)
        check(n == int(r['n_questions_target']), f"element_questions: {e} has {n}, target {r['n_questions_target']}")
    check({q['element_id'] for q in eq} <= set(EL), 'element_questions: unknown element id')
    for q in eq: check(q['question'].strip().endswith('.') and '?' not in q['question'] and len(q['question'].strip()) > 10, f"element_questions: {q['element_id']} must be a statement ending with '.' and no '?'")
    for n in ('impact_modes', 'impact_levels', 'loop'):
        check(open(os.path.join(V2, n + '.csv')).read() == open(os.path.join(V1, n + '.csv')).read(), f'{n}.csv must equal v1')
    dr, er, xr, ks = load('dial_resources.csv'), load('element_resources.csv'), load('decision_resources.csv'), load('decision_stakes.csv')
    check({x['dial_id'] for x in dr} == set(DIAL) and len(dr) == len(DIAL), 'dial_resources: one row per condition')
    for x in dr: check(x['resource_id'] == DIAL[x['dial_id']]['resource_id'] and x['role'] == 'level_of' and x['up_means'] in ('strain', 'build') and x['status'] == 'guess' and x['why'].strip(), f"dial_resources bad row {x['dial_id']}")
    moving = {i for i, r in EL.items() if r['kind'] == 'state'}
    check({x['element_id'] for x in er} == moving, 'element_resources: must cover exactly the moving states')
    for x in er: check(x['resource_id'] in RES and x['weight'] in ('0.2', '0.5', '0.8') and x['up_means'] in ('strain', 'build') and x['status'] == 'guess' and x['why'].strip(), f"element_resources bad row {x}")
    check({x['decision_id'] for x in xr} == DEC, 'decision_resources: every decision needs a row')
    for x in xr: check(x['resource_id'] in RES and x['direction'] in ('draw', 'build') and x['weight'] in ('0.2', '0.5', '0.8') and x['status'] == 'guess' and x['why'].strip(), f"decision_resources bad row {x}")
    check({x['decision_id'] for x in ks} == DEC and len(ks) == len(DEC) and all(1 <= int(x['stakes']) <= 5 and x['status'] == 'guess' and x['why'].strip() for x in ks), 'decision_stakes: one row per decision, stakes 1..5, status guess')
    unreached = sorted(RES - {x['resource_id'] for x in dr + er + xr})
    check(not unreached, f'resources not reached by any bank: {unreached}')
    notes.append(f'banks: attrs {len(da)}, impact {len(ip)}, decision_phrases {len(dp)}, element_questions {len(eq)}, dial_res {len(dr)}, el_res {len(er)}, dec_res {len(xr)}, stakes {len(ks)}')
bank_checks()

print('COUNTS:', {k: len(v) for k, v in layers.items()}, 'grid', len(grid), 'weights', len(dw), 'ties', len(ties), 'id_map', len(idmap))
for n in notes: print('NOTE:', n)
if fails:
    print('FAIL (%d):' % len(fails)); [print('  -', f) for f in fails]; sys.exit(1)
print('ALL CHECKS PASSED')
