"""Confident-CPU, Clef-for-the-rest, measured per engine step (Latent lab story, step 6). CPU only, free, no training, no hosted calls.
  CUDA_VISIBLE_DEVICES= /workspace/kev/.venv/bin/python newsreader/bitmob/mh/hybrid_per_question.py [MODEL_DIR] [OUT.json]
Method. For each engine step the model gives a probability per answer. A band is chosen on the TUNE rows (Clef-labelled rows only, weight 4, written by build_mh_data2*.py and never trained on):
the CPU answers when it is confident (yes-prob <= lo or >= hi for yes/no answers; top-choice prob >= tau for choose-one answers); Clef answers the rest. The band is the one giving the CPU the largest share of answers
such that the hybrid (CPU inside the band, Clef outside) agrees with Clef on >= 97% of that step's answers (the Latent lab's own bar). Then the band is applied unchanged to the 2,000-story TEST (data/clef-labels/test.jsonl);
nothing is fitted on test. Also reported: the CPU's own accuracy on the answers it takes (stricter than the bar).
Units: gate 5 yes/no, scope 5 yes/no, conditions 159 attribute yes/no (Clef yes = mean of its two wordings >= .65, the engine's ATTR_MIN), topics 49 domains tagged or not (engine's tag rule on max(choice,yes) score),
country one choice per story (region then country, confidence = product), expected impact 78 dial|direction yes/no (Clef yes = in its final expected set on test; soft target >= .5 on tune rows),
severity one 5-level choice per changed dial. Raw model probabilities are used (the round's operating-point cuts are switched off). Weights: Clef's measured seconds per story by phase (t field in test.jsonl) and answer counts."""
import os, sys, json, time
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ.setdefault("WORLD_GPU", "0")
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import numpy as np, torch, classify as C
from mh_common import load, predict, ATTR_MIN
torch.set_num_threads(4)
MD = sys.argv[1] if len(sys.argv) > 1 else "/workspace/data/kaggle/mh_r6c1/out/mh"; OUT = sys.argv[2] if len(sys.argv) > 2 else "/workspace/data/latent-lab/hybrid_per_question.json"
TUNE = "/workspace/data/kaggle/mh_r6c1/tune"; TEST = "/workspace/data/clef-labels/test.jsonl"; BAR = 0.97
model, tok, K = load(MD); model.cond_cuts = model.gate_cuts = model.exp_cuts = model.reading_cuts = None
rows100 = C._country_rows(); DOM, DOMY, REG, CTY, DIALS, LV = K["topic_c"], K["topic_y"], K["region"], K["country"], K["severity"], K["levels"]
GATE, SCOPE, COND, EXPK = K["gate"], K["scope"], K["cond"], K["expected"]
R = [json.loads(l) for l in open(TEST) if l.strip()]
tt = json.load(open(f"{TUNE}/texts.json")); Z = np.load(f"{TUNE}/targets.npz"); keep = np.where(Z["w"] >= 4)[0]
assert not ({r["id"] for r in R} & set(json.load(open(f"{TUNE}/keys.json"))["ids"])), "tune/test overlap"
t0 = time.time(); HT = predict(model, tok, [r["state_text"] for r in R]); HU = predict(model, tok, [tt[i] for i in keep]); print("predicted", len(R), "test +", len(keep), "tune rows in", round(time.time() - t0), "s", flush=True)

def tag_rule(pc, py):      # engine place() tagging, arrays (N, 49), (N, 48) -> (N, 49) bool
    py49 = np.zeros_like(pc); 
    for j, d in enumerate(DOMY): py49[:, DOM.index(d)] = py[:, j]
    oth = DOM.index("other"); t = (pc >= .2) | (py49 >= .5); t[:, oth] = pc[:, oth] >= .2
    t[~t.any(1), :] = False
    for n in np.where(~t.any(1))[0]: t[n, pc[n].argmax()] = True
    return t, np.maximum(pc, py49)
