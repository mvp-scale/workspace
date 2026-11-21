"""props_mirror: Python property tests for the two properties proved in lean/Props.lean (P1, P4; playbook 00 section 11; ledger L2868), run against consolidate.py (read-only import).
    python3 props_mirror.py [--n 1500] [--seed 7]
P1 evidence-set union (consolidate.merge_assertions, finish): replaying a store changes nothing; store order does not change the merged key sets or the output (the per-fragment `source` field aside, it names the first store); no duplicate (article, sentence) key.
P4 is_a insertion (consolidate.IsA.add): a refused 'cycle' is exactly a parent that reaches the child; the graph stays acyclic after every add; the oracle is not vacuous (a mutant without the walk is caught).
Prints one vector line per property; exit 1 if any property fails."""
import sys, random, itertools, copy, json
import consolidate as C
def arg(k, d):
    return type(d)(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
N = arg("--n", 1500); SEED = arg("--seed", 7); R = random.Random(SEED)
# ---------- P1 ----------
ARTS = ["a%d" % i for i in range(6)]; PUBS = ["p%d" % i for i in range(4)]
def evid(art, sent):   # content is a function of the key (art, sent): the same fragment seen in two stores is the same fragment
    return {"art": art, "pub": PUBS[hash_(art) % 4], "sent": sent, "spans": [[0, 1]], "attrs": {"polarity": "pos", "direction": None}}
def hash_(s): return sum(map(ord, s))
def rand_store(name):
    asr = {}
    for i in range(R.randint(0, 4)):
        key = "e%d | rel | e%d" % (R.randint(0, 3), R.randint(0, 3))
        ev = [evid(R.choice(ARTS), R.choice(["s0", "s1", None])) for _ in range(R.randint(1, 4))]   # repeats inside one record are allowed too
        asr["%s-%d" % (name, i)] = {"kind": "claim", "key": key, "subj": "x", "pred": "rel", "obj": "y", "evid": ev}
    return {"file": name, "asr": asr, "arts": {}}
class ST_:
    def day(self, a): return "2026-01-0%d" % (1 + hash_(a) % 5)
    def strength(self, ap):
        st = {a for a, _ in ap}; pubs = sorted({p for _, p in ap} - {""}); return len(pubs), len(st), pubs
def run(stores):
    ST = ST_(); return C.finish(C.merge_assertions(stores, ST), ST)
def strip(out):   # drop the field that names the first store that supplied a fragment
    o = copy.deepcopy(out)
    for e in o:
        for f in e["fragments"]: f.pop("source", None)
    return C.canon(o)
def keyset(out): return {(e["id"], f["art"], f["sent"] or "") for e in out for f in e["fragments"]}
def p1():
    c = {"replay": 0, "comm": 0, "perm3": 0, "split_replay": 0, "nodup": 0, "idem_full": 0}; bad = []
    for t in range(N):
        A, B, D = rand_store("A"), rand_store("B"), rand_store("D")
        base = run([A, B])
        if run([A, A]) == run([A]): c["idem_full"] += 1
        else: bad.append(("idem_full", t))
        if run([A, B, B]) == base and run([A, B, A, B]) == base: c["replay"] += 1   # same output incl. source: a replay only repeats keys already there
        else: bad.append(("replay", t))
        if strip(run([A, B])) == strip(run([B, A])) and keyset(run([A, B])) == keyset(run([B, A])): c["comm"] += 1
        else: bad.append(("comm", t))
        outs = {strip(run(list(p))) for p in itertools.permutations([A, B, D])}
        if len(outs) == 1: c["perm3"] += 1
        else: bad.append(("perm3", t))
        if run([A, B, B]) == base: c["split_replay"] += 1
        else: bad.append(("split_replay", t))
        per = [[(f["art"], f["sent"]) for f in e["fragments"]] for e in base]
        if all(len(set(x)) == len(x) for x in per): c["nodup"] += 1
        else: bad.append(("nodup", t))
    return c, bad
# ---------- P4 ----------
def reach(par, x, y):   # independent oracle: does x reach y going up (x == y counts)
    seen = set()
    while x is not None and x not in seen:
        if x == y: return True
        seen.add(x); x = par.get(x)
    return False
def has_cycle(par):
    for n in par:
        seen = set(); x = par.get(n)
        while x is not None:
            if x == n: return True
            if x in seen: break
            seen.add(x); x = par.get(x)
    return False
class NoWalk(C.IsA):   # mutant: the cycle walk removed
    def add(self, child, parent):
        if parent is not None and parent not in self.par: self.refused.append((child, parent, "unknown parent")); return False
        self.par[child] = parent; return True
def p4():
    c = {"adds": 0, "accepted": 0, "refused_cycle": 0, "refused_other": 0, "acyclic_after_each": 0, "cycle_iff_reach": 0, "oracle_catches_mutant": 0, "graphs": 0}; bad = []
    for t in range(N):
        iptc = {"i0": None, "i1": "i0", "i2": "i0", "i3": "i1", "i4": None}
        g = C.IsA(iptc); m = NoWalk(iptc); names = list(iptc) + ["ours:%d" % i for i in range(6)]; c["graphs"] += 1
        for _ in range(R.randint(4, 25)):
            ch, pa = R.choice(names), R.choice(names + [None])
            before = dict(g.par); n0 = len(g.refused); ok = g.add(ch, pa); c["adds"] += 1
            if not ok and g.refused[-1][2] == "cycle":
                c["refused_cycle"] += 1
                good = pa is not None and reach(before, pa, ch)
                if g.par != before: good = False   # a refusal leaves the graph unchanged
            elif not ok: c["refused_other"] += 1; good = g.par == before
            else:
                c["accepted"] += 1; good = not (pa is not None and reach(before, pa, ch))
            if good: c["cycle_iff_reach"] += 1
            else: bad.append(("cycle_iff_reach", t, ch, pa))
            if g.acyclic() and not has_cycle(g.par): c["acyclic_after_each"] += 1
            else: bad.append(("acyclic", t, ch, pa))
            m.add(ch, pa)
        if has_cycle(m.par) and not m.acyclic(): c["oracle_catches_mutant"] += 1   # graphs where the mutant closed a cycle and IsA.acyclic says so
        elif has_cycle(m.par): bad.append(("oracle_misses_mutant", t))
    return c, bad
if __name__ == "__main__":
    c1, b1 = p1(); c4, b4 = p4()
    print("P1 evidence-set union  cases=%d seed=%d  %s  failures=%d" % (N, SEED, json.dumps(c1), len(b1)))
    print("P4 is_a acyclic        cases=%d seed=%d  %s  failures=%d" % (N, SEED, json.dumps(c4), len(b4)))
    for b in (b1 + b4)[:10]: print("FAIL", b)
    sys.exit(1 if b1 or b4 else 0)
