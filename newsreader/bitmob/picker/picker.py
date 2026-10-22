"""Free + BitMob story picker. usage: picker.py in.jsonl out.jsonl [--no-bitmob]
in rows: {id, state_text}. out rows: {id, score, rank, p_free (0-1 prob-ish)}; higher score = more likely to carry a condition.
Score = logistic combination (fitted on Clef-labelled TRAIN only) of: mined-keyword hits (lemma), + WordNet synonyms, change-language,
concreteness, entity density, bag-of-words logistic regression, and (unless --no-bitmob) the BitMob condition score."""
import sys, os, json, pickle, subprocess, numpy as np
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
from lib import *
inp, outp = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2]); use_bm = "--no-bitmob" not in sys.argv
M = pickle.load(open(D + "/picker_meta.pkl", "rb")); tmp = outp + ".nlp.tmp"
subprocess.check_call(["node", D + "/js/nlp.cjs", inp, tmp]); N = load_jsonl(tmp); os.remove(tmp)
R = load_jsonl(inp); ctab = conc_table(); L = [lemset(n) for n in N]
from scipy.stats import rankdata
S = {"kw_lemma": kw_score(L, M["kw_lemma"]), "kw_lemma+wordnet": kw_score(L, M["kw_wn"])}
for key, nm, f in (("chg", "change_language", lambda n: change_feats(n, ctab)), ("conc", "concreteness", lambda n: conc_feats(n, ctab)), ("ner", "entity_density", ner_feats)):
    S[nm] = M[key].decision_function(np.array([f(n) for n in N], float))
v, m = M["bow"]; S["bow_logreg"] = m.decision_function(v.transform([" ".join(n["lem"]) for n in N]))
if use_bm:
    subprocess.check_call(["/workspace/kev/.venv/bin/python", D + "/bm_score.py", inp, outp + ".bm.npy"], cwd="/workspace"); S["bitmob"] = np.load(outp + ".bm.npy"); os.remove(outp + ".bm.npy")
names = M["free"] + (["bitmob"] if use_bm else [])
sc = M["comb_bm" if use_bm else "comb_free"].decision_function(np.column_stack([S[k] for k in names]))
order = np.argsort(-sc); rank = np.empty(len(sc), int); rank[order] = np.arange(1, len(sc) + 1)
with open(outp, "w") as f:
    for r, s, k in zip(R, sc, rank): f.write(json.dumps({"id": r["id"], "score": float(s), "rank": int(k), "p": float(1 / (1 + np.exp(-s)))}) + "\n")
