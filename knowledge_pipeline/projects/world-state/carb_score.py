"""Score triple extractors on the CaRB test set (MIT licence; /workspace/data/anchors/carb/test.tsv) with a CaRB-style token-overlap score (not the official scorer).
Gold row: sentence, relation, arg1, arg2, ... Predicted: subject, relation, object.
    /workspace/models/embed-zs/.venv/bin/python carb_score.py -> runs/harvest/relations/carb_score.json"""
import re, json, collections, warnings; warnings.filterwarnings("ignore")
import spacy, spo_chains as S, facts_lib as FL
tok = lambda s: [w for w in re.findall(r"\w+(?:\.\w+)*|[^\w\s]", (s or "").lower()) if re.search(r"\w", w)]
gold = collections.defaultdict(list)
for l in open("/workspace/data/anchors/carb/test.tsv", encoding="utf-8"):
    f = l.rstrip("\n").split("\t")
    if len(f) >= 4: gold[f[0]].append({"rel": tok(f[1]), "a1": tok(f[2]), "rest": tok(" ".join(f[3:]))})
sents = list(gold)
nlp = spacy.load("en_core_web_sm")
def pr(pred, g):
    """slot-wise token overlap between one predicted and one gold triple -> (precision, recall)"""
    pt = pred["s"] + pred["p"] + pred["o"]; gt = g["a1"] + g["rel"] + g["rest"]
    if not pt or not gt: return 0.0, 0.0
    hit_p = sum(min(len(pred[k]) and 1, 1) and sum(1 for w in pred[k] if w in g[m]) for k, m in (("s", "a1"), ("p", "rel"), ("o", "rest")))
    hit_g = sum(sum(1 for w in g[m] if w in pred[k]) for k, m in (("s", "a1"), ("p", "rel"), ("o", "rest")))
    return hit_p / len(pt), hit_g / len(gt)
def score(preds_by_sent, label):
    P = R = 0.0; npred = ngold = 0; sents_hit = 0
    for s in sents:
        G = gold[s]; Pd = preds_by_sent.get(s, []); ngold += len(G); npred += len(Pd)
        for p in Pd: P += max([pr(p, g)[0] if pr(p, g)[1] > 0.2 else 0.0 for g in G], default=0.0)
        for g in G: R += max([pr(p, g)[1] if pr(p, g)[0] > 0.2 else 0.0 for p in Pd], default=0.0)
        sents_hit += 1 if Pd else 0
    prec = P / max(npred, 1); rec = R / max(ngold, 1); f1 = 2 * prec * rec / max(prec + rec, 1e-9)
    return {"extractor": label, "predicted": npred, "gold": ngold, "sentences_with_a_prediction": sents_hit, "precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3)}
mine_all = {}; mine_so = {}; ff = {}
for s, doc in zip(sents, nlp.pipe(sents)):
    T = S.extract(nlp, [s]); 
    conv = lambda t: {"s": tok(t["s"]), "p": tok(t["p"]), "o": tok(t["o"]), "raw": t}
    mine_all[s] = [conv(t) for t in T if t["s"] or t["o"]]
    mine_so[s] = [conv(t) for t in T if t["s"] and t["o"] and not t["s_pronoun"]]
    try: fts = [f for f in FL.facts_for(s, "2026-01-01T00:00:00Z")[0] if f["kind"] == "triple"]
    except Exception: fts = []
    ff[s] = [{"s": tok(f["value"][0]), "p": tok(f["value"][1]), "o": tok(f["value"][2]), "raw": f} for f in fts if f["value"][0] or f["value"][2]]
res = [score(mine_all, "new extractor, all triples"), score(mine_so, "new extractor, named subject and object only"), score(ff, "existing Fact finder triples")]
# failures for error analysis: gold tuples nothing recovers
miss = []
for s in sents:
    for g in gold[s]:
        best = max([pr(p, g)[1] if pr(p, g)[0] > 0.2 else 0.0 for p in mine_all[s]], default=0.0)
        if best < 0.3: miss.append({"sentence": s, "gold": " | ".join([" ".join(g["a1"]), " ".join(g["rel"]), " ".join(g["rest"])]), "best_recall": round(best, 2)})
json.dump({"v": "carb-score-v0", "data": "CaRB test (MIT), 641 sentences", "scorer": "CaRB-style token overlap written here, not the official scorer", "results": res, "unrecovered_gold_triples": len(miss), "examples": miss[:40]}, open("runs/harvest/relations/carb_score.json", "w"), indent=1)
for r in res: print(r)
print("gold triples with no good match in the new extractor:", len(miss), "of", sum(len(v) for v in gold.values()))
for m in miss[:6]: print("  ", m["gold"][:110], "<-", m["sentence"][:80])
