"""Decomposition test: do support atoms (support-v1 battery), detected on CPU and rebuilt by rule, find a weak atom better than one direct head?
Targets (Clef's agreed label from the evidence batteries): prices.consumer_up, energy.price_up, energy.supply_cut, trust.wrongdoing.
Rules (support-v1.json "rebuild"): AND = lowest score, OR = highest. CPU features for every head: Glance full + Sieve's universal patterns
(numbers, money, up/down words, hedges, negation...), the same for direct and support heads. Cross-fitted: 5 folds over non-test stories, test
scored by the average of the fold models. Scored on test stories where Clef's two wordings for the target agree.
  A direct head on the target                       B rule over CPU support scores
  C learned combination of CPU support scores        D learned combination of support scores + the direct head
  T rule over Clef's own support answers (teacher-level check: is the decomposition logically right?)
Reports average precision (threshold-free) and the operating point chosen on training stories (precision >= 0.8).
Run: models/embed-zs/.venv/bin/python -I newsreader/bitmob/decompose_eval.py"""
import json, hashlib, re, numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import average_precision_score, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
D = "/workspace/data/mm3-train"; F = f"{D}/features"; ids = json.load(open(f"{F}/ids.json"))
SUP = {r["id"]: r for r in map(json.loads, open(f"{D}/queue-support-v1.jsonl"))}; EV = {}
for v in range(1, 7): EV.update({r["id"]: {**EV.get(r["id"], {}), **r["answers"]} for r in map(json.loads, open(f"{D}/queue-evidence-v{v}.jsonl"))})
keep = [k for k, i in enumerate(ids) if i in SUP]; ids = [ids[k] for k in keep]
B = json.load(open("/workspace/newsreader/bitmob/batteries/support-v1.json")); SN = json.load(open(f"{F}/sieve_names.json")); n_univ = 3 * (len(SN["patterns"]) + 3) + 1
G = np.load(f"{F}/glance_full.npy")[keep]; S = np.load(f"{F}/sieve.npy")[keep][:, :n_univ]
h = np.array([int(hashlib.sha256(i.encode()).hexdigest(), 16) % 5 for i in ids]); test = h == 0; TRN = ~test; tr = np.where(TRN)[0]
S = StandardScaler().fit(S[TRN]).transform(S); X = np.hstack([G, S * 0.1])
yes = lambda src, k: np.array([src[i][k] >= .5 for i in ids])
def crossfit(y):
    p = np.zeros(len(ids)); pt = np.zeros(int(test.sum()))
    for a, b in StratifiedKFold(5, shuffle=True, random_state=0).split(tr, y[tr]):
        m = LogisticRegression(C=4, class_weight="balanced", max_iter=5000).fit(X[tr[a]], y[tr[a]]); p[tr[b]] = m.predict_proba(X[tr[b]])[:, 1]; pt += m.predict_proba(X[test])[:, 1] / 5
    p[test] = pt; return p
SA = {c["atom"].split(".")[1]: c["atom"] for c in B["concerns"]}; NAME = {"price": "price_mentioned", "change": "amount_changed", "up": "direction_up", "payer": "payer_consumer", "everyday": "good_everyday",
                                                                   "energy": "energy_mentioned", "disrupted": "supply_disrupted", "official": "official_actor", "accused": "accused_wrongdoing"}
sup_cpu, sup_clef, rep = {}, {}, {"support_atoms": {}, "targets": {}}
for short, nm in NAME.items():
    atom = SA[nm]; a, b = yes({i: SUP[i]["answers"] for i in ids}, f"{atom}|a"), yes({i: SUP[i]["answers"] for i in ids}, f"{atom}|b")
    sup_clef[short] = a & b; sup_cpu[short] = crossfit(a & b); T = test & (a == b)
    rep["support_atoms"][short] = {"clef_yes": int((a & b).sum()), "teacher_self_f1": round(float(f1_score(a, b)), 3), "cpu_avg_precision": round(float(average_precision_score((a & b)[T], sup_cpu[short][T])), 3)}
    print(f"support {short:10s} Clef yes {int((a & b).sum()):4d}  Clef a~b {rep['support_atoms'][short]['teacher_self_f1']:.2f}  CPU average precision {rep['support_atoms'][short]['cpu_avg_precision']:.2f}", flush=True)
