"""Does a jury of three detectors per atom cut false positives versus one detector? Method fixed before looking at results.
Detectors per atom (each a different angle and engine; cut-off per detector chosen on validation stories for best F1 on its own target):
  D1 Glance (potion) on the full story, trained on Clef's wording a        D2 Scholar (e5-small, frozen) on the full story, trained on wording b
  D3 Glance on title + first 80 words (lead), trained on the agreed label    V  Glance full story, trained on the reversed question (veto)
Jury: STRONG yes = D1, D2, D3 all yes and V no; STRONG no = all three no; otherwise SPLIT (no move). Also reported: majority (2 of 3, V no).
Baseline: one detector, Glance full story trained on the agreed label (today's single head).
Truth: Clef's agreed label; scored on test pairs where Clef's two wordings agree (both yes or both no). Split by id hash (fit >= 2, val 1, test 0).
Atoms: the latest version of each atom (data/mm3-train/route-current.json). Scholar vectors are computed on the GPU here only to save time; at
run time it is a CPU model (~4 ms short text, ~200 ms full article).
Run: models/embed-zs/.venv/bin/python -I newsreader/bitmob/consensus_test.py"""
import json, glob, hashlib, numpy as np, torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from model2vec import StaticModel
from transformers import AutoTokenizer, AutoModel

D = "/workspace/data/mm3-train"; Q = {"first": {r["id"]: r for r in map(json.loads, open(f"{D}/queue.jsonl"))}}
ANG = {}
for c in ("civil_unrest|up", "war_terror|up", "crime|up", "cyber_insecurity|up"): ANG[c] = ("first", f"{c}|states", f"{c}|concrete", f"{c}|reversed")
for f in sorted(glob.glob("/workspace/newsreader/bitmob/batteries/evidence-v*.json")):
    B = json.load(open(f)); Q[B["name"]] = {r["id"]: r for r in map(json.loads, open(f"{D}/queue-{B['name']}.jsonl"))}
    for c in B["concerns"]: ANG[c["atom"]] = (B["name"], f"{c['atom']}|a", f"{c['atom']}|b", f"{c['atom']}|reversed")
use = json.load(open(f"{D}/route-current.json"))["atoms_used"]; ANG = {k: v for k, v in ANG.items() if k in use}
ids = sorted(set.intersection(*[set(q) for q in Q.values()])); rows = [Q["first"][i] for i in ids]
h = np.array([int(hashlib.sha256(i.encode()).hexdigest(), 16) % 5 for i in ids]); fit, val, test = h >= 2, h == 1, h == 0
ans = lambda w, k: np.array([Q[w][i]["answers"][k] for i in ids])
full = [r["title"] + ". " + r["text"] for r in rows]; lead = [r["title"] + ". " + " ".join(r["text"].split()[:80]) for r in rows]
pm = StaticModel.from_pretrained("minishlab/potion-base-32M"); G_full, G_lead = pm.encode(full), pm.encode(lead)
tok = AutoTokenizer.from_pretrained("intfloat/e5-small-v2"); m5 = AutoModel.from_pretrained("intfloat/e5-small-v2").cuda().eval(); S = []
with torch.no_grad():
    for i in range(0, len(full), 32):
        b = tok(["query: " + x for x in full[i:i + 32]], truncation=True, max_length=512, padding=True, return_tensors="pt").to("cuda")
        hh = m5(**b).last_hidden_state; mk = b["attention_mask"].unsqueeze(-1); S.append(((hh * mk).sum(1) / mk.sum(1)).cpu().numpy())
S_full = np.concatenate(S)
print(f"{len(ids)} stories ({fit.sum()} fit, {val.sum()} val, {test.sum()} test), {len(ANG)} atoms", flush=True)


def detector(X, y):
    """Train on fit, cut-off on val (best F1 on this detector's own target); returns yes/no for every story, or None if too few examples."""
    if y[fit].sum() < 3 or y[val].sum() < 2: return None
    p = LogisticRegression(C=4, class_weight="balanced", max_iter=4000).fit(X[fit], y[fit]).predict_proba(X)[:, 1]
    cut = max(np.linspace(.05, .95, 37), key=lambda t: f1_score(y[val], p[val] >= t)); return p >= cut


tot = {k: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for k in ("single", "majority", "strong")}; strong_n = split_n = pairs = 0; per = {}; skipped = []
for n, (w, ka, kb, kr) in ANG.items():
    a, b, r = ans(w, ka) >= .5, ans(w, kb) >= .5, ans(w, kr) >= .5; agreed = a & b
    d1, d2, d3, v, single = detector(G_full, a), detector(S_full, b), detector(G_lead, agreed), detector(G_full, r), detector(G_full, agreed)
    if any(x is None for x in (d1, d2, d3, single)): skipped.append(n); continue
    v = v if v is not None else np.zeros(len(ids), bool)
    votes = d1.astype(int) + d2 + d3; strong_yes = (votes == 3) & ~v; strong_no = votes == 0; majority = (votes >= 2) & ~v
    T = test & (a == b)                                         # score only where Clef's own two wordings agree
    y = agreed[T]; out = {}
    for k, pred in (("single", single[T]), ("majority", majority[T]), ("strong", strong_yes[T])):
        c = {"tp": int((pred & y).sum()), "fp": int((pred & ~y).sum()), "fn": int((~pred & y).sum()), "tn": int((~pred & ~y).sum())}
        for x in c: tot[k][x] += c[x]
        out[k] = c
    s = (strong_yes | strong_no)[T]; strong_n += s.sum(); split_n += (~s).sum(); pairs += T.sum()
    out["strong_share"] = round(float(s.mean()), 3); out["strong_no_accuracy"] = round(float((~y[strong_no[T]]).mean()), 4) if strong_no[T].any() else None
    out["split_with_clef_yes"] = int((~s & y).sum()); per[n] = out


def summary(c, stories):
    p = c["tp"] / max(1, c["tp"] + c["fp"]); r = c["tp"] / max(1, c["tp"] + c["fn"])
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / max(1e-9, p + r), 3), "false_pos_per_100_stories": round(100 * c["fp"] / stories, 1), **c}
stories = int((test).sum()); res = {"atoms_scored": len(per), "atoms_skipped_too_few_examples": skipped, "test_stories": stories, "pairs_scored": int(pairs),
       "single": summary(tot["single"], stories), "majority_2_of_3": summary(tot["majority"], stories), "jury_strong_yes": summary(tot["strong"], stories),
       "jury_strong_share": round(strong_n / pairs, 3), "jury_split_share": round(split_n / pairs, 3), "per_atom": per}
json.dump(res, open(f"{D}/consensus-test.json", "w"), indent=1)
for k in ("single", "majority_2_of_3", "jury_strong_yes"): print(f"{k:16s} " + json.dumps({x: res[k][x] for x in ("precision", "recall", "f1", "false_pos_per_100_stories", "tp", "fp", "fn")}))
print(f"jury reaches STRONG on {res['jury_strong_share']:.1%} of pairs, SPLIT on {res['jury_split_share']:.1%}; atoms scored {len(per)}, skipped {len(skipped)}")
