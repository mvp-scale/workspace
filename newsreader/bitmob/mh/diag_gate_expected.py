"""Diagnose the two other stuck engine steps the way conditions was diagnosed (F-0110): read-or-skip (gate, P-0016, bar 90%) and expected impact (P-0020, bar 75% same set). CPU only, free, no training, no hosted calls.
  WE_RULES=rules_v2 CUDA_VISIBLE_DEVICES= /workspace/kev/.venv/bin/python newsreader/bitmob/mh/diag_gate_expected.py   -> data/diag/gate_expected_2026-10-22.txt
Cut-offs (the gate band, the expected shortlist threshold) are fitted on the 894 Clef-labelled TUNE rows only and applied unchanged to the 2,000-story frozen test."""
import os, sys, json, collections, numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("WE_RULES", "rules_v2"); os.environ["WORLD_GPU"] = "0"
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", "/workspace/newsreader/bitmob/mh"]
import torch; torch.set_num_threads(8)
import classify as C
from mh_common import load, predict
from sklearn.metrics import roc_auc_score
OUT = "/workspace/data/diag/gate_expected_2026-10-22.txt"; LINES = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); LINES.append(s)
TUNE = "/workspace/data/kaggle/mh_r6c1/tune"; MD = "/workspace/data/kaggle/mh_r6c1/out/mh"; LAB = "/workspace/data/clef-labels"
R = [json.loads(l) for l in open(f"{LAB}/test.jsonl")]; N = len(R)
model, tok, K = load(MD); CUTS = {a: getattr(model, a, None) for a in ("cond_cuts", "gate_cuts", "exp_cuts", "reading_cuts")}
tt = json.load(open(f"{TUNE}/texts.json")); Z = np.load(f"{TUNE}/targets.npz"); keep = np.where(Z["w"] >= 4)[0]
assert not ({r["id"] for r in R} & set(json.load(open(f"{TUNE}/keys.json"))["ids"]))
texts = [r["state_text"] for r in R]; ttexts = [tt[i] for i in keep]
for a in CUTS: setattr(model, a, None)
HR, HUR = predict(model, tok, texts), predict(model, tok, ttexts)            # raw (no operating-point cuts)
for a, v in CUTS.items(): setattr(model, a, v)
HS = predict(model, tok, texts)                                              # shipped (cuts on) = what scored 81% / 60%
G = K["gate"]; gi = {k: i for i, k in enumerate(G)}; EXPK = K["expected"]; ei = {k: i for i, k in enumerate(EXPK)}
P("GATE AND EXPECTED-IMPACT DIAGNOSIS (F-0110 method), 2026-10-22. Model data/kaggle/mh_r6c1/out/mh, test 2,000 Clef-labelled stories, tune = 894 Clef-labelled rows (cut-offs fitted there only).")
P("NOTE this model ships NO gate or expected cuts (only cond and reading cuts), so shipped = raw for gate and expected below.")
P("cuts active in shipped model:", {a: (v is not None) for a, v in CUTS.items()}, "gate_cuts =", CUTS["gate_cuts"], "\n")

