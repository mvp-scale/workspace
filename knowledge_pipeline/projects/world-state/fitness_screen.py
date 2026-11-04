"""T20 Field Fitness Screen v1. For each Pulse field: do independent labellers agree enough that a small model can learn it?
Voters (same spec ws-v2-frozen, 400 items): Sonnet r1 (p7b), Sonnet r2 (pulse/selfcons), Haiku r1 (p7), Haiku r2 (pulse/selfcons_haiku).
Third system on presence: local Clef (runs/clef_vote.jsonl). Traits: runs/pulse/traits_pilot (4 raters, 150 items). Stdlib only.
Thresholds are published heuristics (Krippendorff alpha 0.8 / 0.667), not proof."""
import json, glob, math, itertools, collections
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
LV = ["minor", "notable", "major", "severe", "extreme"]
ids = json.load(open("runs/pulse/selfcons/ids.json"))
def load(pats):
    d = {}
    for p in pats:
        for f in glob.glob(p):
            for r in J(f): d[r["item_id"]] = r["label"]
    return d
V = {"sonnet_1": load(["runs/p7b/*/labels.jsonl"]), "sonnet_2": load(["runs/pulse/selfcons/labels.jsonl"]),
     "haiku_1": load(["runs/p7/*/labels.jsonl"]), "haiku_2": load(["runs/pulse/selfcons_haiku/labels.jsonl"])}
names = list(V); ids = [i for i in ids if all(i in V[n] for n in names)]

def alpha(units, interval=False):
    """Krippendorff alpha. units: list of lists of values (missing already dropped). nominal by default."""
    o = collections.defaultdict(float); n = 0
    for u in units:
        m = len(u)
        if m < 2: continue
        for a, b in itertools.permutations(range(m), 2): o[(u[a], u[b])] += 1 / (m - 1)
        n += m
    if n < 2: return None
    nc = collections.defaultdict(float)
    for (a, b), v in o.items(): nc[a] += v
    d = (lambda a, b: (a - b) ** 2) if interval else (lambda a, b: 0 if a == b else 1)
    Do = sum(v * d(a, b) for (a, b), v in o.items()) / n
    De = sum(nc[a] * nc[b] * d(a, b) for a in nc for b in nc) / (n * (n - 1))
    return None if De == 0 else round(1 - Do / De, 3)

def status(u):
    c = collections.Counter(u).most_common(); top = c[0][1]
    return "unanimous" if top == len(u) else ("majority" if top > len(u) / 2 else "split")

def screen(units_by_item, interval=False, extra=None):
    """units_by_item: {item: {voter: value}} with only voters that gave a value."""
    U = {i: u for i, u in units_by_item.items() if len(u) >= 2}
    al = alpha([list(u.values()) for u in U.values()], interval)
    st = collections.Counter(status(list(u.values())) for u in U.values()); n = len(U)
    pair = {}
    for a, b in itertools.combinations(names, 2):
        xs = [u[a] == u[b] for u in U.values() if a in u and b in u]
        if xs: pair[a + "~" + b] = round(sum(xs) / len(xs), 3)
    selfc = [pair[k] for k in ("sonnet_1~sonnet_2", "haiku_1~haiku_2") if k in pair]
    cross = [pair[k] for k in pair if k.split("~")[0].split("_")[0] != k.split("~")[1].split("_")[0]]
    loo = {}
    for v in names:
        hit = []
        for u in U.values():
            if v not in u: continue
            others = [x for k, x in u.items() if k != v]
            if len(others) < 2: continue
            c = collections.Counter(others).most_common()
            if len(c) > 1 and c[0][1] == c[1][1]: continue
            hit.append(c[0][0] == u[v])
        loo[v] = round(sum(hit) / len(hit), 3) if hit else None
    guess = round(collections.Counter(collections.Counter(u.values()).most_common(1)[0][0] for u in U.values()).most_common(1)[0][1] / n, 3)
    r = {"n": n, "alpha": al, "unanimous": round(st["unanimous"] / n, 3), "majority": round(st["majority"] / n, 3), "split": round(st["split"] / n, 3),
         "self": round(sum(selfc) / len(selfc), 3) if selfc else None, "cross": round(sum(cross) / len(cross), 3) if cross else None,
         "pair": pair, "voter_vs_others": loo, "consensus_guess": guess}
    r["kind"] = None if r["cross"] is None else ("surface" if r["cross"] >= 0.9 else "mixed" if r["cross"] >= 0.75 else "implied")
    r["verdict"] = "Wait" if n < 30 or al is None else ("Build" if al >= 0.8 else "Rework" if al >= 0.4 else "Don't build")
    if extra: r.update(extra)
    return r


def class_agree(units):
    """Agreement per answer (positive-specific agreement over all voter pairs: 2*both/(a+b)); shows WHICH answers the voters disagree on."""
    cl = collections.Counter(x for u in units.values() for x in u.values()); out = {}
    for c in cl:
        b = t = 0
        for u in units.values():
            for x, y in itertools.combinations(list(u.values()), 2): b += (x == c and y == c); t += (x == c) + (y == c)
        out[str(c)] = {"agree": round(2 * b / t, 3) if t else None, "n": cl[c]}
    return out
