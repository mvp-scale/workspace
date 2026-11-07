"""Track 2 (pre-registered L931): playbook 00 cascade per condition kind. Stages: G1-like keyword rules, G3a hashed n-gram + logistic, G3b encoder head on story (64 tokens), G3b' encoder on sentences (first 4 sentences, max and mean pooled). Same items, grouped 5-fold CV (group = first 60 normalised characters, so syndicated copies stay together). Scored against Sonnet labels and, on items Haiku also labelled, Haiku labels, with the threshold fixed once per kind on out-of-fold scores vs Sonnet. Ceiling = labeller agreement from runs/pulse/perkind_pooled.json; pass = F1 within 0.05 of the ceiling vs both labellers.
    /workspace/models/embed-zs/.venv/bin/python kind_cascade.py   (from projects/world-state)"""
import json, re, os, time, numpy as np, onnxruntime as ort
from tokenizers import Tokenizer
from sklearn.feature_extraction.text import HashingVectorizer, TfidfTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
RULES = {
 "air_pollution": r"smog|air quality|air pollution|particulate|pm ?2\.5|pm ?10|\bhaze\b|\baqi\b|toxic (?:air|fumes)",
 "biodiversity_loss": r"biodiversity|extinct|endangered|species (?:decline|loss|at risk)|deforestation|habitat (?:loss|destruction)|wildlife (?:decline|loss)|coral bleach|poaching",
 "civil_unrest": r"protest|\briot|unrest|demonstrat|clashes?|tear gas|curfew|looting|uprising|\bcoup\b",
 "climate_stress": r"heat ?wave|drought|wildfire|flood|record (?:heat|temperature)|extreme weather|hurricane|cyclone|sea level|\bstorm",
 "cyber_insecurity": r"cyber|\bhack|ransomware|data breach|malware|phishing|ddos|vulnerabilit",
 "disruption": r"outage|shut ?down|suspended|cancel+ed|delays?\b|blackout|\bstrike|closure|disrupt",
 "energy_fuel": r"\bfuel|petrol|gasoline|diesel|oil price|gas price|electricity price|energy price|power cut|energy crisis|\blng\b|crude",
 "fiscal_strain": r"deficit|public debt|budget (?:gap|shortfall)|austerity|debt crisis|borrowing|bailout|downgrade|sovereign debt|spending cuts",
 "food_insecurity": r"famine|hunger|food (?:shortage|insecurity|prices|crisis)|malnutrition|starvation|food aid|\bgrain",
 "housing_cost": r"\brent\b|\brents\b|housing (?:cost|prices|crisis|afford)|mortgage|homeless|house prices|evict",
 "job_security": r"layoff|lay-off|job cuts|redundanc|unemployment|jobless|laid off|hiring freeze|furlough|job losses",
 "land_degradation": r"\bsoil|desertif|erosion|land degradation|landslide|overgraz|salinis|mining damage",
 "pay_growth": r"\bwages?\b|pay (?:rise|growth|deal)|salar|earnings|minimum wage",
 "prices": r"inflation|prices? (?:rose|rise|rising|surge|jump|soar|hike|increase)|cost of living|consumer prices|\bcpi\b",
 "supply_chain_strain": r"supply chain|shortage|port (?:congestion|delays)|backlog|shipping (?:delays|costs)|container|logistics|bottleneck|stockpil",
 "water_stress": r"water (?:shortage|crisis|scarcity|cuts|supply)|drought|reservoir|aquifer|rationing|\btaps\b",
}
KINDS = list(RULES); ceil = {k: v["labeller_f1_ceiling"] for k, v in json.load(open("runs/pulse/perkind_pooled.json"))["per_kind"].items()}
S, H = {}, {}
for r in J("runs/label_store/labels.jsonl"):
    if r["family"] == "sonnet" and r["version"] == "ws-v2-frozen": S[r["item_id"]] = set(r["kinds"])
    if r["family"] == "haiku": H.setdefault(r["item_id"], set()).update(r["kinds"])
pool = {r["id"]: r["text"] for r in J("data/pool_train.jsonl")}
for r in J("runs/pulse/queue_texts.jsonl"): pool[r["id"]] = r["text"]
ids = sorted(i for i in S if i in pool); T = {i: re.sub(r"\s+", " ", pool[i])[:600] for i in ids}
grp = {}; gid = [grp.setdefault(re.sub(r"\W+", "", T[i].lower())[:60], len(grp)) for i in ids]; gid = np.array(gid)
tk = Tokenizer.from_file("runs/embeds/leaf_tokenizer.json"); tk.enable_truncation(max_length=64); tk.no_padding()
so = ort.SessionOptions(); so.intra_op_num_threads = 4; sess = ort.InferenceSession("runs/embeds/student_v6b-student.onnx", so, providers=["CPUExecutionProvider"])
def emb(t):
    e = tk.encode(t); i = np.array([e.ids], dtype=np.int64); return sess.run(None, {"input_ids": i, "attention_mask": np.ones_like(i)})[0][0]