# ================= GATE =================
P("=" * 20, "A. READ-OR-SKIP (gate)", "=" * 20)
P("Rule (classify.read): gate_ok = (happened>=.5 or announced>=.5) and opinion<.5 and recent>=.3. Four of the 328 questions matter; g|forecast and the scope questions do not.")
def gate_rule(h, a, o, r, d=0.0): return ((h >= .5) or (a >= .5)) and (o < .5) and (r >= .3)
gate_v = lambda M: (((M[:, 0] >= .5) | (M[:, 1] >= .5)) & (M[:, 2] < .5) & (M[:, 3] >= .3))
Q = ["g|happened", "g|announced", "g|opinion", "x|recent"]; THR = np.array([.5, .5, .5, .3])
CL = np.array([[r["P"][q] for q in Q] for r in R]); CG = np.array([r["read"]["gate_ok"] for r in R], bool)
assert (gate_v(CL) == CG).all(), "rule on Clef answers must equal stored gate_ok"
def mv(H): return np.stack([H["gate"][:, gi[q]] for q in Q], 1)
MS, MRw = mv(HS), mv(HR)
P(f"Clef accepts {CG.mean():.1%} of stories (gate_ok). Always-'skip' baseline agreement {1-CG.mean():.1%}.")
for nm, M in (("shipped (with tuned gate cuts)", MS), ("raw (no cuts)", MRw)):
    g = gate_v(M); P(f"BitMob gate, {nm}: agreement with Clef {(g==CG).mean():.1%}; accepts {g.mean():.1%}; wrongly accepts {(g&~CG).mean():.1%} of stories, wrongly skips {(~g&CG).mean():.1%}")
M = MS; g = gate_v(M); bad = g != CG
P(f"\nWhich questions drive the disagreement (shipped model; {bad.sum()} disagreeing stories):")
clause = lambda X: np.stack([X[:, 0] >= .5, X[:, 1] >= .5, X[:, 2] < .5, X[:, 3] >= .3], 1)    # happened, announced, opinion-ok, recent-ok
cm, cc = clause(M), clause(CL)
names = ["happened>=.5", "announced>=.5", "opinion<.5", "recent>=.3"]
for j, nm in enumerate(names): P(f"  clause {nm:14s}: BitMob differs from Clef on {(cm[:,j]!=cc[:,j]).mean():.1%} of stories; among the disagreeing-gate stories {(cm[bad,j]!=cc[bad,j]).mean():.1%}")
P("  fix ONE question at a time with Clef's real answer (others stay BitMob) -> gate agreement:")
for j, q in enumerate(Q):
    X = M.copy(); X[:, j] = CL[:, j]; P(f"    Clef answers only {q:12s}: {(gate_v(X)==CG).mean():.1%}")
X = M.copy(); X[:, 0:2] = CL[:, 0:2]; P(f"    Clef answers happened+announced: {(gate_v(X)==CG).mean():.1%}")
X = M.copy(); X[:, 2:4] = CL[:, 2:4]; P(f"    Clef answers opinion+recent    : {(gate_v(X)==CG).mean():.1%}")
P("\nError profile on the gate answers (BitMob shipped minus Clef; AUC = how well BitMob ranks Clef's yes/no at the rule's own cut):")
for j, q in enumerate(Q):
    e = M[:, j] - CL[:, j]; y = CL[:, j] >= THR[j]; hi = CL[:, j] >= THR[j]
    P(f"  {q:12s} mean err {e.mean():+.3f}, std {e.std():.3f}, mean|err| {np.abs(e).mean():.3f}; AUC {roc_auc_score(y, M[:,j]):.3f}; Clef>=cut: BitMob mean {M[hi,j].mean():.2f} vs Clef {CL[hi,j].mean():.2f} (BitMob also >= cut on {(M[hi,j]>=THR[j]).mean():.1%}); Clef<cut: BitMob >= cut on {(M[~hi,j]>=THR[j]).mean():.1%}")
    near = np.abs(CL[:, j] - THR[j]); P(f"      Clef answers within .05 / .10 / .20 of the cut: {(near<.05).mean():.1%} / {(near<.10).mean():.1%} / {(near<.20).mean():.1%} of stories; BitMob error where Clef is within .10 of cut: mean {e[near<.10].mean():+.3f}, std {e[near<.10].std():.3f}")
P("  bias by Clef value band near the recent cut (.3), BitMob mean minus Clef mean:")
for lo, hi_ in ((0, .1), (.1, .2), (.2, .3), (.3, .4), (.4, .5), (.5, .7), (.7, 1.01)):
    m = (CL[:, 3] >= lo) & (CL[:, 3] < hi_); P(f"    recent in [{lo:.1f},{min(hi_,1):.1f}): n={m.sum():4d} bias {np.mean(M[m,3]-CL[m,3]):+.3f}; BitMob >= .3 on {(M[m,3]>=.3).mean():.0%}") if m.sum() else None
