"""Jev -> Clef translation (D-0038 round 2, D-0042). Per question, a monotone map from Jev's answer to Clef's scale, fitted ONLY on stories that both teachers labelled
inside the Clef TRAINING sets (r1_local, r1b, pilots_train, kaggle_pilot2_train). The frozen test (data/clef-labels/test*.jsonl, test_in.jsonl) is never read for fitting.
  fit:   /workspace/kev/.venv/bin/python newsreader/bitmob/mh/translate_jev_clef.py fit [--out data/jev-labels/maps.json]
  apply: from translate_jev_clef import load_maps, translate_record     (used by build_mh_data.py round 2)
Pairs: new Jev rows (data/jev-labels/*.jsonl, Clef-record schema) take priority; for the 328 yes/no questions the OLD Jev rows (data/trainset/*.jsonl, same questions, same text) fill in the rest.
Map choice per key (a key with too little data borrows from its pool; the choice is stored in the json under 'how'):
  isotonic where the key has n >= 200 pairs and >= 20 positives (Clef value >= .5), else Platt (logistic on logit, soft targets as sample weights) where the pool has >= 20 positives, else identity.
  pools, narrowest first:  g|*, s|*, x|* each alone -> attribute: (dial, direction) pool over its attributes and both wordings -> all attributes -> identity
                            place p_choice: per domain -> all domains;  place p_yes: per domain -> all domains;  e| : one pool for up and down together;  done: alone;  severity: per level, pooled over dials.
  country steps: no map (labels are the one-hot chosen country/region); only the agreement of Jev's choice with Clef's is reported.
CV: 5 folds by story id; Brier of the raw Jev value vs the mapped value, both against Clef's answer, on the held-out fold. Gate: accept/reject agreement with Clef on held-out folds, raw vs mapped."""
import os, sys, json, glob, hashlib, argparse
os.environ.setdefault("WE_RULES", "rules_v2"); os.environ.setdefault("WORLD_GPU", "0")
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo"]
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
import classify as C

W = "/workspace/data"; CLEF_TRAIN = [f"{W}/clef-labels/{n}.jsonl" for n in ("r1_local", "r1b", "pilots_train", "kaggle_pilot2_train", "r3")]
OLD_JEV = [f"{W}/trainset/{n}.jsonl" for n in ("night1", "round1", "round2", "loop1", "loop2", "loop3", "loop4", "loop5")]
QS = list(C.QS)
DIALS_DIR = sorted(C.ATTRS)
MIN_N, MIN_POS = 200, 20


def test_ids():
    s = set()
    for f in (f"{W}/clef-labels/test_in.jsonl", f"{W}/clef-labels/test.jsonl", f"{W}/clef-labels/test_noraw_partial.jsonl"):
        if os.path.exists(f): s |= {json.loads(l)["id"] for l in open(f) if l.strip()}
    return s


def jl(f):
    return [json.loads(l) for l in open(f) if l.strip()] if os.path.exists(f) else []


def logit(x):
    x = np.clip(np.asarray(x, float), 0.005, 0.995); return np.log(x / (1 - x))


def fit_one(x, y):
    """-> map dict. x: Jev values, y: Clef values in [0,1] (soft)."""
    x = np.asarray(x, float); y = np.asarray(y, float); n = len(x); pos = int((y >= .5).sum())
    if n >= MIN_N and pos >= MIN_POS:
        ir = IsotonicRegression(y_min=0, y_max=1, increasing=True, out_of_bounds="clip").fit(x, y); return {"t": "iso", "x": [round(float(v), 5) for v in ir.X_thresholds_], "y": [round(float(v), 5) for v in ir.y_thresholds_], "n": n, "pos": pos}
    if pos >= MIN_POS and n - pos >= MIN_POS:
        X = np.concatenate([logit(x), logit(x)])[:, None]; Y = np.concatenate([np.ones(n), np.zeros(n)]); Wt = np.concatenate([y, 1 - y]) + 1e-6
        lr = LogisticRegression(C=10).fit(X, Y, sample_weight=Wt); return {"t": "platt", "a": float(lr.coef_[0, 0]), "b": float(lr.intercept_[0]), "n": n, "pos": pos}
    return {"t": "id", "n": n, "pos": pos}


def apply_map(m, x):
    x = np.asarray(x, float)
    if m is None or m["t"] == "id": return x
    if m["t"] == "iso": return np.interp(x, m["x"], m["y"])
    return 1 / (1 + np.exp(-(m["a"] * logit(x) + m["b"])))


def pairs_for_keys(pairs, keys, getj, getc):
    """-> {key: (x list, y list)} over stories where both teachers have the key."""
    out = {k: ([], []) for k in keys}
    for jr, cr in pairs:
        for k in keys:
            a, b = getj(jr, k), getc(cr, k)
            if a is not None and b is not None: out[k][0].append(a); out[k][1].append(b)
    return out