def rule(expr, v):
    """expr over support names with & and | and parentheses; v: name -> array; & = min, | = max (works for booleans and scores)"""
    toks = re.findall(r"\w+|[&|()]", expr); pos = [0]
    def atom_():
        t = toks[pos[0]]; pos[0] += 1
        if t == "(": r = or_(); pos[0] += 1; return r
        return v[t].astype(float)
    def and_():
        r = atom_()
        while pos[0] < len(toks) and toks[pos[0]] == "&": pos[0] += 1; r = np.minimum(r, atom_())
        return r
    def or_():
        r = and_()
        while pos[0] < len(toks) and toks[pos[0]] == "|": pos[0] += 1; r = np.maximum(r, and_())
        return r
    return or_()
def op_point(score, y):
    st, yt = score[tr], y[tr]; cut = next((t for t in np.linspace(.02, .99, 98) if (st >= t).sum() >= 3 and yt[st >= t].mean() >= .8), .99); return cut
for tgt, expr in B["rebuild"].items():
    a, b = yes(EV, f"{tgt}|a"), yes(EV, f"{tgt}|b"); y = a & b; T = test & (a == b); out = {}
    direct = crossfit(y); cpu_rule = rule(expr, sup_cpu); Z = np.column_stack([sup_cpu[k] for k in NAME])
    learned = np.zeros(len(ids)); learned[tr] = cross_val_predict(LogisticRegression(class_weight="balanced", max_iter=3000), Z[tr], y[tr], cv=StratifiedKFold(5, shuffle=True, random_state=0), method="predict_proba")[:, 1]
    learned[test] = LogisticRegression(class_weight="balanced", max_iter=3000).fit(Z[tr], y[tr]).predict_proba(Z[test])[:, 1]
    Z2 = np.column_stack([Z, direct]); both = np.zeros(len(ids)); both[tr] = cross_val_predict(LogisticRegression(class_weight="balanced", max_iter=3000), Z2[tr], y[tr], cv=StratifiedKFold(5, shuffle=True, random_state=0), method="predict_proba")[:, 1]
    both[test] = LogisticRegression(class_weight="balanced", max_iter=3000).fit(Z2[tr], y[tr]).predict_proba(Z2[test])[:, 1]
    for name, sc in (("A direct head", direct), ("B rule over CPU supports", cpu_rule), ("C learned over CPU supports", learned), ("D supports + direct", both)):
        c = op_point(sc, y); q = (sc >= c)[T]; yt = y[T]
        out[name] = {"avg_precision": round(float(average_precision_score(yt, sc[T])), 3), "precision": round(float((q & yt).sum() / max(1, q.sum())), 3), "recall": round(float((q & yt).sum() / max(1, yt.sum())), 3)}
    tr_rule = rule(expr, sup_clef).astype(bool)[T]; yt = y[T]
    out["T rule over Clef's supports"] = {"precision": round(float((tr_rule & yt).sum() / max(1, tr_rule.sum())), 3), "recall": round(float((tr_rule & yt).sum() / max(1, yt.sum())), 3)}
    rep["targets"][tgt] = {"rule": expr, "test_yes": int(y[T].sum()), **out}
    print(f"\n{tgt} = {expr}   (test positives {int(y[T].sum())})")
    for k, v in out.items(): print(f"  {k:30s} " + "  ".join(f"{m} {x}" for m, x in v.items()))
json.dump(rep, open(f"{D}/decompose-eval.json", "w"), indent=1)
# ---- receipts: 95% bootstrap interval (300 story resamples) on average precision, each method minus the direct head, per target
rng = np.random.default_rng(0); rep["bootstrap"] = {}
for tgt, expr in B["rebuild"].items():
    a, b = yes(EV, f"{tgt}|a"), yes(EV, f"{tgt}|b"); y = a & b; T = np.where(test & (a == b))[0]
    direct = crossfit(y); cpu_rule = rule(expr, sup_cpu); sc = {"A": direct, "B": cpu_rule}; d = {"B - A": []}
    for _ in range(300):
        s = rng.choice(T, len(T))
        if y[s].sum() < 2: continue
        d["B - A"].append(average_precision_score(y[s], cpu_rule[s]) - average_precision_score(y[s], direct[s]))
    v = np.array(d["B - A"]); rep["bootstrap"][tgt] = {"rule_minus_direct_ap": [round(float(v.mean()), 3)] + [round(float(x), 3) for x in np.percentile(v, [2.5, 97.5])], "test_positives": int(y[T].sum())}
    print(f"bootstrap {tgt:22s} rule minus direct average precision {rep['bootstrap'][tgt]['rule_minus_direct_ap']}  (test positives {int(y[T].sum())})")
json.dump(rep, open(f"{D}/decompose-eval.json", "w"), indent=1)
