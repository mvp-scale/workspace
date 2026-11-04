"""Cascade v0: article -> sentences -> claim, several CPU layers, fused per condition with cross-validation. Run with /workspace/models/embed-zs/.venv/bin/python."""
import json, os, re, glob, pathlib, random, yaml, warnings
warnings.filterwarnings("ignore"); os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, spacy
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score
from model2vec import StaticModel
H0 = pathlib.Path(__file__).resolve().parent; J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
m = StaticModel.from_pretrained("minishlab/potion-base-8M"); lib = yaml.safe_load(open(H0 / "specs/probe_library.yaml"))["conditions"]; C = sorted(lib)
probes, ptype = [], []
for c in C:
    for k in ("up", "down"):
        for t in lib[c][k]: probes.append(t); ptype.append(c)
unit = lambda a: a / (np.linalg.norm(a, axis=-1, keepdims=True) + 1e-9); cidx = {c: [j for j, p in enumerate(ptype) if p == c] for c in C}
H = {}; S = {}
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): H[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): S[r["item_id"]] = r["label"]
pool = {r["id"]: r["text"] for r in J(H0 / "data/pool_train.jsonl")}; ids = sorted(i for i in S if i in H)
ref = random.Random(4).sample([i for i in pool if i not in set(ids)], 2000)
def split(t):
    t = re.sub(r"\s+", " ", t).strip(); ss = [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9“\"'])", t) if len(s.split()) >= 3] or [t]; return t, ss[0], ss
def embed(idl, claims=None):
    U, off = [], []
    for n, i in enumerate(idl):
        w, hd, ss = split(pool[i]); cl = (claims[i] if claims else "") or hd; a = len(U); U += [w, hd, cl] + ss; off.append((a, len(U)))
    return m.encode(U), off
PE0 = m.encode(probes); Rn, Ro = embed(ref); mu = Rn.mean(0); cen = lambda x: unit(x - mu); PE = cen(PE0)
def sims(E, off):
    Sm = cen(E) @ PE.T; return {"all": np.stack([Sm[a] for a, b in off]), "head": np.stack([Sm[a + 1] for a, b in off]), "claim": np.stack([Sm[a + 2] for a, b in off]), "sent": np.stack([Sm[a + 3:b].max(0) for a, b in off])}
R = sims(Rn, Ro); st = {g: (R[g].mean(0), R[g].std(0) + 1e-9) for g in R}
claims = {i: H[i].get("claim") for i in ids}; En, Eo = embed(ids, claims); Z = {g: (v - st[g][0]) / st[g][1] for g, v in sims(En, Eo).items()}
# claim reference stats use headline as the stand-in for claim in the reference set (same length scale)
for g in ("claim",): Z[g] = (sims(En, Eo)["claim"] - st["head"][0]) / st["head"][1]
nlp = spacy.load("en_core_web_sm", disable=["textcat"])
CH = set("rise increase surge climb soar jump spike hike grow worsen escalate mount expand boost swell fall drop decline decrease plunge slump cut reduce lower ease shrink dip tumble slash improve recover close shut halt ban kill die".split())
def spfeat(t):
    d = nlp(re.sub(r"\s+", " ", t)); ch = sum(1 for x in d if x.lemma_.lower() in CH and x.pos_ in ("VERB", "NOUN")); ents = [e.label_ for e in d.ents]
    return [ch, ents.count("PERCENT") + ents.count("MONEY"), ents.count("CARDINAL") + ents.count("QUANTITY"), ents.count("GPE") + ents.count("LOC"), len(d.text.split()), len(list(d.sents))]
SP = np.array([spfeat(pool[i]) for i in ids], float)
cs = lambda L: {x["condition"] for x in L["conditions"]}; A = {i: (cs(H[i]), cs(S[i])) for i in ids}
mx = lambda M, c: M[:, cidx[c]].max(1)
sets = {"embed_all": ["all"], "embed+sent+head": ["all", "sent", "head"], "embed+claim": ["all", "claim"], "embed+spacy": ["all", "SP"], "everything": ["all", "sent", "head", "claim", "SP"]}
res = {k: [] for k in sets}; res["per_condition"] = {}; cv = StratifiedKFold(5, shuffle=True, random_state=0)
for c in C:
    y = np.array([1 if (c in A[i][0] and c in A[i][1]) else 0 if (c not in A[i][0] and c not in A[i][1]) else -1 for i in ids]); k = y >= 0
    if y[k].sum() < 30: continue
    row = {}
    for name, parts in sets.items():
        X = np.column_stack([SP if p == "SP" else mx(Z[p], c) for p in parts])[k]
        pred = cross_val_predict(make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, C=1.0)), X, y[k], cv=cv, method="predict_proba")[:, 1]
        row[name] = round(float(roc_auc_score(y[k], pred)), 3); res[name].append(row[name])
    row["n_pos"] = int(y[k].sum()); res["per_condition"][c] = row
