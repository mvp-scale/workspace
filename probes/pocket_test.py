"""Do domain 'pockets' (static embedding models) hold up?  Two tests, same classifier family as the CPU engine.

Encoders: general potion-base-8M, potion-code-16M-v2 (code pocket), potion-science-8M (science pocket), e5-small int8
(CPU engine), and for OWASP only unixcoder-base (a full code encoder, mean-pooled, as the ceiling).

owasp  OWASP Benchmark v1.2 (data/sources/owasp/BenchmarkJava, expectedresults-1.2.csv): 2,740 Java test cases, each a
       real vulnerability (true) or a safe look-alike (false), 11 categories. Text = the file minus licence header, package
       and imports. Split 2/3 train, 1/3 test, stratified by category x label (seed). Head: LogisticRegression(C=1, balanced).
       Score: balanced accuracy (chance 50%). Control: category-only baseline (predict from the category's train rate),
       since the category is visible in the code. Pass: code pocket beats general pocket beyond the paired 95% range.
mmlu   MMLU, 14,042 four-option questions, 57 subjects (probes/v2/mmlu_*.jsonl). Two readouts, chance 25%:
       zero-shot = pick the option whose vector is most similar (cosine) to the question's;
       trained   = one shared head scores (question, option) pairs from [q, o, q*o, |q-o|], trained on half the items of
                   every subject (seeded split by item), scored on the other half; answer = highest-scoring option.
       Pass: accuracy above 25% beyond the 95% (Wilson) range.
Writes data/pocket-test/.  Run: models/embed-zs/.venv/bin/python probes/pocket_test.py owasp|mmlu  (HF_HOME=/workspace/data/hf)
"""
import json, sys, re, csv, random, time, pathlib, collections, math
import numpy as np
from sklearn.linear_model import LogisticRegression

OUT = pathlib.Path("/workspace/data/pocket-test"); OUT.mkdir(parents=True, exist_ok=True)
SEED = 20261016
STATIC = {"general potion-base-8M": "minishlab/potion-base-8M", "code potion-code-16M-v2": "minishlab/potion-code-16M-v2",
          "science potion-science-8M": "minishlab/potion-science-8M"}
bal = lambda y, p: (np.mean(p[y == 1]) + np.mean(1 - p[y == 0])) / 2


def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def encoders(with_unixcoder=False):
    from model2vec import StaticModel
    out = {}
    for name, rid in STATIC.items():
        M = StaticModel.from_pretrained(rid)
        out[name] = lambda texts, M=M: np.asarray(M.encode(texts), np.float32)
    sys.path.insert(0, str(pathlib.Path(__file__).parent)); import state_depth as sd
    out["e5-small int8 (CPU engine)"] = lambda texts: sd.embed(texts)[0]
    if with_unixcoder:
        import torch
        from transformers import AutoTokenizer, AutoModel
        tok = AutoTokenizer.from_pretrained("microsoft/unixcoder-base"); mod = AutoModel.from_pretrained("microsoft/unixcoder-base").eval()
        torch.set_num_threads(16)
        def ux(texts):
            vs = []
            with torch.no_grad():
                for k in range(0, len(texts), 16):
                    b = tok(texts[k:k + 16], padding=True, truncation=True, max_length=512, return_tensors="pt")
                    h = mod(**b).last_hidden_state; m = b["attention_mask"].unsqueeze(-1).float()
                    v = (h * m).sum(1) / m.sum(1); vs.append(torch.nn.functional.normalize(v, dim=-1).numpy())
            return np.concatenate(vs).astype(np.float32)
        out["unixcoder-base (full code encoder, ceiling)"] = ux
    return out