def build_pairs():
    ts = test_ids(); clef = {}
    for f in CLEF_TRAIN:
        for r in jl(f):
            assert r["id"] not in ts, "frozen test id in Clef training set: " + r["id"]; clef[r["id"]] = r
    jev = {}
    for f in sorted(glob.glob(f"{W}/jev-labels/*.jsonl")):
        for r in jl(f):
            if r["id"] in clef: jev[r["id"]] = r
    new_ids = set(jev)
    for f in OLD_JEV:
        for r in jl(f):
            if r["id"] in clef and r["id"] not in jev: jev[r["id"]] = r
    return [(jev[i], clef[i], i in new_ids) for i in sorted(jev)]


def getP(r, k): return r["P"].get(k) if "P" in r else None


def getPl(field):
    def g(r, k):
        for x in r.get("place") or []:
            if x["id"] == k: return x.get(field)
        return None
    return g


def getE(r, k): return (r.get("e_raw") or {}).get(k)


def getS(level):
    def g(r, k):
        v = (r.get("severity") or {}).get(k); return None if not v else v["p"].get(level, 0.0)
    return g


def fit_maps(pairs):
    """pairs: [(jev_rec, clef_rec, jev_is_new)] -> maps dict."""
    maps = {"P": {}, "choice": {}, "yes": {}, "e": {}, "done": None, "sev": {}, "how": {}}
    jc = [(j, c) for j, c, _ in pairs]
    # --- the 328 yes/no questions
    D = pairs_for_keys(jc, QS, getP, getP)
    solo = [k for k in QS if not k.startswith("a|")]
    for k in solo: maps["P"][k] = fit_one(*D[k]); maps["how"][k] = maps["P"][k]["t"]
    allx, ally = [], []
    pool = {}
    for k in QS:
        if not k.startswith("a|"): continue
        _, d, dr, i, w = k.split("|"); pool.setdefault((d, dr), ([], [])); pool[(d, dr)][0].extend(D[k][0]); pool[(d, dr)][1].extend(D[k][1]); allx.extend(D[k][0]); ally.extend(D[k][1])
    allmap = fit_one(allx, ally); maps["P"]["_attr_all"] = allmap
    for (d, dr), (x, y) in pool.items(): maps["P"][f"_attr|{d}|{dr}"] = fit_one(x, y)
    for k in QS:
        if not k.startswith("a|"): continue
        _, d, dr, i, w = k.split("|"); own = fit_one(*D[k]); dp = maps["P"][f"_attr|{d}|{dr}"]
        m = own if own["t"] == "iso" else dp if dp["t"] != "id" else allmap
        maps["P"][k] = m; maps["how"][k] = ("own" if m is own else "dial_dir" if m is dp else "all_attr") + ":" + m["t"]
    # --- place
    doms = [d["id"] for d in C.DOMAINS]
    for field, name, ds in (("p_choice", "choice", doms), ("p_yes", "yes", [d for d in doms if d != "other"])):
        D2 = pairs_for_keys(jc, ds, getPl(field), getPl(field)); ax, ay = [], []
        for d in ds: ax += D2[d][0]; ay += D2[d][1]
        pool = fit_one(ax, ay); maps[name]["_all"] = pool
        for d in ds:
            own = fit_one(*D2[d]); maps[name][d] = own if own["t"] == "iso" else pool
    # --- expected raw answers
    ek = sorted({k for _, c in jc for k in (c.get("e_raw") or {}) if k != "done"} | {k for j, _ in jc for k in (j.get("e_raw") or {}) if k != "done"})
    D3 = pairs_for_keys(jc, ek, getE, getE); ex, ey = [], []
    for k in ek: ex += D3[k][0]; ey += D3[k][1]
    maps["e"]["_all"] = fit_one(ex, ey)
    D4 = pairs_for_keys(jc, ["done"], getE, getE); maps["done"] = fit_one(*D4["done"])
    # --- severity levels pooled over dials
    dials = sorted(C.PHRASES)
    for lv in [l["id"] for l in C.LEVELS]:
        D5 = pairs_for_keys(jc, dials, getS(lv), getS(lv)); sx, sy = [], []
        for d in dials: sx += D5[d][0]; sy += D5[d][1]
        maps["sev"][lv] = fit_one(sx, sy)
    maps["n_pairs"] = len(pairs); maps["n_pairs_new_jev"] = sum(1 for p in pairs if p[2])
    return maps


def norm(d):
    s = sum(d.values()) or 1.0; return {k: v / s for k, v in d.items()}


