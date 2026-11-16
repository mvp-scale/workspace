"""analyze2: the consolidated tool. One call, article in, Pulse out, with the working.
Differences from analyze.py: one decider source (decider.py); facts functions imported (facts_lib.py), no exec; windows leave room for the headline so no body text is cut; one batched encoder pass over all windows with several threads; the parse runs only if the article has numbers or dates; named record for each proposal."""
import json, re, time
from dataclasses import dataclass
import numpy as np, onnxruntime as ort
from tokenizers import Tokenizer
import decider as D, facts_lib as FL, span_rules as SR, extract as EX
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
    def window_spans(self, title, body):
        r"""Offsets (a, b) of each window in b = re.sub(r"\s+", " ", body); windows() cuts b[a:b]. Pure function of its arguments."""
        b = re.sub(r"\s+", " ", body); off = [o for o in self.tk.encode(b).offsets if o[1] > o[0]]
        k = self.max_pieces - (len(self.tk.encode(re.sub(r"\s+", " ", title) + ". ").ids) if self.fit else 0); k = max(k, 8); out = []
        for i in range(0, len(off), k):
            seg = off[i:i + k]; out.append((seg[0][0], seg[-1][1]))
            if len(out) >= self.cap: break
        return out or [(0, len(b))]
    def windows(self, title, body):
        b = re.sub(r"\s+", " ", body); return [b[x:y] for x, y in self.window_spans(title, body)]
    def _forward(self, title, body):
        t = re.sub(r"\s+", " ", title); spans = self.window_spans(title, body); b = re.sub(r"\s+", " ", body); W = [t + ". " + b[x:y] for x, y in spans]; enc = self.tkt.encode_batch([w[:1200] for w in W]); L = max(len(x.ids) for x in enc)
        ids = np.zeros((len(enc), L), dtype=np.int64); m = np.zeros((len(enc), L), dtype=np.int64)
        for i, x in enumerate(enc): ids[i, :len(x.ids)] = x.ids; m[i, :len(x.ids)] = 1
        return self.sess.run(None, {"input_ids": ids, "attention_mask": m})[0], spans
    def read(self, title, body):
        V, spans = self._forward(title, body)
        return softmax(V @ self.tW + self.tb).mean(0), softmax(V @ self.sW + self.sb).mean(0), len(spans)
    def read_detail(self, title, body, keep_vectors=False):
        r"""Same pass as read(), with the working kept (T150 P1c). Returns {pt, ps, nw, offsets, offsets_text, pt_w, ps_w[, V]}. pt, ps, nw equal read()'s three values. offsets are in re.sub(r"\s+", " ", body); offsets_text are in the analysis text re.sub(r"\s+", " ", title + ". " + body). pt_w and ps_w are per-window probabilities (rows = windows); their mean over rows is pt and ps. V (window vectors) only when keep_vectors=True. Stateless, so safe on the shared Analyzer."""
        V, spans = self._forward(title, body); pt_w = softmax(V @ self.tW + self.tb); ps_w = softmax(V @ self.sW + self.sb)
        pre = len(re.sub(r"\s+", " ", title)) + 2 - (1 if re.sub(r"\s+", " ", body).startswith(" ") else 0)
        d = {"pt": pt_w.mean(0), "ps": ps_w.mean(0), "nw": len(spans), "offsets": [list(x) for x in spans], "offsets_text": [[x + pre, y + pre] for x, y in spans], "pt_w": pt_w, "ps_w": ps_w}
        if keep_vectors: d["V"] = V
        return d