out = {"conditions": len(res["per_condition"]), "mean_auc": {k: round(float(np.mean(res[k])), 3) for k in sets}, "per_condition": res["per_condition"]}
# power-word guard on the direction lexicon
UP = r"\b(ris(?:e|es|ing)|rose|risen|increas\w*|surg\w*|climb\w*|soar\w*|jump\w*|spik\w*|hik\w*|grow\w*|grew|worsen\w*|escalat\w*|mount\w*|expand\w*|boost\w*|swell\w*|record high)\b"
DN = r"\b(fall\w*|fell|drop\w*|declin\w*|decreas\w*|plung\w*|slump\w*|reduc\w*|eas(?:e|es|ed|ing)|shrink\w*|shrank|dip\w*|tumbl\w*|slash\w*|fewer|improv\w*|recover\w*)\b"
byc = {}
for i in ids:
    hh = {x["condition"]: x["direction"] for x in H[i]["conditions"]}; ss = {x["condition"]: x["direction"] for x in S[i]["conditions"]}; t = pool[i].lower(); sc = len(re.findall(UP, t)) - len(re.findall(DN, t))
    for c in hh:
        if c in ss and hh[c] == ss[c] and sc != 0: byc.setdefault(hh[c], [0, 0]); byc[hh[c]][0] += 1; byc[hh[c]][1] += ((sc > 0) == (hh[c] == "up"))
out["direction_lexicon_without_generic_words"] = {k: f"{v[1]}/{v[0]} = {v[1]/v[0]:.2f}" for k, v in byc.items()}; out["direction_balanced_accuracy"] = round(sum(v[1] / v[0] for v in byc.values()) / len(byc), 3)
json.dump(out, open(H0 / "runs/fusion/yield.json", "w"), indent=1); print(json.dumps({k: v for k, v in out.items() if k != "per_condition"}, indent=1))

# ---- demo export for the HTML mockup (DEMO=1): fits the "everything" model per condition on all strong answers, then exports a few items with every layer ----
if os.environ.get("DEMO"):
    b = json.load(open(H0 / "runs/bakeoff/b300/ids.json")); Bk = {f: {r["item_id"]: {k: v for k, v in r["label"].items() if v != "none"} for r in J(H0 / f"runs/bakeoff/b300/{f}/labels.jsonl")} for f in ("haiku", "sonnet")}
    import itertools
    cand = []
    for i in b["agree"] + b["disagree"] + b["none"]:
        if i not in Bk["haiku"] or i not in Bk["sonnet"] or i not in H or i not in S: continue
        nm = [{x["condition"] for x in H[i]["conditions"]}, {x["condition"] for x in S[i]["conditions"]}, set(Bk["haiku"][i]), set(Bk["sonnet"][i])]
        if sum(1 for v in nm if v) < 3: continue
        jac = [len(a & b_) / len(a | b_) for a, b_ in itertools.combinations(nm, 2) if a | b_]; cand.append((float(np.mean(jac)), i, H[i]["topic"]))
    cand.sort(); pick, seen = [], set()
    for j, i, tp in cand:
        if tp not in seen: seen.add(tp); pick.append(i)
        if len(pick) == 5: break
    easy = [i for j, i, tp in sorted(cand, reverse=True) if i not in pick][:3]; show = pick + easy
    models = {}
    for c in C:
        y = np.array([1 if (c in A[i][0] and c in A[i][1]) else 0 if (c not in A[i][0] and c not in A[i][1]) else -1 for i in ids]); k = y >= 0
        if y[k].sum() < 30: continue
        X = np.column_stack([mx(Z[p], c) if p != "SP" else SP for p in ("all", "sent", "head", "claim", "SP")])[k]; sc = StandardScaler().fit(X); lr = LogisticRegression(max_iter=500).fit(sc.transform(X), y[k]); models[c] = (sc, lr)
    LAY = ["whole text", "best sentence", "headline", "claim"] + ["spaCy " + n for n in ("change words", "% or money", "numbers", "places", "length", "sentences")]
    items = []
    for i in show:
        t = ids.index(i); w, hd, ss = split(pool[i]); d = nlp(re.sub(r"\s+", " ", pool[i]))
        rows = []
        for c, (sc, lr) in models.items():
            x = np.array([[mx(Z[p], c)[t] for p in ("all", "sent", "head", "claim")] + list(SP[t])]); xs = sc.transform(x)[0]; p_ = float(lr.predict_proba(sc.transform(x))[0, 1])
            top = sorted(((float(Z["all"][t][j]), probes[j]) for j in cidx[c]), reverse=True)[:3]
            rows.append({"c": c, "p": round(p_, 3), "z": [round(float(v), 2) for v in x[0][:4]], "contrib": [round(float(lr.coef_[0][q] * xs[q]), 3) for q in range(len(xs))], "bias": round(float(lr.intercept_[0]), 3), "top": [{"z": round(a, 2), "probe": b_} for a, b_ in top]})
        rows.sort(key=lambda r: -r["p"]); lo = pool[i].lower(); upw = sorted(set(re.findall(UP, lo))); dnw = sorted(set(re.findall(DN, lo)))
        items.append({"id": i, "topic": H[i]["topic"], "headline": hd, "sentences": ss, "claim": claims[i], "rows": rows[:7], "layers": LAY,
                      "ai": {"A Haiku": {x["condition"]: x["direction"] for x in H[i]["conditions"]}, "A Sonnet": {x["condition"]: x["direction"] for x in S[i]["conditions"]}, "B Haiku": Bk["haiku"][i], "B Sonnet": Bk["sonnet"][i]},
                      "lex": {"up": upw, "down": dnw, "score": len(re.findall(UP, lo)) - len(re.findall(DN, lo))}, "ents": [[e.text, e.label_] for e in d.ents], "changes": sorted({x.text.lower() for x in d if x.lemma_.lower() in CH and x.pos_ in ("VERB", "NOUN")})})
    json.dump({"items": items}, open(H0 / "runs/fusion/demo.json", "w")); print("demo items", len(items), [len(x["rows"]) for x in items])
