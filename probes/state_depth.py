"""Does a richer state help the CPU classifier learn sooner?  Step 1: build the items (no model, no training).

Data: Persuasion for Good, data/AnnotatedData/300_dialog.xlsx (300 dialogues, every sentence hand-labelled by
annotators who saw the whole conversation). Only persuadee (role 1) sentences are items; the label is ee_label_1.
Three states per item, built mechanically from the file (nothing hand-written per item):
  S1  the sentence alone
  S2  Situation (setting + the persuader's last turn) + Task (the speaker's role + what they already said in this reply) + the sentence
  S3  S2 + Action (the two exchanges before that: what each side has done so far)
Questions (yes/no, from the human label):
  agree   agree-donation or provide-donation-amount
  refuse  negative-reaction-to-donation or disagree-donation
  askorg  ask-org-info
Split by dialogue (seeded): train pool 250 items, test 200 items, each drawn 1/4 per question's positives + 1/4 other.
Writes data/state-depth/items.jsonl.  Run: python3 probes/state_depth.py build
"""
import json, random, sys, collections, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent / "v2"))
import _xlsx_min

SRC = "/workspace/data/sources/p4g/repo/data/AnnotatedData/300_dialog.xlsx"
OUT = pathlib.Path("/workspace/data/state-depth"); OUT.mkdir(parents=True, exist_ok=True)
SEED = 20261016
Q = {"agree": {"agree-donation", "provide-donation-amount"},
     "refuse": {"negative-reaction-to-donation", "disagree-donation"},
     "askorg": {"ask-org-info"}}
SETTING = "An online chat. One person (the persuader) is trying to get the other (the speaker) to donate part of their task payment to the charity Save the Children."
TASK = "The speaker is replying to the persuader and deciding whether to donate, and how much."
norm = lambda s: " ".join((s or "").split())


def dialogues():
    d = collections.defaultdict(list)
    for a in _xlsx_min.read(SRC)[1:]:
        a = a + [""] * (9 - len(a))
        d[a[1]].append({"row": int(a[0]), "role": a[2], "turn": int(a[3]), "text": norm(a[4]), "ee": a[6]})
    for v in d.values(): v.sort(key=lambda u: u["row"])
    return d


def turns(units):
    """Group sentence units into speaker turns (consecutive units, same role and turn index)."""
    out = []
    for u in units:
        if out and out[-1]["role"] == u["role"] and out[-1]["turn"] == u["turn"]: out[-1]["units"].append(u)
        else: out.append({"role": u["role"], "turn": u["turn"], "units": [u]})
    return out


def who(r): return "Persuader" if r == "0" else "Speaker"


def build_items():
    items = []
    for did, units in dialogues().items():
        ts = turns(units)
        for ti, t in enumerate(ts):
            if t["role"] != "1": continue
            prev_er = next((ts[j] for j in range(ti - 1, -1, -1) if ts[j]["role"] == "0"), None)
            pj = ts.index(prev_er) if prev_er else ti
            history = ts[max(0, pj - 4):pj]           # the two exchanges before the persuader's last turn
            for k, u in enumerate(t["units"]):
                if len(u["text"]) < 2: continue
                said = " ".join(x["text"] for x in t["units"][:k])
                last = " ".join(x["text"] for x in prev_er["units"]) if prev_er else "(nothing yet)"
                sit = f"Situation: {SETTING} The persuader just said: \"{last}\""
                task = f"Task: {TASK}" + (f" Earlier in this reply the speaker said: \"{said}\"" if said else "")
                act = "Action so far: " + (" ".join(f"{who(h['role'])}: \"{' '.join(x['text'] for x in h['units'])}\"" for h in history) or "(start of the chat)")
                sent = f"Sentence: \"{u['text']}\""
                items.append({"id": f"{did}#{u['row']}", "dialogue": did, "row": u["row"], "label": u["ee"],
                              "y": {q: int(u["ee"] in s) for q, s in Q.items()},
                              "S1": u["text"], "S2": "\n".join([sit, task, sent]), "S3": "\n".join([sit, task, act, sent])})
    return items


