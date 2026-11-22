"""knowledge_yield: yield metrics for one window, from the consolidated output (knowledge step, owner yes L2936). Read-only, no model, no hosted call, CPU only, no clock, no random: same input, same numbers. PROVISIONAL: the numbers are shown with their definition, never used as a gate (L2901).
    python3 knowledge_yield.py <consolidated.json> [--contested <n>] [--json]
    import knowledge_yield as KY; KY.yield_block(body, contested_n=None)

Definitions (articles = len(body["observations"]), never the store size):
  pct_reinforced   : assertion edges with strength >= 2 (>= 2 independent publishers: one publisher per story root, copies count once) / assertion edges * 100
  contested_per_100: contested edges / articles * 100. Contested = the count passed in (contradiction edges from the slow clock), else body["contested"] (list or {"n"}) when present, else the fallback: assertion edges whose fragments carry both a positive and a negative polarity (basis says which)
  bridging         : capability nodes used by >= 2 Areas (node areas_n, else len(areas))
  answerable       : named targets (subject or object entity, upper-case-free label of 3+ letters, not iso) that carry >= 1 assertion edge with strength >= 2, i.e. a question about them gets a known statement from educate.py
Output keys: pct_reinforced, contested_per_100, bridging, answerable (the four of KNOWLEDGE_SCHEMA.md) plus counts, basis, provisional."""
import os, sys, json


def _assertions(body):
    return [e for e in body.get("edges", []) if e.get("kind") == "assertion"]


def _caps(body):
    c = (body.get("concepts") or {}).get("capabilities") or body.get("capabilities") or {}
    return c.get("nodes", []) if isinstance(c, dict) else c


def _contested(body, A, contested_n):
    if contested_n is not None: return int(contested_n), "contradiction edges passed in"
    c = body.get("contested")
    if isinstance(c, dict) and "n" in c: return int(c["n"]), "body contested.n"
    if isinstance(c, list): return len(c), "body contested list"
    both = [e for e in A if len({f.get("polarity") for f in e.get("fragments", []) if f.get("polarity")}) > 1]
    return len(both), "fallback: edges with both positive and negative fragments"


def yield_block(body, contested_n=None):
    A = _assertions(body); art = len(body.get("observations") or [])
    reinf = [e for e in A if e.get("strength", 0) >= 2]
    cn, basis = _contested(body, A, contested_n)
    bridging = [n["id"] for n in _caps(body) if (n.get("areas_n") if n.get("areas_n") is not None else len(n.get("areas") or [])) >= 2]
    ans = set()
    for e in reinf:
        for x in (e.get("subj"), e.get("obj")):
            if not x or x.startswith("iso:") or x.startswith("country:"): continue
            if len(x.split(":", 1)[-1]) >= 3: ans.add(x)
    r = lambda v: round(v, 4)
    return {"pct_reinforced": r(100.0 * len(reinf) / len(A)) if A else 0.0,
            "contested_per_100": r(100.0 * cn / art) if art else 0.0,
            "bridging": len(bridging), "answerable": len(ans),
            "counts": {"articles": art, "assertions": len(A), "reinforced": len(reinf), "contested": cn, "bridging_ids": sorted(bridging)},
            "basis": {"articles": "len(observations)", "contested": basis, "reinforced": "strength >= 2 independent publishers", "answerable": "named entities with a known (strength >= 2) edge"},
            "provisional": True}


def main(a):
    if not a or a[0].startswith("--"): print(__doc__); return
    body = json.load(open(a[0], encoding="utf-8"))
    cn = int(a[a.index("--contested") + 1]) if "--contested" in a else None
    y = yield_block(body, cn)
    if "--json" in a: print(json.dumps(y, sort_keys=True, indent=1)); return
    c = y["counts"]
    print("articles %d | assertions %d | reinforced %d (%.2f%%) | contested %d (%.2f per 100 articles; %s) | bridging %d | answerable %d  [PROVISIONAL]" % (c["articles"], c["assertions"], c["reinforced"], y["pct_reinforced"], c["contested"], y["contested_per_100"], y["basis"]["contested"], y["bridging"], y["answerable"]))


if __name__ == "__main__": main(sys.argv[1:])
