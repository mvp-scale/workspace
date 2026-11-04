"""T21: the 51 traits as present/absent flags scored under the READY RULE (GO.md, ledger L492-L495): agreement over ALL eval items with the Wilson low end >= 0.80, low end above always saying the common answer, and for rare flags (present share < 0.5) recall >= 0.80 of real cases. Threshold set on a 12.5% validation split of train to reach recall 0.80; eval = Sonnet-labelled devq items. Readers: frozen leaf, Qwen3-4B, concatenation. /workspace/models/embed-zs/.venv/bin/python -I traits_ready.py"""
import json, math, numpy as np
from sklearn.linear_model import LogisticRegression
J = lambda p: [json.loads(l) for l in open(p)]; D = "runs/pulse/ceiling/"; ids = json.load(open(D + "main_ids.json"))["ids"]; pos = {i: k for k, i in enumerate(ids)}
Q = json.load(open("specs/traits_v0.json"))["questions"]; qid = [q["id"] for q in Q]; grp = {q["id"]: q["group"] for q in Q}; qtext = {q["id"]: q["question"] for q in Q}
tr = {r["item_id"]: r["label"] for r in J("runs/pulse/traits_main/train/labels.jsonl")}; ev = {r["item_id"]: r["label"] for r in J("runs/pulse/traits_main/eval/labels.jsonl")}
for r in J("runs/pulse/traits_pilot/sonnet_r1/labels.jsonl"): ev.setdefault(r["item_id"], r["label"])
import os
tri = [i for i in tr if i in pos]; tri = tri[:int(len(tri) * float(os.environ.get("TR_FRAC", 1)))]; evi = [i for i in ev if i in pos]
def wil(k, m, z=1.96):
    p = k / m; d = 1 + z * z / m; c = (p + z * z / (2 * m)) / d; s = z * math.sqrt(p * (1 - p) / m + z * z / (4 * m * m)) / d; return c - s
out = {}
for en in ("leaf", "qwen3-4b", "ens"):
    E = np.load(D + f"{en}_main.npy").astype(np.float32); Xt = E[[pos[i] for i in tri]]; Xe = E[[pos[i] for i in evi]]; rows = {}
    for q in qid:
        yt = np.array([-1 if tr[i][q] == "cannot tell" else int(tr[i][q] != "not at all") for i in tri]); ye = np.array([-1 if ev[i][q] == "cannot tell" else int(ev[i][q] != "not at all") for i in evi]); mt, me = yt >= 0, ye >= 0
        y = ye[me]; share = float(y.mean()); guess = max(share, 1 - share)
        if yt[mt].sum() < 8 or y.sum() < 5:
            k = int((y == 0).sum()); rows[q] = {"group": grp[q], "share": round(share, 3), "agree": round(k / len(y), 3), "low": round(wil(k, len(y)), 3), "guess": round(guess, 3), "recall": None, "ready": False, "why": "too few real cases to learn or test"}; continue
        rng = np.random.RandomState(0); idx = np.where(mt)[0]; rng.shuffle(idx); nv = max(30, len(idx) // 8); vi, ti = idx[:nv], idx[nv:]
        clf = LogisticRegression(C=1.0, max_iter=300, class_weight="balanced").fit(Xt[ti], yt[ti]); pv = clf.predict_proba(Xt[vi])[:, 1]; yv = yt[vi]
        thr = 0.5
        if yv.sum() >= 3: thr = float(np.sort(pv[yv == 1])[max(0, int(0.2 * yv.sum()) - 0)]) - 1e-9
        p = clf.predict_proba(Xe[me])[:, 1]; pr = p >= thr; k = int((pr == (y == 1)).sum()); rec = float(pr[y == 1].mean()) if y.sum() else None; low = wil(k, len(y))
        rare = share < 0.5; ok = low >= 0.80 and low > guess and (not rare or (rec is not None and rec >= 0.80))
        rows[q] = {"group": grp[q], "share": round(share, 3), "agree": round(k / len(y), 3), "low": round(low, 3), "guess": round(guess, 3), "recall": round(rec, 3) if rec is not None else None, "ready": bool(ok), "why": "" if ok else ("low end under 0.80" if low < 0.80 else "does not beat always guessing" if low <= guess else "finds under 80% of real cases")}
    out[en] = rows; print(en, "READY", sum(r["ready"] for r in rows.values()), "of", len(rows), "| mean agree", round(float(np.mean([r["agree"] for r in rows.values()])), 3), flush=True)
json.dump(out, open("runs/pulse/traits_ready.json", "w"), indent=1)
best = {}
for q in qid:
    for en in out:
        if out[en][q]["ready"]: best[q] = en; break
print("ready by any reader:", len(best), "of 51"); print("by group:", {g: sum(1 for q in best if grp[q] == g) for g in sorted(set(grp.values()))})
for q, en in list(best.items())[:60]: print(f"  {q} [{grp[q]}] {en}: agree {out[en][q]['agree']} low {out[en][q]['low']} guess {out[en][q]['guess']} recall {out[en][q]['recall']} share {out[en][q]['share']} - {qtext[q][:70]}")
