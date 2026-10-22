"""Round-2 training data for the multi-head reader (D-0038, D-0042). Training rows only: the frozen test (data/clef-labels/test_in.jsonl, test*.jsonl) is excluded by id and asserted absent.
  /workspace/kev/.venv/bin/python newsreader/bitmob/mh/build_mh_data2.py OUT_DIR TUNE_DIR [--maps data/jev-labels/maps.json] [--clef f.jsonl ...] [--jev f.jsonl ...] [--tune_frac .15] [--no_old]
Sources, highest priority first when a story has several:
  (c) Clef rows (data/clef-labels/{r1_local,r1b,pilots_train,kaggle_pilot2_train}.jsonl by default): every head, as labelled, row weight 2.
  (b) new Jev rows (every data/jev-labels/*.jsonl by default except pilot*.jsonl, which overlap): every head, translated to Clef's scale by translate_jev_clef.py, weight 1.
  (a) old Jev rows (data/trainset: night1 minus the held-out 2,000, round1, round2, loop1-5; ~14k): only the heads whose old labels carry the engine's semantics: gate, scope, 318 attributes (translated), main topic (old topic_p, untranslated), region+country. Weight 1.
Per-head loss masks m_<head> (N,) tell the trainer which heads a row trains; expected/done/severity keep their element masks. With e_raw present the expected targets are Clef's raw e| probabilities for the dials the engine asked, not the filtered list.
tune split: 15% of rows by md5(id), written to TUNE_DIR in the same format and NOT in OUT_DIR; OUT_DIR/keys.json lists tune_ids so the split is checkable. Outputs: {texts.json, targets.npz, keys.json, sources.json}."""
import os, sys, json, glob, argparse, hashlib, collections
os.environ.setdefault("WE_RULES", "rules_v2"); os.environ.setdefault("WORLD_GPU", "0")
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo", os.path.dirname(os.path.abspath(__file__))]
import numpy as np, classify as C
import translate_jev_clef as T

W = "/workspace/data"
ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("tune"); ap.add_argument("--maps", default=f"{W}/jev-labels/maps.json")
ap.add_argument("--clef", nargs="*", default=[f"{W}/clef-labels/{n}.jsonl" for n in ("r1_local", "r1b", "pilots_train", "kaggle_pilot2_train", "r3", "r5")])      # missing files are skipped (translate_jev_clef.jl)
ap.add_argument("--jev", nargs="*", default=[f for f in sorted(glob.glob(f"{W}/jev-labels/*.jsonl")) if "pilot" not in f]); ap.add_argument("--tune_frac", type=float, default=0.15); ap.add_argument("--no_old", action="store_true")
ap.add_argument("--max_old", type=int, default=0, help="dry runs: cap the old Jev rows"); a = ap.parse_args()
for f in a.clef + a.jev: assert "test" not in os.path.basename(f) and "pilot50" not in f, f"refusing {f}"
TEST = T.test_ids(); maps = T.load_maps(a.maps)
sel = {}; src = collections.Counter()
for f in a.clef:
    for r in T.jl(f):
        if r["id"] in TEST: continue
        sel.setdefault(r["id"], (r, "clef", float(os.environ.get("CLEF_W", "4.0"))));
for f in a.jev:
    for r in T.jl(f):
        if r["id"] in TEST or r["id"] in sel: continue
        sel[r["id"]] = (T.translate_record(r, maps), "jev", 1.0)
if not a.no_old:
    n_old = 0
    for f in T.OLD_JEV:
        for r in T.jl(f):
            if r["id"] in TEST or r["id"] in sel: continue
            if a.max_old and n_old >= a.max_old: break
            r = dict(r); r["state_text"] = f"{r['title']}. {r['description']}"; r.pop("place", None); r.pop("e_raw", None); r.pop("severity", None); r.pop("expected", None)
            sel[r["id"]] = (T.translate_record(r, maps), "old_jev", 1.0); n_old += 1