# --- brittleness of Clef's own gate ---
P("\nBrittleness of Clef's OWN gate decision (Clef's answers on the 4 gate questions nudged, rule re-applied, vs Clef's stored gate):")
rng = np.random.default_rng(0)
for s in (0.01, 0.02, 0.05, 0.10):
    ag = [(gate_v(np.clip(CL + rng.normal(0, s, CL.shape), 0, 1)) == CG).mean() for _ in range(20)]
    P(f"  noise ±{s:.2f} on each of the four answers: gate unchanged on {np.mean(ag):.1%} of stories (min over 20 draws {np.min(ag):.1%})")
for b in (-.02, .02):
    P(f"  all four answers {b:+.2f}: gate unchanged on {(gate_v(np.clip(CL+b,0,1))==CG).mean():.1%}")
P("Clef against itself, other groupings of the same questions (existing runs, data/clef-labels/*_compare.json): fast mode 300 stories gate agreement 72.3%; two-step 294 stories 82.0%; two-step with meta-blocks 147 stories 100%.")
C_ = [json.loads(l) for l in open("/workspace/data/diag/screen_real/clef_answers_all.jsonl")]; C_ = [o for o in C_ if "F" in o]; byid = {r["id"]: r for r in R}
if C_:
    a = [gate_v(np.array([[o["F"][q] for q in Q]]))[0] == byid[o["id"]]["read"]["gate_ok"] for o in C_]; d = [abs(o["F"][q] - byid[o["id"]]["P"][q]) for o in C_ for q in Q]
    P(f"Clef rerun of the identical full battery (Kaggle T4, F-0110 control), {len(C_)} stories: gate reproduced on {np.mean(a):.0%}; mean |answer difference| on the 4 gate questions {np.mean(d):.4f}")
# --- what the gate does downstream ---
rd_total = sum(len([x for x in r["read"]["readings"] if x["direction"] != "conflict"]) for r in R); rd_fail = sum(len([x for x in r["read"]["readings"] if x["direction"] != "conflict"]) for r, g_ in zip(R, CG) if not g_)
ex_fail = sum(1 for r, g_ in zip(R, CG) if not g_ and r["expected"]); ex_pass = sum(1 for r, g_ in zip(R, CG) if g_ and r["expected"])
P(f"\nDownstream: Clef readings on gate-skipped stories {rd_fail}/{rd_total} ({rd_fail/max(rd_total,1):.1%}); non-empty expected sets on skipped stories {ex_fail}/{(~CG).sum()}, on accepted {ex_pass}/{CG.sum()}.")
# --- fit: cut refit and Clef-asked-when-unsure on tune ---
TG = Z["gate"][keep]; TU = np.stack([TG[:, gi[q]] for q in Q], 1); YG = gate_v(TU); MU_R = np.stack([HUR["gate"][:, gi[q]] for q in Q], 1)
P(f"\nFIT ON TUNE ({len(keep)} Clef rows; Clef accepts {YG.mean():.1%} there). Raw BitMob agreement on tune {(gate_v(MU_R)==YG).mean():.1%}.")
def cal(p, c, pv): return np.where(p <= c, pv * p / c, pv + (1 - pv) * (p - c) / (1 - c))
def apply(Mx, cs): X = Mx.copy(); [X.__setitem__((slice(None), j), cal(Mx[:, j], cs[j], THR[j])) for j in range(4)]; return X
cs = THR.copy(); best = (gate_v(MU_R) == YG).mean()
for it in range(3):
    for j in range(4):
        for c in np.linspace(.05, .9, 35):
            t = cs.copy(); t[j] = c; s = (gate_v(apply(MU_R, t)) == YG).mean()
            if s > best + 1e-6: best, cs = s, t