F = {}
F["story_type"] = screen({i: {n: V[n][i]["story_type"] for n in names} for i in ids})
F["story_type"]["classes"] = class_agree({i: {n: V[n][i]["story_type"] for n in names} for i in ids})
F["topic"] = screen({i: {n: V[n][i]["topic"] for n in names} for i in ids})
F["condition_present"] = screen({i: {n: bool(V[n][i]["conditions"]) for n in names} for i in ids})
posn = {i: {n: V[n][i]["conditions"] for n in names if V[n][i]["conditions"]} for i in ids}
F["condition_present"]["classes"] = class_agree({i: {n: bool(V[n][i]["conditions"]) for n in names} for i in ids})
F["which_condition"] = screen({i: {n: c[0]["condition"] for n, c in u.items()} for i, u in posn.items()})
dirs, sizes = {}, {}
for i, u in posn.items():
    if len(u) < 2: continue
    top = collections.Counter(c[0]["condition"] for c in u.values()).most_common(1)[0][0]
    d = {}; s = {}
    for n, cs in u.items():
        m = [c for c in cs if c["condition"] == top]
        if m: d[n] = m[0]["direction"]; s[n] = LV.index(m[0]["level"])
    dirs[i] = d; sizes[i] = s
F["direction"] = screen(dirs)
F["direction"]["classes"] = class_agree(dirs); F["which_condition"]["classes"] = class_agree({i: {n: c[0]["condition"] for n, c in u.items()} for i, u in posn.items()}); F["topic"]["classes"] = class_agree({i: {n: V[n][i]["topic"] for n in names} for i in ids})
F["size"] = screen(sizes, interval=True); F["size"]["classes"] = class_agree({i: {n: LV[v] for n, v in u.items()} for i, u in sizes.items()})
within1 = [abs(a - b) <= 1 for u in sizes.values() for a, b in itertools.combinations(u.values(), 2)]
F["size"]["within_one"] = round(sum(within1) / len(within1), 3)

# third system on presence: local Clef (differently worded question: is the main subject a change in a real-world condition?)
cv = J("runs/clef_vote.jsonl"); cl = [(int(r["raw"]["noul"] >= 0.5), r["haiku"], r["sonnet"]) for r in cv]
ag = lambda a, b: round(sum(x[a] == x[b] for x in cl) / len(cl), 3)
st3 = collections.Counter("unanimous" if len(set(x)) == 1 else "majority" for x in cl)
F["condition_present"]["clef"] = {"n": len(cl), "clef~sonnet": ag(0, 2), "clef~haiku": ag(0, 1), "haiku~sonnet": ag(1, 2),
    "unanimous3": round(st3["unanimous"] / len(cl), 3), "note": "Clef asked a different wording (main subject is a change), threshold 0.5"}

# traits: 4 raters x 150 items x 51 questions
T = {n: {r["item_id"]: r["label"] for r in J(f"runs/pulse/traits_pilot/{n}/labels.jsonl")} for n in ("sonnet_r1", "sonnet_r2", "haiku_r1", "haiku_r2")}
tids = [i for i in T["sonnet_r1"] if all(i in T[n] for n in T)]; grp = json.load(open("runs/pulse/traits_pilot_result.json"))["questions"]
tq = {}
for q in grp:
    U = {}
    for i in tids:
        u = {n: (T[n][i][q] != "not at all") for n in T if T[n][i].get(q) not in (None, "cannot tell")}
        if len(u) >= 2: U[i] = u
    if len(U) < 30: tq[q] = {"verdict": "Wait", "n": len(U), "group": grp[q]["group"]}; continue
    al = alpha([list(u.values()) for u in U.values()]); pos = sum(any(u.values()) for u in U.values()) / len(U)
    cr = [u["sonnet_r1"] == u["haiku_r1"] for u in U.values() if "sonnet_r1" in u and "haiku_r1" in u]
    tq[q] = {"group": grp[q]["group"], "n": len(U), "alpha": al, "present_share": round(pos, 3), "cross": round(sum(cr) / len(cr), 3) if cr else None,
             "verdict": "Don't build" if al is None else ("Build" if al >= 0.8 else "Rework" if al >= 0.4 else "Don't build")}
    if pos < 0.05: tq[q]["verdict"] = "Wait"; tq[q]["why"] = "present in under 5% of items"
F["traits"] = {"n_questions": len(tq), "counts": dict(collections.Counter(v["verdict"] for v in tq.values())), "questions": tq}
json.dump({"voters": names, "n_items": len(ids), "fields": F}, open("runs/pulse/fitness_screen_v1.json", "w"), indent=1)
print("items", len(ids))
for k, v in F.items():
    if k == "traits": print("traits", v["counts"]); continue
    print(f"{k:18} n={v['n']:4} alpha={v['alpha']} self={v['self']} cross={v['cross']} unan={v['unanimous']} split={v['split']} guess={v['consensus_guess']} {v['kind']} -> {v['verdict']}")
print(F["condition_present"]["clef"]); print("size within1", F["size"]["within_one"])
