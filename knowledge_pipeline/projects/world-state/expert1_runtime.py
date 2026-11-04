"""Expert 1 runtime: the code that serves the artefact. Portable stack only: numpy, scipy, scikit-learn, model2vec. No GPU, no network.
    from expert1_runtime import Expert; e = Expert("runs/expert1/expert1_v2.pkl"); e.read("Headline. Description.")
Each field returns answer and status ('answered' or 'unknown'). Condition fields appear only when condition_present is answered and true (contract v1)."""
import re, pickle, numpy as np, scipy.sparse as sp
from model2vec import StaticModel
def _lg(p): p = np.clip(p, 1e-6, 1 - 1e-6); return np.log(p / (1 - p))
class Expert:
    def __init__(self, path):
        self.M = pickle.load(open(path, "rb")); self.sm = StaticModel.from_pretrained(self.M["static"]); self.cond_idx = {c: k for k, c in enumerate(self.M["cond"].classes_)}
    def read(self, text):
        if len(re.sub(r"\s+", " ", text or "").strip()) < 40:                         # gate Q08: under 40 characters cannot carry a claim
            return {k: {"answer": None, "status": "unknown", "reason": "input shorter than 40 characters"} for k in ("story_type", "topic_top2", "condition_present")}
        M = self.M; t = re.sub(r"\s+", " ", text); h = re.split(r"(?<=[.!?])\s", t, 1)[0]; e = np.hstack([self.sm.encode([t]), self.sm.encode([h])])
        xwc = sp.hstack([M["vw"].transform([t]), M["vc"].transform([t])]).tocsr(); xt = sp.hstack([M["vt"].transform([t]), sp.csr_matrix(M["ss"].transform(e) * 0.1)]).tocsr()
        ps = M["story"].predict_proba(xwc)[0]; pt = M["topic"].predict_proba(xt)[0]; o2 = np.argsort(-pt)[:2]
        pr = float(1 / (1 + np.exp(-(_lg(M["ph"].predict_proba(xwc)[:, 1]) + _lg(M["ps"].predict_proba(xwc)[:, 1])) / 2))[0]); cp = max(pr, 1 - pr)
        out = {"story_type": {"answer": str(M["story"].classes_[ps.argmax()]), "confidence": float(ps.max()), "status": "answered" if ps.max() >= M["cuts"]["story_type"] else "unknown"},
               "topic_top2": {"answer": [str(M["topic"].classes_[k]) for k in o2], "confidence": float(pt[o2].sum()), "status": "answered" if pt[o2].sum() >= M["cuts"]["topic_top2"] else "unknown"},
               "condition_present": {"answer": bool(pr > .5), "confidence": cp, "status": "answered" if cp >= M["cuts"]["condition_present"] else "unknown"}}
        if pr > .5 and out["condition_present"]["status"] == "answered":
            xc = xwc[:, M["keepc"]]; pc = M["cond"].predict_proba(xc)[0]; c2 = np.argsort(-pc)[:2]; top = M["cond"].classes_[c2[0]]
            xd = sp.hstack([xc, sp.csr_matrix(([2.0], ([0], [self.cond_idx[top]])), shape=(1, len(self.cond_idx)))]).tocsr()
            out["condition"] = {"answer": [str(M["cond"].classes_[k]) for k in c2], "confidence": float(pc.max()), "status": "answered" if pc.max() >= M["cond_cut"] else "unknown",
                                "direction": str(M["dirm"].predict(xd)[0]), "size": M["LV"][int(M["sizem"].predict(xd)[0])]}
        return out


class Expert3(Expert):
    """v3 cascade: the linear path always; the ONNX bge-small encoder only for routed items (cheap condition probability >= gate_present for which-condition, linear topic top-2 mass < gate_topic for topic).
    Stack: numpy, scipy, scikit-learn (unpickle), model2vec, onnxruntime, tokenizers. No torch."""
    def __init__(self, path, onnx_path=None, tok_path=None):
        super().__init__(path); import onnxruntime as ort; from tokenizers import Tokenizer
        onnx_path = onnx_path or self.M.get("onnx_path", "runs/embeds/bge_small.onnx"); tok_path = tok_path or self.M.get("tok_path", "runs/embeds/bge_tokenizer.json")   # the artefact names its own encoder files
        so = ort.SessionOptions(); so.intra_op_num_threads = 1; so.inter_op_num_threads = 1; self.sess = ort.InferenceSession(onnx_path, so, providers=["CPUExecutionProvider"])
        self.tk = Tokenizer.from_file(tok_path); 
        if "enc_max_tokens" not in self.M: raise ValueError("artefact has no enc_max_tokens: the encoder length used in training must be recorded, not guessed")
        self.tk.enable_truncation(max_length=self.M["enc_max_tokens"]); self.tk.no_padding(); self.H = self.M["enc_heads"]
    def embed(self, text):
        e = self.tk.encode(re.sub(r"\s+", " ", text)[:1200]); ids = np.array([e.ids], dtype=np.int64); v = self.sess.run(None, {"input_ids": ids, "attention_mask": np.ones_like(ids)})[0]
        return (v / np.linalg.norm(v, axis=1, keepdims=True))[0].astype(np.float32) * 1.5
    @staticmethod
    def _soft(z): z = z - z.max(); p = np.exp(z); return p / p.sum()
    def read(self, text, force_encoder=False):
        out = super().read(text)
        if out["condition_present"]["status"] == "unknown" and out["condition_present"].get("reason"): out["path"] = "linear"; return out
        M = self.M; t = re.sub(r"\s+", " ", text); xwc = sp.hstack([M["vw"].transform([t]), M["vc"].transform([t])]).tocsr()
        pp = float(1 / (1 + np.exp(-(_lg(M["ph"].predict_proba(xwc)[:, 1]) + _lg(M["ps"].predict_proba(xwc)[:, 1])) / 2))[0]); pt_lin = out["topic_top2"]["confidence"]
        r_c = force_encoder or pp >= M["gate_present"]; r_t = force_encoder or pt_lin < M["gate_topic"]; out["path"] = "encoder" if (r_c or r_t) else "linear"
        if not (r_c or r_t): return out
        e = self.embed(text)
        if r_t:
            H = self.H["topic"]; xt = M["vt"].transform([t]); P = self._soft(np.asarray(xt @ H["W"]).ravel() + e @ H["V"] + H["b"]); o2 = np.argsort(-P)[:2]
            out["topic_top2"] = {"answer": [str(H["classes"][k]) for k in o2], "confidence": float(P[o2].sum()), "status": "answered" if P[o2].sum() >= M["cuts"]["topic_top2"] else "unknown", "source": "encoder"}
        if r_c and out["condition_present"]["status"] == "answered" and out["condition_present"]["answer"]:
            H = self.H["cond"]; xc = xwc[:, M["keepc"]]; P = self._soft(np.asarray(xc @ H["W"]).ravel() + e @ H["V"] + H["b"]); c2 = np.argsort(-P)[:2]; top = H["classes"][c2[0]]
            xd = sp.hstack([xc, sp.csr_matrix(([2.0], ([0], [self.cond_idx[top]])), shape=(1, len(self.cond_idx)))]).tocsr()
            out["condition"] = {"answer": [str(H["classes"][k]) for k in c2], "confidence": float(P.max()), "status": "answered" if P.max() >= M["cond_cut_enc"] else "unknown", "direction": str(M["dirm"].predict(xd)[0]), "size": M["LV"][int(M["sizem"].predict(xd)[0])], "source": "encoder"}
        return out


