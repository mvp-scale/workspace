"""T158 claims round: cause table on CaRB errors for one extractor's saved predictions (runs/pulse/t158-claims/<split>-<name>.json). Each gold tuple is 'recovered' (some prediction with precision>0.2 and recall>=0.5) or gets ONE cause, first rule that fires:
 missed claim (no prediction shares a verb token with the gold relation) | pronoun subject | speaker as subject (speech verb, subject is the speaker, gold subject is the clause actor) | wrong subject | object from a prepositional phrase (prediction's predicate carries a preposition the gold relation lacks, object tokens differ) | wrong or partial object | split (two or more predictions jointly cover it) | other span mismatch.
    /workspace/models/embed-zs/.venv/bin/python claims-causes.py dev base"""
import sys, json, collections, pathlib
sys.argv = sys.argv[:]; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import importlib.util
sp = importlib.util.spec_from_file_location("cr", str(HERE / "claims-round.py")); CR = importlib.util.module_from_spec(sp); sp.loader.exec_module(CR)
PRON = {"he", "she", "it", "they", "we", "i", "you", "who", "which", "that", "this", "these", "those", "there", "him", "her", "them", "his", "their", "its"}
SPEECH = {"said", "say", "says", "told", "tell", "reported", "claimed", "announced", "warned", "stated", "added", "noted", "argued", "suggested", "confirmed", "denied", "explained", "alleged", "declared", "wrote", "according"}
PREPS = {"in", "on", "at", "under", "for", "of", "to", "from", "with", "by", "over", "after", "before", "during", "into", "about", "against", "between", "through", "as"}
def causes(split, name):
    d = json.load(open(CR.OUT / ("%s-%s.json" % (split, name)))); gold = CR.load_gold(split); C = collections.Counter(); ex = collections.defaultdict(list); n = 0
    for s in d["sentences"]:
        Pd = d["preds"][s]
        for g in gold[s]:
            n += 1; sc = [(CR.pr(p, g), p) for p in Pd]
            if any(pp > 0.2 and rr >= 0.5 for (pp, rr), p in sc): C["recovered"] += 1; continue
            gv = set(g["rel"]); rel = [(x, p) for x, p in sc if (set(p["p"]) & gv) or (set(p["p"]) - PREPS and set(p["p"]) & set(g["rest"]))]
            if not rel:
                c = "missed claim"
            else:
                (pp, rr), p = max(rel, key=lambda t: t[0][1] + t[0][0]); ps = set(p["s"]); sub_ok = bool(ps & set(g["a1"])); ob_ok = bool(set(p["o"]) & set(g["rest"]))
                if not sub_ok and ps and ps <= PRON: c = "pronoun subject"
                elif not sub_ok and set(p["p"]) & SPEECH: c = "speaker as subject"
                elif not sub_ok: c = "wrong subject"
                elif not ob_ok and len(p["p"]) > 1 and p["p"][-1] in PREPS and p["p"][-1] not in g["rel"]: c = "object from a prepositional phrase"
                elif not ob_ok: c = "wrong or partial object"
                elif sum(1 for x, q in sc if x[1] > 0.2 and x[0] > 0.2) >= 2: c = "split"
                else: c = "other span mismatch"
            C[c] += 1; ex[c].append(" | ".join(g["raw"][1:4]) + "  <=  " + g["raw"][0][:70])
    spur = sum(1 for s in d["sentences"] for p in d["preds"][s] if not any(CR.pr(p, g)[0] > 0.2 and CR.pr(p, g)[1] > 0.2 for g in gold[s]))
    return {"gold": n, "causes": dict(C.most_common()), "spurious_predictions": spur, "examples": {k: v[:3] for k, v in ex.items()}}
if __name__ == "__main__":
    r = causes(sys.argv[1], sys.argv[2]); print(json.dumps(r, indent=1)); json.dump(r, open(CR.OUT / ("causes-%s-%s.json" % (sys.argv[1], sys.argv[2])), "w"), indent=1)
