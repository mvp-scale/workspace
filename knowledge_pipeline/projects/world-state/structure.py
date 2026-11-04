"""Structure layer v1 (CPU, deterministic): entities of every type, scope, attribution/claimer, realis and modality, negation, hedging, evidence markers, dates.
Run with /workspace/models/embed-zs/.venv/bin/python structure.py   (builds features for the 7,710 doubly-labelled items, saves runs/structure/feat.npz, then scores story type and the cut-the-field test)"""
import json, os, re, glob, pathlib, warnings
warnings.filterwarnings("ignore"); os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, spacy
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score, recall_score, balanced_accuracy_score
from model2vec import StaticModel
H0 = pathlib.Path(__file__).resolve().parent; J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
REPORT = set("say announce report claim warn state declare confirm deny tell add explain note insist argue allege suggest reveal admit".split())
MODAL = {"will": "future", "would": "cond", "may": "hedge", "might": "hedge", "could": "hedge", "should": "opinion", "must": "opinion", "shall": "future", "can": "can"}
OPIN = re.compile(r"\b(i think|we believe|in my view|opinion|editorial|should|must|ought|need to|calls? for|urge[sd]?|demand[s]?|deserve[sd]?|wrong|unacceptable|shameful|best|worst)\b", re.I)
HEDGE = re.compile(r"\b(reportedly|allegedly|apparently|appears?|seems?|suspected|believed|likely|unlikely|possibly|perhaps|may|might|could)\b", re.I)
FUT = re.compile(r"\b(will|plans? to|expected to|set to|due to|to be|forecast|projected|poised|aims? to|vows? to|promise[sd]?)\b", re.I)
EVID = re.compile(r"\b(data|figures?|statistics|study|survey|poll|report|according to|official[s]?|police|ministry|spokes\w+|analysts?|research(?:ers)?|census|index)\b", re.I)
NEG = re.compile(r"\b(no|not|n't|never|denied?|denies|without|none|neither|nor|rejected?)\b", re.I)
GLOBAL = re.compile(r"\b(global|worldwide|world|international|countries|nations|united nations|un |g20|g7|eu |europe|asia|africa)\b", re.I)
H = {}; S = {}
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): H[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): S[r["item_id"]] = r["label"]
pool = {r["id"]: r["text"] for r in J(H0 / "data/pool_train.jsonl")}; ids = sorted(i for i in S if i in H)
nlp = spacy.load("en_core_web_sm")
ENT = ["PERSON", "NORP", "FAC", "ORG", "GPE", "LOC", "PRODUCT", "EVENT", "LAW", "DATE", "TIME", "PERCENT", "MONEY", "QUANTITY", "CARDINAL", "ORDINAL"]
NAMES = ["n_words", "n_sent", "report_verb", "claimer_found", "quote", "modal_future", "modal_hedge", "modal_opinion", "past_tense_verbs", "negation", "hedge_words", "future_words", "opinion_words", "evidence_words", "numbers", "distinct_gpe", "global_words", "question"] + ["ent_" + e for e in ENT]
def feat(doc, t):
    toks = [x for x in doc]; verbs = [x for x in toks if x.pos_ in ("VERB", "AUX")]; rep = [x for x in verbs if x.lemma_.lower() in REPORT]
    claimer = sum(1 for x in rep if any(c.dep_ in ("nsubj", "nsubjpass") for c in x.children)); ents = [e.label_ for e in doc.ents]; gp = {e.text.lower() for e in doc.ents if e.label_ in ("GPE", "LOC")}
    mods = [MODAL.get(x.lower_) for x in toks if x.lower_ in MODAL]
    return [len(toks), len(list(doc.sents)), len(rep), claimer, int('"' in t or "“" in t), mods.count("future"), mods.count("hedge") + mods.count("cond"), mods.count("opinion"), sum(1 for x in verbs if x.tag_ in ("VBD", "VBN")),
            len(NEG.findall(t)), len(HEDGE.findall(t)), len(FUT.findall(t)), len(OPIN.findall(t)), len(EVID.findall(t)), sum(1 for x in toks if x.like_num), len(gp), len(GLOBAL.findall(t + " ")), int("?" in t)] + [ents.count(e) for e in ENT]
txts = [re.sub(r"\s+", " ", pool[i]) for i in ids]; F = np.array([feat(d, t) for d, t in zip(nlp.pipe(txts, batch_size=64), txts)], float)
m = StaticModel.from_pretrained("minishlab/potion-base-8M"); E = m.encode(txts)
np.savez(H0 / "runs/structure/feat.npz", F=F, ids=np.array(ids), names=np.array(NAMES))
cv = StratifiedKFold(5, shuffle=True, random_state=0); out = {"items": len(ids), "feature_names": NAMES}
# (1) story type
agree = [k for k, i in enumerate(ids) if H[i]["story_type"] == S[i]["story_type"]]; y = np.array([H[ids[k]]["story_type"] for k in agree]); cls = sorted(set(y))
out["story_type_agreed_n"] = len(agree); out["story_type_share"] = {c: round(float((y == c).mean()), 3) for c in cls}
for name, X in (("structure", F[agree]), ("embedding", E[agree]), ("both", np.hstack([F[agree], E[agree]]))):
    p = cross_val_predict(make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, C=0.3, class_weight="balanced")), X, y, cv=cv)
    out[f"story_{name}"] = {"balanced_accuracy": round(float(balanced_accuracy_score(y, p)), 3), "recall": {c: round(float(recall_score(y == c, p == c)), 2) for c in cls}}
# (2) cut the field: item-level 'both models name a condition' vs 'both name none'
cs = lambda L: {x["condition"] for x in L["conditions"]}; lab = []
for i in ids:
    h, s = cs(H[i]), cs(S[i]); lab.append(1 if h and s else 0 if not h and not s else -1)
lab = np.array(lab); k = lab >= 0; out["field"] = {"voted": len(ids), "both_name": int((lab == 1).sum()), "both_none": int((lab == 0).sum()), "mixed": int((lab == -1).sum())}
Fz = {"embedding": E, "structure": F, "both": np.hstack([F, E])}
for name, X in Fz.items():
    p = cross_val_predict(make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, C=0.1)), X[k], lab[k], cv=cv, method="predict_proba")[:, 1]
    auc = roc_auc_score(lab[k], p); res = {"auc": round(float(auc), 3)}
    for tgt in (0.90, 0.95):
        best = 0
        for lo in np.linspace(0.02, 0.5, 49):
            for hi in np.linspace(0.5, 0.98, 49):
                dec = (p <= lo) | (p >= hi); 
                if dec.sum() == 0: continue
                acc = np.mean(((p >= hi) == (lab[k] == 1))[dec])
                if acc >= tgt: best = max(best, dec.mean())
        res[f"coverage_at_{int(tgt*100)}pct_agreement"] = round(float(best), 3)
    out[f"cut_field_{name}"] = res
json.dump(out, open(H0 / "runs/structure/yield.json", "w"), indent=1); print(json.dumps({k: v for k, v in out.items() if k != "feature_names"}, indent=1))