CHG_TOOL, CHG_VER, FAC_TOOL, FAC_VER = "change-lexicon", "change-lexicon-v0", "factuality-tagger", "factuality-rules-v1"  # same strings extract.py writes (checked by the P2 test)
BUNDLE_PROV = {"change-lexicon": "Inferred", "factuality-tagger": "Inferred", "fact-finder": "Observed"}  # mirrors pool_build.PROV, a PROPOSAL awaiting owner confirmation (T150 P1d)
NOT_ASSERTED = {"predicted", "denied", "question"}  # a frame in such a sentence gets asserted=False (target page, Condition rule)
def _thing_tok(t):
    """The token extract's change loop names as 'thing' (same four rules as EX.sentence_tags; that function returns only its lemma)."""
    thing = None
    for c in t.children:
        if c.dep_ in ("nsubj", "nsubjpass", "dobj"): thing = c
        elif c.dep_ == "prep" and c.lower_ in ("in", "of"): thing = next((g for g in c.children if g.dep_ == "pobj"), thing)
    return thing
TIME_UNITS = {"second", "minute", "hour", "day", "week", "month", "year", "quarter", "decade", "century", "time", "period"}  # "fell in 30 hours": the amount counts time, not the thing that changed
def _amount_head(doc, s, e):
    """The token the amount hangs from: the head of the amount's span (as FL.head_of), stepping over at most two prepositions or auxiliaries (rose BY 5%, an increase OF 5%). No climb to a verb further up, so an amount cannot bind to a change word through a long chain."""
    sp = doc.char_span(s, e, alignment_mode="expand")
    if sp is None or len(sp) == 0: return None
    inside = {t.i for t in sp}; cand = [t.head for t in sp if t.head.i not in inside]; h = cand[0] if cand else None; hops = 0
    while h is not None and h.pos_ in ("ADP", "AUX", "PART", "SYM") and h.head.i != h.i and hops < 2: h = h.head; hops += 1
    return h
