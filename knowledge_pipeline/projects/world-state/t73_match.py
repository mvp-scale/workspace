"""T73 stage 3: match rates for the 563 same-event pairs under text keys and under GLiNER-entity keys (same triples, same pairs; only the keys change). Unjudged.
    python3 t73_match.py -> runs/pulse/t73_match.json"""
import os, json, re
R = json.load(open(os.environ.get("T73DIR", "runs/pulse") + "/t73_triples.json")); EN = json.load(open(os.environ.get("T73DIR", "runs/pulse") + "/t73_entities.json"))
DET = re.compile(r"^(the|a|an|his|her|their|its|our|my|your|this|that|these|those)\s+"); POSS = re.compile(r"['’]s\b")
def canon(x): x = POSS.sub("", x.lower()).strip(); x = DET.sub("", x); return re.sub(r"\s+", " ", re.sub(r"[^\w\s-]", " ", x)).strip()
def ekey(phrase, text_key, sent):
    p = canon(phrase); best = None
    for e in EN.get(sent, []):
        c = canon(e)
        if c and p and (c in p or p in c) and (best is None or len(c) > len(best)): best = c
    return ("E:" + best, True) if best else ("T:" + text_key, False)
def keys(t):
    sk, sm = ekey(t["s"], t["s_key"], t["sent_text"]); ok, om = ekey(t["o"], t["o_key"], t["sent_text"])
    return {"text_exact": (t["s_key"], t["p"], t["o_key"]), "text_pair": (t["s_key"], t["o_key"]), "ent_pair": (sk, ok), "ent_pred": (sk, t["p_lemma"], ok)}, (sm, om)
res = {}
for g in ("copy", "independent"):
    C = {k: [0, 0] for k in ("text_exact", "text_pair", "ent_pair", "ent_pred")}; mapped = [0, 0]; pairs = 0
    for r in (x for x in R if x["group"] == g):
        pairs += 1; KB = [keys(t)[0] for t in r["B"]]
        for t in r["A"]:
            ka, mm = keys(t); mapped[0] += mm[0] + mm[1]; mapped[1] += 2
            for k in C: C[k][1] += 1; C[k][0] += any(kb[k] == ka[k] for kb in KB)
    res[g] = {"pairs": pairs, "triples": C["text_exact"][1], "phrases_mapped_to_an_entity": round(mapped[0] / max(1, mapped[1]), 4), **{k: round(v[0] / max(1, v[1]), 4) for k, v in C.items()}}
res["note"] = "Match rate = share of A-side triples with an equal key among the B-side triples of the same pair. text_* are the T66 keys recomputed on this sample; ent_* map subject and object phrases to GLiNER entities by containment. Unjudged."
json.dump(res, open(os.environ.get("T73DIR", "runs/pulse") + "/t73_match.json", "w"), indent=1); print(json.dumps(res, indent=1))
