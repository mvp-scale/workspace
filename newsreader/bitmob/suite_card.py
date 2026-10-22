"""Per-model acceptance card (T-0025): every candidate x every area from data/suite/<model>/<area>.json|.npz, written to data/scorecard/models.json.

Bars are the scorecard's (scorecard.py, criteria rev 2): T2 per-type AP (happened 0.95, announced 0.90, opinion 0.85, forecast 0.85), P2 topic accuracy 0.85,
K2 AP >= 0.70 per key, K6 <= 2.5 false alarms per 1,000 per key (threshold = max F1 on the night1 held-out part, scored on testA). Country has no
per-model bar: its criteria (C1-C11) score named-country extraction, which the script does; the reader row shows agreement with the engine's country.
Every model on the shortlist gets a row, so a model that was never run shows as "not run" with the reason.
  python3 newsreader/bitmob/suite_card.py
"""
import json, os, glob
import numpy as np

W = "/workspace/data"; TAG = os.environ.get("SUITE_TAG", ""); OUT = f"{W}/scorecard/models{TAG}.json"
AREAS = ["type", "topic", "country", "conditions"]
SHORTLIST = {"tfidf": "TF-IDF + LR", "e5": "e5-small frozen + LR", "e5tfidf": "e5 + TF-IDF + LR", "potion": "potion-32M frozen + LR",
             "potion_ft": "potion-32M fine-tuned (model2vec)", "setfit": "SetFit (e5 body)", "e5ft": "e5-small fine-tuned", "ensemble": "ensemble e5+TF-IDF / e5 fine-tuned"}
T2 = {"happened": 0.95, "announced": 0.90, "opinion": 0.85, "forecast": 0.85}


def k6(z):
    P, Y, nn = z["P"], z["Y"].astype(bool), int(z["n_night"]); ok = n = 0
    for i in range(P.shape[1]):
        if Y[nn:, i].sum() < 3: continue
        pv, yv = P[:nn, i], Y[:nn, i]; best, th = -1, 0.5
        for t in np.unique(np.round(pv, 2)):
            pr = pv >= t; f1 = 2 * (pr & yv).sum() / max(1, pr.sum() + yv.sum())
            if f1 > best: best, th = f1, t
        neg = ~Y[nn:, i]; n += 1; ok += ((P[nn:, i] >= th) & neg).sum() / max(1, neg.sum()) <= 0.0025
    return int(ok), n


def cell(area, r, z):
    if area == "type":
        ap = r["per_key_AP"]; ok = [k for k, b in T2.items() if ap.get(k, 0) >= b]
        why = "; ".join(f"{k} {ap.get(k, 0):.3f}{' pass' if k in ok else f' (pass mark {b})'}" for k, b in T2.items())
        return {"pass": len(ok), "of": 4, "metric": f"AP {r['mean_AP']:.3f}", "score": r["mean_AP"], "value": r["mean_AP"], "bar": None,
                "parts": [{"k": k, "v": ap.get(k, 0), "bar": b} for k, b in T2.items()], "why": f"Ranking score per story kind: {why}"}
    if area == "topic":
        a = r["accuracy"]; return {"pass": int(a >= 0.85), "of": 1, "metric": f"acc {a:.3f}", "score": a, "value": a, "bar": 0.85, "why": f"Topic: {a:.3f} right vs pass mark 0.85 (average of per-topic F1 scores {r['macroF1']:.3f})"}
    if area == "country":
        a = r["accuracy"]; return {"pass": None, "of": None, "metric": f"acc {a:.3f}", "score": a, "value": a, "bar": None, "why": f"Agrees with Jev's country on {a:.3f} of stories (16 countries); no pass mark for models: the country pass marks score the script checker"}
    ap = r["per_key_AP"]; w = sum(v >= 0.70 for v in ap.values()); f6 = k6(z) if z is not None else (None, None)
    return {"pass": w, "of": len(ap), "metric": f"AP {r['mean_AP']:.3f}", "score": r["mean_AP"], "value": r["mean_AP"], "bar": 0.70, "k6": f6,
            "why": f"{w} of {len(ap)} conditions reach ranking score 0.70; {f6[0]} of {f6[1]} stay within 2.5 false alarms per 1,000 stories"}


def build():
    rows = []
    for m, name in SHORTLIST.items():
        row = {"id": m, "name": name, "areas": {}, "ms": None}
        for a in AREAS:
            f = f"{W}/suite{TAG}/{m}/{a}.json"
            if not os.path.exists(f): continue
            r = json.load(open(f)); zf = f[:-5] + ".npz"
            row["areas"][a] = cell(a, r, np.load(zf, allow_pickle=True) if os.path.exists(zf) else None)
            if r.get("ms_per_story") is not None: row["ms"] = r["ms_per_story"]
        row["status"] = "not run yet" if not row["areas"] else f"{len(row['areas'])}/4 areas scored"
        rows.append(row)
    for d in sorted(glob.glob(f"{W}/suite_kaggle*")) if TAG == "_r3" else []:   # encoders fine-tuned on Kaggle (same round-3 train, same frozen test), scored locally on CPU
        run = os.path.basename(d)[len("suite_kaggle"):]
        for md in sorted(glob.glob(f"{d}/*/")):
            m = os.path.basename(md.rstrip("/")); row = {"id": f"kaggle{run}:{m}", "name": f"{m} fine-tuned on Kaggle (run {run})", "areas": {}, "ms": None}
            for a in AREAS:
                f = f"{md}{a}.json"
                if not os.path.exists(f): continue
                r = json.load(open(f)); zf = f[:-5] + ".npz"; row["areas"][a] = cell(a, r, np.load(zf, allow_pickle=True) if os.path.exists(zf) else None)
                if r.get("ms_per_story") is not None: row["ms"] = r["ms_per_story"]
            row["status"] = f"{len(row['areas'])}/4 areas scored"; rows.append(row)
    cv = json.load(open(f"{W}/country-val/country-val.json")) if os.path.exists(f"{W}/country-val/country-val.json") else None
    if cv: rows.append({"id": "country_script", "name": "country script checker v2", "ms": 10.8, "status": "country only (D-0015 label)",
                        "areas": {"country": {"pass": 0, "of": 2, "metric": f"recall {cv['C1']['fresh_random']:.3f}", "score": None, "value": cv['C1']['fresh_random'], "bar": 0.97, "label": "recall",
                                              "why": f"Recall {cv['C1']['fresh_random']:.3f} / precision {cv['C2']['fresh_all']:.3f} on fresh stories vs pass mark 0.97 (F-0062)"}}})
    for a in AREAS:   # mark the best model per area
        sc = [(r["areas"][a]["score"], r) for r in rows if a in r["areas"] and r["areas"][a].get("score") is not None]
        if sc: max(sc, key=lambda x: x[0])[1]["areas"][a]["best"] = True
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"areas": AREAS, "models": rows, "test": "night1 held-out 2,000 + testA 9,997, Jev labels (interim; not the jury set)"}, open(OUT, "w"), indent=1)
    return rows


if __name__ == "__main__":
    for r in build(): print(r["name"], {a: v["metric"] + (f" {v['pass']}/{v['of']}" if v["of"] else "") for a, v in r["areas"].items()})
