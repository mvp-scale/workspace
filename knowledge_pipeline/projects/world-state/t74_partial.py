"""T74: partial-triple matching across same-event article pairs, with a chance control. Reads the T73 files (no model run). Unjudged match rates.
    python3 t74_partial.py -> runs/pulse/t74_partial.json"""
import json, re, random, os
exec(open("t73_match.py").read().split("res = {}")[0])  # reuses canon(), ekey(), the loaded R (pairs) and EN (entities)
def elems(t):
    sk, sm = ekey(t["s"], t["s_key"], t["sent_text"]); ok, om = ekey(t["o"], t["o_key"], t["sent_text"])
    return {"s": {("T", t["s_key"])} | ({("E", sk)} if sm else set()), "p": {t["p_lemma"]}, "o": {("T", t["o_key"])} | ({("E", ok)} if om else set())}
def match(a, b):  # which elements agree (text key equal, or same entity)
    return {"s": bool(a["s"] & b["s"]), "p": bool(a["p"] & b["p"]), "o": bool(a["o"] & b["o"])}
def rates(pairs_A, pairs_B):
    n = 0; c = {"p+s": 0, "p+o": 0, "s+o": 0, "any2": 0, "all3": 0}
    for A, B in zip(pairs_A, pairs_B):
        EB = [elems(t) for t in B]
        for t in A:
            ea = elems(t); n += 1; ms = [match(ea, eb) for eb in EB]
            c["p+s"] += any(m["p"] and m["s"] for m in ms); c["p+o"] += any(m["p"] and m["o"] for m in ms); c["s+o"] += any(m["s"] and m["o"] for m in ms)
            c["any2"] += any(sum(m.values()) >= 2 for m in ms); c["all3"] += any(all(m.values()) for m in ms)
    return {"triples": n, **{k: round(v / max(1, n), 4) for k, v in c.items()}}
res = {}; random.seed(7)
for g in ("copy", "independent"):
    G = [r for r in R if r["group"] == g]; res[g] = {"pairs": len(G), "real": rates([r["A"] for r in G], [r["B"] for r in G])}
    other = [r["B"] for r in G]; random.shuffle(other)
    for k in range(len(other)):  # a B that is not this pair's own
        if other[k] is G[k]["B"]: other[k] = other[(k + 1) % len(other)]
    res[g]["control_random_B_same_group"] = rates([r["A"] for r in G], other)
    res[g]["excess_any2"] = round(res[g]["real"]["any2"] - res[g]["control_random_B_same_group"]["any2"], 4)
res["note"] = "Match = share of A-side triples with at least one B-side triple agreeing on the named elements. Element agreement: equal text key or the same GLiNER entity (predicate: equal lemma). Control: B taken from a different random pair of the same group. Unjudged."
json.dump(res, open(os.environ.get("T73DIR", "runs/pulse") + "/t74_partial.json", "w"), indent=1); print(json.dumps(res, indent=1))