for i in sel: assert i not in TEST, "frozen test id in training: " + i
GATE = ["g|happened", "g|announced", "g|opinion", "g|forecast", "x|recent"]; SCOPE = ["s|national", "s|local", "s|new", "x|us_focus", "x|foreign_focus"]
ATT = [(d, dr, i) for (d, dr), lst in sorted(C.ATTRS.items()) for i in range(len(lst))]; COND = [f"{d}|{dr}|{i}" for d, dr, i in ATT]
DOM = [d["id"] for d in C.DOMAINS]; DOMY = [d for d in DOM if d != "other"]
rows100 = C._country_rows(); REG = sorted({x["region"] for x in rows100}) + ["GLOBAL"]; CTY = [x["id"] for x in rows100] + ["other_here", "global"]
DIALS = sorted(C.PHRASES); EXP = [f"{d}|{u}" for d in DIALS for u in ("up", "down")]; LV = [l["id"] for l in C.LEVELS]
READ = [f"{d}|{dr}" for (d, dr) in sorted(C.ATTRS)]; ri_ = {k: i for i, k in enumerate(READ)}; ATT_OF = {k: [j for j, (d, dr, i) in enumerate(ATT) if f"{d}|{dr}" == k] for k in READ}
keys = {"gate": GATE, "scope": SCOPE, "cond": COND, "topic_c": DOM, "topic_y": DOMY, "region": REG, "country": CTY, "expected": EXP, "done": ["done"], "severity": DIALS, "levels": LV, "reading": READ}
ci = {k: i for i, k in enumerate(CTY)}; ri = {k: i for i, k in enumerate(REG)}; ei = {k: i for i, k in enumerate(EXP)}; di = {d: i for i, d in enumerate(DIALS)}; reg_of = {x["id"]: x["region"] for x in rows100}
MH = ["gate", "scope", "cond", "topic_c", "topic_y", "region", "country", "reading"]


def build(items):
    N = len(items); Z = lambda *s: np.zeros(s, np.float32)
    Tg = {k: Z(N, len(keys[k])) for k in ("gate", "scope", "cond", "topic_c", "topic_y", "region", "country", "expected")} | {"expected_mask": Z(N, len(EXP)), "done": Z(N), "done_mask": Z(N), "severity": Z(N, len(DIALS), 5), "sev_mask": Z(N, len(DIALS)), "w": Z(N), "reading": Z(N, len(READ)), "reading_mask": np.ones((N, len(READ)), np.float32), "reading_pw": np.ones((N, len(READ)), np.float32)}
    for h in MH: Tg["m_" + h] = Z(N)
    for n, (r, kind, w) in enumerate(items):
        P = r["P"]; Tg["w"][n] = w
        if r.get("fast"): heads = {"gate", "scope", "cond", "reading"}      # round 6: Clef fast-mode rows carry P (328) + read only: place/country/expected/severity heads are masked, as for old Jev rows
        else: heads = set(r.get("_heads") or ["gate", "scope", "cond", "topic_c", "topic_y", "expected", "done", "severity"]) | {"region", "country", "reading"}
        for h in MH:
            if h in heads: Tg["m_" + h][n] = 1.0
        for j, k in enumerate(GATE): Tg["gate"][n, j] = P[k]
        for j, k in enumerate(SCOPE): Tg["scope"][n, j] = P[k]
        for j, (d, dr, i) in enumerate(ATT): Tg["cond"][n, j] = (P[f"a|{d}|{dr}|{i}|0"] + P[f"a|{d}|{dr}|{i}|1"]) / 2
        # reading-level labels (round 5). Attribute rule = classify.read(): a (dial,dir) fires when any attribute's two-wordings mean >= ATTR_MIN. Clef rows use the engine's own readings; a dial that fires in BOTH directions is a conflict: both keys masked.
        fire = np.array([(Tg["cond"][n, ATT_OF[k]] >= C.ATTR_MIN).any() for k in READ])
        if kind == "clef": lab = np.zeros(len(READ), np.float32); [lab.__setitem__(ri_[f"{x['dial']}|{x['direction']}"], 1.0) for x in r["read"]["readings"] if x["direction"] != "conflict"]
        else: lab = fire.astype(np.float32)
        Tg["reading"][n] = lab
        for d in DIALS:
            if f"{d}|up" in ri_ and f"{d}|down" in ri_ and fire[ri_[f"{d}|up"]] and fire[ri_[f"{d}|down"]]: Tg["reading_mask"][n, ri_[f"{d}|up"]] = Tg["reading_mask"][n, ri_[f"{d}|down"]] = 0.0; Tg["reading"][n, ri_[f"{d}|up"]] = Tg["reading"][n, ri_[f"{d}|down"]] = 0.0
        if "topic_c" in heads:
            pc = {x["id"]: x["p_choice"] for x in r["place"]}; s = sum(pc.values()) or 1.0
            for j, d in enumerate(DOM): Tg["topic_c"][n, j] = pc.get(d, 0.0) / s
        if "topic_y" in heads:
            py = {x["id"]: x["p_yes"] for x in r["place"]}
            for j, d in enumerate(DOMY): Tg["topic_y"][n, j] = py.get(d, 0.0)
        det = r.get("country_detail"); c = r.get("country", "global")
        if "region" not in heads: pass      # fast rows: no country labels, masked above
        elif det and det.get("region_choice"): reg = det["region_choice"]; other = bool(det.get("chose_other_here"))
        else: reg = "GLOBAL" if (c == "global" or c not in reg_of) else reg_of[c]; other = False
        if "region" in heads: Tg["region"][n, ri[reg]] = 1.0; Tg["country"][n, ci["global" if reg == "GLOBAL" else "other_here" if other else c]] = 1.0
        if r.get("e_raw"):
            for k, v in r["e_raw"].items():
                if k == "done": Tg["done"][n] = v; Tg["done_mask"][n] = 1.0
                else: Tg["expected"][n, ei[k[2:]]] = v; Tg["expected_mask"][n, ei[k[2:]]] = 1.0
        elif "expected" in heads and r.get("place"):      # round-1 style fallback (filtered list), only Clef rows without raw answers
            reported = {x["dial"] for x in r["read"]["readings"] if x["direction"] != "conflict"}; allowed = C.allowed_dials(r["place"])
            for d in DIALS:
                if d in reported or d not in allowed: continue
                Tg["expected_mask"][n, ei[f"{d}|up"]] = Tg["expected_mask"][n, ei[f"{d}|down"]] = 1.0
            for x in r["expected"]: Tg["expected"][n, ei[f"{x['dial']}|{x['direction']}"]] = 1.0
            if r["expected"]: Tg["done"][n] = float(np.mean([x["p_done"] for x in r["expected"]])); Tg["done_mask"][n] = 1.0
        for d, v in (r.get("severity") or {}).items():
            p = np.array([v["p"].get(l, 0.0) for l in LV], np.float32)
            if p.sum() > 0: Tg["severity"][n, di[d]] = p / p.sum(); Tg["sev_mask"][n, di[d]] = 1.0
    pos = (Tg["reading"] * Tg["reading_mask"]).sum(0); neg = ((1 - Tg["reading"]) * Tg["reading_mask"]).sum(0)
    Tg["reading_pw"][:] = np.clip(np.sqrt(neg / np.maximum(pos, 1)), 1, 20)[None, :]      # per-key pos_weight = clip(sqrt(neg/pos), 1, 20)
    return Tg