class ExpertS(Expert3):
    """v6-student challenger: the fine-tuned leaf student (ONNX, 22.6M, one pass for every item) reads story type, topic, condition presence (stacked with the sparse gate) and which condition; direction and size keep the v5 models. Same contract as Expert3."""
    def __init__(self, path):
        Expert.__init__(self, path); import onnxruntime as ort; from tokenizers import Tokenizer
        S = self.M["student"]; so = ort.SessionOptions(); so.intra_op_num_threads = 1; so.inter_op_num_threads = 1; self.ssess = ort.InferenceSession(S["onnx_path"], so, providers=["CPUExecutionProvider"])
        self.stk = Tokenizer.from_file(S["tok_path"]); self.stk.enable_truncation(max_length=S["max_tokens"]); self.stk.no_padding(); self.S = S
    def student(self, text):
        e = self.stk.encode(re.sub(r"\s+", " ", text)[:1200]); ids = np.array([e.ids], dtype=np.int64); return self.ssess.run(None, {"input_ids": ids, "attention_mask": np.ones_like(ids)})[0][0].astype(np.float32)
    def read(self, text, force_encoder=False):
        if len(re.sub(r"\s+", " ", text or "").strip()) < 40:
            return {k: {"answer": None, "status": "unknown", "reason": "input shorter than 40 characters"} for k in ("story_type", "topic_top2", "condition_present")}
        M = self.M; S = self.S; t = re.sub(r"\s+", " ", text); xwc = sp.hstack([M["vw"].transform([t]), M["vc"].transform([t])]).tocsr(); v = self.student(text)
        lin = lambda k: v @ S[k + "_W"].T + S[k + "_b"]
        ps = self._soft(lin("s")); pt = self._soft(lin("t")); o2 = np.argsort(-pt)[:2]; lp = lin("p"); zs = (_lg(M["ph"].predict_proba(xwc)[:, 1]) + _lg(M["ps"].predict_proba(xwc)[:, 1]))[0] / 2
        z = S["stack"][0] * zs + S["stack"][1] * float(lp[1] - lp[0]) + S["stack"][2]; pr = float(1 / (1 + np.exp(-z)))
        ans = "answered" if (pr >= S["cut_yes"] or pr <= 1 - M["cuts"]["condition_present"]) else "unknown"
        out = {"story_type": {"answer": S["story_cl"][int(ps.argmax())], "confidence": float(ps.max()), "status": "answered" if ps.max() >= M["cuts"]["story_type"] else "unknown"},
               "topic_top2": {"answer": [S["topic_cl"][k] for k in o2], "confidence": float(pt[o2].sum()), "status": "answered" if pt[o2].sum() >= M["cuts"]["topic_top2"] else "unknown"},
               "condition_present": {"answer": bool(pr >= S["cut_yes"]), "confidence": max(pr, 1 - pr), "probability": pr, "status": ans}, "path": "student"}
        if out["condition_present"]["answer"] and ans == "answered":
            pc = self._soft(lin("c")); c2 = np.argsort(-pc)[:2]; top = S["cond_cl"][int(c2[0])]; xc = xwc[:, M["keepc"]]
            xd = sp.hstack([xc, sp.csr_matrix(([2.0], ([0], [self.cond_idx[top]])), shape=(1, len(self.cond_idx)))]).tocsr()
            out["condition"] = {"answer": [S["cond_cl"][int(k)] for k in c2], "confidence": float(pc.max()), "status": "answered" if pc.max() >= S["cond_cut"] else "unknown", "direction": str(M["dirm"].predict(xd)[0]), "size": M["LV"][int(M["sizem"].predict(xd)[0])]}
        return out
