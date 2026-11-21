"""MN-DS gold -> IPTC codes (plan v2 step 1, ledger L2730). MN-DS gold labels are names; scoring must compare codes, never names.
Level 1: exact current label, plus IPTC top concepts renamed with the code kept (politics -> medtop:11000000 'politics and government', modified 2025-03-31; religion and belief -> medtop:12000000 'religion', modified 2021-12-21).
Level 2: exact current or retired label whose top concept equals the item's level-1 code; anything else is 'unmatched' and is reported, never hand-mapped.
Build the table: python3 mnds_codes.py  -> specs/mnds_name_to_code_v1.json"""
import json, os, collections
SRC = "/workspace/data/ontology_src/iptc/medtop.json"; MN = "/workspace/data/anchors/mn_ds"; OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "specs/mnds_name_to_code_v1.json")
RENAMED_L1 = {"politics": "medtop:11000000", "religion and belief": "medtop:12000000"}
def build():
    d = json.load(open(SRC)); C = d["conceptSet"]; node = {c["qcode"]: c for c in C}
    par = {c["qcode"]: (c.get("broader") or [None])[0] for c in C}
    par = {k: ("medtop:" + v.rsplit("/", 1)[1] if v and "/" in v else v) for k, v in par.items()}
    def top(q):
        seen = 0
        while par.get(q) and seen < 10: q = par[q]; seen += 1
        return q
    l1 = {c["prefLabel"]["en-GB"].lower(): c["qcode"] for c in C if not par.get(c["qcode"]) and not c.get("retired")}
    l1.update(RENAMED_L1)
    by = collections.defaultdict(list)
    for c in C: by[c["prefLabel"]["en-GB"].lower()].append(c["qcode"])
    l2 = {}; names = set()
    for f in ("gold_T28_clean.json", "gold_fresh2.json", "gold_fresh.json", "gold_T28.json", "gold_T28b.json"):
        p = os.path.join(MN, f)
        if os.path.exists(p):
            for v in json.load(open(p)).values():
                if v.get("l2"): names.add((v["l1"].lower(), v["l2"].lower()))
    for a, b in sorted(names):
        t = l1.get(a); cand = [q for q in by.get(b, []) if t and top(q) == t]
        cur = [q for q in cand if not node[q].get("retired")]
        l2[a + " | " + b] = {"code": (cur or cand or [None])[0], "status": "current" if cur else "retired" if cand else "unmatched"}
    out = {"version": "mnds_name_to_code_v1", "iptc_release": d.get("dateReleased"), "rules": __doc__.split("\n")[1:4], "l1": l1, "l2": l2,
           "l2_counts": dict(collections.Counter(v["status"] for v in l2.values()))}
    json.dump(out, open(OUT, "w"), indent=1); return out
_T = None
def table():
    global _T
    if _T is None: _T = json.load(open(OUT)) if os.path.exists(OUT) else build()
    return _T
def gold_codes(g):
    """g = MN-DS gold entry {'l1','l2'} -> (l1_code, l2_code or None, l2_status)."""
    T = table(); a = g["l1"].lower(); c1 = T["l1"].get(a); e = T["l2"].get(a + " | " + (g.get("l2") or "").lower(), {})
    return c1, e.get("code"), e.get("status", "unmatched")
if __name__ == "__main__":
    o = build(); print(o["version"], o["iptc_release"], len(o["l1"]), "l1 names;", o["l2_counts"])
