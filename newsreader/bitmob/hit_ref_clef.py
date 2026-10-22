#!/usr/bin/env python3
"""Hit-chain reference from the Clef labels of the frozen test (D-0038): adds set 'clef_test' to data/bitmob-integration/hit_reference.json, same schema as 'jev_testA',
but topic counts EVERY tagged domain (place()[].tagged), so stories_with_topic = n and the topic column is no longer one tag per story.
  python3 newsreader/bitmob/hit_ref_clef.py [--in data/clef-labels/test.jsonl] [--out PATH]   default --out is a scratch print only (no write); --apply writes hit_reference.json (backup .bak first)
Safe on partial data: n is the number of labelled stories; --apply refuses below --min-n (default 2000, the full frozen test)."""
import json, sys, os, shutil, argparse, collections
W = "/workspace"; REF = f"{W}/data/bitmob-integration/hit_reference.json"
ap = argparse.ArgumentParser(); ap.add_argument("--in", dest="inp", default=f"{W}/data/clef-labels/test.jsonl"); ap.add_argument("--out"); ap.add_argument("--apply", action="store_true"); ap.add_argument("--min-n", type=int, default=2000)
a = ap.parse_args()
if not os.path.exists(a.inp): sys.exit(f"no Clef labels yet: {a.inp}")
ref = json.load(open(REF)); tn, dn = ref["topic_names"], ref["dial_names"]; rows = [json.loads(l) for l in open(a.inp) if l.strip()]
def typ(P):
    h, an, o, f = (P[f"g|{k}"] for k in ("happened", "announced", "opinion", "forecast"))      # same rule as the engine's type_weight
    return "fact" if (h >= .5 or an >= .5) and o < .5 and f < .5 else "forecast" if f >= .5 else "opinion" if o >= .5 else "unclear"
topic, country, cond, tp = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter(); nr = gc = 0
for r in rows:
    for t in r["place"]:
        if t["tagged"]: topic[tn.get(t["id"], t["id"])] += 1
    country[r["country"]] += 1
    cs = [x for x in r["read"]["readings"] if x["direction"] != "conflict"]
    for x in cs: cond[f"{dn.get(x['dial'], x['dial'])} {x['direction']}"] += 1
    nr += not cs; gc += not r["read"]["gate_ok"]; tp[typ(r["P"])] += 1
s = {"source": f"Clef Flash Q4 labels on the frozen test ({os.path.relpath(a.inp, W)}); every tagged domain counts (place(): choice >= 0.2 or yes >= 0.5); conditions = the engine's readings", "n": len(rows), "stories_with_topic": len(rows),
     "topic": dict(topic.most_common()), "country": dict(country.most_common()), "cond": dict(cond.most_common()), "no_reading": nr, "gate_closed": gc, "type": dict(tp.most_common()), "expected": None}
print(json.dumps({k: (v if not isinstance(v, dict) else dict(list(v.items())[:4])) for k, v in s.items()}, indent=1)[:1500]); print("mean tags/story", round(sum(topic.values()) / max(len(rows), 1), 2))
if a.out: json.dump(s, open(a.out, "w"), indent=1); print("wrote", a.out)
if a.apply:
    if len(rows) < a.min_n: sys.exit(f"refusing: {len(rows)} stories < {a.min_n} (partial data)")
    shutil.copy(REF, REF + ".bak"); ref["sets"]["clef_test"] = s; ref["made"] = __import__("datetime").datetime.now().isoformat(timespec="seconds"); json.dump(ref, open(REF + ".tmp", "w"), indent=1); os.replace(REF + ".tmp", REF); print("applied")
