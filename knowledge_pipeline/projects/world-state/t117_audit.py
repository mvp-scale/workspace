"""T117: rung 0 audit of the queue labels (T111 plus T114) against the engine's 1736 stories. Counts only: headline overlap, dial and direction mix.
    OUT=<folder> LABELS=<labels.jsonl> python3 t117_audit.py -> <OUT>/t117_audit.json"""
import os, json, re, collections, pathlib
OUT = pathlib.Path(os.environ.get("OUT", "runs/pulse/t117")); OUT.mkdir(parents=True, exist_ok=True)
nk = lambda t: re.sub(r"\W+", " ", t.lower()).strip()
L = [json.loads(l) for l in open(os.environ.get("LABELS", "runs/pulse/t114/labels_all.jsonl"))]
eng = {}
for fn in ("clef-q4km.jsonl", "clef-q4km-w3.jsonl"):
    for l in open("/workspace/data/newsreader/labels/" + fn):
        r = json.loads(l); eng.setdefault(r["id"], r)
et = {nk(r["title"]) for r in eng.values()}
ov = [r for r in L if nk(r["title"]) in et]
dup = len(L) - len({nk(r["title"]) for r in L})
jd = collections.Counter(r["dial"] for r in L if r["dial"] not in ("none", "error")); jn = sum(jd.values())
ed = collections.Counter(x["dial"] for r in eng.values() for x in (r.get("readings") or [])[:1]); en = sum(ed.values())
jdir = collections.Counter(r["direction"] for r in L if r["dial"] not in ("none", "error") and r["direction"] in ("up", "down"))
edir = collections.Counter(); 
for r in eng.values():
    w = collections.Counter()
    for x in r.get("readings") or []: w[x["direction"]] += x.get("strength", 1.0)
    if w["up"] != w["down"] and max(w, key=w.get) in ("up", "down"): edir["up" if w["up"] > w["down"] else "down"] += 1
top = sorted(set(jd) | set(ed), key=lambda k: -(jd[k] / max(jn, 1) + ed[k] / max(en, 1)))[:15]
res = {"labels": len(L), "engine_stories": len(eng), "labels_sharing_headline_with_engine_story": len(ov), "overlap_share": round(len(ov) / len(L), 5), "duplicate_headlines_inside_labels": dup,
       "jev_up_share": round(jdir["up"] / max(sum(jdir.values()), 1), 4), "engine_up_share": round(edir["up"] / max(sum(edir.values()), 1), 4),
       "dial_share_jev_vs_engine": {k: [round(jd[k] / max(jn, 1), 4), round(ed[k] / max(en, 1), 4)] for k in top},
       "largest_dial_share_gap": round(max(abs(jd[k] / max(jn, 1) - ed[k] / max(en, 1)) for k in set(jd) | set(ed)), 4),
       "note": "Jev share is over all labelled stories that got a dial; engine share is the first stored reading of each engine story that has one."}
json.dump(res, open(OUT / "t117_audit.json", "w"), indent=1); print(json.dumps(res, indent=1))
