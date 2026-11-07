"""analyze2: the consolidated tool. One call, article in, Pulse out, with the working.
Differences from analyze.py: one decider source (decider.py); facts functions imported (facts_lib.py), no exec; windows leave room for the headline so no body text is cut; one batched encoder pass over all windows with several threads; the parse runs only if the article has numbers or dates; named record for each proposal."""
import json, re, time
from dataclasses import dataclass
import numpy as np, onnxruntime as ort
from tokenizers import Tokenizer
import decider as D, facts_lib as FL
def softmax(z): z = z - z.max(axis=-1, keepdims=True); p = np.exp(z); return p / p.sum(axis=-1, keepdims=True)
@dataclass
class Proposal: source: D.Source; confidence: float; validated: bool; answer: str; how: str
class Reader:
    """BitMob Reader v6b-student (registry; formerly BitMob Expert 1 v6b-student and Pulse reader). Whole article in windows; probabilities averaged."""
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
    def __init__(self, S, field_table, thr=700, **kw): self.S, self.FT, self.thr, self.reader = S, field_table, thr, Reader(S, **kw)
    def analyze(self, title, body, date=None):
        T = {}; t0 = time.perf_counter(); pt, ps, nw = self.reader.read(title, body); o2 = np.argsort(-pt)[:2]; T["reader_ms"] = (time.perf_counter() - t0) * 1000
        t1 = time.perf_counter(); text = re.sub(r"\s+", " ", title + ". " + body)[:12000]; parsed = bool(NUM_OR_DATE.search(text)); facts = FL.facts_for(text, (date + "T00:00:00Z") if date else None)[0] if parsed else []
        T["solver_ms"] = (time.perf_counter() - t1) * 1000; am = [f for f in facts if f["kind"] == "amount" and f["status"] == "stated"]; dt = [f for f in facts if f["kind"] == "date" and f["status"] == "stated"]
        P = {"story_type": Proposal(D.Source.TRAINED_HEAD, float(ps.max()), True, self.S["story_cl"][int(ps.argmax())], f"reader, {nw} windows"),
             "topic": Proposal(D.Source.TRAINED_HEAD, float(pt[o2].sum()), True, " / ".join(self.S["topic_cl"][k] for k in o2), f"reader, {nw} windows"),
             "change": Proposal(D.Source.STATED_FACT, 0.0, False, "not run", "no extractor wired yet"),
             "size": Proposal(D.Source.STATED_FACT, 0.0, bool(am), "; ".join(f["text"] + " (" + (f["noun"] or f["verb"] or "") + ")" for f in am[:4]) or "no stated amount", f"solver, {len(am)} amounts stated"),
             "traits": Proposal(D.Source.STATED_FACT, 0.0, False, "not run", "no extractor wired yet")}
        t2 = time.perf_counter(); res = {}
        for k, p in P.items():
            o = D.decide(self.FT[k]["marker"], p.source, p.validated, int(1000 * p.confidence), self.thr, True)
            res[k] = {"outcome": o.name, "answer": p.answer if o >= D.Outcome.ANSWER_PROVISIONAL else None, "proposed": p.answer, "confidence": p.confidence if p.source == D.Source.TRAINED_HEAD else None, "how": p.how}
        T["decider_ms"] = (time.perf_counter() - t2) * 1000; T["total_ms"] = sum(T.values())
        return {"fields": res, "evidence": {"stated_amounts": [f["text"] for f in am[:8]], "stated_dates": [f["text"] for f in dt[:5]], "windows": nw, "parse_ran": parsed}, "ms": {k: round(v, 3) for k, v in T.items()}}
