"""Which CPU student learns the atoms best? Same held-out split as train_mm3.py (id hash % 5 == 0), labels fixed before looking:
  first battery (queue.jsonl):        civil_unrest, war_terror, crime, cyber_insecurity  -> yes = states and concrete both >= 0.5
  evidence battery (queue-evidence-v1): 9 evidence atoms                                  -> yes = paraphrases a and b both >= 0.5
  topic / scope / kind: Clef's top option (first battery).
Students: A potion-32M frozen + logistic; B e5-small frozen + logistic; E [potion | e5] frozen + logistic;
          C e5-small fine-tuned on all of Clef's soft answers (both batteries), 20 epochs, cut-offs on a 20% validation slice;
          F mean of A and C probabilities (cut-off on the same validation slice).
Every cut-off is chosen on training stories only. Reports F1 per atom, median, and CPU ms per story (one thread).
Run: models/embed-zs/.venv/bin/python -I newsreader/bitmob/train_atoms.py"""
import json, hashlib, time, os, numpy as np, torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from model2vec import StaticModel
from transformers import AutoTokenizer, AutoModel

D = "/workspace/data/mm3-train"; first = {r["id"]: r for r in map(json.loads, open(f"{D}/queue.jsonl"))}
ev = {r["id"]: r for r in map(json.loads, open(f"{D}/queue-evidence-v1.jsonl"))}
ids = sorted(set(first) & set(ev)); rows = [first[i] for i in ids]; text = [r["title"] + ". " + r["text"] for r in rows]
h = lambda i: int(hashlib.sha256(i.encode()).hexdigest(), 16) % 5
test = np.array([h(i) == 0 for i in ids]); val = np.array([h(i) == 1 for i in ids]); fit = ~test & ~val; tr = ~test
ATOMS = {f"{c}": ("first", (f"{c}|states", f"{c}|concrete")) for c in ("civil_unrest|up", "war_terror|up", "crime|up", "cyber_insecurity|up")}
B = json.load(open("/workspace/newsreader/bitmob/batteries/evidence-v1.json"))
ATOMS.update({c["atom"]: ("ev", (f"{c['atom']}|a", f"{c['atom']}|b")) for c in B["concerns"]})
src = lambda w, i: (first if w == "first" else ev)[i]["answers"]
Y = np.array([[all(src(w, i)[k] >= .5 for k in ks) for (w, ks) in ATOMS.values()] for i in ids]); NAMES = list(ATOMS)
CH = {c: list(rows[0]["answers"][c]) for c in ("topic", "scope", "kind")}; CHY = {c: np.array([max(r["answers"][c], key=r["answers"][c].get) for r in rows]) for c in CH}
print(f"{len(ids)} stories ({fit.sum()} fit, {val.sum()} val, {test.sum()} test); yes in training: " + ", ".join(f"{n} {Y[tr, j].sum()}" for j, n in enumerate(NAMES)), flush=True)
best_cut = lambda y, p: 0.5 if y.sum() < 2 else max(np.linspace(.05, .95, 37), key=lambda t: f1_score(y, p >= t))
R = {"stories": len(ids), "test": int(test.sum()), "yes_test": {n: int(Y[test, j].sum()) for j, n in enumerate(NAMES)}}


def report(name, Pt, Pv, ms, CHP=None):
    """Pt/Pv: probabilities on test/val stories; cut-off per atom from val."""
    r = {"cpu_ms_story": round(ms, 2), "atoms": {}}
    for j, n in enumerate(NAMES):
        c = best_cut(Y[val, j], Pv[:, j]); r["atoms"][n] = round(float(f1_score(Y[test, j], Pt[:, j] >= c)), 3) if Y[test, j].sum() >= 3 else None
    v = [x for x in r["atoms"].values() if x is not None]; r["median"] = round(float(np.median(v)), 3); r["mean"] = round(float(np.mean(v)), 3)
    if CHP:
        for c, (opts, P) in CHP.items():
            o = np.argsort(-P, 1); t = np.array([opts.index(x) for x in CHY[c][test]]); r[f"{c}_top1"] = round(float((o[:, 0] == t).mean()), 3)
            if c == "topic": r["topic_top3"] = round(float((o[:, :3] == t[:, None]).any(1).mean()), 3)
    R[name] = r; print(f"{name}: median {r['median']} mean {r['mean']} ms {r['cpu_ms_story']} " + json.dumps(r["atoms"]) + (f" topic3 {r.get('topic_top3')} scope {r.get('scope_top1')}" if CHP else ""), flush=True)
    return r