def build_bundles(doc, text, facts):
    r"""Evidence bundles for change (T151 P2c). One per NON-negated change-lexicon hit on the parse `doc` of `text`: {id, dial (= condition), direction, thing, size, sentence [s,e], span [s,e] of the change word, text (the word, from the parse), factuality (sentence tag), asserted, tool, version, factuality_tool, factuality_version, provenance}. size = the first amount with status 'stated' lying in the same sentence that hangs directly from the change word ('change': rose 5%, rose by 5%, an increase of 5%) or from its thing ('thing'), at most two prepositions away, else None. Evidence only: nothing reads it to answer a field. Returns (bundles, info)."""
    fx, ch, sc = EX.sentence_tags(doc); out = []; neg = 0; amts = [f for f in facts if f["kind"] == "amount" and f["status"] == "stated"]
    for h in ch:
        if h["negated"]: neg += 1; continue
        a, b = h["span"]; sent = next((x for x in fx if x[0] <= a < x[1]), None)
        if sent is None: continue
        tok = doc.char_span(a, b); tok = tok[0] if tok is not None and len(tok) == 1 else None; thing = _thing_tok(tok) if tok is not None else None; size = None; names = {x for x in (tok.lower_ if tok is not None else None, thing.lower_ if thing is not None else None, thing.lemma_.lower() if thing is not None else None) if x}
        if tok is not None:
            bound = []
            for f in amts:
                if not (sent[0] <= f["s"] and f["e"] <= sent[1]): continue
                h_ = _amount_head(doc, f["s"], f["e"])
                via = None if h_ is None else ("change" if h_.i == tok.i else ("thing" if (h_.lower_ in names or h_.lemma_.lower() in names) and h_.lemma_.lower() not in TIME_UNITS else None))
                if via: bound.append((0 if via == "change" else 1, f["s"], f, via))
            if bound: _, _, f, via = min(bound, key=lambda x: x[:2]); size = {"text": f["text"], "span": [f["s"], f["e"]], "value": f["value"], "unit": f["unit"], "status": f["status"], "bound_via": via, "tool": FL.FACT_TOOL, "version": FL.FACT_VERSION, "provenance": BUNDLE_PROV["fact-finder"]}
        out.append({"id": "chg-%d-%d" % (a, b), "dial": h["condition"], "condition": h["condition"], "direction": h["direction"], "thing": h["thing"], "size": size, "sentence": [sent[0], sent[1]], "span": [a, b], "text": h["word"], "factuality": sent[2], "asserted": sent[2] not in NOT_ASSERTED,
                    "tool": CHG_TOOL, "version": CHG_VER, "factuality_tool": FAC_TOOL, "factuality_version": FAC_VER, "provenance": BUNDLE_PROV[CHG_TOOL]})
    bad = {x["i"]: x["why"] for x in FL.check_literal([{"span": b_["span"], "text": b_["text"]} for b_ in out], text)}  # the change word as the parse names it must be the text slice
    bad.update({i: "size span: " + w["why"] for i, b_ in enumerate(out) if b_["size"] for w in FL.check_literal([{"span": b_["size"]["span"], "text": b_["size"]["text"]}], text)})
    kept = [b_ for i, b_ in enumerate(out) if i not in bad]; held = [{"id": b_["id"], "why": bad[i]} for i, b_ in enumerate(out) if i in bad]
    return kept, {"negated_skipped": neg, "held": held, "hits": len(ch)}
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
        wd = None
        if sr is None: det = self.reader.read_detail(title, body); pt, ps, nw = det["pt"], det["ps"], det["nw"]; o2 = np.argsort(-pt)[:2]; wd = {"n": nw, "offsets": det["offsets_text"], "topic_top2": [[[int(k), round(float(r[k]), 6)] for k in np.argsort(-r)[:2]] for r in det["pt_w"]], "story_top2": [[[int(k), round(float(r[k]), 6)] for k in np.argsort(-r)[:2]] for r in det["ps_w"]]}
        T["reader_ms"] = (time.perf_counter() - t0) * 1000
        t1 = time.perf_counter(); text = re.sub(r"\s+", " ", title + ". " + body)[:12000]; parsed = bool(NUM_OR_DATE.search(text)); doc_ = None; ff = FL.facts_for(text, (date + "T00:00:00Z") if date else None) if parsed else None; facts = ff[0] if ff else []; doc_ = ff[2] if ff else None; facts, held_f = FL.quarantine(facts, text)  # a fact whose span no longer holds its text is held back before any layer reads it (T150)
        T["solver_ms"] = (time.perf_counter() - t1) * 1000; t1b = time.perf_counter(); sp_ = SR.spans(text, (date + "T00:00:00Z") if date else None); sp_, held_s = FL.quarantine(sp_, text); T["span_rules_ms"] = (time.perf_counter() - t1b) * 1000; t1c = time.perf_counter(); extra_parse = doc_ is None; doc_ = FL.nlp(text) if extra_parse else doc_; bundles, binfo = build_bundles(doc_, text, facts); binfo.update({"parse": "extra, tags only" if extra_parse else "shared with the fact finder"}); T["bundle_ms"] = (time.perf_counter() - t1c) * 1000; am = [f for f in facts if f["kind"] == "amount" and f["status"] == "stated"]; dt = [f for f in facts if f["kind"] == "date" and f["status"] == "stated"]
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
        return {"fields": res, "evidence": {"stated_amounts": [f["text"] for f in am[:8]], "stated_dates": [f["text"] for f in dt[:5]], "windows": nw, "windows_detail": wd if wd is not None else {"n": 0, "offsets": [], "sparse_path": True}, "quarantined": [{"kind": x.get("kind"), "s": (x["span"][0] if "span" in x else x.get("s")), "e": (x["span"][1] if "span" in x else x.get("e")), "why": x.get("why")} for x in held_f + held_s], "encoder_skipped": sr is not None, "parse_ran": parsed, "bundles": bundles, "bundles_info": binfo, "span_rules": {"counts": dict(__import__("collections").Counter(x["kind"] for x in sp_)), "items": [[x["kind"], x["s"], x["e"], x["value"]] for x in sp_ if x["kind"] != "number_word" or x["value"] is not None][:60], "tool": "span-rules-v0"}}, "ms": {k: round(v, 3) for k, v in T.items()}}
