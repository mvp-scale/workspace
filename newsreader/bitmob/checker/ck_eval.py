"""Score BitMob + CPU checker (no Clef at serving) against Clef on the 2,000-story frozen test with score_mh.py's definitions. Every threshold is fitted on the 894 Clef tune rows only.
  CUDA_VISIBLE_DEVICES= kev/.venv/bin/python newsreader/bitmob/checker/ck_eval.py CHECKER_DIR OUT.json
Steps: cond (shortlist at tune-fit 95% raw cut -> checker mean of 2 wordings -> global pivot c fitted on tune), gate (4 questions, stories unsure by +-d), expected (shortlist among BitMob's allowed+unreported dials)."""
import os, sys, json, time, resource, itertools, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh", os.path.dirname(os.path.abspath(__file__))]
import torch; torch.set_num_threads(8)
import classify as C
from mh_common import load, predict, calibrate_cond, apply_reading_floor
from ck_common import ck_load, ck_predict, ck_text
import ck_questions as Q
CK, OUT = sys.argv[1], sys.argv[2]; B = "/workspace/data/kaggle/mh_r6c1"; D = "/workspace/data/checker"
R = [json.loads(l) for l in open("/workspace/data/clef-labels/test.jsonl")]; N = len(R); tune = np.load(f"{D}/bm_tune.npz"); tt = json.load(open(f"{B}/tune/texts.json")); Zt = np.load(f"{B}/tune/targets.npz"); keep = tune["keep"]; tun_txt = [tt[i] for i in keep]; NT = len(keep)
model, tok, K = load(f"{B}/out/mh"); cc, rc = model.cond_cuts, model.reading_cuts
for a in ("cond_cuts", "gate_cuts", "exp_cuts", "reading_cuts"): setattr(model, a, None)
t0 = time.time(); H = predict(model, tok, [r["state_text"] for r in R]); bm_ms = (time.time() - t0) / N * 1000; print("BitMob raw", round(bm_ms, 1), "ms/story", flush=True)
ck, ctok = ck_load(CK); nparam = sum(p.numel() for p in ck.parameters())
A = [k.split("|") for k in K["cond"]]; G, DIALS, EXPK, LV = K["gate"], K["severity"], K["expected"], K["levels"]; gi = [G.index(k) for k in Q.GATE_Q]
cond_ship = lambda raw, reading: apply_reading_floor(calibrate_cond(raw, cc), reading, rc, K)
ATT_OF = {}
for j, (d, dr, i) in enumerate(A): ATT_OF.setdefault((d, dr), []).append(j)
# ---------------- helpers
def cond_pairs(Hc, txt, cut):
    sl = [np.where(Hc[n] >= cut)[0] for n in range(len(txt))]
    return sl, [(n, j, w) for n in range(len(txt)) for j in sl[n] for w in (0, 1)]
def run_ck(items, txt, qf):
    texts = [ck_text(qf(it), txt[it[0]]) for it in items]; return ck_predict(ck, ctok, texts) if texts else np.zeros(0)
def cond_with(Hc, txt, cut, c, vals=None):
    """-> new cond matrix: shortlisted attributes get the (pivoted) checker mean; vals = precomputed dict (n,j)->mean"""
    out = np.minimum(Hc, C.ATTR_MIN - 0.01)      # only shortlisted attributes may fire (BitMob alone cannot trigger outside the shortlist)
    for (n, j), v in vals.items(): out[n, j] = v if c is None else (.65 * v / c if v <= c else .65 + .35 * (v - c) / (1 - c))
    return out
def ck_means(Hc, txt, cut):
    sl, items = cond_pairs(Hc, txt, cut); p = run_ck(items, txt, lambda it: Q.cond_q(*A[it[1]][:2], int(A[it[1]][2]), it[2])); m = {}
    for (n, j, w), v in zip(items, p): m.setdefault((n, j), []).append(v)
    return {k: float(np.mean(v)) for k, v in m.items()}, {k: float(v[0]) for k, v in m.items()}, sl
def keys_from_cond(cm):
    """engine rule on cond (n,159) matrix -> set of (dial,dir) fired (conflicts excluded)"""
    out = []
    for n in range(len(cm)):
        s = set()
        for d in {k[0] for k in ATT_OF}:
            pr = {dr for dr in ("up", "down") if (d, dr) in ATT_OF and (cm[n, ATT_OF[(d, dr)]] >= C.ATTR_MIN).any()}
            if len(pr) == 1: s.add((d, next(iter(pr))))
        out.append(s)
    return out