CACHE = "runs/pulse/kind_cascade_emb.npz"
if os.path.exists(CACHE): z = np.load(CACHE); assert list(z["ids"]) == ids; E1, E2 = z["E1"], z["E2"]
else:
    t0 = time.time(); E1 = np.array([emb(T[i]) for i in ids], dtype=np.float32); E2 = []
    for n, i in enumerate(ids):
        ss = [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“‘'])", T[i]) if len(s) > 15][:4] or [T[i]]; V = np.array([emb(s) for s in ss]); E2.append(np.concatenate([V.max(0), V.mean(0)]))
        if n % 4000 == 0: print("embedded", n, round(time.time() - t0), "s", flush=True)
    E2 = np.array(E2, dtype=np.float32); np.savez(CACHE, ids=np.array(ids), E1=E1, E2=E2)
print("items", len(ids), "groups", len(grp), flush=True)
X = TfidfTransformer().fit_transform(HashingVectorizer(ngram_range=(1, 2), n_features=2 ** 18, alternate_sign=False, norm=None).transform([T[i] for i in ids]))
folds = list(GroupKFold(5).split(np.zeros(len(ids)), groups=gid))
f1 = lambda p, y: 2 * int((p & (y == 1)).sum()) / max(int(p.sum()) + int(y.sum()), 1)
hid = np.array([n for n, i in enumerate(ids) if i in H]); res = {}
for k in KINDS:
    y = np.array([int(k in S[i]) for i in ids]); yh = np.array([int(k in H[ids[n]]) for n in hid]); R = re.compile(RULES[k], re.I)
    sc = {"rules": np.array([1.0 if R.search(T[i]) else 0.0 for i in ids])}
    for name, M in (("sparse", X), ("enc_story", E1), ("enc_sent", E2)):
        o = np.zeros(len(ids))
        for a, b in folds: o[b] = LogisticRegression(C=3.0 if name != "sparse" else 10.0, max_iter=2000, class_weight="balanced").fit(M[a], y[a]).predict_proba(M[b])[:, 1]
        sc[name] = o
    res[k] = {"positives_sonnet": int(y.sum()), "positives_haiku_subset": int(yh.sum()), "labeller_ceiling": ceil.get(k)}
    for name, o in sc.items():
        ths = [0.5] if name == "rules" else np.linspace(0.1, 0.95, 35); th = max(ths, key=lambda t: f1(o >= t, y)); p = o >= th
        fs, fh = f1(p, y), f1(p[hid], yh); tp = int((p & (y == 1)).sum())
        res[k][name] = {"f1_vs_sonnet": round(fs, 3), "f1_vs_haiku": round(fh, 3), "precision": round(tp / max(int(p.sum()), 1), 3), "recall": round(tp / max(int(y.sum()), 1), 3), "pass_both": bool(ceil.get(k) is not None and fs >= ceil[k] - 0.05 and fh >= ceil[k] - 0.05)}
    print(k, {n: (res[k][n]["f1_vs_sonnet"], res[k][n]["f1_vs_haiku"], res[k][n]["pass_both"]) for n in ("rules", "sparse", "enc_story", "enc_sent")}, flush=True)
summ = {n: sum(res[k][n]["pass_both"] for k in KINDS) for n in ("rules", "sparse", "enc_story", "enc_sent")}
summ["sparse_within_0.05_of_enc_story_vs_sonnet"] = sum(res[k]["sparse"]["f1_vs_sonnet"] >= res[k]["enc_story"]["f1_vs_sonnet"] - 0.05 for k in KINDS)
summ["rules_within_0.10_of_enc_story_vs_sonnet"] = sum(res[k]["rules"]["f1_vs_sonnet"] >= res[k]["enc_story"]["f1_vs_sonnet"] - 0.10 for k in KINDS)
summ["enc_sent_beats_enc_story_by_0.03_or_more"] = sum(res[k]["enc_sent"]["f1_vs_sonnet"] >= res[k]["enc_story"]["f1_vs_sonnet"] + 0.03 for k in KINDS)
json.dump({"items": len(ids), "summary": summ, "per_kind": res}, open("runs/pulse/kind_cascade.json", "w"), indent=1); print("SUMMARY", summ)