def country_choice(preg, pcty):
    out, conf = [], []; rg = {x["id"]: x["region"] for x in rows100}
    for n in range(len(preg)):
        g = int(preg[n].argmax()); gname = REG[g]
        if gname == "GLOBAL": out.append("global"); conf.append(float(preg[n, g])); continue
        cand = [j for j, c in enumerate(CTY) if rg.get(c) == gname or c == "other_here"]; j = max(cand, key=lambda j: pcty[n, j]); s = sum(pcty[n, k] for k in cand)
        out.append("global" if CTY[j] == "other_here" else CTY[j]); conf.append(float(preg[n, g] * pcty[n, j] / max(s, 1e-9)))
    return np.array(out, object), np.array(conf)

def band_binary(p, y, bar=BAR, min_recall=0.0):
    """p, y flat arrays. Returns (lo, hi) maximising CPU share with hybrid agreement >= bar. lo=-1/hi=2 means that side unused."""
    N = len(p); ql = np.unique(np.concatenate([[-1.0], np.quantile(p, np.linspace(0, 1, 201))])); qh = np.unique(np.concatenate([np.quantile(p, np.linspace(0, 1, 201)), [2.0]]))
    best = (-1.0, 2.0, 0.0)
    cl = lambda lo: ((p <= lo) & y).sum(); ch = lambda hi: ((p >= hi) & ~y).sum()      # errors on each side
    for lo in ql:
        el = cl(lo); sl = (p <= lo).sum()
        for hi in qh:
            if hi <= lo: continue
            if (el + ch(hi)) / N <= 1 - bar and (y.sum() == 0 or (((p <= lo) & y).sum()) <= (1 - min_recall) * y.sum()):
                sh = (p >= hi).sum()
                if (sl + sh) / N > best[2]: best = (float(lo), float(hi), (sl + sh) / N)
    return best
def band_choice(conf, ok, bar=BAR):
    N = len(conf); best = (2.0, 0.0)
    for tau in np.unique(np.quantile(conf, np.linspace(0, 1, 401))):
        m = conf >= tau
        if (m & ~ok).sum() / N <= 1 - bar and m.mean() > best[1]: best = (float(tau), float(m.mean()))
    return best
def report(share, hyb_agree, own_acc, n, **kw):
    return {"cpu_share": round(float(share), 4), "hybrid_agreement": round(float(hyb_agree), 4), "cpu_own_accuracy": round(float(own_acc), 4) if own_acc == own_acc else None, "n_answers": int(n), **kw}
def eval_binary(p, y, lo, hi):
    m = (p <= lo) | (p >= hi); dec = p >= hi; err = m & (dec != y)
    return m.mean(), 1 - err.sum() / len(p), (1 - err.sum() / max(m.sum(), 1)) if m.any() else float("nan")
res = {}; test_y = {}; tune_y = {}; ntune = {}

# ---- yes/no steps: tune (Clef rows) and test arrays as (rows, items) ----
Pt = np.array([[r["P"][k] for k in GATE + SCOPE] for r in R])
steps = {"gate": (HU["gate"], Z["gate"][keep] >= .5, HT["gate"], Pt[:, :5] >= .5), "scope": (HU["scope"], Z["scope"][keep] >= .5, HT["scope"], Pt[:, 5:] >= .5)}
ca = lambda r, j: (r["P"][f"a|{COND[j].split('|')[0]}|{COND[j].split('|')[1]}|{COND[j].split('|')[2]}|0"] + r["P"][f"a|{COND[j].split('|')[0]}|{COND[j].split('|')[1]}|{COND[j].split('|')[2]}|1"]) / 2
YC = np.array([[ca(r, j) for j in range(len(COND))] for r in R]) >= ATTR_MIN
steps["conditions"] = (HU["cond"], Z["cond"][keep] >= ATTR_MIN, HT["cond"], YC)
et = np.zeros((len(R), len(EXPK)), bool)
for n, r in enumerate(R):
    for x in r["expected"]: et[n, EXPK.index(f"{x['dial']}|{x['direction']}")] = True
