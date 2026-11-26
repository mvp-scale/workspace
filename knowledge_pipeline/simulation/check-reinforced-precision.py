"""check-reinforced-precision (T158 fix r2): HEURISTIC precision of reinforced edges (strength >= 2), automatic, no human labels, no model.
Per staged area (c1, mix): 40 reinforced edges sampled with a fixed seed (random.Random(158), sorted edge ids; all of them when fewer than 40). An edge is FLAGGED as a probably wrong merge when
  (a) its slot members' subjects resolve to different identity ids (member keys 'subject | predicate | object'; identity id = the subject id as stored; a country name typed to iso:XX at g4 is one id), or
  (b) subject == object (a self-loop: 'houthis accuse houthis'), or
  (c) no two of its fragments' sentences share a content token (stopwords, the verb words and the 'title #' prefix removed): the fragments are about different things.
This is a heuristic, not a truth label: it misses a wrong merge whose sentences share words (a Houthi operation vs a coalition operation) and may flag a right one. check-agent-grounding.py covers who-did-it.
Run: python check-reinforced-precision.py [--json]   Import: score(area_key) -> dict"""
import json, re, sys, random, pathlib
HERE = pathlib.Path(__file__).resolve().parent; SL = HERE.parent.parent / "demo" / "mockups" / "structure-live"
STOP = set("the a an and of to in on at for by with from is was were be been has have had that this it its as he she they his her their said says say not but are will would also after before which who has more than into over about".split())
def toks(s, verb):
    s = str(s or ""); s = s.split("#", 1)[1] if "#" in s[:300] else s; vw = set(re.findall(r"[a-z0-9]+", (verb or "").lower()))
    return {t for t in re.findall(r"[a-z0-9]+", s.lower()) if len(t) > 2 and t not in STOP and t not in vw}
def ident(sid, cmap):
    t, _, n = str(sid).partition(":")
    return cmap.get(n.lower(), sid) if t in ("concept", "place", "org", "unk", "group") and n.lower() in cmap else sid
def flags(e, cmap):
    f = []; ms = [(m.get("key") or "").split(" | ") for m in (e.get("slot") or {}).get("members") or []]
    subs = {ident(m[0], cmap) for m in ms if m and m[0]} or {ident(e["subject"], cmap)}
    if len(subs) > 1: f.append("subjects differ: " + " / ".join(sorted(subs)))
    objs = {str(e.get("object"))} | {m[2] for m in ms if len(m) > 2}
    if any(o != "None" and ident(o, cmap) in subs for o in objs) or (e.get("object") and ident(e["object"], cmap) == ident(e["subject"], cmap)): f.append("subject == object")
    fr = e.get("fragments") or []; T = [toks(x.get("sent"), e.get("predicate")) for x in fr]
    if len(T) >= 2 and not any(T[i] & T[j] for i in range(len(T)) for j in range(i + 1, len(T))): f.append("no shared content token")
    return f
def score(key, n=40, seed=158):
    k = json.load(open(SL / ("area-" + key) / "trace" / "slow_consolidate" / "knowledge.json")); cm = {}
    R = sorted(i for i, e in k["edges"].items() if (e.get("strength") or 0) >= 2); S = sorted(random.Random(seed).sample(R, min(n, len(R)))); bad = []
    for i in S:
        f = flags(k["edges"][i], cm)
        if f: e = k["edges"][i]; bad.append({"edge": i, "key": "%s | %s | %s" % (e["subject"], e["predicate"], e["object"]), "flags": f})
    return {"area": key, "reinforced_edges": len(R), "sampled": len(S), "flagged": len(bad), "unflagged_rate": round(1 - len(bad) / len(S), 4) if S else None, "flagged_edges": bad}
if __name__ == "__main__":
    AREAS = sys.argv[sys.argv.index("--area") + 1].split(",") if "--area" in sys.argv else ["c1", "mix"]
    out = {a: score(a) for a in AREAS}
    if "--json" in sys.argv: print(json.dumps(out, indent=1))
    else:
        for a, r in out.items():
            print("%s: reinforced edges %d, sampled %d, flagged %d, unflagged %s (heuristic)" % (a, r["reinforced_edges"], r["sampled"], r["flagged"], r["unflagged_rate"]))
            for b in r["flagged_edges"]: print("   ", b["key"][:110], "|", "; ".join(b["flags"])[:120])