P(f"  refit the four cut-offs on tune (coordinate descent): cuts {np.round(cs,3).tolist()} -> tune agreement {best:.1%}; applied unchanged to test (raw model): {(gate_v(apply(MRw, cs))==CG).mean():.1%}")
Mrefit = apply(MRw, cs)
def unsure(Mx, d):
    up = np.stack([Mx[:, 0] + d >= .5, Mx[:, 1] + d >= .5, Mx[:, 2] - d < .5, Mx[:, 3] + d >= .3], 1); lo = np.stack([Mx[:, 0] - d >= .5, Mx[:, 1] - d >= .5, Mx[:, 2] + d < .5, Mx[:, 3] - d >= .3], 1)
    f = lambda c: (c[:, 0] | c[:, 1]) & c[:, 2] & c[:, 3]
    return f(up) != f(lo)
def hybrid(Mx, d, Cl, base=None): u = unsure(Mx, d); g_ = np.where(u, gate_v(Cl), gate_v(Mx)); return g_, u
TUNEBASE = {"shipped cuts": None, "refit cuts": apply(MU_R, cs)}
MUS = np.stack([HUR["gate"][:, gi[q]] for q in Q], 1)       # tune raw; 'shipped' cuts for tune below
model.gate_cuts = CUTS["gate_cuts"]; HU_S = predict(model, tok, ttexts); MU_S = np.stack([HU_S["gate"][:, gi[q]] for q in Q], 1)
P("  Clef-asks-when-unsure: BitMob decides unless moving any of its 4 values by ±d could flip the gate; then Clef answers the gate questions (its two usual blocks: 28 questions, 2 calls).")
P("  d    | tune: Clef-asked share, agreement | TEST shipped cuts: Clef-asked share, agreement | TEST refit cuts: share, agreement")
rows = []
for d in (0, .02, .05, .08, .10, .15, .20, .25, .30, .40, 1.0):
    gt, ut = hybrid(MU_S, d, TU); gS, uS = hybrid(MS, d, CL); gF, uF = hybrid(Mrefit, d, CL); gtF, utF = hybrid(apply(MU_R, cs), d, TU)
    rows.append((d, ut.mean(), (gt == YG).mean(), uS.mean(), (gS == CG).mean(), uF.mean(), (gF == CG).mean(), utF.mean(), (gtF == YG).mean()))
    P(f"  {d:4.2f} | {ut.mean():6.1%} {(gt==YG).mean():6.1%} | {uS.mean():6.1%} {(gS==CG).mean():6.1%} | {uF.mean():6.1%} {(gF==CG).mean():6.1%}   (tune refit: {utF.mean():.1%}/{(gtF==YG).mean():.1%})")
# pre-registered choice: smallest d whose TUNE agreement >= 95% (5 points above the 90% bar to leave room for tune-to-test slack)
for tag, ix_t, ix_s in (("shipped cuts", 2, 4), ("refit cuts", 8, 6)):
    sel = next(r for r in rows if r[ix_t] >= .95); dsel = sel[0]
    P(f"  chosen on tune (smallest d with tune agreement >= 95%), {tag}: d={dsel} -> TEST " + (f"Clef asked on {sel[3]:.1%} of stories, agreement {sel[4]:.1%}" if tag.startswith("ship") else f"Clef asked on {sel[5]:.1%} of stories, agreement {sel[6]:.1%}"))
    sh = sel[3] if tag.startswith("ship") else sel[5]; P(f"    = {28*sh:.1f} Clef questions/story on average ({28*sh/328:.1%} of the 328-question battery); about {0.2*sh + 0.131*28*sh:.2f} Clef s/story by the per-call/per-question fit from the A/B run (estimate; full battery 44.6 s on the same T4s)")