def translate_P(P, maps):
    Q = dict(P)
    for k in QS:
        if k in P and k in maps["P"]: Q[k] = float(apply_map(maps["P"][k], [P[k]])[0])
    return Q


def tag_rule(pl):
    """classify.place()'s tagging on a list of {id,p_choice,p_yes}."""
    for x in pl: x["tagged"] = bool(x["id"] != "other" and (x["p_choice"] >= .2 or x["p_yes"] >= .5) or (x["id"] == "other" and x["p_choice"] >= .2))
    if not any(x["tagged"] for x in pl): max(pl, key=lambda x: x["p_choice"])["tagged"] = True
    return pl


def translate_record(r, maps):
    """A Jev record (Clef-record schema, or an old record with only P/topic_p/country_p) -> a Clef-schema record on Clef's scale. Marks which heads the record can train in r['_heads']."""
    o = dict(r); o["teacher"] = "jev->clef"; heads = {"gate", "scope", "cond"}
    o["P"] = translate_P(r["P"], maps); o["read"] = C.read(o["P"])
    if "place" in r and r["place"]:
        pl = []
        for x in r["place"]:
            pc = float(apply_map(maps["choice"].get(x["id"]), [x["p_choice"]])[0]); py = float(apply_map(maps["yes"].get(x["id"]), [x["p_yes"]])[0]) if x["id"] != "other" else 0.0
            pl.append({"id": x["id"], "name": x.get("name"), "p_choice": pc, "p_yes": py})
        s = sum(x["p_choice"] for x in pl) or 1.0
        for x in pl: x["p_choice"] /= s
        o["place"] = tag_rule(pl); heads |= {"topic_c", "topic_y"}
    elif "topic_p" in r:
        o["place"] = [{"id": k, "name": k, "p_choice": float(v), "p_yes": 0.0, "tagged": False} for k, v in r["topic_p"].items()]; heads |= {"topic_c"}      # old rows: main-topic soft target only, untranslated
    if r.get("e_raw"):
        e = {k: float(apply_map(maps["e"]["_all"], [v])[0]) for k, v in r["e_raw"].items() if k != "done"}; e["done"] = float(apply_map(maps["done"], [r["e_raw"].get("done", 0.0)])[0]); o["e_raw"] = e; heads |= {"expected", "done"}
        rep = {x["dial"] for x in o["read"]["readings"] if x["direction"] != "conflict"}; allowed = C.allowed_dials(o["place"]) if "place" in r and r["place"] else None; out = []
        for d in sorted({k.split("|")[1] for k in e if k != "done"}):
            if d in rep or (allowed is not None and d not in allowed): continue
            pu, pd = e.get(f"e|{d}|up", 0.0), e.get(f"e|{d}|down", 0.0); net = pu - pd
            if max(pu, pd) >= C.EXPECT_MIN and abs(net) > .05: out.append({"dial": d, "direction": "up" if net > 0 else "down", "strength": abs(net), "p_done": e["done"]})
        o["expected"] = sorted(out, key=lambda x: -x["strength"])[:C.EXPECT_TOP]
    if r.get("severity"):
        sv = {}
        for d, v in r["severity"].items():
            p = norm({lv: float(apply_map(maps["sev"].get(lv), [x])[0]) for lv, x in v["p"].items()}); sv[d] = {**v, "p": p}
        o["severity"] = sv; heads |= {"severity"}
    o["_heads"] = sorted(heads); return o


def load_maps(path=f"{W}/jev-labels/maps.json"):
    return json.load(open(path))