def draw(pool, n, rng):
    """1/4 from each question's positives, 1/4 from items positive for none; no repeats."""
    groups = {q: [i for i in pool if i["y"][q]] for q in Q} | {"other": [i for i in pool if not any(i["y"].values())]}
    got, seen = [], set()
    for g, members in groups.items():
        members = [i for i in members if i["id"] not in seen]
        for i in rng.sample(members, min(n // 4, len(members))): got.append(i); seen.add(i["id"])
    rng.shuffle(got); return got


def build():
    items = build_items(); rng = random.Random(SEED)
    dids = sorted({i["dialogue"] for i in items}); rng.shuffle(dids)
    test_d = set(dids[:120])                       # 120 dialogues for test, 180 for training
    train = draw(sorted([i for i in items if i["dialogue"] not in test_d], key=lambda i: i["id"]), 250, rng)
    test = draw(sorted([i for i in items if i["dialogue"] in test_d], key=lambda i: i["id"]), 200, rng)
    with open(OUT / "items.jsonl", "w") as f:
        for split, xs in (("train", train), ("test", test)):
            for i in xs: f.write(json.dumps(i | {"split": split}, ensure_ascii=False) + "\n")
    print(f"persuadee sentences in the file: {len(items)};  train {len(train)} (from {len(dids) - 120} dialogues), test {len(test)} (from 120 other dialogues)")
    for split, xs in (("train", train), ("test", test)):
        print(f"  {split}: " + ", ".join(f"{q} yes={sum(i['y'][q] for i in xs)}" for q in Q))
    print("words per state (median / max):", {s: (sorted(len(i[s].split()) for i in train)[len(train) // 2], max(len(i[s].split()) for i in train)) for s in ("S1", "S2", "S3")})
    both = collections.Counter((i["y"]["agree"], i["y"]["refuse"], i["y"]["askorg"]) for i in train)
    print("label overlap in train (agree, refuse, askorg) -> count:", dict(both))
    print("\n=== 4 example items (exact strings the encoder will get, before its 'query: ' prefix) ===")
    for i in [next(x for x in train if x["y"][q]) for q in Q] + [next(x for x in train if not any(x["y"].values()))]:
        print(f"\n--- {i['id']}  human label: {i['label']}  ->  {i['y']}")
        for s in ("S1", "S2", "S3"): print(f"[{s}]\n{i[s]}")


SIZES = [12, 24, 48, 100, 148, 200, 248]   # multiples of 4 so each draw is 1/4 per group
DRAWS = 20
STATES = ("S1", "S2", "S3")


def embed(texts):
    """Exact copy of the CPU engine's encode (probes/cpu_engine.py, onnx-int8 runtime): same graph, tokenizer, 'query: ' prefix,
    512-token cap, mean pooling, unit length. In-process because the engine's /embed inspection route cuts text at 2,000 characters."""
    import numpy as np, onnxruntime as ort
    from tokenizers import Tokenizer
    from huggingface_hub import hf_hub_download
    tok = Tokenizer.from_file(hf_hub_download("intfloat/e5-small-v2", "tokenizer.json")); tok.enable_truncation(512)
    sess = ort.InferenceSession("/workspace/data/embed-zs/engine/e5.int8.onnx", providers=["CPUExecutionProvider"])
    out = []
    for t in texts:
        e = tok.encode("query: " + t); ids = np.array([e.ids], np.int64); m = np.array([e.attention_mask], np.int64)
        h = sess.run(None, {"input_ids": ids, "attention_mask": m, "token_type_ids": np.zeros_like(ids)})[0][0]
        v = h[m[0] == 1].mean(0); out.append(v / np.linalg.norm(v))
    return np.array(out, np.float32), "intfloat/e5-small-v2 (onnx-int8, data/embed-zs/engine/e5.int8.onnx)"


def train():
    """Learning curve per state and question; same classifier as the CPU engine's sidecar (LogisticRegression C=1, balanced)."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from tokenizers import Tokenizer
    from huggingface_hub import hf_hub_download
    items = [json.loads(l) for l in open(OUT / "items.jsonl")]
    tr = [i for i in items if i["split"] == "train"]; te = [i for i in items if i["split"] == "test"]
    tok = Tokenizer.from_file(hf_hub_download("intfloat/e5-small-v2", "tokenizer.json"))
    for s in STATES:
        n = [len(tok.encode("query: " + i[s]).ids) for i in items]
        print(f"{s}: tokens median {sorted(n)[len(n) // 2]}, max {max(n)}, over the 512 cap (end cut off): {sum(x > 512 for x in n)}")
    V = {}
    for s in STATES:
        V[s], enc = embed([i[s] for i in items])
    print("encoder:", enc)
    idx = {i["id"]: k for k, i in enumerate(items)}
    Xtr = {s: V[s][[idx[i["id"]] for i in tr]] for s in STATES}; Xte = {s: V[s][[idx[i["id"]] for i in te]] for s in STATES}
    group = lambda i: next((q for q in Q if i["y"][q]), "other")
    by_g = collections.defaultdict(list)
    for k, i in enumerate(tr): by_g[group(i)].append(k)
    bal = lambda y, p: (np.mean(p[y == 1]) + np.mean(1 - p[y == 0])) / 2   # balanced accuracy: mean of yes-recall and no-recall; chance = 50%
    rng = random.Random(SEED); curve = {}; per_item = {}
    for n in SIZES:
        draws = [sorted(sum((rng.sample(by_g[g], n // 4) for g in by_g), [])) for _ in range(DRAWS if n < 248 else 1)]
        for s in STATES:
            for q in Q:
                ytr = np.array([i["y"][q] for i in tr]); yte = np.array([i["y"][q] for i in te]); scores = []
                for d in draws:
                    clf = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(Xtr[s][d], ytr[d])
                    pred = clf.predict(Xte[s]); scores.append(bal(yte, pred))
                    if n == 248: per_item[(s, q)] = (pred, clf.predict_proba(Xte[s])[:, 1])
                sc = sorted(scores); curve[(n, s, q)] = (float(np.mean(sc)), sc[0], sc[-1])
    print(f"\nBalanced accuracy on the 200 test sentences (chance 50%). mean over {DRAWS} random training draws [lowest-highest draw]")
    for q in Q:
        print(f"\n  question: {q}\n  {'train n':>8}  " + "  ".join(f"{s:>18}" for s in STATES))
        for n in SIZES: print(f"  {n:>8}  " + "  ".join(f"{curve[(n, s, q)][0]:6.1%} [{curve[(n, s, q)][1]:.0%}-{curve[(n, s, q)][2]:.0%}]" for s in STATES))
    # at n=248: paired bootstrap over test sentences, difference vs S1
    print("\nAt 248 training items, difference vs S1 (paired bootstrap over the 200 test sentences, 2000 resamples, 95% range):")
    brng = np.random.default_rng(SEED)
    for q in Q:
        yte = np.array([i["y"][q] for i in te])
        for s in ("S2", "S3"):
            diffs = []
            for _ in range(2000):
                b = brng.integers(0, len(te), len(te))
                if yte[b].sum() in (0, len(b)): continue
                diffs.append(bal(yte[b], per_item[(s, q)][0][b]) - bal(yte[b], per_item[("S1", q)][0][b]))
            lo, hi = np.percentile(diffs, [2.5, 97.5]); d = bal(yte, per_item[(s, q)][0]) - bal(yte, per_item[("S1", q)][0])
            verdict = "better" if lo > 0 else "worse" if hi < 0 else "no clear difference"
            print(f"  {q:7} {s} - S1 = {d:+.1%}  [{lo:+.1%}, {hi:+.1%}]  -> {verdict}")
    with open(OUT / "test_answers.jsonl", "w") as f:
        for k, i in enumerate(te):
            f.write(json.dumps({"id": i["id"], "human_label": i["label"], "sentence": i["S1"], "y": i["y"],
                                "answers_at_248": {q: {s: {"yes": int(per_item[(s, q)][0][k]), "p": round(float(per_item[(s, q)][1][k]), 3)} for s in STATES} for q in Q}}, ensure_ascii=False) + "\n")
    json.dump({f"{n}|{s}|{q}": v for (n, s, q), v in curve.items()}, open(OUT / "curve.json", "w"), indent=1)
    print(f"\nwrote {OUT}/test_answers.jsonl (every test sentence, its human label, each state's answer) and curve.json")


# ---------- Step 3: the grid. Which TypeSafe fields go into the encoder x how deep the state is x how deep the question is.
# Wordings written 2026-10-16 before any grid run; do not edit after scoring (a new wording = a new key).
QW = {
 "agree": {
  "minimal": {"instructions": "Does the speaker agree to donate?",
              "criteria": {"true": "Agrees to donate or names an amount.", "false": "Does not agree to donate."}},
  "deep": {"instructions": "In this chat a persuader asks the speaker to donate part of their task payment to Save the Children. In the sentence, does the speaker agree to donate?",
           "criteria": {"true": "The speaker says yes to donating, accepts the request, or states an amount they will give, even briefly (for example 'sure', 'I guess so', '$1 is fine').",
                        "false": "The speaker declines, hesitates, asks a question, chats, or talks about something else; agreeing with a point is not agreeing to donate."}}},
 "refuse": {
  "minimal": {"instructions": "Does the speaker push back on donating?",
              "criteria": {"true": "Refuses or reacts negatively to donating.", "false": "Does not push back on donating."}},
  "deep": {"instructions": "In this chat a persuader asks the speaker to donate part of their task payment to Save the Children. In the sentence, does the speaker push back on donating?",
           "criteria": {"true": "The speaker declines, doubts the charity, says they cannot afford it, prefers another way to help, or otherwise reacts negatively to the request to donate.",
                        "false": "The speaker agrees, asks a neutral question, chats, or is positive; mild hedging that still agrees is not pushing back."}}},
 "askorg": {
  "minimal": {"instructions": "Does the speaker ask about the charity?",
              "criteria": {"true": "Asks for information about the charity.", "false": "Does not ask about the charity."}},
  "deep": {"instructions": "In this chat a persuader asks the speaker to donate part of their task payment to Save the Children. In the sentence, does the speaker ask about the charity?",
           "criteria": {"true": "The speaker asks a question about Save the Children: what it does, where the money goes, its website, its record, how it helps children.",
                        "false": "The speaker makes a statement, answers a question, or asks about something other than the charity (for example the persuader, the task, how to donate)."}}}}


def compose(state, q, depth, fields):
    """The exact encoder input. fields 1 = state only; 2 = instructions + state; 3 = instructions + criteria + state."""
    if fields == 1: return state
    w = QW[q][depth]; head = f"Question: {w['instructions']}"
    if fields == 3: head += f"\nYes means: {w['criteria']['true']}\nNo means: {w['criteria']['false']}"
    return head + "\n" + state


def context_of(i, s):
    """The state without its Sentence line (for the split variant: sentence and context encoded separately)."""
    return i[s].rsplit("\nSentence: ", 1)[0]


def static_embed(texts):
    from model2vec import StaticModel
    import numpy as np
    P = StaticModel.from_pretrained("minishlab/potion-base-8M").encode(texts); return P / np.linalg.norm(P, axis=1, keepdims=True)


def grid():
    import numpy as np, time
    from sklearn.linear_model import LogisticRegression
    from tokenizers import Tokenizer
    from huggingface_hub import hf_hub_download
    items = [json.loads(l) for l in open(OUT / "items.jsonl")]
    tr = [i for i in items if i["split"] == "train"]; te = [i for i in items if i["split"] == "test"]
    print("=== the fixed question wordings (instructions + criteria) ===")
    for q in QW:
        for d in ("minimal", "deep"): print(f"[{q} / {d}]\n{compose('<state>', q, d, 3)}\n")
    # every distinct encoder input
    cells = []   # (cell name, question -> list of texts per item) ; split cells handled separately
    for s in STATES:
        cells.append((f"{s} | state only", {q: [i[s] for i in items] for q in Q}))
        for f in (2, 3):
            for d in ("minimal", "deep"):
                cells.append((f"{s} | {'state+instr' if f == 2 else 'state+instr+criteria'} | {d}", {q: [compose(i[s], q, d, f) for i in items] for q in Q}))
    texts = sorted({t for _, m in cells for v in m.values() for t in v} | {context_of(i, s) for i in items for s in ("S2", "S3")})
    tok = Tokenizer.from_file(hf_hub_download("intfloat/e5-small-v2", "tokenizer.json"))
    over = {t for t in texts if len(tok.encode("query: " + t).ids) > 512}
    print(f"{len(texts)} distinct encoder inputs; {len(over)} over e5's 512-token cap (their end, the sentence, is cut off)")
    cache = OUT / "vectors.npz"; V = {}
    have = dict(np.load(cache, allow_pickle=True)) if cache.exists() else {}
    for enc in ("static", "e5"):
        key_t, key_v = f"{enc}_texts", f"{enc}_vecs"
        if key_t in have and list(have[key_t]) == texts: V[enc] = dict(zip(texts, have[key_v])); continue
        t0 = time.time(); M = static_embed(texts) if enc == "static" else embed(texts)[0]
        print(f"{enc}: encoded {len(texts)} texts in {time.time() - t0:.0f} s", flush=True)
        have[key_t] = np.array(texts, dtype=object); have[key_v] = M; V[enc] = dict(zip(texts, M))
    np.savez(cache, **have)
    idx = {i["id"]: k for k, i in enumerate(items)}; tri = [idx[i["id"]] for i in tr]; tei = [idx[i["id"]] for i in te]
    group = lambda i: next((q for q in Q if i["y"][q]), "other")
    by_g = collections.defaultdict(list)
    for k, i in enumerate(tr): by_g[group(i)].append(k)
    rng = random.Random(SEED)
    draws = {n: [sorted(sum((rng.sample(by_g[g], n // 4) for g in sorted(by_g)), [])) for _ in range(DRAWS if n < 248 else 1)] for n in SIZES}
    bal = lambda y, p: (np.mean(p[y == 1]) + np.mean(1 - p[y == 0])) / 2
    split_cells = [(f"{s} | split: sentence vector + context vector", s) for s in ("S2", "S3")]
    res = {"sizes": SIZES, "draws": DRAWS, "questions": list(Q), "wordings": QW, "test_n": len(te), "cells": {}}
    per_item = {}
    for enc in ("static", "e5"):
        for name, m in cells + split_cells:
            for q in Q:
                if isinstance(m, str):   # split variant
                    X = np.array([np.concatenate([V[enc][i["S1"]], V[enc][context_of(i, m)]]) for i in items])
                else:
                    X = np.array([V[enc][t] for t in m[q]])
                ytr = np.array([tr[k]["y"][q] for k in range(len(tr))]); yte = np.array([i["y"][q] for i in te])
                Xtr, Xte = X[tri], X[tei]; curve = []
                for n in SIZES:
                    sc = []
                    for d in draws[n]:
                        clf = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(Xtr[d], ytr[d])
                        p = clf.predict(Xte); sc.append(float(bal(yte, p)))
                        if n == 248: per_item[(enc, name, q)] = p
                    curve.append([float(np.mean(sc)), min(sc), max(sc)])
                res["cells"][f"{enc} | {name} | {q}"] = curve
            print(f"{enc:6} {name:52} " + "  ".join(f"{q} {res['cells'][f'{enc} | {name} | {q}'][-1][0]:.1%}" for q in Q), flush=True)
    # paired bootstrap at 248 vs the S1 state-only baseline of the same encoder
    brng = np.random.default_rng(SEED); B = brng.integers(0, len(te), (2000, len(te))); res["vs_baseline"] = {}
    for (enc, name, q), p in per_item.items():
        yte = np.array([i["y"][q] for i in te]); b0 = per_item[(enc, "S1 | state only", q)]
        diffs = np.array([bal(yte[b], p[b]) - bal(yte[b], b0[b]) for b in B])
        lo, hi = np.percentile(diffs, [2.5, 97.5]); res["vs_baseline"][f"{enc} | {name} | {q}"] = [float(bal(yte, p) - bal(yte, b0)), float(lo), float(hi)]
    with open(OUT / "grid_answers.jsonl", "w") as f:
        for k, i in enumerate(te):
            f.write(json.dumps({"id": i["id"], "sentence": i["S1"], "human_label": i["label"], "y": i["y"],
                                "answers_at_248": {f"{enc} | {name} | {q}": int(p[k]) for (enc, name, q), p in per_item.items()}}, ensure_ascii=False) + "\n")
    res["examples"] = {f"{s} | {f} | {d}": compose(tr[0][s], "agree", d, f) for s in STATES for f in (1, 2, 3) for d in ("minimal", "deep")}
    json.dump(res, open(OUT / "grid.json", "w"), indent=1)
    print(f"\nwrote {OUT}/grid.json, grid_answers.jsonl, vectors.npz")


if __name__ == "__main__":
    {"build": build, "train": train, "grid": grid}[sys.argv[1]]()
