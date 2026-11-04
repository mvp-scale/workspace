"""Runner for the gates that our data files can answer. The contract (quality.yaml) holds each gate as prose only (test, threshold), with no command and no data source, so the ledger cannot compute them itself; it only draws what someone records with `cp.mjs measure`. This script computes the measurable ones from the saved files and records a measure line ONLY when the numbers changed since the last record. Run after every labelling or training run (the drivers call it).
Gates covered: Q07 Q08 Q09 Q14 Q15 Q17 Q18. Not covered (no data yet, or needs the frozen test, or a second agent): the rest."""
import json, glob, collections, subprocess, pathlib
H0 = pathlib.Path(__file__).resolve().parent; J = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
pool = {r["id"]: r for r in J(H0 / "data/pool_train.jsonl")}; n = len(pool); allp = sum(1 for i, r in pool.items() if r["date"] and i[:3] in ("cc:", "nq:") and len(r["text"]) >= 40); l40 = sum(1 for r in pool.values() if len(r["text"]) >= 40)
labs = [r for f in glob.glob(str(H0 / "runs/p7/*/labels.jsonl")) for r in J(f)]; full = sum(1 for r in labs if all((r.get("provenance") or {}).get(k) for k in ("teacher", "model", "prompt_version", "date", "text_sha256")))
rej = sum(sum(1 for _ in open(d)) for d in glob.glob(str(H0 / "runs/p7/*/rejects.jsonl"))); spend = sum(json.loads(l).get("usd", 0) for f in glob.glob(str(H0 / "runs/p7/*/spend.jsonl")) for l in open(f))
cc = collections.Counter(x["condition"] for r in labs for x in r["label"]["conditions"]); ok30 = sum(1 for v in cc.values() if v >= 30); short = [k for k, v in cc.items() if v < 30]
try: t1 = json.load(open(H0 / "runs/structure/t1_dupes.json")); tw = round(t1["n"] * t1["thr0.8"]["items_with_twin"])
except FileNotFoundError: t1 = None   # Q09 is skipped when its input file is missing
M = [{"gate": "Q07", "pass": allp == n, "value": f"{allp:,} of {n:,} pool items have a date, a source and 40+ characters; {n - allp:,} fail (the nr files carry no source). English not checked.", "n_in": n, "n_pass": allp},
     {"gate": "Q08", "pass": l40 == n, "value": f"{l40:,} of {n:,} pool items have 40+ characters", "n_in": n, "n_pass": l40},
     *([{"gate": "Q09", "pass": tw == 0, "value": f"{tw:,} of {t1['n']:,} labelled items have a near-twin at word-trigram cosine 0.8 (t1_dupes.json; TF-IDF cosine, not MinHash); bar is none kept; the near-twins are still in the pool, not yet removed", "n_in": t1["n"], "n_pass": t1["n"] - tw}] if t1 else []),
     {"gate": "Q14", "pass": (len(labs) / (len(labs) + rej)) >= 0.95, "value": f"{len(labs):,} of {len(labs) + rej:,} label rows pass the schema ({100 * len(labs) / (len(labs) + rej):.2f}%); bar 95%", "n_in": len(labs) + rej, "n_pass": len(labs)},
     {"gate": "Q15", "pass": full == len(labs), "value": f"{full:,} of {len(labs):,} labels carry teacher, model, prompt version, date and text sha", "n_in": len(labs), "n_pass": full},
     {"gate": "Q17", "pass": ok30 >= 25, "value": f"{ok30} of 38 conditions have 30+ Haiku positives (bar 25 of 38); short: {', '.join(short) or 'none'}", "n_in": 38, "n_pass": ok30},
     {"gate": "Q18", "pass": spend <= 20, "value": f"Haiku labelling spend {spend:.2f} USD (summed spend.jsonl) against the T05 cap 20 USD"}]
sig_p = H0 / "runs/gates_auto_last.json"; last = json.load(open(sig_p)) if sig_p.exists() else {}; new = [m for m in M if last.get(m["gate"]) != [m.get("n_in"), m.get("n_pass"), m["pass"]]]
if new:
    subprocess.run(["node", "cp.mjs", "measure", "T8", "--who", "gates_auto", "--measures", json.dumps(new)], cwd=H0.parents[1] / ".ledger", capture_output=True); json.dump({m["gate"]: [m.get("n_in"), m.get("n_pass"), m["pass"]] for m in M}, open(sig_p, "w"))
print("recorded" if new else "no change", [m["gate"] for m in new])