def write(d, items, extra=None):
    os.makedirs(d, exist_ok=True); Tg = build(items); np.savez_compressed(f"{d}/targets.npz", **Tg)
    json.dump([r["state_text"] for r, _, _ in items], open(f"{d}/texts.json", "w")); json.dump({"ids": [r["id"] for r, _, _ in items], **keys, **(extra or {})}, open(f"{d}/keys.json", "w"))
    json.dump(dict(collections.Counter(k for _, k, _ in items)), open(f"{d}/sources.json", "w")); return Tg


ids = sorted(sel); is_tune = lambda i: int(hashlib.md5(i.encode()).hexdigest(), 16) % 1000 < int(a.tune_frac * 1000)
tr = [sel[i] for i in ids if not is_tune(i)]; tu = [sel[i] for i in ids if is_tune(i)]
Ttr = write(a.out, tr, {"tune_ids": [i for i in ids if is_tune(i)]}); write(a.tune, tu)
assert not ({r["id"] for r, _, _ in tr} & TEST) and not ({r["id"] for r, _, _ in tr} & {r["id"] for r, _, _ in tu}), "split leak"
print("train", len(tr), dict(collections.Counter(k for _, k, _ in tr)), "| tune", len(tu), dict(collections.Counter(k for _, k, _ in tu)))
print("head rows:", {h: int(Ttr["m_" + h].sum()) for h in MH}, "| expected asked", int((Ttr["expected_mask"].sum(1) > 0).sum()), "done rows", int(Ttr["done_mask"].sum()), "severity rows", int((Ttr["sev_mask"].sum(1) > 0).sum()))