def frozen(X, name, ms):
    Pt, Pv = np.zeros((test.sum(), len(NAMES))), np.zeros((val.sum(), len(NAMES)))
    for j in range(len(NAMES)):
        if Y[fit, j].sum() < 2: continue
        m = LogisticRegression(C=4, class_weight="balanced", max_iter=4000).fit(X[fit], Y[fit, j]); Pt[:, j], Pv[:, j] = m.predict_proba(X[test])[:, 1], m.predict_proba(X[val])[:, 1]
    CHP = {}
    for c, opts in CH.items():
        m = LogisticRegression(C=4, max_iter=4000).fit(X[fit], CHY[c][fit]); p = m.predict_proba(X[test]); P = np.zeros((test.sum(), len(opts)))
        for k, o in enumerate(m.classes_): P[:, opts.index(o)] = p[:, k]
        CHP[c] = (opts, P)
    return report(name, Pt, Pv, ms, CHP), Pt, Pv


torch.set_num_threads(1)
pm = StaticModel.from_pretrained("minishlab/potion-base-32M"); t = time.perf_counter(); XA = pm.encode(text); msA = (time.perf_counter() - t) * 1000 / len(text)
_, PtA, PvA = frozen(XA, "A potion", msA)
tok = AutoTokenizer.from_pretrained("intfloat/e5-small-v2"); dev = "cuda"; MAXLEN = 512
def enc(model, ks, bs=32, device=dev):
    model.eval(); out = []
    with torch.no_grad():
        for i in range(0, len(ks), bs):
            b = tok(["query: " + text[k] for k in ks[i:i + bs]], truncation=True, max_length=MAXLEN, padding=True, return_tensors="pt").to(device)
            hh = model(**b).last_hidden_state; m = b["attention_mask"].unsqueeze(-1); out.append(((hh * m).sum(1) / m.sum(1)).cpu().numpy())
    return np.concatenate(out)
XB = enc(AutoModel.from_pretrained("intfloat/e5-small-v2").to(dev), list(range(len(text))))
cpu1 = AutoModel.from_pretrained("intfloat/e5-small-v2"); t = time.perf_counter(); enc(cpu1, list(range(40)), bs=1, device="cpu"); msB = (time.perf_counter() - t) * 1000 / 40
frozen(XB, "B e5 frozen", msB)
nrm = lambda X: X / np.linalg.norm(X, axis=1, keepdims=True)
frozen(np.hstack([nrm(XA), nrm(XB)]), "E potion+e5 frozen", msA + msB)
# C: fine-tune on every soft answer of both batteries
KEYS = [("first", k) for k in rows[0]["answers"] if k.count("|") == 2] + [("ev", k) for k in ev[ids[0]]["answers"] if k.count("|") == 1 and not isinstance(ev[ids[0]]["answers"][k], dict)]
SOFT = np.array([[src(w, i)[k] for (w, k) in KEYS] for i in ids], np.float32); CHS = {c: np.array([[r["answers"][c][o] for o in CH[c]] for r in rows], np.float32) for c in CH}
col = {f"{w}:{k}": n for n, (w, k) in enumerate(KEYS)}
class Tagger(torch.nn.Module):
    def __init__(s):
        super().__init__(); s.enc = AutoModel.from_pretrained("intfloat/e5-small-v2"); d = s.enc.config.hidden_size
        s.yes = torch.nn.Linear(d, len(KEYS)); s.ch = torch.nn.ModuleDict({c: torch.nn.Linear(d, len(o)) for c, o in CH.items()})
    def forward(s, **b):
        hh = s.enc(**b).last_hidden_state; m = b["attention_mask"].unsqueeze(-1); v = (hh * m).sum(1) / m.sum(1)
        return s.yes(v), {c: l(v) for c, l in s.ch.items()}