em = Z["expected_mask"][keep] > 0; rows_e = em.any(1)
steps["expected impact"] = (HU["expected"][rows_e], Z["expected"][keep][rows_e] >= .5, HT["expected"], et)
tg_u, sc_u = tag_rule(HU["topic_c"], HU["topic_y"]); tg_c_u, _ = tag_rule(Z["topic_c"][keep], Z["topic_y"][keep])      # Clef tune tags: engine rule on Clef's own choice/yes numbers
tg_t, sc_t = tag_rule(HT["topic_c"], HT["topic_y"]); tg_c_t = np.array([[next(x for x in r["place"] if x["id"] == d)["tagged"] for d in DOM] for r in R])
steps["topics"] = None
def run_binary(REC):
    res = {}
    for name, v in steps.items():
        if v is None: continue
        pu, yu, pt, yt = v; lo, hi, sh = band_binary(pu.ravel(), yu.ravel(), min_recall=REC); s, ha, oa = eval_binary(pt.ravel(), yt.ravel(), lo, hi); su, hau, oau = eval_binary(pu.ravel(), yu.ravel(), lo, hi)
        extra = {}
        if name == "conditions":      # catch rate on Clef's fired readings (any attribute of a dial|direction fires), hybrid = CPU inside the band, Clef outside
            grp = {}
            for j, k in enumerate(COND): d, dr, i = k.split("|"); grp.setdefault((d, dr), []).append(j)
            inb = (pt <= lo) | (pt >= hi); hyb = np.where(inb, pt >= hi, yt)
            pos = np.stack([yt[:, g].any(1) for g in grp.values()], 1); got = np.stack([hyb[:, g].any(1) for g in grp.values()], 1); cpu_only = np.stack([(inb & (pt >= hi))[:, g].any(1) for g in grp.values()], 1)
            fp = (got & ~pos).sum(); extra = {"catch_rate_clef_readings": round(float((got & pos).sum() / pos.sum()), 4), "clef_readings": int(pos.sum()), "false_readings_per_1000_story_dials": round(float(1000 * fp / pos.size), 2),
                                               "catch_rate_if_cpu_alone_answers_all": round(float(((pt >= .5).reshape(len(pt), -1)[:, :][:, [g[0] for g in grp.values()]] & False).sum()), 4)}
            extra.pop("catch_rate_if_cpu_alone_answers_all")
            extra["yes_answers_taken_by_cpu"] = int((inb & (pt >= hi) & yt).sum()); extra["clef_yes_answers"] = int(yt.sum())
        res[name] = report(s, ha, oa, yt.size, band={"cpu_says_no_at_or_below": round(lo, 4), "cpu_says_yes_at_or_above": round(hi, 4)}, tune={"n_answers": int(yu.size), "cpu_share": round(float(su), 4), "hybrid_agreement": round(float(hau), 4)}, **extra)
    # topics: score = max(choice, yes) per domain; "tagged" by engine rule
    pu, yu, pt, yt = sc_u.ravel(), tg_c_u.ravel(), sc_t.ravel(), tg_c_t.ravel(); mu, mt = tg_u.ravel(), tg_t.ravel()
    lo, hi, sh = band_binary(pu, yu, min_recall=REC); inb = lambda p: (p <= lo) | (p >= hi)
    def topic_eval(p, mod, cl):
        m = inb(p); err = m & (mod != cl); return m.mean(), 1 - err.sum() / len(p), 1 - err.sum() / max(m.sum(), 1)
    s, ha, oa = topic_eval(pt, mt, yt); su, hau, _ = topic_eval(pu, mu, yu)
    res["topics"] = report(s, ha, oa, yt.size, band={"cpu_says_not_tagged_at_or_below": round(lo, 4), "cpu_says_tagged_at_or_above": round(hi, 4)}, tune={"n_answers": int(yu.size), "cpu_share": round(float(su), 4), "hybrid_agreement": round(float(hau), 4)})


    return res