def tpr_fpr(pred, truth):
    tp = sum(len(p & t) for p, t in zip(pred, truth)); pos = sum(len(t) for t in truth); fp = sum(len(p - t) for p, t in zip(pred, truth)); neg = 78 * len(truth) - pos; return tp / pos, fp / neg, tp, fp, pos
# ---------------- tune side (everything fitted here)
Ht = tune["cond"]; Yt = tune["y_cond"]; ys = np.sort(Ht[Yt >= C.ATTR_MIN])[::-1]; CUT = float(ys[int(.95 * len(ys)) - 1]); print("tune-fit 95% raw cut", CUT, flush=True)
truth_t = keys_from_cond(Yt); ship_t = cond_ship(Ht, tune["reading"]); m_t, m1_t, sl_t = ck_means(Ht, tun_txt, CUT)
best = None; rows = []
for c in [None] + [round(x, 2) for x in np.arange(0.10, 0.91, 0.05)]:
    pr = keys_from_cond(cond_with(ship_t, tun_txt, CUT, c, m_t)); tp, fp, _, nfp, pos = tpr_fpr(pr, truth_t); rows.append((c, tp, fp)); ok = fp <= 0.0008
    if ok and (best is None or tp > best[1]): best = (c, tp, fp)
print("tune cond fit (c, caught, false alarm):", [(c, round(a, 3), round(b, 5)) for c, a, b in rows], "\n chosen", best, flush=True)
C_PIV = best[0] if best else rows[0][0]
# gate on tune: truth from Clef values
def gate_rule(g, o, r, an): return (g >= .5 or an >= .5) and o < .5 and r >= .3      # happened, opinion, recent, announced
def gate_of(v): return np.array([gate_rule(x[0], x[2], x[3], x[1]) for x in v])        # v columns in Q.GATE_Q order: happened, announced, opinion, recent
gt_t = gate_of(tune["y_gate"][:, gi]); gb_t = tune["gate"][:, gi]
gck_t = ck_predict(ck, ctok, [ck_text(Q.gate_q(k), tun_txt[n]) for n in range(NT) for k in Q.GATE_Q]).reshape(NT, 4)
def unsure(v, d):
    out = np.zeros(len(v), bool); base = gate_of(v)
    for s in itertools.product((-d, d), repeat=4): out |= gate_of(v + np.array(s)) != base
    return out
mix_opts = {"checker": lambda b, k: k, "avg": lambda b, k: (b + k) / 2}; gres = []
for d in (0.0, .05, .1, .15, .2, .3, 1.0):
    u = unsure(gb_t, d) if d < 1 else np.ones(NT, bool)
    for nm, f in mix_opts.items():
        g = np.where(u, gate_of(f(gb_t, gck_t)), gate_of(gb_t)); gres.append((d, nm, float(u.mean()), float((g == gt_t).mean())))
print("tune gate fit (d, mix, unsure share, agreement) BitMob alone", round(float((gate_of(gb_t) == gt_t).mean()), 4), "checker on all", [(r[1], round(r[3], 4)) for r in gres if r[0] == 1.0], flush=True)
cand = [r for r in gres if r[3] >= .93]; gsel = min(cand, key=lambda r: r[2]) if cand else max(gres, key=lambda r: r[3]); D_G, MIX_G = gsel[0], gsel[1]; print("gate chosen on tune", gsel, flush=True)
# ---------------- test side
Hs = cond_ship(H["cond"], H["reading"]); m_s, m1_s, sl_s = ck_means(H["cond"], [r["state_text"] for r in R], CUT)
G_ALL = np.array([[H["gate"][n, g] for g in gi] for n in range(N)]); txt = [r["state_text"] for r in R]
gck = ck_predict(ck, ctok, [ck_text(Q.gate_q(k), txt[n]) for n in range(N) for k in Q.GATE_Q]).reshape(N, 4)
rows100 = C._country_rows(); DOM = K["topic_c"]; DOMY = K["topic_y"]
def place(n):
    pc = dict(zip(DOM, H["topic_c"][n])); py = dict(zip(DOMY, H["topic_y"][n])); tag = {d: (pc[d] >= .2 or py.get(d, 0) >= .5) and d != "other" or (d == "other" and pc[d] >= .2) for d in DOM}
    if not any(tag.values()): tag[max(pc, key=pc.get)] = True
    return [{"id": d, "tagged": bool(tag[d])} for d in DOM]
