"""Removal tests on the jury (each detector removed in turn, the veto removed) and a two-stage cascade. Setup copied from consensus_test.py.\nDoes a jury of three detectors per atom cut false positives versus one detector? Method fixed before looking at results.
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



VARIANTS = {"full jury (Glance a, Scholar b, Glance lead) + veto": ("d1", "d2", "d3"), "without Scholar (Glance a, Glance lead)": ("d1", "d3"),
            "without Glance lead (Glance a, Scholar b)": ("d1", "d2"), "without Glance full (Scholar b, Glance lead)": ("d2", "d3")}
res = {k: {"tp": 0, "fp": 0, "fn": 0} for k in list(VARIANTS) + ["no veto (full jury)", "single head", "cascade: Glance pair, Scholar only on split"]}
esc = pairs = 0; esc2 = [0]; story_esc = np.zeros(len(ids), bool)
for n, (w, ka, kb, kr) in ANG.items():
    a, b, r = ans(w, ka) >= .5, ans(w, kb) >= .5, ans(w, kr) >= .5; agreed = a & b
    det = {"d1": detector(G_full, a), "d2": detector(S_full, b), "d3": detector(G_lead, agreed)}; v = detector(G_full, r); single = detector(G_full, agreed)
    if any(x is None for x in list(det.values()) + [single]): continue
    v = v if v is not None else np.zeros(len(ids), bool); T = test & (a == b); y = agreed[T]
    preds = {k: np.all([det[d] for d in ds], 0) & ~v for k, ds in VARIANTS.items()}
    preds["no veto (full jury)"] = det["d1"] & det["d2"] & det["d3"]; preds["single head"] = single
    s1_yes = det["d1"] & det["d3"]; s1_no = ~det["d1"] & ~det["d3"]; split = ~(s1_yes | s1_no)          # stage 1: the two Glance detectors
    preds["cascade: Glance pair, Scholar only on split"] = ((s1_yes) | (split & det["d2"])) & ~v               # stage 2: Scholar breaks the tie
    esc += split[T].sum(); pairs += T.sum(); esc2[0] += (~s1_no)[T].sum(); story_esc |= (~s1_no) & test
    for k, p in preds.items():
        p = p[T]; res[k]["tp"] += int((p & y).sum()); res[k]["fp"] += int((p & ~y).sum()); res[k]["fn"] += int((~p & y).sum())
stories = int(test.sum()); out = {}
for k, c in res.items():
    p = c["tp"] / max(1, c["tp"] + c["fp"]); rc = c["tp"] / max(1, c["tp"] + c["fn"]); out[k] = {"precision": round(p, 3), "recall": round(rc, 3), "fp_per_100": round(100 * c["fp"] / stories, 1)}
    print(f"{k:48s} precision {p:.2f}  recall {rc:.2f}  false positives/100 stories {100 * c['fp'] / stories:5.1f}")
print(f"cascade escalates {esc / pairs:.1%} of story-atom pairs to Scholar")
print(f"stories needing Scholar at least once (cascade B): {story_esc[test].mean():.1%} of {int(test.sum())} test stories")
print(f"cascade B (Glance settles NO only; any Glance yes goes to Scholar, which must agree): same verdicts as the full jury, Scholar runs on {esc2[0] / pairs:.1%} of pairs")
json.dump({"variants": out, "cascade_escalated": round(esc / pairs, 3)}, open(f"{D}/ablation-jury.json", "w"), indent=1)
