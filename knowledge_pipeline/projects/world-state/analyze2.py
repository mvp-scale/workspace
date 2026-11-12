"""analyze2: the consolidated tool. One call, article in, Pulse out, with the working.
Differences from analyze.py: one decider source (decider.py); facts functions imported (facts_lib.py), no exec; windows leave room for the headline so no body text is cut; one batched encoder pass over all windows with several threads; the parse runs only if the article has numbers or dates; named record for each proposal."""
import json, re, time
from dataclasses import dataclass
import numpy as np, onnxruntime as ort
from tokenizers import Tokenizer
import decider as D, facts_lib as FL, span_rules as SR
def softmax(z): z = z - z.max(axis=-1, keepdims=True); p = np.exp(z); return p / p.sum(axis=-1, keepdims=True)
@dataclass
class Proposal: source: D.Source; confidence: float; validated: bool; answer: str; how: str
class Reader:
    """BitMob Domain v6b-student (registry; formerly BitMob Expert 1 v6b-student and Pulse reader). Whole article in windows; probabilities averaged."""
    def __init__(self, S, threads=8, max_pieces=64, cap=12, fit_headline=True):
        self.S, self.max_pieces, self.cap, self.fit = S, max_pieces, cap, fit_headline
        self.tk = Tokenizer.from_file(S["tok_path"]); self.tk.no_truncation()
        self.tkt = Tokenizer.from_file(S["tok_path"]); self.tkt.enable_truncation(max_length=max_pieces); self.tkt.no_padding()
        so = ort.SessionOptions(); so.intra_op_num_threads = threads; so.inter_op_num_threads = 1
        self.sess = ort.InferenceSession(S["onnx_path"], so, providers=["CPUExecutionProvider"]); self.tW, self.tb, self.sW, self.sb = S["t_W"].T, S["t_b"], S["s_W"].T, S["s_b"]
    def windows(self, title, body):
        b = re.sub(r"\s+", " ", body); off = [o for o in self.tk.encode(b).offsets if o[1] > o[0]]
        k = self.max_pieces - (len(self.tk.encode(re.sub(r"\s+", " ", title) + ". ").ids) if self.fit else 0); k = max(k, 8); out = []
        for i in range(0, len(off), k):
            seg = off[i:i + k]; out.append(b[seg[0][0]:seg[-1][1]])
            if len(out) >= self.cap: break
        return out or [b]
    def read(self, title, body):
        t = re.sub(r"\s+", " ", title); W = [t + ". " + w for w in self.windows(title, body)]; enc = self.tkt.encode_batch([w[:1200] for w in W]); L = max(len(x.ids) for x in enc)
        ids = np.zeros((len(enc), L), dtype=np.int64); m = np.zeros((len(enc), L), dtype=np.int64)
        for i, x in enumerate(enc): ids[i, :len(x.ids)] = x.ids; m[i, :len(x.ids)] = 1
        V = self.sess.run(None, {"input_ids": ids, "attention_mask": m})[0]
        return softmax(V @ self.tW + self.tb).mean(0), softmax(V @ self.sW + self.sb).mean(0), len(W)
