"""Gist of ONE article: greedy coverage selection of sentences within a word budget (reference for lean/GistSelect.lean).
Similarities are integers (cosine x 1000). Coverage = sum over sentences of the best similarity to a chosen sentence.
    CUDA_VISIBLE_DEVICES= /workspace/models/embed-zs/.venv/bin/python gist.py -> runs/harvest/article_gist.json"""
import os, json, subprocess, warnings
os.environ["HF_HOME"] = "/workspace/data/hf"; os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["CUDA_VISIBLE_DEVICES"] = ""; warnings.filterwarnings("ignore")
import numpy as np
from sentence_transformers import SentenceTransformer
L = json.load(open("runs/harvest/article_levels.json")); B = json.load(open("runs/harvest/article_beats.json")); sents = B["all_sentences"]; n = len(sents); BUDGET, K = 120, 4
m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); m.max_seq_length = 256
enc = lambda xs: m.encode(xs, batch_size=32, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True).astype(np.float32)
E = enc(sents); M = np.rint(E @ E.T * 1000).astype(int); M = np.maximum(M, 0); W = [len(s.split()) for s in sents]
def credit(S, i): return max([M[i][j] for j in S], default=0)
def coverage(S): return sum(credit(S, i) for i in range(n))
def used(S): return sum(W[j] for j in S)
def greedy(fuel, S=None):
    S = list(S or [])
    for _ in range(fuel):
        cands = [j for j in range(n) if j not in S and used(S) + W[j] <= BUDGET]; best = None
        for j in cands:
            if best is None or (coverage(S + [best]) - coverage(S)) < (coverage(S + [j]) - coverage(S)): best = j
        if best is None or not (coverage(S + [best]) - coverage(S)) > 0: break
        S.append(best)
    return S
S = greedy(K); steps = []; cur = []
for j in S: before = coverage(cur); cur = cur + [j]; steps.append({"piece": j + 1, "words": W[j], "gain": int(coverage(cur) - before), "coverage_after": round(coverage(cur) / (n * 1000), 3)})
first = []; 
for j in range(n):
    if len(first) < K and used(first) + W[j] <= BUDGET: first.append(j)
    else: break
cut_sent = len(B["beats"]["first_250_words"]["pieces"])  # sentences that fit in the first 250 words
# similarity of each text to the full article (mean of 250-word chunks)
words = L["raw"]["body"].split(); chunks = [" ".join(words[a:a + 250]) for a in range(0, len(words), 250)]; full = enc(chunks).mean(axis=0); full /= np.linalg.norm(full)
def to_full(idx): return round(float(enc([" ".join(sents[j] for j in sorted(idx))])[0] @ full), 3)
# the same selection by Lean, from the same integer table
lean_src = open("lean/GistSelect.lean").read(); lean_src = lean_src[:lean_src.index("-- a tiny worked example")]
tab = "def tabM : Array (Array Nat) := #[" + ", ".join("#[" + ", ".join(str(int(x)) for x in row) + "]" for row in M) + "]\ndef tabW : Array Nat := #[" + ", ".join(map(str, W)) + "]\n"
run = lean_src + "\n" + tab + f"#eval greedy (fun i j => tabM[i]![j]!) (fun j => tabW[j]!) {n} {BUDGET} {K} []\n"
os.makedirs("/tmp/claude-0/-workspace/9a1e4c0f-d8b5-4941-bf45-6c192267eff5/scratchpad", exist_ok=True); open("/tmp/claude-0/-workspace/9a1e4c0f-d8b5-4941-bf45-6c192267eff5/scratchpad/GistRun.lean", "w").write(run)
out = subprocess.run([os.path.expanduser("~/.elan/bin/lean"), "/tmp/claude-0/-workspace/9a1e4c0f-d8b5-4941-bf45-6c192267eff5/scratchpad/GistRun.lean"], capture_output=True, text=True).stdout.strip().splitlines()
lean_pick = json.loads(out[-1]) if out and out[-1].startswith("[") else None
res = {"v": "article-gist-v0", "idx": B["idx"], "title": B["title"], "budget_words": BUDGET, "max_pieces": K, "model": "BAAI/bge-small-en-v1.5 (CPU)", "pieces": n,
       "gist": [{"piece": j + 1, "text": sents[j], "words": W[j], "inside_first_250_words": bool(j < cut_sent)} for j in sorted(S)], "pick_order": [j + 1 for j in S], "steps": steps,
       "coverage": {"gist": round(coverage(S) / (n * 1000), 3), "first_pieces": round(coverage(first) / (n * 1000), 3)}, "first_pieces": [j + 1 for j in first], "similarity_to_full_article": {"gist": to_full(S), "first_pieces": to_full(first)},
       "lean_pick_order": None if lean_pick is None else [j + 1 for j in lean_pick], "python_equals_lean": lean_pick == S}
json.dump(res, open("runs/harvest/article_gist.json", "w"), indent=1); print(json.dumps({k: res[k] for k in ("pick_order", "steps", "coverage", "first_pieces", "similarity_to_full_article", "lean_pick_order", "python_equals_lean")}, indent=0)); [print(" ", g["piece"], g["words"], g["inside_first_250_words"], g["text"][:100]) for g in res["gist"]]
