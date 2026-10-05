import json, time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import offline as O
from news_data import H, Q, TYPE_Q, DIALS
KEYS = [(d, s, i) for d in DIALS for s in (1, -1) for i in range(4)]
def ask(item):
    kind, text, exp = item
    qs = {f"{d}|{s}|{i}": {"type": "noul", "instructions": Q[(d, s)][i]} for d, s, i in KEYS}
    qs.update({f"type|{k}": {"type": "noul", "instructions": v} for k, v in TYPE_Q.items()})
    names = list(qs); out = {}; t0 = time.time()
    for j in range(0, len(names), 20):
        a = O.call("News item:\n" + text, {k: qs[k] for k in names[j:j + 20]}); out.update({k: a[k]["noul"] for k in a})
    return out, time.time() - t0
t0 = time.time()
with ThreadPoolExecutor(2) as ex: res = list(ex.map(ask, H))
wall = time.time() - t0; per = sum(r[1] for r in res) / len(res)
json.dump([{"kind": h[0], "text": h[1], "exp": h[2], "p": r[0]} for h, r in zip(H, res)], open("/workspace/data/persona-lab/news.json", "w"))
vote = lambda p: 1 if p >= .65 else (-1 if p <= .35 else 0)
def present(P, d, s):
    v = [vote(P[f"{d}|{s}|{i}"]) for i in range(4)]; return sum(x == 1 for x in v) >= 3 and sum(x == -1 for x in v) <= 1
def moves(P, rule="group"):
    if P["type|happened"] < .5: return {}
    m = {}
    for d in DIALS:
        if rule == "group": up, dn = present(P, d, 1), present(P, d, -1)
        else: up, dn = P[f"{d}|1|0"] >= .5, P[f"{d}|-1|0"] >= .5
        if up != dn: m[d] = 1 if up else -1
    return m
K = defaultdict(list)
for (kind, text, exp), (P, _) in zip(H, res): K[kind].append((exp, P, moves(P), moves(P, "single")))
d_ok = d_wrong = 0; per_dial = defaultdict(lambda: [0, 0])
for exp, P, m, _ in K["dial"]:
    (dial, s), = exp.items(); ok = m.get(dial) == s; d_ok += ok; d_wrong += (m.get(dial) == -s); per_dial[dial][0] += ok; per_dial[dial][1] += 1
n = len(K["dial"])
fire = lambda rows, i: sum(1 for r in rows if r[i]) / len(rows)
irr = fire(K["irrelevant"], 2); of = fire(K["opinion"] + K["forecast"], 2)
amb = sum(1 for exp, P, m, _ in K["ambiguous"] if list(exp)[0] not in m) / len(K["ambiguous"])
found = tot = extra = 0
for exp, P, m, _ in K["multi"]:
    tot += len(exp); found += sum(m.get(d) == s for d, s in exp.items()); extra += len([d for d in m if d not in exp])
g30 = K["irrelevant"] + K["opinion"] + K["forecast"]; grp, sng = fire(g30, 2), fire(g30, 3)
notp = sum(1 for r in K["opinion"] + K["forecast"] if r[1]["type|happened"] < .5) / 20
print(f"N1 directed: right dial+direction {d_ok}/{n} = {d_ok/n:.0%} (target >= 80%); wrong direction {d_wrong}/{n} = {d_wrong/n:.0%} (<= 5%)")
print("   per dial (right/total):", {d: f"{a}/{b}" for d, (a, b) in per_dial.items()})
print(f"N2 irrelevant: a dial moved in {irr:.0%} of 20 (<= 10%)")
print(f"N3 opinion/forecast: a dial moved in {of:.0%} of 20 (<= 20%); flagged 'not something that happened' in {notp:.0%}")
print(f"N4 ambiguous: contested dial did not move in {amb:.0%} of 10 (>= 60%)")
print(f"N5 multi-dial: found {found}/{tot} = {found/tot:.0%} of expected (>= 60%); extra dials per headline {extra/14:.2f} (<= 1)")
print(f"N6 time per headline: {per:.2f} s sequential for 75 questions (<= 0.5 s); wall {wall:.0f}s for 100 headlines on 2 threads")
print(f"N7 false triggers on 30 irrelevant/opinion/forecast headlines: 4-question group rule {grp:.0%} vs single-question rule {sng:.0%} (group must be lower by >= 5 points)")
print("\nmisses (directed):")
for (kind, text, exp), (P, _) in zip(H, res):
    if kind == "dial":
        (dial, s), = exp.items(); m = moves(P)
        if m.get(dial) != s: print("  ", text[:70], "| expected", dial, s, "| got", m, "| happened P", round(P["type|happened"], 2))