torch.manual_seed(0); M = Tagger().to(dev); EPOCHS, BS = 20, 16; idx = np.where(fit)[0]
opt = torch.optim.AdamW(M.parameters(), lr=4e-5, weight_decay=0.01); sched = torch.optim.lr_scheduler.OneCycleLR(opt, 4e-5, total_steps=EPOCHS * ((len(idx) + BS - 1) // BS))
pw = torch.tensor(np.clip((1 - SOFT[fit].mean(0)) / np.maximum(SOFT[fit].mean(0), 1e-3), 1, 5), device=dev); t0 = time.perf_counter()
for ep in range(EPOCHS):
    M.train(); np.random.RandomState(ep).shuffle(idx); tot = 0
    for i in range(0, len(idx), BS):
        bi = idx[i:i + BS]; b = tok(["query: " + text[k] for k in bi], truncation=True, max_length=MAXLEN, padding=True, return_tensors="pt").to(dev); ly, lc = M(**b)
        loss = torch.nn.functional.binary_cross_entropy_with_logits(ly, torch.tensor(SOFT[bi], device=dev), pos_weight=pw)
        for c in CH: loss = loss + 0.3 * -(torch.tensor(CHS[c][bi], device=dev) * torch.log_softmax(lc[c], -1)).sum(-1).mean()
        opt.zero_grad(); loss.backward(); opt.step(); sched.step(); tot += loss.item() * len(bi)
    if ep % 5 == 4: print(f"  C epoch {ep + 1}: loss {tot / len(idx):.4f} ({time.perf_counter() - t0:.0f}s)", flush=True)
R["C_train_gpu_s"] = round(time.perf_counter() - t0, 1)
def run(ks, device):
    M.to(device).eval(); PY, PC = [], {c: [] for c in CH}
    with torch.no_grad():
        for k in ks:
            b = tok(["query: " + text[k]], truncation=True, max_length=MAXLEN, return_tensors="pt").to(device); ly, lc = M(**b)
            PY.append(torch.sigmoid(ly)[0].cpu().numpy()); [PC[c].append(torch.softmax(lc[c], -1)[0].cpu().numpy()) for c in CH]
    PY = np.array(PY); P = np.array([[min(PY[r, col[f"{w}:{k}"]] for k in ks_) for (w, ks_) in ATOMS.values()] for r in range(len(ks))])
    return P, {c: (CH[c], np.array(v)) for c, v in PC.items()}
PvC, _ = run(np.where(val)[0], dev); t = time.perf_counter(); PtC, CHC = run(np.where(test)[0], "cpu"); msC = (time.perf_counter() - t) * 1000 / test.sum()
report("C e5 fine-tuned", PtC, PvC, msC, CHC)
report("F mean(A, C)", (PtA + PtC) / 2, (PvA + PvC) / 2, msA + msC)
os.makedirs(f"{D}/model", exist_ok=True); torch.save(M.cpu().state_dict(), f"{D}/model/tagger-atoms.pt")
json.dump({"keys": [f"{w}:{k}" for w, k in KEYS], "atoms": {n: [w, list(ks)] for n, (w, ks) in ATOMS.items()}, "choices": CH, "maxlen": MAXLEN}, open(f"{D}/model/tagger-atoms.json", "w"), indent=1)
json.dump(R, open(f"{D}/results-atoms.json", "w"), indent=1); print("saved")
