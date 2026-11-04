"""Repair for review MM3-0555 (hosted Jev): presence figures that are NOT scored against a teacher that trained the scored model.
ph = Haiku-trained presence model -> scored vs Sonnet. ps = Sonnet-trained presence model -> scored vs Haiku. The shipped blend (ph+ps) is scored vs both and labelled circular-benefit.
Loads only runs/expert1/expert1_v1.pkl. Cut-offs: 80 percent running agreement on random half A, reported on half B (same split seed as build_expert.py)."""
import json, glob, re, pickle, pathlib, numpy as np, scipy.sparse as sp, warnings
warnings.filterwarnings("ignore")
from model2vec import StaticModel
H0 = pathlib.Path(".").resolve(); J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
art = pickle.load(open(H0 / "runs/expert1/expert1_v1.pkl", "rb")); old = {}; sn = {}
for f in glob.glob(str(H0 / "runs/p7/chunk*/labels.jsonl")):
    for r in J(f): old[r["item_id"]] = r["label"]
for f in glob.glob(str(H0 / "runs/p7b/*/labels.jsonl")):
    for r in J(f): sn[r["item_id"]] = r["label"]
pool = {r["id"]: r for r in J(H0 / "data/pool_train.jsonl")}; oi = sorted(old); dt = np.array([pool[i]["date"] or "" for i in oi]); o = np.argsort(dt, kind="stable"); o = o[dt[o] != ""]
test = [oi[k] for k in np.array_split(o, 5)[4]]; vt = [i for i in test if i in sn]; txt = [re.sub(r"\s+", " ", pool[i]["text"]) for i in vt]
xwc = sp.hstack([art["vw"].transform(txt), art["vc"].transform(txt)]).tocsr(); lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
ph = art["ph"].predict_proba(xwc)[:, 1]; ps = art["ps"].predict_proba(xwc)[:, 1]; bl = 1 / (1 + np.exp(-(lg(ph) + lg(ps)) / 2))
yh = np.array([1 if old[i]["conditions"] else 0 for i in vt]); ys = np.array([1 if sn[i]["conditions"] else 0 for i in vt])
perm = np.random.RandomState(3).permutation(len(vt)); A_, B_ = perm[:len(vt) // 2], perm[len(vt) // 2:]
def cut(conf, ok):
    q = np.argsort(-conf); run = np.cumsum(ok[q]) / np.arange(1, len(q) + 1); idx = np.where(run >= 0.8)[0]; return float(conf[q][idx.max()]) if len(idx) else 1.01
def rep(p, y):
    conf = np.maximum(p, 1 - p); ok = ((p > .5).astype(int) == y); c = cut(conf[A_], ok[A_]); a = conf[B_] >= c
    return {"forced_agreement": round(float(ok.mean()), 3), "answered_share_B": round(float(a.mean()), 3), "agreement_on_answered_B": round(float(ok[B_][a].mean()), 3) if a.any() else None}
res = {"n": len(vt), "NON_CIRCULAR_ph_haiku_trained_vs_sonnet": rep(ph, ys), "NON_CIRCULAR_ps_sonnet_trained_vs_haiku": rep(ps, yh), "CIRCULAR_BENEFIT_blend_vs_sonnet": rep(bl, ys), "CIRCULAR_BENEFIT_blend_vs_haiku": rep(bl, yh),
       "note": "The headline presence figure for the DoD is the first line. The shipped blend is better against either teacher partly because it was trained on that teacher."}
json.dump(res, open(H0 / "runs/expert1/noncircular_report.json", "w"), indent=1); print(json.dumps(res, indent=1))