P("  Clef asked for the gate on EVERY story: agreement 100% by construction (stored answers are those of the same usual blocks); cost 28 questions/story, 2 calls, about 3.9 s/story of the 44.6 s (9%). Asking only the 4 needed questions alone would be 4 q but changes the grouping (Clef agrees with itself only 72-82% across groupings): not recommended without a real run.")

# --- cheaper variant: Clef answers only its usual block 15 (g|happened and g|announced sit there with 18 attribute questions; 20 q, 1 call); BitMob keeps opinion and recent
def unsure_ha(Mx, d): 
    f = lambda sh: ((Mx[:, 0] + sh >= .5) | (Mx[:, 1] + sh >= .5))
    return f(d) != f(-d)
def hyb_ha(Mx, d, Cl): u = unsure_ha(Mx, d); X = Mx.copy(); X[u, 0:2] = Cl[u, 0:2]; return gate_v(X), u
P("  Variant H: Clef answers its block 15 (happened + announced, 20 questions, 1 call) only when BitMob's happened/announced pair is unsure by ±d; BitMob decides opinion and recent.")
P("  d    | tune: Clef-asked share, agreement | TEST: share, agreement, Clef q/story")
rows2 = []
for d in (0, .05, .10, .15, .20, .30, 1.0):
    gt, ut = hyb_ha(MU_S, d, TU); gS, uS = hyb_ha(MS, d, CL); rows2.append((d, ut.mean(), (gt == YG).mean(), uS.mean(), (gS == CG).mean()))
    P(f"  {d:4.2f} | {ut.mean():6.1%} {(gt==YG).mean():6.1%} | {uS.mean():6.1%} {(gS==CG).mean():6.1%}  {20*uS.mean():5.1f} q/story")
sel = next(r for r in rows2 if r[2] >= .95); P(f"  chosen on tune (smallest d with tune agreement >= 95%): d={sel[0]} -> TEST Clef asked on {sel[3]:.1%} of stories, agreement {sel[4]:.1%}, {20*sel[3]:.1f} Clef questions/story ({20*sel[3]/328:.1%} of battery), about {(0.1+0.131*20)*sel[3]:.2f} Clef s/story (estimate)")
sel = next(r for r in rows2 if r[2] >= .90); P(f"  smallest d with tune agreement >= 90% (the bar itself, no margin): d={sel[0]} -> TEST Clef asked on {sel[3]:.1%}, agreement {sel[4]:.1%}, {20*sel[3]:.1f} q/story")
tm = {k: np.mean([r["t"][k] for r in R]) for k in ("ask", "place", "country", "expected", "severity")}; P("  Clef seconds/story by phase in the stored labelling run (its own hardware): " + ", ".join(f"{k} {v:.2f}" for k, v in tm.items()))

# ================= EXPECTED =================
P("\n" + "=" * 20, "B. EXPECTED IMPACT", "=" * 20)
PH = list(C.PHRASES); DIALK = [k for k in EXPK]
def clef_set(e):
    out = []
    for d in PH:
        if f"e|{d}|up" not in e: continue
        pu, pd = e[f"e|{d}|up"], e[f"e|{d}|down"]; net = pu - pd
        if max(pu, pd) >= C.EXPECT_MIN and abs(net) > .05: out.append((round(abs(net), 3), d, "up" if net > 0 else "down"))
    return {(d, dr) for _, d, dr in sorted(out, key=lambda x: -x[0])[:C.EXPECT_TOP]}
