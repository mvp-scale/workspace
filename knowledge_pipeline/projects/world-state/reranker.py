"""reranker: the topic re-ranker of the self-improvement loop, round 1 (runs/pulse/topic_loop/r1, ledger L2751 adopted, L2756 wiring), used by live_trace.py's topic_landing stage.
Input: the landing's 1,059 raw article-to-card cosines (Landing.encode()["sc"], text[:2000], bge-small), in card order. Model: StandardScaler + multinomial logistic regression (primary_reranker.pkl, trained on MN-DS train publishers only).
Answer: argmax of p * live_mix (the pickle's prior_correction, normalised): the reading the round-1 live check adopted. Calibrated p and the abstain line come from specs/rerank_calibration_v1.json (rerank_calibrate.py: publisher-held-out out-of-fold predictions on MN-DS train only).
Fails fast when the card list or cards_sha differ from the landing's (opt out in the caller with ALLOW_NO_RERANK=1, same pattern as ALLOW_NO_LANDING)."""
import os, json, math, pickle, hashlib, pathlib
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent; MODEL = str(HERE / "runs/pulse/topic_loop/r1/primary_reranker.pkl"); CAL = str(HERE / "specs/rerank_calibration_v1.json"); FEATS = ["log_q1", "margin", "agree_landing"]
def sha_file(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
def cal_features(q, agree):
    """q: the corrected posterior (sums to 1, K classes); agree: 1.0 when the landing's own level-1 code is the same as the re-ranker's. One path for the fit and the trace."""
    s = np.sort(q)[::-1]; return {"log_q1": round(math.log(max(float(s[0]), 1e-9)), 5), "margin": round(float(s[0] - s[1]), 5), "agree_landing": float(agree)}
def cal_prob(f, cal):
    x = (np.array([f[k] for k in cal["features"]], float) - np.array(cal["scaler_mean"])) / np.array(cal["scaler_scale"]); return 1 / (1 + math.exp(-(float(x @ np.array(cal["coef"])) + cal["intercept"])))
class Reranker:
    def __init__(self, landing, share=None, damp_k=0.5, path=MODEL, cal_path=CAL):
        m = pickle.load(open(path, "rb")); ids = list(landing.ids)
        if list(m["card_ids"]) != ids: raise RuntimeError("re-ranker card_ids differ from the landing's card list (%d vs %d cards)" % (len(m["card_ids"]), len(ids)))
        if m["cards_sha"] != landing.cards_sha: raise RuntimeError("re-ranker was trained on cards %s, the landing has cards %s" % (m["cards_sha"][:16], landing.cards_sha[:16]))
        self.m = m; self.mean = np.array(m["scaler_mean"], float); self.scale = np.array(m["scaler_scale"], float); self.W = np.array(m["coef"], float); self.b = np.array(m["intercept"], float).ravel(); self.codes = list(m["classes"]); self.live = np.array(m["live_mix"], float)
        self.model_sha16 = sha_file(path)[:16]; self.split_sha = m.get("split_sha256"); P = landing.P; self.ids = ids; self.share = share; self.damp_k = damp_k
        self.card_l1 = np.array([P.chain(q)[0] for q in ids]); self.card_l2 = [P.chain(q)[1] if len(P.chain(q)) > 1 else None for q in ids]
        self.cls_cards = [np.where(self.card_l1 == c)[0] for c in self.codes]; self.cal = None; self.cal_why = "no calibration file " + os.path.basename(cal_path)
        if os.path.exists(cal_path):
            raw = open(cal_path, "rb").read(); c = json.loads(raw)
            if c["model_sha16"] != self.model_sha16 or c["cards_sha"] != landing.cards_sha: self.cal_why = "calibration was fitted on model %s / cards %s, not %s / %s" % (c["model_sha16"], c["cards_sha"][:16], self.model_sha16, landing.cards_sha[:16])
            else: c["sha16"] = hashlib.sha256(raw).hexdigest()[:16]; self.cal = c; self.cal_why = None
        self.version = "rerank-r1; model %s; live-mix prior; %s" % (self.model_sha16, ("calib " + self.cal["sha16"]) if self.cal else "UNCALIBRATED")
    def posterior(self, sc):
        """sc: raw cosines (n_cards,) or (n, n_cards). -> corrected posterior (n, K): softmax(logits) * live_mix, normalised."""
        sc = np.atleast_2d(np.asarray(sc, float)); z = ((sc - self.mean) / self.scale) @ self.W.T + self.b; z -= z.max(1, keepdims=True); p = np.exp(z); p /= p.sum(1, keepdims=True); q = p * self.live; return q / q.sum(1, keepdims=True)
    def apply(self, sc, landing_l1):
        """-> dict(l1_code, p (floor permille / 1000 when calibrated, else None), pm, decision, top2, node, features). node = best card (damped like the landing's ranking) under the answered level-1 code, so the level-2 code the journal keeps is under it."""
        q = self.posterior(sc)[0]; o = np.argsort(-q, kind="stable")[:2]; code = self.codes[int(o[0])]; f = cal_features(q, code == landing_l1); r = {"l1_code": code, "top2": [[self.codes[int(i)], round(float(q[i]), 3)] for i in o], "q1": float(q[o[0]]), "features": f, "p": None, "pm": None, "decision": "EVIDENCE_ONLY"}
        rk = np.asarray(sc, float) - (self.damp_k * self.share if self.share is not None else 0.0); ci = self.cls_cards[int(o[0])]; j = int(ci[np.argmax(rk[ci])]); r["node"] = self.ids[j]; r["node_l2"] = self.card_l2[j]
        if self.cal: pm = int(1000 * cal_prob(f, self.cal)); r.update(pm=pm, p=pm / 1000, decision="ANSWER_L1" if pm >= self.cal["line_permille"] else "ABSTAIN")
        return r
