"""Score Echo against Clef's same-event judgements (data/mm3-train/echo-pairs.json from echo_pairs.py).
Truth: same event = questions 1 and 2 yes and 3 no; different = 1 and 2 no and 3 yes; anything else = Clef split (counted, not scored).
Scores compared (AUC, and precision/recall at the cut chosen on half the pairs, applied to the other half):
  Echo        Glance cosine (the engine as built)       Scholar  e5 cosine of the two full stories (second approach: a word-order engine)
  Titles      word overlap (Jaccard) of the two titles  Echo + place  Glance cosine, halved when Locate finds no shared country
Run: models/embed-zs/.venv/bin/python -I newsreader/bitmob/echo_eval.py"""
import json, re, csv, numpy as np
from sklearn.metrics import roc_auc_score
D = "/workspace/data/mm3-train"; F = f"{D}/features"; ids = json.load(open(f"{F}/ids.json")); first = {r["id"]: r for r in map(json.loads, open(f"{D}/queue.jsonl"))}; rows = [first[i] for i in ids]
P = json.load(open(f"{D}/echo-pairs.json")); S = np.load(f"{F}/scholar_full.npy"); S /= np.linalg.norm(S, axis=1, keepdims=True)
cn = [r["name"] for r in csv.DictReader(open("/workspace/probes/world-engine/data/countries_world100.csv"))]; CRE = re.compile(r"\b(" + "|".join(map(re.escape, sorted(cn, key=len, reverse=True))) + r")\b")
tw = lambda t: {w for w in re.findall(r"[a-z]{3,}", t.lower())}
y, keep, split = [], [], 0
for k, p in enumerate(P):
    a = {int(n): v for n, v in p["a"].items()}
    if a[1] >= .5 and a[2] >= .5 and a[3] < .5: y.append(1); keep.append(k)
    elif a[1] < .5 and a[2] < .5 and a[3] >= .5: y.append(0); keep.append(k)
    else: split += 1
y = np.array(y); Pk = [P[k] for k in keep]
def place(p):
    A, B = rows[p["i"]], rows[p["j"]]; ca = set(CRE.findall(A["title"] + " " + A["text"][:2000])); cb = set(CRE.findall(B["title"] + " " + B["text"][:2000])); return bool(ca & cb) or (not ca and not cb)
scores = {"Echo (Glance cosine)": np.array([p["glance_cos"] for p in Pk]), "Scholar cosine": np.array([float(S[p["i"]] @ S[p["j"]]) for p in Pk]),
          "Titles word overlap": np.array([len(tw(rows[p["i"]]["title"]) & tw(rows[p["j"]]["title"])) / max(1, len(tw(rows[p["i"]]["title"]) | tw(rows[p["j"]]["title"]))) for p in Pk])}
scores["Echo + place (Locate)"] = scores["Echo (Glance cosine)"] * np.array([1.0 if place(p) else 0.5 for p in Pk])
print(f"{len(P)} pairs judged; Clef consensus on {len(keep)} ({y.sum()} same event, {len(y) - y.sum()} different), split {split}")
half = np.arange(len(y)) % 2 == 0; out = {"pairs": len(P), "consensus": len(keep), "same_event": int(y.sum()), "split": split, "scores": {}}
for name, s in scores.items():
    auc = roc_auc_score(y, s) if 0 < y.sum() < len(y) else float("nan")
    t = max(np.unique(s[half]), key=lambda t: (lambda q: 2 * (q & y[half]).sum() / max(1, q.sum() + y[half].sum()))(s[half] >= t)); q = s[~half] >= t; yy = y[~half]
    pr = (q & yy).sum() / max(1, q.sum()); rc = (q & yy).sum() / max(1, yy.sum())
    out["scores"][name] = {"auc": round(float(auc), 3), "cut": round(float(t), 3), "precision": round(float(pr), 3), "recall": round(float(rc), 3)}
    print(f"  {name:24s} AUC {auc:.2f}  at cut {t:.2f}: precision {pr:.2f} recall {rc:.2f} (cut chosen on the other half)")
json.dump(out, open(f"{D}/echo-eval.json", "w"), indent=1)
# second look: is the place rule the problem, or place itself? And the cheap combination (Glance cosine + title overlap, rank average).
from scipy.stats import rankdata
def ctry(p, which):
    r = rows[p[which]]; return set(CRE.findall(r["title"] + " " + r["text"][:2000]))
found = np.array([bool(ctry(p, "i")) and bool(ctry(p, "j")) for p in Pk]); shared = np.array([bool(ctry(p, "i") & ctry(p, "j")) for p in Pk])
print(f"  place check: both stories name a country in {found.mean():.0%} of pairs; among same-event pairs where both name one, they share it {shared[found & (y == 1)].mean():.0%}; among different-event pairs {shared[found & (y == 0)].mean():.0%}")
soft = scores["Echo (Glance cosine)"] * np.where(found & ~shared, 0.8, 1.0)
combo = (rankdata(scores["Echo (Glance cosine)"]) + rankdata(scores["Titles word overlap"])) / 2
for name, s in (("Echo, place only penalises when both name different countries", soft), ("Echo + titles (rank average)", combo)):
    print(f"  {name:62s} AUC {roc_auc_score(y, s):.2f}")