CE = [{(x["dial"], x["direction"]) for x in r["expected"]} for r in R]; ER = [r["e_raw"] for r in R]
reb = np.mean([clef_set(e) == c for e, c in zip(ER, CE)]); P(f"Sanity: rebuilding Clef's set from its stored e answers with the engine rule equals the stored set on {reb:.1%} of stories (rounding/ties explain the rest).")
empty = np.mean([not c for c in CE]); P(f"Clef's expected set is EMPTY on {empty:.1%} of stories; sizes {dict(sorted(collections.Counter(len(c) for c in CE).items()))}. Always-empty baseline would score {empty:.1%} on 'same set as Clef' (the model's 60.2% is BELOW that).")
keyf = lambda H: np.array([[H["expected"][n, ei[f"{d}|{dr}"]] for d in PH for dr in ("up", "down")] for n in range(N)])
ECOL = [(d, dr) for d in PH for dr in ("up", "down")]
EL = lambda H, n: {f"e|{d}|{dr}": float(H["expected"][n, ei[f"{d}|{dr}"]]) for d, dr in ECOL}
# reported / allowed (model and Clef)
rows100 = C._country_rows()
DOM, DOMY = K["topic_c"], K["topic_y"]; COND = K["cond"]
def mkP(H, n):
    Pm = {}
    for j, k in enumerate(G): Pm[k] = float(H["gate"][n, j])
    for j, k in enumerate(K["scope"]): Pm[k] = float(H["scope"][n, j])
    for j, k in enumerate(COND): d, dr, i = k.split("|"); Pm[f"a|{d}|{dr}|{i}|0"] = Pm[f"a|{d}|{dr}|{i}|1"] = float(H["cond"][n, j])
    return Pm
def place_allowed(H, n):
    pc = dict(zip(DOM, H["topic_c"][n])); py = dict(zip(DOMY, H["topic_y"][n])); tag = {d: (pc[d] >= .2 or py.get(d, 0) >= .5) and d != "other" or (d == "other" and pc[d] >= .2) for d in DOM}
    if not any(tag.values()): tag[max(pc, key=pc.get)] = True
    return C.allowed_dials([{"id": d, "tagged": bool(tag[d])} for d in DOM])
rep = lambda rd: {x["dial"] for x in rd["readings"] if x["direction"] != "conflict"}
REP_C = [rep(r["read"]) for r in R]; ALW_C = [C.allowed_dials(r["place"]) for r in R]
REP_M = [rep(C.read(mkP(HS, n))) for n in range(N)]; ALW_M = [place_allowed(HS, n) for n in range(N)]
def mset(ev, reported, allowed):     # model e values -> set by the engine's rule (reported/allowed exclude dials)
    e = {f"e|{d}|{dr}": ev[f"e|{d}|{dr}"] for d in PH if d not in reported and d in allowed for dr in ("up", "down")}; return clef_set(e)
EV_S = [EL(HS, n) for n in range(N)]; EV_R = [EL(HR, n) for n in range(N)]
P("\nWhich input makes the set differ from Clef's? exact-set agreement with Clef over 2,000 stories (BitMob = shipped cuts unless noted):")
P("  reported dials | allowed dials | e answers        | same set | of Clef-non-empty stories")
ne = np.array([bool(c) for c in CE])
for rn, REPS in (("Clef", REP_C), ("BitMob", REP_M)):
    for an, ALWS in (("Clef", ALW_C), ("BitMob", ALW_M)):
        for en, EV in (("BitMob shipped", EV_S), ("BitMob raw", EV_R)):
            ok = np.array([mset(EV[n], REPS[n], ALWS[n]) == CE[n] for n in range(N)]); P(f"  {rn:14s} | {an:13s} | {en:16s} | {ok.mean():6.1%}   | {ok[ne].mean():6.1%}")
okc = np.array([clef_set({k: v for k, v in ER[n].items() if k.startswith('e|')}, ) == CE[n] for n in range(N)])
# --- error profile on e cells ---
cells_c, cells_m, cells_r = [], [], []; story_cell = []
for n in range(N):
    for d in PH:
        if f"e|{d}|up" in ER[n]:
            for dr in ("up", "down"): cells_c.append(ER[n][f"e|{d}|{dr}"]); cells_m.append(EV_S[n][f"e|{d}|{dr}"]); cells_r.append(EV_R[n][f"e|{d}|{dr}"])