def cv_report(pairs, k=5):
    ids = sorted(p[0]["id"] for p in pairs); fold = {i: int(hashlib.md5(i.encode()).hexdigest(), 16) % k for i in ids}
    def gate(P): return bool((P["g|happened"] >= .5 or P["g|announced"] >= .5) and P["g|opinion"] < .5 and P["x|recent"] >= .3)
    rows = {"gate_agree_raw": [], "gate_agree_mapped": [], "brier": {}}; br = {}
    jr_all = []
    for f in range(k):
        tr = [p for p in pairs if fold[p[0]["id"]] != f]; te = [p for p in pairs if fold[p[0]["id"]] == f]
        if not te or not tr: continue
        m = fit_maps(tr)
        for j, c, _ in te:
            jp = translate_P(j["P"], m); rows["gate_agree_raw"].append(gate(j["P"]) == gate(c["P"])); rows["gate_agree_mapped"].append(gate(jp) == gate(c["P"]))
            for k_ in QS:
                grp = k_ if not k_.startswith("a|") else "attributes"; grp = {"g": "gate questions", "s": "scope questions", "x": "recent/focus questions", "a": "attributes"}[k_.split("|")[0]]
                b = br.setdefault(grp, [0.0, 0.0, 0]); b[0] += (j["P"][k_] - c["P"][k_]) ** 2; b[1] += (jp[k_] - c["P"][k_]) ** 2; b[2] += 1
    out = {}
    for f in range(k):      # place / expected / severity groups, same folds
        tr = [p for p in pairs if fold[p[0]["id"]] != f]; te = [p for p in pairs if fold[p[0]["id"]] == f]
        if not te or not tr: continue
        m = fit_maps(tr)
        for j, c, _ in te:
            if j.get("place") and c.get("place"):
                cj = {x["id"]: x for x in j["place"]}
                for x in c["place"]:
                    y = cj.get(x["id"])
                    if not y: continue
                    for fld, nm, mp in (("p_choice", "topic choice", m["choice"]), ("p_yes", "topic yes/no", m["yes"])):
                        if fld == "p_yes" and x["id"] == "other": continue
                        v = float(apply_map(mp.get(x["id"]), [y[fld]])[0]); b = br.setdefault(nm, [0.0, 0.0, 0]); b[0] += (y[fld] - x[fld]) ** 2; b[1] += (v - x[fld]) ** 2; b[2] += 1
            if j.get("e_raw") and c.get("e_raw"):
                for kk, yv in j["e_raw"].items():
                    if kk in c["e_raw"]:
                        v = float(apply_map(m["done"] if kk == "done" else m["e"]["_all"], [yv])[0]); b = br.setdefault("expected impact" if kk != "done" else "already in effect", [0.0, 0.0, 0]); b[0] += (yv - c["e_raw"][kk]) ** 2; b[1] += (v - c["e_raw"][kk]) ** 2; b[2] += 1
            if j.get("severity") and c.get("severity"):
                for d, v0 in j["severity"].items():
                    if d in c["severity"]:
                        for lv, yv in v0["p"].items():
                            v = float(apply_map(m["sev"].get(lv), [yv])[0]); b = br.setdefault("severity levels", [0.0, 0.0, 0]); b[0] += (yv - c["severity"][d]["p"].get(lv, 0)) ** 2; b[1] += (v - c["severity"][d]["p"].get(lv, 0)) ** 2; b[2] += 1
    out.update({g: {"brier_raw": round(v[0] / v[2], 5), "brier_mapped": round(v[1] / v[2], 5), "n_values": v[2]} for g, v in br.items()})
    out["gate_agreement_vs_clef"] = {"raw_jev": round(float(np.mean(rows["gate_agree_raw"])), 4), "mapped": round(float(np.mean(rows["gate_agree_mapped"])), 4), "n_stories": len(rows["gate_agree_raw"])}
    return out


def country_agreement(pairs):
    a = [j["country"] == c["country"] for j, c, new in pairs if "country_detail" in j]
    return {"jev_vs_clef_country_same": round(float(np.mean(a)), 4), "n": len(a)} if a else None


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["fit"]); ap.add_argument("--out", default=f"{W}/jev-labels/maps.json"); a = ap.parse_args()
    pairs = build_pairs(); print(len(pairs), "stories labelled by both teachers;", sum(1 for p in pairs if p[2]), "with new Jev rows")
    maps = fit_maps(pairs); rep = cv_report(pairs)
    hap = {k: maps["P"][k] for k in ("g|happened", "g|announced", "g|opinion", "g|forecast", "x|recent")}
    rawj = np.mean([j["P"]["g|happened"] for j, c, _ in pairs]); rawc = np.mean([c["P"]["g|happened"] for j, c, _ in pairs]); mapj = np.mean(apply_map(maps["P"]["g|happened"], [j["P"]["g|happened"] for j, c, _ in pairs]))
    rep["g|happened_mean"] = {"jev_raw": round(float(rawj), 3), "clef": round(float(rawc), 3), "jev_mapped": round(float(mapj), 3), "share>=.5 jev raw": round(float(np.mean([j["P"]["g|happened"] >= .5 for j, c, _ in pairs])), 3),
                              "share>=.5 clef": round(float(np.mean([c["P"]["g|happened"] >= .5 for j, c, _ in pairs])), 3), "share>=.5 jev mapped": round(float(np.mean(apply_map(maps["P"]["g|happened"], [j["P"]["g|happened"] for j, c, _ in pairs]) >= .5)), 3)}
    rep["how_counts"] = {t: sum(1 for v in maps["how"].values() if v.endswith(t) or v == t) for t in ("iso", "platt", "id")}
    rep["country"] = country_agreement(pairs)
    maps["cv"] = rep; os.makedirs(os.path.dirname(a.out), exist_ok=True); json.dump(maps, open(a.out, "w")); print(json.dumps(rep, indent=1))