def owasp():
    root = pathlib.Path("/workspace/data/sources/owasp/BenchmarkJava")
    rows = [r for r in csv.reader(open(root / "expectedresults-1.2.csv")) if r and not r[0].startswith("#")]
    src = root / "src/main/java/org/owasp/benchmark/testcode"
    items = []
    for name, cat, real, cwe in rows:
        t = (src / f"{name}.java").read_text()
        t = re.sub(r"^\s*/\*\*.*?\*/\s*", "", t, flags=re.S)                     # licence header
        t = "\n".join(l for l in t.splitlines() if not re.match(r"\s*(package|import)\s", l)).strip()
        items.append({"id": name, "cat": cat, "y": int(real == "true"), "cwe": cwe, "text": t})
    rng = random.Random(SEED); strata = collections.defaultdict(list)
    for k, i in enumerate(items): strata[(i["cat"], i["y"])].append(k)
    test = set()
    for ks in strata.values(): rng.shuffle(ks); test |= set(ks[: len(ks) // 3])
    tr = [k for k in range(len(items)) if k not in test]; te = sorted(test)
    y = np.array([i["y"] for i in items]); cats = sorted({i["cat"] for i in items})
    print(f"OWASP: {len(items)} test cases, {y.sum()} real vulnerabilities; train {len(tr)}, test {len(te)}; categories: {', '.join(cats)}")
    print(f"characters per case (median): {sorted(len(i['text']) for i in items)[len(items) // 2]}")
    print("example input (first 400 chars of", items[0]["id"], "):\n" + items[0]["text"][:400] + "\n...")
    # control: category-only baseline
    rate = {c: np.mean([y[k] for k in tr if items[k]["cat"] == c]) for c in cats}
    base = np.array([int(rate[items[k]["cat"]] >= 0.5) for k in te])
    # also: per-category train rate as a probability -> best possible from category alone (balanced threshold per category is the same thing)
    res = {"n_train": len(tr), "n_test": len(te), "category_only": float(bal(y[te], base)), "encoders": {}}
    print(f"\ncategory-only baseline (knows the category, not the code): balanced accuracy {res['category_only']:.1%}\n")
    sizes = [50, 100, 200, 400, 800, len(tr)]; preds = {}
    for name, enc in encoders(with_unixcoder=True).items():
        t0 = time.time(); X = enc([i["text"] for i in items]); secs = time.time() - t0
        curve = []
        for n in sizes:
            sc = []
            for d in range(10 if n < len(tr) else 1):
                sub = sorted(random.Random(SEED + d).sample(tr, n)) if n < len(tr) else tr
                if len(set(y[sub])) < 2: continue
                p = LogisticRegression(C=1.0, max_iter=5000, class_weight="balanced").fit(X[sub], y[sub]).predict(X[te])
                sc.append(bal(y[te], p))
                if n == len(tr): preds[name] = p
            curve.append([float(np.mean(sc)), float(min(sc)), float(max(sc))])
        per_cat = {c: float(bal(y[te][[items[k]["cat"] == c for k in te]], preds[name][[items[k]["cat"] == c for k in te]])) for c in cats}
        res["encoders"][name] = {"curve": dict(zip(map(str, sizes), curve)), "per_category": per_cat, "encode_seconds": round(secs, 1)}
        print(f"{name:45} encode {secs:6.1f}s | " + "  ".join(f"n={n}: {c[0]:.1%}" for n, c in zip(sizes, curve)), flush=True)
    # paired bootstrap vs general pocket
    B = np.random.default_rng(SEED).integers(0, len(te), (2000, len(te))); yt = y[te]; g = preds["general potion-base-8M"]
    print("\nAt full training, difference vs the general pocket (paired bootstrap over the test cases, 95% range):")
    res["vs_general"] = {}
    for name, p in preds.items():
        if name == "general potion-base-8M": continue
        diffs = np.array([bal(yt[b], p[b]) - bal(yt[b], g[b]) for b in B]); lo, hi = np.percentile(diffs, [2.5, 97.5]); d = bal(yt, p) - bal(yt, g)
        res["vs_general"][name] = [float(d), float(lo), float(hi)]
        print(f"  {name:45} {d:+.1%} [{lo:+.1%}, {hi:+.1%}] -> {'better' if lo > 0 else 'worse' if hi < 0 else 'no clear difference'}")
    print("\nPer category at full training (balanced accuracy; 'cat-only' cannot separate within a category, so it is 50% there):")
    print(f"  {'category':12} {'n test':>6}  " + "  ".join(f"{n.split()[0]:>9}" for n in res["encoders"]))
    for c in cats:
        print(f"  {c:12} {sum(items[k]['cat'] == c for k in te):>6}  " + "  ".join(f"{res['encoders'][n]['per_category'][c]:9.1%}" for n in res["encoders"]))
    json.dump(res, open(OUT / "owasp.json", "w"), indent=1)
    with open(OUT / "owasp_test_answers.jsonl", "w") as f:
        for j, k in enumerate(te): f.write(json.dumps({"id": items[k]["id"], "category": items[k]["cat"], "real_vulnerability": items[k]["y"], "answers": {n: int(p[j]) for n, p in preds.items()}}) + "\n")
    print(f"\nwrote {OUT}/owasp.json and owasp_test_answers.jsonl")


def mmlu():
    files = sorted(pathlib.Path("/workspace/probes/v2").glob("mmlu_*.jsonl"))
    items = [json.loads(l) for f in files for l in open(f)]
    L = ["A", "B", "C", "D"]
    for i in items: i["subject"] = i["family"][5:]
    rng = random.Random(SEED); by_s = collections.defaultdict(list)
    for k, i in enumerate(items): by_s[i["subject"]].append(k)
    train = set()
    for ks in by_s.values(): ks = sorted(ks); rng.shuffle(ks); train |= set(ks[: len(ks) // 2])
    te = [k for k in range(len(items)) if k not in train]; tr = sorted(train)
    ans = np.array([L.index(i["expected"]) for i in items])
    print(f"MMLU: {len(items)} questions, {len(by_s)} subjects; trained readout: train {len(tr)}, test {len(te)} (half of every subject)")
    print("example:", json.dumps({"state": items[0]["state"], "options": items[0]["question"]["criteria"], "answer": items[0]["expected"]})[:400])
    res = {"n": len(items), "n_test_trained": len(te), "encoders": {}}
    for name, enc in encoders().items():
        t0 = time.time()
        Qv = enc([i["state"] for i in items])
        Ov = enc([str(i["question"]["criteria"][l]) for i in items for l in L]).reshape(len(items), 4, -1)
        secs = time.time() - t0
        Qn = Qv / np.linalg.norm(Qv, axis=1, keepdims=True); On = Ov / np.linalg.norm(Ov, axis=2, keepdims=True)
        zs = np.argmax(np.einsum("nd,nkd->nk", Qn, On), 1)
        feat = lambda ks: np.concatenate([np.repeat(Qn[ks][:, None], 4, 1), On[ks], Qn[ks][:, None] * On[ks], np.abs(Qn[ks][:, None] - On[ks])], 2).reshape(len(ks) * 4, -1)
        ytr = np.array([[int(j == ans[k]) for j in range(4)] for k in tr]).ravel()
        clf = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(feat(tr), ytr)
        trained = np.argmax(clf.decision_function(feat(te)).reshape(len(te), 4), 1)
        z_ok = zs == ans; t_ok = trained == ans[te]
        per = {}
        for s, ks in by_s.items():
            kt = [j for j, k in enumerate(te) if items[k]["subject"] == s]
            per[s] = {"n": len(ks), "zero_shot": float(z_ok[ks].mean()), "n_test": len(kt), "trained": float(t_ok[kt].mean())}
        zl, zh = wilson(z_ok.sum(), len(z_ok)); tl, th = wilson(t_ok.sum(), len(t_ok))
        res["encoders"][name] = {"zero_shot": [float(z_ok.mean()), zl, zh], "trained": [float(t_ok.mean()), tl, th], "per_subject": per, "encode_seconds": round(secs, 1)}
        print(f"{name:32} encode {secs:6.1f}s | zero-shot {z_ok.mean():.1%} [{zl:.1%}-{zh:.1%}] | trained {t_ok.mean():.1%} [{tl:.1%}-{th:.1%}]  (chance 25%)", flush=True)
    # per subject table, sorted by the best trained score
    names = list(res["encoders"])
    print(f"\nper subject, trained readout on the held-out half (chance 25%); n = test items")
    print(f"  {'subject':38} {'n':>4}  " + "  ".join(f"{n.split()[0][:9]:>9}" for n in names))
    for s in sorted(by_s, key=lambda s: -max(res['encoders'][n]['per_subject'][s]['trained'] for n in names)):
        n_t = res["encoders"][names[0]]["per_subject"][s]["n_test"]
        print(f"  {s:38} {n_t:>4}  " + "  ".join(f"{res['encoders'][n]['per_subject'][s]['trained']:9.1%}" for n in names))
    json.dump(res, open(OUT / "mmlu.json", "w"), indent=1)
    print(f"\nwrote {OUT}/mmlu.json")


if __name__ == "__main__":
    {"owasp": owasp, "mmlu": mmlu}[sys.argv[1]]()
