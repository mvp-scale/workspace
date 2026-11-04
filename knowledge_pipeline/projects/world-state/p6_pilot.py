#!/usr/bin/env python3
"""P6 pilot 1,000: 500 gate-flagged + 500 random from the training pool, labelled with the FROZEN guideline (ws-v2-frozen) by Haiku and Sonnet.
Waits for the P4 gate (runs/p4/gate_flagged_ids.txt). Writes runs/p6/yield.json and ledger notes. Cap $3 per model run; total expected about $1.5."""
import json, pathlib, random, subprocess, sys, threading, time, collections
HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parents[1] / "kit/live")); from heartbeat import beat, finish
J = lambda p: [json.loads(l) for l in open(p) if l.strip()]
PY, KIT, LED = str(HERE.parent / ".venv/bin/python"), HERE.parents[1] / "kit/teacher/claude_batch.py", HERE.parents[1] / ".ledger"
def note(task, text): subprocess.run(["node", "cp.mjs", "note", task, text, "--who", "p6_pilot"], cwd=LED, capture_output=True)
t0 = time.time(); flag_f = HERE / "runs/p4/gate_flagged_ids.txt"
beat("p6-pilot", pid=__import__("os").getpid(), where="[CPU]+[API]", task="T6", state="queued", progress="waiting for the P4 gate", cap=3.0, last="pilot 1,000: 500 flagged + 500 random")
while not flag_f.exists() and time.time() - t0 < 3300: time.sleep(20)
if not flag_f.exists(): finish("p6-pilot", "failed", last="gate did not finish in 55 min"); note("T6", "P6 pilot did NOT start: the P4 gate had not finished in 55 minutes."); sys.exit(1)
pool = {r["id"]: r for r in J(HERE / "data/pool_train.jsonl")}; flagged = [i for i in flag_f.read_text().split("\n") if i in pool]
rnd = random.Random(20261030); rnd.shuffle(flagged); f500 = flagged[:500]; rest = [i for i in pool if i not in set(f500)]; rnd.shuffle(rest); r500 = rest[:500]
(HERE / "data/pilot1000.jsonl").write_text("".join(json.dumps(pool[i]) + "\n" for i in f500 + r500)); strat = {i: "flagged" for i in f500} | {i: "random" for i in r500}
out = HERE / "runs/p6"; out.mkdir(exist_ok=True)
beat("p6-pilot", state="running", progress="labelling 1,000 with Haiku and Sonnet (frozen guideline)", last=f"gate flagged {len(flagged)} of {len(pool)}")
def run(fam): subprocess.run([PY, str(KIT), "--spec", str(HERE / f"specs/world_state_v2_frozen_{fam}.json"), "--items", str(HERE / "data/pilot1000.jsonl"), "--out", str(out / fam), "--key-file", "/workspace/secrets/vault.env", "--cap-usd", "6"], stdout=open(out / f"{fam}.log", "w"), stderr=subprocess.STDOUT)
th = [threading.Thread(target=run, args=(f,)) for f in ("haiku", "sonnet")]; [t.start() for t in th]; [t.join() for t in th]
L = {f: {r["item_id"]: r["label"] for r in J(out / f / "labels.jsonl")} for f in ("haiku", "sonnet")}
spend = {f: sum(r.get("usd", 0) for r in J(out / f / "spend.jsonl")) for f in L}; rej = {f: len(J(out / f / "rejects.jsonl")) if (out / f / "rejects.jsonl").exists() else 0 for f in L}
ids = lambda l: {c["condition"] for c in l["conditions"]}
res = {"flagged_by_gate": len(flagged), "pool": len(pool), "spend_usd": {k: round(v, 3) for k, v in spend.items()}, "rejects": rej, "labelled": {f: len(L[f]) for f in L}}
for s in ("flagged", "random"):
    both = [i for i in strat if strat[i] == s and i in L["haiku"] and i in L["sonnet"]]
    if not both: continue
    tp = sum(len(ids(L["haiku"][i]) & ids(L["sonnet"][i])) for i in both); a = sum(len(ids(L["haiku"][i])) for i in both); b = sum(len(ids(L["sonnet"][i])) for i in both)
    res[s] = {"items": len(both), "haiku_has_condition": round(sum(bool(L["haiku"][i]["conditions"]) for i in both) / len(both), 3), "sonnet_has_condition": round(sum(bool(L["sonnet"][i]["conditions"]) for i in both) / len(both), 3),
              "topic_same": round(sum(L["haiku"][i]["topic"] == L["sonnet"][i]["topic"] for i in both) / len(both), 3), "story_same": round(sum(L["haiku"][i]["story_type"] == L["sonnet"][i]["story_type"] for i in both) / len(both), 3),
              "condition_overlap": round(2 * tp / (a + b), 3) if a + b else None}
pos = {f: collections.Counter(c for l in L[f].values() for c in ids(l)) for f in L}
res["positives_per_condition_haiku"] = dict(pos["haiku"].most_common()); res["conditions_with_30_plus_haiku"] = sum(v >= 30 for v in pos["haiku"].values()); res["conditions_seen_haiku"] = len(pos["haiku"])
json.dump(res, open(out / "yield.json", "w"), indent=1)
note("T6", f"RESULT P6 pilot 1,000 (frozen guideline ws-v2-frozen; 500 gate-flagged + 500 random; runs/p6/yield.json): gate flagged {len(flagged)} of {len(pool)} ({len(flagged)/len(pool):.0%}). Spend Haiku ${spend['haiku']:.2f}, Sonnet ${spend['sonnet']:.2f}; rejects {rej}. Flagged stratum: {res.get('flagged')}. Random stratum: {res.get('random')}. Conditions with 30+ Haiku positives in this pilot: {res['conditions_with_30_plus_haiku']} of {res['conditions_seen_haiku']} seen.")
finish("p6-pilot", "done", last=f"pilot labelled; {res['conditions_with_30_plus_haiku']} conditions have 30+ examples", spent=round(sum(spend.values()), 2))
print(json.dumps(res, indent=1)[:3000])