res_a = run_binary(0.0); res_b = run_binary(0.90)
# ---- choose-one steps ----
rkeep = keep
ctu_lab = np.array([("global" if (lambda g: REG[g] == "GLOBAL")(int(Z["region"][i].argmax())) else None) for i in rkeep], object)
rg = {x["id"]: x["region"] for x in rows100}
def tune_country_label(i):
    g = int(Z["region"][i].argmax()); gn = REG[g]
    if gn == "GLOBAL": return "global"
    cand = [j for j, c in enumerate(CTY) if rg.get(c) == gn or c == "other_here"]; j = max(cand, key=lambda j: Z["country"][i, j]); return "global" if CTY[j] == "other_here" else CTY[j]
cu, cfu = country_choice(HU["region"], HU["country"]); cl_u = np.array([tune_country_label(i) for i in keep], object); ct, cft = country_choice(HT["region"], HT["country"]); cl_t = np.array([r["country"] for r in R], object)
tau, _ = band_choice(cfu, cu == cl_u); m = cft >= tau; res["country"] = report(m.mean(), 1 - (m & (ct != cl_t)).sum() / len(R), 1 - (m & (ct != cl_t)).sum() / max(m.sum(), 1), len(R), band={"cpu_answers_when_confidence_at_least": round(tau, 4)},
                                                                              tune={"n_answers": len(keep), "cpu_share": round(float((cfu >= tau).mean()), 4), "hybrid_agreement": round(float(1 - ((cfu >= tau) & (cu != cl_u)).mean()), 4)})
sm = Z["sev_mask"][keep] > 0; su_ = HU["severity"][sm]; yu_ = Z["severity"][keep][sm].argmax(-1); sev_t = []; yt_ = []; pr = []
for n, r in enumerate(R):
    for d, v in r["severity"].items(): sev_t.append(HT["severity"][n][DIALS.index(d)]); yt_.append(LV.index(v["level"]))
sev_t = np.array(sev_t); yt_ = np.array(yt_); tau, _ = band_choice(su_.max(-1), su_.argmax(-1) == yu_); m = sev_t.max(-1) >= tau; er = m & (sev_t.argmax(-1) != yt_)
res["severity"] = report(m.mean(), 1 - er.sum() / len(m), 1 - er.sum() / max(m.sum(), 1), len(m), band={"cpu_answers_when_confidence_at_least": round(tau, 4)},
                         tune={"n_answers": int(len(yu_)), "cpu_share": round(float((su_.max(-1) >= tau).mean()), 4), "hybrid_agreement": round(float(1 - ((su_.max(-1) >= tau) & (su_.argmax(-1) != yu_)).mean()), 4)})

# ---- overall: share of Clef's work the CPU would take ----
tsec = {k: float(np.mean([r["t"][k] for r in R])) for k in ("ask", "place", "country", "expected", "severity")}
ask_s = tsec["ask"]; tw = {"gate": ask_s * 5 / 328, "scope": ask_s * 5 / 328, "conditions": ask_s * 318 / 328, "topics": tsec["place"], "country": tsec["country"], "expected impact": tsec["expected"], "severity": tsec["severity"]}
qw = {"gate": 5, "scope": 5, "conditions": 318, "topics": 97, "country": 2, "expected impact": 79, "severity": 39}; tot_t = sum(tw.values()); tot_q = sum(qw.values())
def assemble(rb):
    st = {**rb, "country": res["country"], "severity": res["severity"]}; st = {k: st[k] for k in ("gate", "scope", "conditions", "topics", "country", "expected impact", "severity")}
    for k in st: st[k]["clef_seconds_per_story"] = round(tw[k], 3); st[k]["clef_questions_per_story"] = qw[k]
    return {"steps": st, "clef_work_taken_by_cpu_by_seconds": round(float(sum(st[k]["cpu_share"] * tw[k] for k in tw) / tot_t), 4), "clef_work_taken_by_cpu_by_question_count": round(float(sum(st[k]["cpu_share"] * qw[k] for k in qw) / tot_q), 4)}