cc_, cm_, cr_ = map(np.array, (cells_c, cells_m, cells_r)); trig = cc_ >= C.EXPECT_MIN
P(f"\nError profile on the e answers Clef actually gave ({len(cc_)} answers; {trig.sum()} are >= .5 ({trig.mean():.1%})):")
for nm, cm_x in (("raw", cr_), ("shipped", cm_)):
    e = cm_x - cc_; P(f"  BitMob {nm}: mean err {e.mean():+.3f}, std {e.std():.3f}; at Clef>=.5 mean err {e[trig].mean():+.3f} (BitMob mean {cm_x[trig].mean():.2f} vs Clef {cc_[trig].mean():.2f}); BitMob>=.5 on {(cm_x[trig]>=.5).mean():.1%} of Clef's yes; BitMob>=.5 where Clef<.5: {(cm_x[~trig]>=.5).mean():.2%} ({(cm_x[~trig]>=.5).sum()} answers); AUC {roc_auc_score(trig, cm_x):.3f}")
for q in (.5, .7, .9):
    m = cc_ >= q; P(f"    Clef >= {q}: BitMob raw mean {cr_[m].mean():.2f} vs Clef {cc_[m].mean():.2f} (n={m.sum()})")
# --- brittleness of Clef's own set ---
P("\nBrittleness of Clef's OWN expected set (its stored e answers nudged, engine rule re-applied, exact-set match with its stored set; 5 draws):")
def noisy(e, f): return {k: float(np.clip(f(v), 0, 1)) if k.startswith("e|") else v for k, v in e.items()}
rng = np.random.default_rng(1)
for s in (0.01, 0.02, 0.05, 0.10):
    a = []
    for _ in range(5): a.append([clef_set(noisy(ER[n], lambda v: v + rng.normal(0, s))) == CE[n] for n in range(N)])
    a = np.array(a); P(f"  noise ±{s:.2f}: same set on {a.mean():.1%} of stories; on Clef-non-empty stories {a[:, ne].mean():.1%}")
for b in (-.02, .02): a = np.array([clef_set(noisy(ER[n], lambda v: v + b)) == CE[n] for n in range(N)]); P(f"  all answers {b:+.2f}: same set on {a.mean():.1%}; non-empty stories {a[ne].mean():.1%}")
# near-threshold mass
near = []
for n in range(N):
    if not CE[n]: continue
    e = ER[n]; v = [abs(max(e[f"e|{d}|up"], e[f"e|{d}|down"]) - .5) for d in PH if f"e|{d}|up" in e] + [abs(abs(e[f"e|{d}|up"] - e[f"e|{d}|down"]) - .05) for d in PH if f"e|{d}|up" in e]; near.append(min(v))
P(f"  non-empty stories with some answer within .02 of a decision line (.5 or net .05): {np.mean(np.array(near)<.02):.1%}; within .05: {np.mean(np.array(near)<.05):.1%}")
# real Clef-vs-Clef
for f in ("test_2step300", "test_2step300_metablocks"):
    try:
        O = {json.loads(l)["id"]: json.loads(l) for l in open(f"{LAB}/{f}.jsonl")}; ids = [i for i in O if i in byid]; m = [{(x["dial"], x["direction"]) for x in O[i]["expected"]} == {(x["dial"], x["direction"]) for x in byid[i]["expected"]} for i in ids]
        P(f"  Clef vs Clef, same stories, different grouping/mode ({f}, {len(ids)} stories): identical expected set on {np.mean(m):.1%}")
    except Exception as ex: P("  (could not read", f, ex, ")")

