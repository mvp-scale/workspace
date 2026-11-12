"""Track A: do triple-derived notes (negation, modality, attribution, passive, question, hits) add to the existing happened head? Same 1818 items, same folds as factuality_head_cv.py.
    /workspace/models/embed-zs/.venv/bin/python trackA_happened.py -> runs/harvest/relations/trackA_happened.json"""
import json, sys, math, re, warnings, collections, numpy as np; warnings.filterwarnings("ignore")
sys.path.insert(0, "."); from expert1_runtime import Expert3
import spacy; from spacy.tokens import Doc
import spo_chains as S
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.feature_extraction.text import TfidfVectorizer
import scipy.sparse as sp
nlp = spacy.load("en_core_web_sm"); e = Expert3("runs/expert1/expert1_v5_leaf.pkl")
items = [json.loads(l) for l in open("/workspace/data/anchors/maven_fact/items_T33b.jsonl")]; G = json.load(open("/workspace/data/anchors/maven_fact/gold_T33b.json"))
X = np.array([e.embed(x["text"]) for x in items], dtype=np.float32); y = np.array([1 if G[x["id"]]["yes"] else 0 for x in items]); grp = np.array([x["id"].split(":")[1] for x in items])
MODS = ["will", "would", "could", "may", "might", "can", "should", "must", "plan", "expect", "intend", "try", "hope", "want", "seek", "threaten", "promise", "propose", "need", "refuse", "agree", "aim", "vow"]
def notes(text):
    w = text.split(); a = w.index("«") if "«" in w else 0; b = w.index("»") if "»" in w else a + 1
    toks = [t for t in w if t not in ("«", "»")]; lo, hi = a, max(b - 1, a + 1)  # trigger token range in the cleaned tokens
    d = Doc(nlp.vocab, words=toks)
    for _, proc in nlp.pipeline: d = proc(d)
    T = S.extract(nlp, [d]); vh = [t for t in T if lo <= t["v_i"] < hi]; ah = [t for t in T if (t["s_i"] is not None and lo <= t["s_i"] < hi) or (t["o_i"] is not None and lo <= t["o_i"] < hi)]; use = vh or ah
    f = np.zeros(6 + len(MODS), dtype=np.float32)
    if use:
        f[0] = any(t["neg"] for t in use); f[1] = any(t["modal"] for t in use); f[2] = any(t["attrib"] or t["said_by"] for t in use); f[3] = any(t["passive"] for t in use)
        for t in use:
            for m in t["modal"]: 
                if m in MODS: f[6 + MODS.index(m)] = 1
    f[4] = 1.0 if vh else 0.0; f[5] = 1.0 if ah and not vh else 0.0
    q = 1.0 if d.text.strip().endswith("?") else 0.0
    return np.append(f, q)
F = np.array([notes(x["text"]) for x in items], dtype=np.float32)
rule = ((F[:, 0] == 0) & (F[:, 1] == 0)).astype(int)
def bal(pred): 
    P = (y == 1).sum(); N = (y == 0).sum(); return ((pred[y == 1] == 1).sum() / P + (pred[y == 0] == 0).sum() / N) / 2
def win(t, k=4):
    w = t.split(); a = w.index("«") if "«" in w else 0; b = w.index("»") if "»" in w else a
    return " ".join(w[max(0, a - k):a] + ["TRIGGER"] + w[b + 1:b + 1 + k]).lower()
WT = [win(x["text"]) for x in items]
def run(Xm, window=False):
    oof = np.zeros(len(y), dtype=int)
    for tr, te in GroupKFold(n_splits=5).split(Xm, y, grp):
        if window:
            tv = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True).fit([WT[i] for i in tr]); Xtr = sp.hstack([sp.csr_matrix(Xm[tr]), tv.transform([WT[i] for i in tr])]).tocsr(); Xte = sp.hstack([sp.csr_matrix(Xm[te]), tv.transform([WT[i] for i in te])]).tocsr()
        else: Xtr, Xte = Xm[tr], Xm[te]
        m = LogisticRegression(C=1.0, class_weight="balanced", max_iter=3000).fit(Xtr, y[tr]); oof[te] = m.predict(Xte)
    return oof
XF = np.hstack([X, F * 3.0]); oof_e = run(X); oof_en = run(XF); oof_w = run(X, True); oof_wn = run(XF, True); oof_notes = run(F)
oof_b, oof_c = oof_w, oof_wn
docs = sorted(set(grp)); idx = {g: np.where(grp == g)[0] for g in docs}; rng = np.random.default_rng(5); diffs = []
for _ in range(2000):
    pick = rng.choice(len(docs), len(docs)); ii = np.concatenate([idx[docs[k]] for k in pick]); yy = y[ii]
    if (yy == 1).sum() == 0 or (yy == 0).sum() == 0: continue
    ba = lambda p: ((p[ii][yy == 1] == 1).mean() + (p[ii][yy == 0] == 0).mean()) / 2; diffs.append(ba(oof_wn) - ba(oof_w))
res = {"v": "trackA-v0", "items": len(y), "documents": len(docs), "trigger_found_in_triples": round(float(((F[:, 4] + F[:, 5]) > 0).mean()), 3), "rule_not_negated_not_modal": round(float(bal(rule)), 3), "notes_only_logistic": round(float(bal(oof_notes)), 3), "embedding_head_alone": round(float(bal(oof_e)), 3), "embedding_head_plus_notes": round(float(bal(oof_en)), 3), "head_with_window_features_reproduced": round(float(bal(oof_w)), 3), "head_with_window_plus_notes": round(float(bal(oof_wn)), 3),
       "gain_over_window_head": round(float(bal(oof_wn) - bal(oof_w)), 3), "gain_bootstrap_95_over_window_head": [round(float(np.percentile(diffs, 2.5)), 3), round(float(np.percentile(diffs, 97.5)), 3)], "flag_rates": {"negated": round(float(F[:, 0].mean()), 3), "modal": round(float(F[:, 1].mean()), 3), "attributed": round(float(F[:, 2].mean()), 3)}}
by = {}
for g in ("CT+", "PS+", "CT-", "PS-", "Uu"):
    ii = [k for k, x in enumerate(items) if G[x["id"]]["factuality"] == g]; by[g] = {"n": len(ii), "window_head_says_happened": round(float(np.mean(oof_w[ii])), 3), "window_head_plus_notes_says_happened": round(float(np.mean(oof_wn[ii])), 3)}
res["share_predicted_happened_by_gold_class"] = by
json.dump(res, open("runs/harvest/relations/trackA_happened.json", "w"), indent=1); print(json.dumps(res, indent=1))