PL = [place(n) for n in range(N)]; ALLOWED = [C.allowed_dials(p) for p in PL]; ei = {k: i for i, k in enumerate(EXPK)}
def mkP(n, cond, gate4, expv=None):
    P = {}
    for j, k in enumerate(G): P[k] = float(H["gate"][n, j])
    for j, k in enumerate(K["scope"]): P[k] = float(H["scope"][n, j])
    for k, v in zip(Q.GATE_Q, gate4): P[k] = float(v)
    for j, (d, dr, i) in enumerate(A): P[f"a|{d}|{dr}|{i}|0"] = P[f"a|{d}|{dr}|{i}|1"] = float(cond[n, j])
    return P
def exp_set(pe, reported, allowed):
    out = []
    for d in DIALS:
        if d in reported or d not in allowed: continue
        pu, pdn = float(pe[f"{d}|up"]), float(pe[f"{d}|down"]); net = pu - pdn
        if max(pu, pdn) >= C.EXPECT_MIN and abs(net) > .05: out.append((abs(net), d, "up" if net > 0 else "down"))
    return {(d, dr) for _, d, dr in sorted(out, reverse=True)[:C.EXPECT_TOP]}
def score(cond, gate4, pe_override=None):
    gok = []; tp = fp = fn = tn = 0; eok = []
    allk = {(d, u) for d in DIALS for u in ("up", "down")}
    for n, r in enumerate(R):
        rd = C.read(mkP(n, cond, gate4[n])); gok.append(rd["gate_ok"] == r["read"]["gate_ok"])
        mk = {(x["dial"], x["direction"]) for x in rd["readings"] if x["direction"] != "conflict"}; ck_ = {(x["dial"], x["direction"]) for x in r["read"]["readings"] if x["direction"] != "conflict"}
        tp += len(mk & ck_); fn += len(ck_ - mk); fp += len(mk - ck_); tn += len(allk - mk - ck_)
        pe = dict(zip(EXPK, H["expected"][n])); pe.update(pe_override.get(n, {}) if pe_override else {}); rep = {d for d, _ in mk}
        eok.append(exp_set(pe, rep, ALLOWED[n]) == {(x["dial"], x["direction"]) for x in r["expected"]})
    TPR, FPR = tp / max(tp + fn, 1), fp / max(fp + tn, 1)
    return {"gate": round(float(np.mean(gok)), 4), "cond_TPR": round(TPR, 4), "cond_FPR": round(FPR, 5), "cond_pos": tp + fn, "cond_false_alarms": fp, "expected": round(float(np.mean(eok)), 4)}
res = {}; G_BM = np.array([[H["gate"][n, g] for g in gi] for n in range(N)])
gate_cols_bm = G_BM
res["bitmob_alone_shipped"] = score(Hs, G_BM)
# cond with checker
cond_ck = cond_with(Hs, txt, CUT, C_PIV, m_s); res["cond_checker"] = score(cond_ck, G_BM)
cond_ck1 = cond_with(Hs, txt, CUT, C_PIV, m1_s); res["cond_checker_1wording"] = score(cond_ck1, G_BM)
shortlist_n = float(np.mean([len(s) for s in sl_s]))
# gate with checker
us = unsure(G_BM, D_G) if D_G < 1 else np.ones(N, bool); gmix = np.where(us[:, None], mix_opts[MIX_G](G_BM, gck), G_BM); res["gate_checker"] = score(Hs, gmix)
res["gate_checker_all_stories"] = score(Hs, gck)
# expected: fit shortlist cut + pivot on tune using Clef's asked-key mask as the candidate set (tune has no BitMob placement)
Et, Yet, Mt = tune["expected"], tune["y_exp"], tune["y_expm"] > 0
def exp_truth(y, m, n):
    out = []
    for d in DIALS:
        if not (m[n, ei[f"{d}|up"]] and m[n, ei[f"{d}|down"]]): continue
        pu, pdn = y[n, ei[f"{d}|up"]], y[n, ei[f"{d}|down"]]; net = pu - pdn
        if max(pu, pdn) >= .5 and abs(net) > .05: out.append((abs(net), d, "up" if net > 0 else "down"))
    return {(d, dr) for _, d, dr in sorted(out, reverse=True)[:C.EXPECT_TOP]}
