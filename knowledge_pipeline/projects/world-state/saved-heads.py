"""T158-H1: loader and scorer for the saved CPU heads (function sentence head t210, factuality head). Add-only; imported by path (file name has a hyphen).
Needs the embed-zs venv (sentence_transformers, onnxruntime) and cwd = projects/world-state for expert1_runtime. CPU only, local HF cache only (HF_HUB_OFFLINE=1)."""
import os, sys, re, time, pickle, hashlib, pathlib
os.environ.setdefault("HF_HUB_OFFLINE", "1"); os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent
FUNC_PKL = HERE / "runs/pulse/function_head_v1/function_head.pkl"; FACT_PKL = HERE / "runs/pulse/factuality_v1/factuality_head.pkl"
class SavedHeads:
    def __init__(self, function=True, factuality=True):
        t0 = time.perf_counter(); self.f = pickle.load(open(FUNC_PKL, "rb")) if function and FUNC_PKL.exists() else None; self.q = pickle.load(open(FACT_PKL, "rb")) if factuality and FACT_PKL.exists() else None
        if str(HERE) not in sys.path: sys.path.insert(0, str(HERE))
        from sentence_transformers import SentenceTransformer
        self.bge = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu"); self.bge.max_seq_length = 128
        self.e5 = self.v6 = None
        if self.f:
            self.e5 = SentenceTransformer("intfloat/e5-small-v2", device="cpu"); self.e5.max_seq_length = 128
            cwd = os.getcwd(); os.chdir(HERE)
            try:
                from expert1_runtime import ExpertS; self.v6 = ExpertS("runs/expert1/expert1_v6b_student.pkl")
            finally: os.chdir(cwd)
        self.load_s = time.perf_counter() - t0
    def score(self, sents):
        """sents: list of sentence strings -> {"function_p": [...], "function_answer": [...], "factuality_p": [...]}; function_p = P(subjective/opinion) (Jev-copy label), factuality_p = P(happened)."""
        out = {}
        if not sents: return {"function_p": [], "function_answer": [], "factuality_p": []}
        Xb = self.bge.encode(sents, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
        if self.f:
            X6 = np.array([self.v6.student(t) for t in sents], dtype=np.float32); Xe = self.e5.encode(["query: " + t for t in sents], batch_size=64, normalize_embeddings=True, show_progress_bar=False)
            p = self.f["model"].predict_proba(np.hstack([X6, Xb, Xe]).astype(np.float32))[:, 1]; out["function_p"] = [float(x) for x in p]
            out["function_answer"] = ["opinion" if x > self.f["hi"] else ("fact" if x < self.f["lo"] else "unsure") for x in p]
        if self.q: out["factuality_p"] = [float(x) for x in self.q["model"].predict_proba(Xb)[:, 1]]
        return out
def sha256(path): return hashlib.sha256(open(path, "rb").read()).hexdigest()
