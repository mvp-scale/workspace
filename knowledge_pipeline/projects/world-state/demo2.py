"""Adds the 'everything extracted' card data to runs/fusion/demo.json (structure layer, story type from the CPU model, scope heuristic). Run with the embed venv."""
import json, os, re, glob, pathlib, warnings
warnings.filterwarnings("ignore"); os.environ["CUDA_VISIBLE_DEVICES"] = ""
H0 = pathlib.Path(__file__).resolve().parent
src = open(H0 / "structure.py").read(); exec(src[:src.index("H = {}; S = {}")]); exec(src[src.index("nlp = spacy.load"):src.index("txts = [re.sub")])
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from model2vec import StaticModel
D = json.load(open(H0 / "runs/fusion/demo.json")); st = np.load(H0 / "runs/structure/feat.npz"); ids = list(st["ids"]); F = st["F"]
Hh = {}; Ss = {}
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): Hh[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): Ss[r["item_id"]] = r["label"]
pool = {r["id"]: r["text"] for r in J(H0 / "data/pool_train.jsonl")}; m = StaticModel.from_pretrained("minishlab/potion-base-8M")
agree = [k for k, i in enumerate(ids) if Hh[i]["story_type"] == Ss[i]["story_type"]]; y = np.array([Hh[ids[k]]["story_type"] for k in agree])
E = m.encode([re.sub(r"\s+", " ", pool[i]) for i in ids]); clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, C=0.3, class_weight="balanced")).fit(np.hstack([F, E])[agree], y)
for it in D["items"]:
    i = it["id"]; t = re.sub(r"\s+", " ", pool[i]); d = nlp(t); f = np.array([feat(d, t)], float); k = ids.index(i)
    pr = clf.predict_proba(np.hstack([f, E[k:k + 1]]))[0]; cls = list(clf.classes_)
    ents = {}
    for e in d.ents: ents.setdefault(e.label_, [])
    for e in d.ents:
        if e.text not in ents[e.label_]: ents[e.label_].append(e.text)
    rep = [{"verb": x.text, "claimer": " ".join(w.text for w in x.children if w.dep_ in ("nsubj", "nsubjpass") for w in w.subtree)} for x in d if x.lemma_.lower() in REPORT and x.pos_ in ("VERB", "AUX")]
    places = {e.text.lower() for e in d.ents if e.label_ in ("GPE", "LOC")}; gl = GLOBAL.findall(t + " ")
    scope = "world / multi-country" if gl or len(places) >= 3 else "one or two named places" if places else "no place named"
    low = t
    it["x"] = {"story_ai": [Hh[i]["story_type"], Ss[i]["story_type"]], "story_cpu": {c: round(float(p), 2) for c, p in zip(cls, pr)}, "scope": scope, "places": sorted(places), "global_words": sorted({g.strip().lower() for g in gl}),
               "entities": ents, "reporting": rep, "quote": bool('"' in t or "“" in t), "modal": sorted({x.lower_ for x in d if x.lower_ in MODAL}), "future": sorted({m_.group(0).lower() for m_ in FUT.finditer(low)}), "hedge": sorted({m_.group(0).lower() for m_ in HEDGE.finditer(low)}),
               "opinion": sorted({m_.group(0).lower() for m_ in OPIN.finditer(low)}), "negation": sorted({m_.group(0).lower() for m_ in NEG.finditer(low)}), "evidence": sorted({m_.group(0).lower() for m_ in EVID.finditer(low)}),
               "numbers": [x.text for x in d if x.like_num][:8], "topic_ai": [Hh[i]["topic"], Ss[i]["topic"]]}
json.dump(D, open(H0 / "runs/fusion/demo.json", "w")); print("ok", [(it["x"]["story_ai"], max(it["x"]["story_cpu"], key=it["x"]["story_cpu"].get), it["x"]["scope"]) for it in D["items"]])
