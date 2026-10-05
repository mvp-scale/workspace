"""End-to-end demo: RSS evidence -> local classifier readings -> events (duplicates merged) -> world state across levels -> decisions -> audience opinion on new items -> scenario branch.
    /workspace/kev/.venv/bin/python demo.py [--n 100000]"""
import sys, json, time, copy, datetime, email.utils
import numpy as np
import engine as E, classify as C
L = "/workspace/probes/world-engine/ledger"; N = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 100_000
ev = {e["evidence_id"]: e for e in map(json.loads, open(f"{L}/evidence.jsonl"))}; ms = [json.loads(l) for l in open(f"{L}/measurements.jsonl")]; cl = json.load(open(f"{L}/clusters.json"))
# ---- events: one per cluster; per dial the strongest reading among its usable items
groups = {}
for m in ms: groups.setdefault(cl[m["evidence_id"]], []).append(m)
events = []
for cid, members in groups.items():
    use = [m for m in members if m["gate_ok"]]
    if not use: continue
    best = {}
    for m in use:
        for r in m["readings"]:
            if r["direction"] != "conflict" and (r["dial"] not in best or abs(r["amount"]) > abs(best[r["dial"]]["amount"])): best[r["dial"]] = r
    events.append({"event": cid, "title": use[0]["title"], "entry": use[0]["entry"], "evidence_count": len(use), "readings": list(best.values()), "published": email.utils.parsedate_to_datetime(ev[use[0]["evidence_id"]]["published_at"])})
events.sort(key=lambda e: e["published"])
def feed(world, events, start=0):
    for i, e in enumerate(events):
        for r in e["readings"]: world.add(start + i, e["entry"], r["dial"], r["amount"], e["event"])
        world.add(start + i, "COUNTRY:usa", "news_overload", 0.01 * e["evidence_count"], e["event"])
    return start + len(events)
def build(seed=0, noise=True):
    w = E.World(seed, noise); end = feed(w, events); w.run(end + 20); return w
print(f"{sum(len(g) for g in groups.values())} evidence items -> {len(events)} usable events (duplicates merged, opinion/forecast/stale items gated)")
for e in events:
    mv = ", ".join(f"{r['dial']} {'+' if r['direction']=='up' else '-'}{abs(r['amount']):.3f}" for r in e["readings"]) or "no dial moved"
    print(f"  {e['event']} x{e['evidence_count']} {e['entry'][:7]:7s} {e['title'][:62]:62s} | {mv}")
w = build(); print("\nSTATE after all events and 20 settling ticks (largest dial deviations per node; 0 = neutral):")
for n in E.NODES:
    d = w.delta[n]; top = np.argsort(-np.abs(d))[:3]; print(f"  {n:22s}", ", ".join(f"{E.DIALS[i]} {d[i]:+.3f}" for i in top if abs(d[i]) > 1e-4) or "neutral")
big = max((l for l in w.log if l["node"].startswith("COUNTRY")), key=lambda l: abs(l["amount"])); print(f"\nTRACE of the largest country-level change ({big['event']}, {big['dial']}):")
for l in sorted([l for l in w.log if l["event"] == big["event"] and l["dial"] == big["dial"]], key=lambda l: (l["tick"], l["node"])): print(f"  tick {l['tick']:3d}  {l['node']:22s} {l['amount']:+.4f}  via {' > '.join(p.split(':')[1] for p in l['path'])}")
t0 = time.time(); pop = E.Population(N); print(f"\nPOPULATION: {N:,} people built in {time.time()-t0:.1f}s")
t0 = time.time(); eff = pop.effective(w); pr = pop.propensity(eff); dt = time.time() - t0; base = pop.propensity(pop.base); print(f"effective state + 8 decisions for all {N:,} people: {dt*1000:.0f} ms")
G = pop.groups(); STAGE = lambda x: "calm" if abs(x) < .005 else ("building" if abs(x) < .02 else "imminent")
print("\nDECISIONS: change in propensity vs a neutral world (stage: <0.005 calm, <0.02 building, else imminent; sign = toward/away):")
print(f"  {'':14s}" + "".join(f"{s.split(':')[1]:>14s}" for s in ("COUNTRY:usa", "SEGMENT:income_low", "SEGMENT:income_high", "SEGMENT:age_young", "SEGMENT:age_senior")))
for j, d in enumerate(E.DECS):
    row = ""
    for s in ("COUNTRY:usa", "SEGMENT:income_low", "SEGMENT:income_high", "SEGMENT:age_young", "SEGMENT:age_senior"):
        x = float((pr[G[s], j] - base[G[s], j]).mean()); row += f"{x:+.4f} {STAGE(x)[:5]:>6s}  "
    print(f"  {d:14s}{row}")