Tt = [exp_truth(Yet, Mt, n) for n in range(NT)]
tr_cells = (Yet >= .5) & Mt; sc = np.sort(Et[tr_cells])[::-1]
cand_items = [(n, k) for n in range(NT) for k in range(len(EXPK)) if Mt[n, k]]
pall = run_ck([(n, k) for n, k in cand_items], tun_txt, lambda it: Q.exp_q(*EXPK[it[1]].split("|")))
PK = {it: v for it, v in zip(cand_items, pall)}
def tune_exp(cut, c):
    ok = []
    for n in range(NT):
        pe = {}
        for d in DIALS:
            for u in ("up", "down"):
                k = ei[f"{d}|{u}"]
                if not Mt[n, k]: continue
                v = Et[n, k]
                if v >= cut:
                    x = PK[(n, k)]; v = x if c is None else (.5 * x / c if x <= c else .5 + .5 * (x - c) / (1 - c))
                pe[f"{d}|{u}"] = v
        s = set(); out = []
        for d in DIALS:
            if f"{d}|up" not in pe or f"{d}|down" not in pe: continue
            pu, pdn = pe[f"{d}|up"], pe[f"{d}|down"]; net = pu - pdn
            if max(pu, pdn) >= .5 and abs(net) > .05: out.append((abs(net), d, "up" if net > 0 else "down"))
        ok.append({(d, dr) for _, d, dr in sorted(out, reverse=True)[:C.EXPECT_TOP]} == Tt[n])
    return float(np.mean(ok))
erows = []
for rec in (.90, .95, .98):
    cut = float(sc[int(rec * len(sc)) - 1])
    for c in (None, .2, .3, .4, .5):
        erows.append((rec, cut, c, tune_exp(cut, c)))
print("tune expected fit (recall, cut, pivot, same-set):", [(a, round(b, 3), c, round(d, 4)) for a, b, c, d in erows], "BitMob alone on tune (same candidate set):", round(tune_exp(2.0, None), 4), flush=True)
eb = max(erows, key=lambda r: (r[3], r[0])); E_CUT, E_PIV = eb[1], eb[2]; print("expected chosen on tune", eb, flush=True)
# test: candidates = BitMob allowed & unreported dials (reported from cond_ck result), shortlist by E_CUT
ov = {}; items = []
rep_ck = keys_from_cond(cond_ck)
for n in range(N):
    rep = {d for d, _ in rep_ck[n]}
    for d in DIALS:
        if d in rep or d not in ALLOWED[n]: continue
        for u in ("up", "down"):
            if H["expected"][n, ei[f"{d}|{u}"]] >= E_CUT: items.append((n, ei[f"{d}|{u}"]))
pe_vals = run_ck(items, txt, lambda it: Q.exp_q(*EXPK[it[1]].split("|")))
for (n, k), x in zip(items, pe_vals): ov.setdefault(n, {})[EXPK[k]] = float(x if E_PIV is None else (.5 * x / E_PIV if x <= E_PIV else .5 + .5 * (x - E_PIV) / (1 - E_PIV)))
res["expected_checker"] = score(cond_ck, G_BM, ov)
# all three together
res["all_checker"] = score(cond_ck, gmix, ov)
# timing: per-story serving cost on 100 stories, calls batched per story as a server would (cond pairs both wordings + unsure gate + expected)
sub = list(range(0, N, 20)); t0 = time.time()
for n in sub:
    tx = []
    for j in sl_s[n]: tx += [ck_text(Q.cond_q(*A[j][:2], int(A[j][2]), w), txt[n]) for w in (0, 1)]
    if us[n]: tx += [ck_text(Q.gate_q(k), txt[n]) for k in Q.GATE_Q]
    tx += [ck_text(Q.exp_q(*EXPK[k].split("|")), txt[n]) for (m, k) in items if m == n]
    if tx: ck_predict(ck, ctok, tx, bs=64)
ck_ms = (time.time() - t0) / len(sub) * 1000
n_cond = sum(len(s) for s in sl_s) * 2; n_gate = int(us.sum()) * 4; n_exp = len(items)
out = {"checker": CK, "params_M": round(nparam / 1e6, 1), "tune_fit": {"cond_cut95": CUT, "cond_pivot": C_PIV, "cond_fit_row": best, "gate_d": D_G, "gate_mix": MIX_G, "gate_row": gsel, "exp_cut": E_CUT, "exp_pivot": E_PIV, "exp_row": eb},
       "shortlist_per_story": shortlist_n, "checker_calls_per_story": {"cond_pairs": n_cond / N, "gate_pairs": n_gate / N, "expected_pairs": n_exp / N, "gate_unsure_share": float(us.mean())},
       "bars": {"gate": .90, "cond": "TPR>=.95&FPR<=.0025 or TPR>=.9&FPR<=.001", "expected": .75}, "results": res,
       "cpu_ms_per_story": {"bitmob_raw": round(bm_ms, 1), "checker_per_story_batched": round(ck_ms, 1), "total": round(bm_ms + ck_ms, 1), "threads": 8},
       "peak_rss_MB_of_this_process": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)}
json.dump(out, open(OUT, "w"), indent=1, default=str); print(json.dumps(out, indent=1, default=str))
