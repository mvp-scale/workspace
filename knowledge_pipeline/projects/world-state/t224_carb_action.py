"""T224 (plan T148-W1; carb_score.py with a copular filter): action-only score. Score triple extractors on the CaRB test set (MIT licence; /workspace/data/anchors/carb/test.tsv) with a CaRB-style token-overlap score (not the official scorer).
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
import os, json
COP = {"is", "are", "was", "were", "be", "been", "being", "has", "have", "had", "'s", "s"}
act = lambda x: bool(x["rel"]) and x["rel"][0] not in COP
actp = lambda x: bool(x["p"]) and x["p"][0] not in COP
full = {s: list(v) for s, v in gold.items()}
ngold_all = sum(len(v) for v in gold.values()); gold_act = {s: [g for g in v if act(g)] for s, v in gold.items()}
preds = {}
for s in sents:
    T = S.extract(nlp, [s]); conv = lambda t: {"s": tok(t["s"]), "p": tok(t["p"]), "o": tok(t["o"])}
    preds[s] = [conv(t) for t in T if t["s"] or t["o"]]
r_full = score(preds, "all gold, all predictions")
gold.clear(); gold.update(gold_act); sents[:] = [s for s in sents if gold[s]]
r_act = score({s: [p for p in preds[s] if actp(p)] for s in sents}, "action gold only, action predictions only")
res = {"gold_total": ngold_all, "gold_action": sum(len(v) for v in gold_act.values()), "share_action": sum(len(v) for v in gold_act.values()) / ngold_all, "sentences_with_action_gold": len(sents), "full": r_full, "action_only": r_act, "scorer": "in-house CaRB-style token overlap, not the official scorer"}

miss = []
for s in sents:
    for g in gold[s]:
        P = [p for p in preds[s] if actp(p)]; best = max([pr(p, g)[1] if pr(p, g)[0] > 0.2 else 0.0 for p in P], default=0.0)
        if best < 0.3: miss.append({"sentence": s, "gold": " | ".join([" ".join(g["a1"]), " ".join(g["rel"]), " ".join(g["rest"])]), "best_recall": round(best, 2), "preds_in_sentence": len(P)})
res["action_misses"] = len(miss); res["action_miss_examples"] = miss[::max(1, len(miss) // 60)][:60]
os.makedirs("runs/pulse/t224", exist_ok=True); json.dump(res, open("runs/pulse/t224/t224_carb_action.json", "w"), indent=1); print(json.dumps(res, indent=1))