NUM_OR_DATE = re.compile(r"\d|\b(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|dozens?|hundreds?|yesterday|today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.I)
class Analyzer:
    def __init__(self, S, field_table, thr=700, sparse=None, **kw):
        self.S, self.FT, self.thr, self.reader = S, field_table, thr, Reader(S, **kw); self.sparse = None
        if sparse:  # sparse heads in front of the reader (Rounds 1 and 2): when both are confident they answer topic and story type and the encoder is skipped
            import pickle; self.sparse = pickle.load(open(sparse, "rb"))
            for k in ("story", "topic"):  # sklearn's predict_proba on one sparse row took 1.5 s; the same sums as one matrix product take 0.1 ms (max difference 6e-07)
                m = self.sparse[k + "_model"]; self.sparse[k + "_W"] = np.ascontiguousarray(m.coef_.T.astype(np.float32)); self.sparse[k + "_b"] = m.intercept_.astype(np.float32)
    def _sparse_proba(self, k, x):
        H = self.sparse; z = np.asarray(H[k + "_vec"].transform([x]).astype(np.float32) @ H[k + "_W"]).ravel() + H[k + "_b"]; p = 1 / (1 + np.exp(-z)); t = p.sum()
        return p / t if t > 0 else np.full_like(p, 1 / len(p))
    def sparse_read(self, title, body):
        H = self.sparse; x = re.sub(r"\s+", " ", title + ". " + body)[:12000]
        ps = self._sparse_proba("story", x); pt = self._sparse_proba("topic", x)
        o2 = np.argsort(-pt)[:2]; sc, tm = float(ps.max()), float(pt[o2].sum())
        if sc >= H["story_thr"] and tm >= H["topic_thr"]: return H["story_model"].classes_[int(ps.argmax())], sc, " / ".join(str(H["topic_model"].classes_[k]) for k in o2), tm
        return None
    def analyze(self, title, body, date=None):
        T = {}; t0 = time.perf_counter(); sr = self.sparse_read(title, body) if self.sparse else None
        if sr is None: pt, ps, nw = self.reader.read(title, body); o2 = np.argsort(-pt)[:2]
        T["reader_ms"] = (time.perf_counter() - t0) * 1000
        t1 = time.perf_counter(); text = re.sub(r"\s+", " ", title + ". " + body)[:12000]; parsed = bool(NUM_OR_DATE.search(text)); facts = FL.facts_for(text, (date + "T00:00:00Z") if date else None)[0] if parsed else []
        T["solver_ms"] = (time.perf_counter() - t1) * 1000; t1b = time.perf_counter(); sp_ = SR.spans(text, (date + "T00:00:00Z") if date else None); T["span_rules_ms"] = (time.perf_counter() - t1b) * 1000; am = [f for f in facts if f["kind"] == "amount" and f["status"] == "stated"]; dt = [f for f in facts if f["kind"] == "date" and f["status"] == "stated"]
        if sr is not None: nw = 0; st_ = Proposal(D.Source.TRAINED_HEAD, sr[1], True, str(sr[0]), "sparse head, encoder skipped"); tp_ = Proposal(D.Source.TRAINED_HEAD, sr[3], True, sr[2], "sparse head, encoder skipped")
        else: st_ = Proposal(D.Source.TRAINED_HEAD, float(ps.max()), True, self.S["story_cl"][int(ps.argmax())], f"reader, {nw} windows"); tp_ = Proposal(D.Source.TRAINED_HEAD, float(pt[o2].sum()), True, " / ".join(self.S["topic_cl"][k] for k in o2), f"reader, {nw} windows")
        P = {"story_type": st_,
             "topic": tp_,
             "change": Proposal(D.Source.STATED_FACT, 0.0, False, "not run", "no extractor wired yet"),
             "size": Proposal(D.Source.STATED_FACT, 0.0, bool(am), "; ".join(f["text"] + " (" + (f["noun"] or f["verb"] or "") + ")" for f in am[:4]) or "no stated amount", f"solver, {len(am)} amounts stated"),
             "traits": Proposal(D.Source.STATED_FACT, 0.0, False, "not run", "no extractor wired yet")}
        t2 = time.perf_counter(); res = {}
        for k, p in P.items():
            o = D.decide(self.FT[k]["marker"], p.source, p.validated, int(1000 * p.confidence), self.thr, True)
            res[k] = {"outcome": o.name, "answer": p.answer if o >= D.Outcome.ANSWER_PROVISIONAL else None, "proposed": p.answer, "confidence": p.confidence if p.source == D.Source.TRAINED_HEAD else None, "how": p.how}
        T["decider_ms"] = (time.perf_counter() - t2) * 1000; T["total_ms"] = sum(T.values())
        return {"fields": res, "evidence": {"stated_amounts": [f["text"] for f in am[:8]], "stated_dates": [f["text"] for f in dt[:5]], "windows": nw, "encoder_skipped": sr is not None, "parse_ran": parsed, "span_rules": {"counts": dict(__import__("collections").Counter(x["kind"] for x in sp_)), "items": [[x["kind"], x["s"], x["e"], x["value"]] for x in sp_ if x["kind"] != "number_word" or x["value"] is not None][:60], "tool": "span-rules-v0"}}, "ms": {k: round(v, 3) for k, v in T.items()}}