# --- screen-then-check ---
P("\nScreen-then-check for expected impact: BitMob shortlists dials (either direction >= cut), Clef answers all questions in the 20-question blocks that contain a shortlisted dial (its usual blocks; the e list is built from the non-reported, allowed dials, then 'done').")
P("Front (reported/allowed dials) taken from Clef here, so that this isolates the e answers; with BitMob front, see the table above (the front costs agreement before any e question is asked).")
EM = Z["expected_mask"][keep] > 0; TE = Z["expected"][keep]; UH = HUR["expected"]
col = lambda d, dr: ei[f"{d}|{dr}"]
tr_cells = []; tr_score = []
for n in range(len(keep)):
    for d in PH:
        if EM[n, col(d, "up")] and EM[n, col(d, "down")]:
            t = max(TE[n, col(d, "up")], TE[n, col(d, "down")]); s = max(UH[n, col(d, "up")], UH[n, col(d, "down")]); tr_cells.append(t >= C.EXPECT_MIN); tr_score.append(s)
tr_cells = np.array(tr_cells); tr_score = np.array(tr_score)
P(f"  tune: {len(tr_cells)} dial cells with Clef answers, {tr_cells.sum()} reach .5; BitMob AUC for 'Clef reaches .5' on tune {roc_auc_score(tr_cells, tr_score):.3f}")
def blocks_for(n, reported, allowed):
    lst = [d for d in PH if d not in reported and d in allowed]; qs = [f"{d}|{dr}" for d in lst for dr in ("up", "down")] + ["done"]; return lst, [qs[j:j + 20] for j in range(0, len(qs), 20)], qs
def sim(thr, EV):
    ok = []; qn = []; share0 = 0; nb = []; qfull = []
    for n in range(N):
        lst, bl, qs = blocks_for(n, REP_C[n], ALW_C[n]); cand = {d for d in lst if max(EV[n][f"e|{d}|up"], EV[n][f"e|{d}|down"]) >= thr}
        asked = [b for b in bl if any((q.split("|")[0] in cand) for q in b if q != "done")]
        clef_d = {q.split("|")[0] for b in asked for q in b if q != "done"}
        e = {}
        for d in lst:
            src = ER[n] if d in clef_d else EV[n]
            if d in clef_d and f"e|{d}|up" not in ER[n]: src = EV[n]
            e[f"e|{d}|up"] = src[f"e|{d}|up"]; e[f"e|{d}|down"] = src[f"e|{d}|down"]
        ok.append(clef_set(e) == CE[n]); qn.append(sum(len(b) for b in asked)); nb.append(len(asked)); qfull.append(len(qs))
    return np.mean(ok), np.mean(qn), np.mean(nb), np.mean(qfull), np.array(qn)
for rec in (.90, .95, .98, .99):
    thr = float(np.sort(tr_score[tr_cells])[::-1][int(rec * tr_cells.sum()) - 1]); ag, q, b, qf, qa = sim(thr, EV_R)
    P(f"  tune-fit cut {thr:.3f} (catches {rec:.0%} of Clef's >=.5 dials on tune): TEST same set {ag:.1%}; Clef asked {q:.1f} e-questions/story in {b:.2f} calls (full e battery {qf:.1f} q/story, {(qa==0).mean():.0%} of stories need no Clef question at all)")
P("  Clef asks every e question (full e battery) = 100% by construction (stored answers), cost above; the same-set bar needs Clef's actual answers, the CPU cannot reproduce the exact set alone.")
thr0 = float(np.sort(tr_score[tr_cells])[::-1][int(.98 * tr_cells.sum()) - 1])
P("  lower-cut sweep (test) to see how far agreement can be bought:")
for thr in (.30, .20, .15, .10, .07, .05, .03):
    ag, q, b, qf, qa = sim(thr, EV_R); P(f"    cut {thr:.2f}: same set {ag:.1%}, Clef {q:.1f} q/story of {qf:.1f} ({q/qf:.0%}), {(qa==0).mean():.0%} stories with no Clef question")
open(OUT, "w").write("\n".join(LINES) + "\n"); print("wrote", OUT)
