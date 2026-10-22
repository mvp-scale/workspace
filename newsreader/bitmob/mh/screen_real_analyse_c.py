"""F-0110 job 2 analysis: variant C (shortlisted attribute + k neighbours of its block) vs A, B and full battery, same 298 stories. Only the shortlisted questions' answers are used (neighbour answers are ignored).
  CUDA_VISIBLE_DEVICES= /workspace/kev/.venv/bin/python newsreader/bitmob/mh/screen_real_analyse_c.py OUT_C.jsonl   (A/B/ctrl from data/diag/screen_real/clef_answers_all.jsonl)"""
import os, sys, json, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import classify as C
D = "/workspace/data/diag/screen_real"; Z = np.load(f"{D}/prep.npz"); H = Z["H"]; idx = Z["idx"]
R = [json.loads(l) for l in open("/workspace/data/clef-labels/test.jsonl")]; K = json.load(open("/workspace/data/kaggle/mh_r6c1/out/mh/keys.json")); A = [k.split("|") for k in K["cond"]]
pos_of = {R[i]["id"]: n for n, i in enumerate(idx)}
S = {json.loads(l)["id"]: json.loads(l) for l in open(f"{D}/stories.jsonl")}
O = {}; [O.__setitem__(json.loads(l)["id"], json.loads(l)) for l in open(f"{D}/clef_answers_all.jsonl")]
OC = {}; [OC.__setitem__(json.loads(l)["id"], json.loads(l)) for l in open(sys.argv[1])]
keys = lambda rd: {(x["dial"], x["direction"]) for x in rd["readings"] if x["direction"] != "conflict"}
def read(n, newP):
    P = dict(R[idx[n]]["P"])
    for j, (d, dr, i) in enumerate(A): P[f"a|{d}|{dr}|{i}|0"] = P[f"a|{d}|{dr}|{i}|1"] = float(H[n, j])
    P.update(newP); return keys(C.read(P))
def score(name, get, ids):
    tp = fp = pos = neg = same = 0; dif = []; secs = []; nq = []
    for i in ids:
        n = pos_of[i]; r = R[idx[n]]; sk = {q for g in S[i]["A"] for q in g}; P_new, t, q = get(i); P_new = {k: v for k, v in P_new.items() if k in sk}
        assert set(P_new) == sk, (i, len(sk), len(P_new))
        b = keys(r["read"]); m = read(n, P_new); tp += len(m & b); fp += len(m - b); pos += len(b); neg += 78 - len(b); same += (m == b); secs.append(t); nq.append(q); dif += [abs(P_new[k] - r["P"][k]) for k in P_new]
    print(f"{name:34s} stories {len(ids)}: readings caught {tp}/{pos} = {tp/max(pos,1):.1%}; false alarms {fp} ({fp/max(neg,1):.4%}); identical readings {same}/{len(ids)} = {same/max(len(ids),1):.1%}; Clef s/story mean {np.mean(secs):.2f} (median {np.median(secs):.2f}); Clef questions/story {np.mean(nq):.1f}; mean |new-stored| answer {np.mean(dif):.3f}")
ids = [i for i in OC if i in O and i in S]
cnt = lambda v: (lambda i: sum(map(len, S[i][v])))
print(f"stories answered in both runs: {len(ids)} of 298")
score("A bare shortlisted questions", lambda i: (O[i]["A"], O[i]["tA"], sum(map(len, S[i]["A"]))), ids)
score("B whole 20-question blocks", lambda i: (O[i]["B"], O[i]["tB"], sum(map(len, S[i]["B"]))), ids)
SC = {json.loads(l)["id"]: json.loads(l) for l in open(f"{D}/stories_c.jsonl")}
for v in ("C3", "C7"): score(f"{v} +{v[1:]} neighbours", lambda i, v=v: (OC[i][v], OC[i]["t" + v], sum(map(len, SC[i][v]))), ids)
Cn = [o for o in O.values() if "F" in o]; print(f"full battery (control, {len(Cn)} stories, same Kaggle T4s earlier): Clef s/story mean {np.mean([o['tF'] for o in Cn]):.2f}")