# ---- audience opinion
aud = E.Audience(); print(f"\nAUDIENCE CLASSIFIER fitted on {aud.n_ideas} ideas x 400 people (model answers as truth).")
ITEMS = {"Nightfall (late-night membership, 21 to 30, big cities, app, $25 a month)": E.O.PRODUCTS["nightfall"], "Gardenway (free paper newsletter for retired rural people)": E.O.PRODUCTS["gardenway"],
         "Neighbour Loop ($12 a month, app + ID photo, anyone on the street)": E.O.PRODUCTS["nl_p1a1s1"]}
for name, text in ITEMS.items():
    iv = aud.demands(text); op, p = aud.opinion(pop, eff, iv); op0, _ = aud.opinion(pop, pop.base, iv)
    print(f"\n  OPINION on {name}")
    print("   ", " | ".join(f"{n.split(':')[1]} {v['noul']:.2f} ({v['share_yes']:.0%} yes)" for n, v in op.items() if n in ("COUNTRY:usa", "SEGMENT:income_low", "SEGMENT:income_high", "SEGMENT:age_young", "SEGMENT:age_senior")))
    print(f"    regions: " + " | ".join(f"{n.split(':')[1]} {op[n]['noul']:.2f}" for n in op if n.startswith("REGION")) + f"   (neutral-world US value {op0['COUNTRY:usa']['noul']:.3f} vs now {op['COUNTRY:usa']['noul']:.3f})")
    drivers = []
    for d in E.DIALS:
        if abs(w.delta["COUNTRY:usa"][E.DIALS.index(d)]) > 1e-4:
            p2 = aud.probability(pop, pop.effective(w, zero=(d,)), iv); drivers.append((float(p.mean() - p2.mean()), d))
    print("    which dials moved this opinion (current minus that dial reset):", ", ".join(f"{d} {x:+.4f}" for x, d in sorted(drivers, key=lambda t: -abs(t[0]))[:3]) or "none")
# ---- scenario branch
print("\nSCENARIO (branch, observed state untouched): a hypothetical headline is read by the local classifier and injected")
hypo = {"evidence_id": "hypo", "published_at": email.utils.format_datetime(datetime.datetime.now(datetime.timezone.utc)), "title": "Gasoline and diesel prices jump 25% as refinery outages spread across the country", "description": "Drivers and households face sharply higher fuel bills ahead of winter."}
P = C.ask(hypo); r = C.read(P); print("  classifier:", "event" if r["gate_ok"] else "gated", "| entry", r["entry"], "|", ", ".join(f"{x['dial']} {x['direction']} {x['strength']:.2f}" for x in r["readings"]) or "no dial moved")
w2 = copy.deepcopy(w); start = w2.tick
for x in r["readings"]:
    if x["direction"] != "conflict": w2.add(start, r["entry"], x["dial"], x["amount"], "scenario-1")
w2.run(10); pr2 = pop.propensity(pop.effective(w2))
print(f"  {'':14s}" + "".join(f"{s.split(':')[1]:>14s}" for s in ("COUNTRY:usa", "SEGMENT:income_low", "SEGMENT:income_high", "SEGMENT:age_young", "SEGMENT:age_senior")) + "   (scenario minus current state)")
for j, d in enumerate(E.DECS):
    row = ""
    for s in ("COUNTRY:usa", "SEGMENT:income_low", "SEGMENT:income_high", "SEGMENT:age_young", "SEGMENT:age_senior"):
        x = float((pr2[G[s], j] - pr[G[s], j]).mean()); row += f"{x:+.4f} {STAGE(x)[:5]:>6s}  "
    print(f"  {d:14s}{row}")
print("  observed world digest unchanged:", w.digest() == build().digest())
# ---- noise, repeatability, ensembles
print("\nCHANNEL NOISE and REPEATABILITY")
a, b, c = build(7), build(7), build(8); print(f"  same seed same state: {a.digest()==b.digest()} | different seed differs: {a.digest()!=c.digest()} | noise off vs on differ: {build(0, False).digest()!=build(0, True).digest()}")
sub = E.DECS.index("subscribe"); vals = []
for s in range(20):
    ws = build(s); vals.append(float((pop.propensity(pop.effective(ws))[G["SEGMENT:income_low"], sub] - base[G["SEGMENT:income_low"], sub]).mean()))
nz = float((pop.propensity(pop.effective(build(0, False)))[G["SEGMENT:income_low"], sub] - base[G["SEGMENT:income_low"], sub]).mean())
print(f"  'subscribe' propensity change for the low-income segment over 20 noise seeds: min {min(vals):+.4f}, mean {np.mean(vals):+.4f}, max {max(vals):+.4f} (no noise: {nz:+.4f})")
