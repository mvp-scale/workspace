"""T158 claims round (playbook 00 gate G2): CaRB (MIT, /workspace/data/anchors/carb) dev/test scoring of the triple extractors, with the same in-house CaRB-style token-overlap scorer as carb_score.py (L2481), not the official CaRB matcher (not on disk).
Extractors: base = spo_chains.extract (en_core_web_sm; the 0.402 baseline); v0 = the page path (facts_lib triples + partial claims + raw-units.claims_v0 attribution/pronoun); v1 = claims-v1.py (add-only rules).
    /workspace/models/embed-zs/.venv/bin/python claims-round.py dev|test [names...]  -> runs/pulse/t158-claims/<split>-<name>.json (per-sentence stats for the paired bootstrap)"""
import re, sys, json, time, collections, importlib.util, pathlib, warnings; warnings.filterwarnings("ignore")
import spacy
HERE = pathlib.Path(__file__).resolve().parent; OUT = HERE / "runs" / "pulse" / "t158-claims"; OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent.parent / "simulation"))
import spo_chains as S, facts_lib as FL, scan_gate as SG
tok = lambda s: [w for w in re.findall(r"\w+(?:\.\w+)*|[^\w\s]", (s or "").lower()) if re.search(r"\w", w)]
def load_gold(split):
    gold = collections.defaultdict(list)
    for l in open("/workspace/data/anchors/carb/%s.tsv" % split, encoding="utf-8"):
        f = l.rstrip("\n").split("\t")
        if len(f) >= 4: gold[f[0]].append({"rel": tok(f[1]), "a1": tok(f[2]), "rest": tok(" ".join(f[3:])), "raw": f})
    return gold
def pr(pred, g):
    """slot-wise token overlap of one predicted and one gold triple -> (precision, recall); identical to carb_score.py"""
    pt = pred["s"] + pred["p"] + pred["o"]; gt = g["a1"] + g["rel"] + g["rest"]
    if not pt or not gt: return 0.0, 0.0
    hit_p = sum(sum(1 for w in pred[k] if w in g[m]) for k, m in (("s", "a1"), ("p", "rel"), ("o", "rest")))
    hit_g = sum(sum(1 for w in g[m] if w in pred[k]) for k, m in (("s", "a1"), ("p", "rel"), ("o", "rest")))
    return hit_p / len(pt), hit_g / len(gt)
def sent_stats(Pd, G):
    """per-sentence sums for the micro P/R: P = sum over predictions of the best precision among gold it recalls >0.2 of; R likewise"""
    P = R = 0.0
    for p in Pd: P += max([pr(p, g)[0] if pr(p, g)[1] > 0.2 else 0.0 for g in G], default=0.0)
    for g in G: R += max([pr(p, g)[1] if pr(p, g)[0] > 0.2 else 0.0 for p in Pd], default=0.0)
    partial = sum(1 for p in Pd if not p["s"] or not p["o"])
    return [P, len(Pd), R, len(G), partial]
def prf(st):
    P = sum(x[0] for x in st); n = sum(x[1] for x in st); R = sum(x[2] for x in st); ng = sum(x[3] for x in st); pa = sum(x[4] for x in st)
    p = P / max(n, 1); r = R / max(ng, 1); return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / max(p + r, 1e-9), 3), "predicted": n, "gold": ng, "partial_share": round(pa / max(n, 1), 3)}
conv = lambda s, p, o, **k: {"s": tok(s), "p": tok(p), "o": tok(o), **k}
_sm = _lg = None
def sm():
    global _sm
    _sm = _sm or spacy.load("en_core_web_sm"); return _sm
def lg():
    global _lg
    _lg = _lg or spacy.load("en_core_web_lg", exclude=["ner"]); return _lg   # NER off: claims v1 does not need it and it is a third of the parse time
def ex_base(s, nlp=None):
    return [conv(t["s"], t["p"], t["o"]) for t in S.extract(nlp or sm(), [s]) if t["s"] or t["o"]]
_RU = None
def ru():
    global _RU
    if _RU is None:
        sp = importlib.util.spec_from_file_location("ru", str(HERE.parent.parent / "simulation" / "raw-units.py")); _RU = importlib.util.module_from_spec(sp); sp.loader.exec_module(_RU)
    return _RU
def ex_v0(s):
    """the page path on one sentence: facts_lib triples (as units_for makes them), claims_v0 (pronoun resolver + attribution claims)"""
    R = ru(); kept, _ = FL.quarantine(FL.facts_for(s, None)[0], s); spots, sents = SG.scan(s, "2026-01-01T00:00:00Z"); U = []
    for f in kept:
        v = f.get("value")
        if f["kind"] != "triple" or not (isinstance(v, list) and len(v) == 3 and v[1]): continue
        if v[0] and v[2]: U.append({"type": "triple", "subject": v[0], "predicate": v[1], "value": v[2], "sentence": 0, "spans": R.triple_spans(s, f["s"], f["e"], v, sents)})
        elif v[0] or v[2]: U.append({"type": "partial_claim", "subject": v[0] or None, "predicate": v[1], "value": v[2] or None, "sentence": 0, "spans": []})
    ents = R.lg_ents(s); R.claims_v0(U, s, ents, sents, spots, {}, {"l1": None, "node": None}, None)
    return [conv(u["subject"], u["predicate"], u["value"]) for u in U]
def run(name, split, fn):
    gold = load_gold(split); sents = list(gold); st = []; preds = {}; t0 = time.perf_counter()
    for s in sents:
        P = fn(s); preds[s] = [{k: p[k] for k in ("s", "p", "o")} for p in P]; st.append(sent_stats(P, gold[s]))
    ms = (time.perf_counter() - t0) * 1000 / len(sents)
    res = {"name": name, "split": split, "sentences": len(sents), **prf(st), "ms_per_sentence": round(ms, 1)}
    json.dump({"result": res, "per_sentence": st, "sentences": sents, "preds": preds}, open(OUT / ("%s-%s.json" % (split, name)), "w"))
    print(json.dumps(res)); return res
EXTRACTORS = {"base": ex_base, "v0": ex_v0}
if __name__ == "__main__":
    split = sys.argv[1]; names = sys.argv[2:] or list(EXTRACTORS)
    if "v1" in names or "base-lg" in names:
        sp = importlib.util.spec_from_file_location("claims_v1", str(HERE / "claims-v1.py")); V1 = importlib.util.module_from_spec(sp); sp.loader.exec_module(V1)
        EXTRACTORS["v1"] = lambda s: [conv(x["s"], x["p"], x["o"]) for x in V1.extract(s, lg())]; EXTRACTORS["base-lg"] = lambda s: ex_base(s, lg())
    for n in names: run(n, split, EXTRACTORS[n])