out = {"made": time.strftime("%FT%T"), "model": MD, "test": {"file": TEST, "n_stories": len(R)}, "tune": {"dir": TUNE, "clef_labelled_rows": int(len(keep)), "note": "only Clef-labelled tune rows (weight 4) are used; Jev-translated rows excluded; not trained on; no id overlap with test (asserted)"},
       "bar": BAR, "agreement_only": assemble(res_a), "agreement_and_catch": assemble(res_b),
       "definitions": {"agreement_only": "band chosen so hybrid agreement >= 97% on tune (the lab's bar as written). Degenerate for rare-yes steps (conditions, expected impact): answering 'no' to everything already scores >= 99%.",
                       "agreement_and_catch": "same, and the hybrid must also keep >= 90% of Clef's yes answers (CPU 'no' answers may miss at most 10% of them) on tune; applied to every yes/no step. Choose-one steps (country, severity) are identical in both.",
                       "weights": {"seconds_per_story": {k: round(v, 3) for k, v in tw.items()}, "questions_per_story": qw, "note": "gate/scope/conditions share Clef's one 328-question read, split by question count; topics/country/expected/severity use Clef's measured phase times (test.jsonl field t)"}},
       "caveats": ["Expected impact is scored per dial|direction against Clef's final expected set, not through the engine's full expected() rule; tune labels for it are soft targets >= .5.",
                   "Bands are fitted on 894 Clef-labelled tune rows; test agreement can land under 97% for that reason (reported as is).",
                   "Raw model probabilities: the round's operating-point cuts were switched off.", "Conditions catch rate is per Clef-fired dial|direction reading (any attribute fires)."]}
# conditions against the engine's own bar (F-0020: TPR >= .90 at FPR <= .001): from data/kaggle/mh_r6c1/hybrid.json (this model, same 2,000 test stories), the smallest share of stories Clef must double-check is hb["checked_share"]; the CPU keeps the rest
hj = "/workspace/data/kaggle/mh_r6c1/hybrid.json"
if os.path.exists(hj):
    hb = json.load(open(hj))["smallest_share_reaching_F0020"]; cs = 1 - hb["checked_share"]; st = out["agreement_and_catch"]["steps"]
    out["conditions_at_engine_bar"] = {"source": hj, "clef_must_check_share_of_stories": hb["checked_share"], "cpu_share_of_conditions_work": round(cs, 3), "TPR": hb["TPR"], "FPR": hb["FPR"],
        "overall_by_seconds": round(float((cs * tw["conditions"] + sum(st[k]["cpu_share"] * tw[k] for k in tw if k != "conditions")) / tot_t), 4),
        "overall_by_question_count": round(float((cs * qw["conditions"] + sum(st[k]["cpu_share"] * qw[k] for k in qw if k != "conditions")) / tot_q), 4),
        "note": "Same as agreement_and_catch except conditions use the engine's real bar instead of the 97% per-answer bar."}
os.makedirs(os.path.dirname(OUT), exist_ok=True); json.dump(out, open(OUT, "w"), indent=1)
for m in ("agreement_only", "agreement_and_catch"):
    print(m, out[m]["clef_work_taken_by_cpu_by_seconds"], out[m]["clef_work_taken_by_cpu_by_question_count"])
    for k, v in out[m]["steps"].items(): print(f"  {k:16s} share {v['cpu_share']:.3f} hybrid {v['hybrid_agreement']:.4f} own {v['cpu_own_accuracy']} band {v['band']} tune {v['tune']['cpu_share']}/{v['tune']['hybrid_agreement']}", {x: v[x] for x in v if x.startswith(('catch', 'false', 'yes_ans', 'clef_yes', 'clef_read'))})
