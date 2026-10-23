"""Build checker training pairs from Clef-labelled TRAIN rows only (ds rows with w>=4) x BitMob's raw shortlist. Asserts: no frozen-test id, no tune id.
  kev/.venv/bin/python newsreader/bitmob/checker/ck_build.py OUTDIR
Per story: conditions = attributes with BitMob raw p >= cut98 (fitted on the 894 tune rows) + every Clef trigger (>=0.65) + 2 random, one random wording each, weight 3 on Clef yes (>=.5);
gate = all 4 questions; expected = asked keys with BitMob p >= tune-fit 98% cut or Clef >= .5, + 1 random asked key. Targets = Clef's soft values (conditions: mean of the two wordings)."""
import os, sys, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ck_questions as Q
O = "/workspace/data/checker"; B = "/workspace/data/kaggle/mh_r6c1"; out = sys.argv[1]; os.makedirs(out, exist_ok=True); rng = np.random.RandomState(0)
tr, tu = np.load(f"{O}/bm_train.npz"), np.load(f"{O}/bm_tune.npz"); K = json.load(open(f"{B}/ds/keys.json")); tt = json.load(open(f"{B}/ds/texts.json"))
test = {json.loads(l)["id"] for l in open("/workspace/data/clef-labels/test.jsonl")}; tuneids = set(json.load(open(f"{B}/tune/keys.json"))["ids"])
ids = [str(i) for i in tr["ids"]]; assert not (set(ids) & test) and not (set(ids) & tuneids), "leak"
cond, expk = [k.split("|") for k in K["cond"]], K["expected"]
qt, qix = [], {}
def qid(t):
    if t not in qix: qix[t] = len(qt); qt.append(t)
    return qix[t]
Aq = [(qid(Q.cond_q(d, dr, int(i), 0)), qid(Q.cond_q(d, dr, int(i), 1))) for d, dr, i in cond]; Gq = [qid(Q.gate_q(k)) for k in Q.GATE_Q]; Eq = [qid(Q.exp_q(*k.split("|"))) for k in expk]
gidx = [K["gate"].index(k) for k in Q.GATE_Q]
# cuts fitted on tune only
yc = tu["y_cond"] >= 0.65; s = np.sort(tu["cond"][yc])[::-1]; cut_c = float(s[int(0.98 * len(s)) - 1])
ye = (tu["y_exp"] >= 0.5) & (tu["y_expm"] > 0); s = np.sort(tu["expected"][ye])[::-1]; cut_e = float(s[int(0.98 * len(s)) - 1])
print("cond cut98", cut_c, "expected cut98", cut_e, "tune trigger cells", yc.sum(), ye.sum())
S, QI, T, W, KD = [], [], [], [], []
def add(n, q, t, w, kd): S.append(n); QI.append(q); T.append(t); W.append(w); KD.append(kd)
for n in range(len(ids)):
    Hn, Yn = tr["cond"][n], tr["y_cond"][n]; sel = set(np.where((Hn >= cut_c) | (Yn >= 0.65))[0]) | set(rng.choice(len(Yn), 2, replace=False))
    for j in sel: add(n, Aq[j][rng.randint(2)], float(Yn[j]), 3.0 if Yn[j] >= 0.5 else 1.0, 0)
    for q, g in zip(Gq, gidx): add(n, q, float(tr["y_gate"][n, g]), 1.0, 1)
    m = tr["y_expm"][n] > 0
    if m.any():
        cand = np.where(m)[0]; sel = set(cand[(tr["expected"][n][cand] >= cut_e) | (tr["y_exp"][n][cand] >= 0.5)]) | {int(rng.choice(cand))}
        for j in sel: add(n, Eq[j], float(tr["y_exp"][n, j]), 3.0 if tr["y_exp"][n, j] >= 0.5 else 1.0, 2)
S, QI, T, W, KD = map(np.array, (S, QI, T, W, KD))
np.savez_compressed(f"{out}/pairs.npz", s=S.astype(np.int32), q=QI.astype(np.int32), t=T.astype(np.float32), w=W.astype(np.float32), kind=KD.astype(np.int8))
json.dump([tt[i] for i in tr["keep"]], open(f"{out}/stories.json", "w")); json.dump(qt, open(f"{out}/questions.json", "w"))
json.dump({"cut_cond98": cut_c, "cut_exp98": cut_e}, open(f"{out}/cuts98.json", "w"))
print("stories", len(ids), "pairs", len(S), {k: int((KD == i).sum()) for i, k in enumerate(("cond", "gate", "expected"))}, "yes(>=.5):", {k: int(((KD == i) & (T >= .5)).sum()) for i, k in enumerate(("cond", "gate", "expected"))}, "questions", len(qt))
