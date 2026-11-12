"""Gist for each of the 9 articles in article_topics.json, the first-sentences baseline, a Lean check of every selection, and blind judging files.
    CUDA_VISIBLE_DEVICES= /workspace/models/embed-zs/.venv/bin/python gist_many.py -> runs/harvest/gist_judging/{items.json,key.json,selections.json}"""
import os, json, random, subprocess, warnings
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["CUDA_VISIBLE_DEVICES"] = ""; warnings.filterwarnings("ignore")
import numpy as np
from sentence_transformers import SentenceTransformer
A = json.load(open("runs/harvest/article_topics.json"))["articles"]; BUDGET, K = 120, 4; OUT = "runs/harvest/gist_judging"
SP = "/tmp/claude-0/-workspace/9a1e4c0f-d8b5-4941-bf45-6c192267eff5/scratchpad"; LEAN = os.path.expanduser("~/.elan/bin/lean")
m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 256
enc = lambda xs: m.encode(xs, batch_size=32, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True).astype(np.float32)
lean_src = open("lean/GistSelect.lean").read(); lean_src = lean_src[:lean_src.index("-- a tiny worked example")]
def select(M, W, n):
    cov = lambda S: sum(max([M[i][j] for j in S], default=0) for i in range(n)); used = lambda S: sum(W[j] for j in S); S = []
    for _ in range(K):
        cands = [j for j in range(n) if j not in S and used(S) + W[j] <= BUDGET]; best = None
        for j in cands:
            if best is None or cov(S + [best]) - cov(S) < cov(S + [j]) - cov(S): best = j
        if best is None or not cov(S + [best]) - cov(S) > 0: break
        S.append(best)
    return S, cov
rng = random.Random(20261107); items = []; key = []; sel = []
for a in A:
    sents = a["sentences"]; n = len(sents); E = enc(sents); M = np.maximum(np.rint(E @ E.T * 1000).astype(int), 0).tolist(); W = [len(s.split()) for s in sents]
    S, cov = select(M, W, n); first = []
    for j in range(n):
        if len(first) < K and sum(W[x] for x in first) + W[j] <= BUDGET: first.append(j)
        else: break
    src = lean_src + "\ndef tabM : Array (Array Nat) := #[" + ", ".join("#[" + ", ".join(map(str, r)) + "]" for r in M) + "]\ndef tabW : Array Nat := #[" + ", ".join(map(str, W)) + f"]\n#eval greedy (fun i j => tabM[i]![j]!) (fun j => tabW[j]!) {n} {BUDGET} {K} []\n"
    open(f"{SP}/GistRun_{a['idx']}.lean", "w").write(src); out = subprocess.run([LEAN, f"{SP}/GistRun_{a['idx']}.lean"], capture_output=True, text=True).stdout.strip().splitlines(); lp = json.loads(out[-1]) if out and out[-1].startswith("[") else None
    g_txt = " ".join(sents[j] for j in sorted(S)); f_txt = " ".join(sents[j] for j in first); swap = rng.random() < 0.5; A_, B_ = (f_txt, g_txt) if swap else (g_txt, f_txt)
    items.append({"id": f"art{len(items)+1}", "title": a["title"], "article": " ".join(sents), "text_A": A_, "text_B": B_})
    key.append({"id": items[-1]["id"], "A_is": "first_sentences" if swap else "gist", "B_is": "gist" if swap else "first_sentences"})
    sel.append({"id": items[-1]["id"], "idx": a["idx"], "title": a["title"], "sentences": n, "gist_pieces": [j + 1 for j in S], "gist_words": sum(W[j] for j in S), "first_pieces": [j + 1 for j in first], "first_words": sum(W[j] for j in first), "coverage_gist": round(cov(S) / (n * 1000), 3), "coverage_first": round(cov(first) / (n * 1000), 3), "lean_pieces": None if lp is None else [j + 1 for j in lp], "python_equals_lean": lp == S, "gist_beyond_first_250_words": sum(1 for j in S if sum(W[:j + 1]) > 250)})
    print(items[-1]["id"], a["title"][:40], "| gist", [j + 1 for j in S], "first", [j + 1 for j in first], "| lean agrees:", lp == S, "| coverage", sel[-1]["coverage_gist"], "vs", sel[-1]["coverage_first"], flush=True)
json.dump(items, open(f"{OUT}/items.json", "w"), indent=1); json.dump(key, open(f"{OUT}/key.json", "w"), indent=1); json.dump(sel, open(f"{OUT}/selections.json", "w"), indent=1)
