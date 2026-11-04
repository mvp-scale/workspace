#!/usr/bin/env python3
"""P1 gold-Q by model jury (owner decision 2: models stand in for people until before P12; decision 9 stage 2: Jev sees headline+description only).
50 items from the frozen 300: 25 random + 25 that local Clef flags as 'something is changing'. Raters: Haiku, Sonnet (full spec, current guideline), Clef, Jev (typed choice questions).
Writes gold/q50_jury.jsonl and runs/p1/jury_agreement.json. PROVISIONAL: the pass line is 0.8 x pairwise agreement, marked provisional."""
import json, pathlib, random, shutil, subprocess, sys, itertools, glob
HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, "/workspace/demo"); import backends
ns = {"__file__": str(HERE / "clef_probe.py")}; exec(open(HERE / "clef_probe.py").read().split("items = {")[0], ns); Q = ns["Q"]
J = lambda p: [json.loads(l) for l in open(p) if l.strip()]
out = HERE / "runs" / "p1"; out.mkdir(parents=True, exist_ok=True); (HERE / "gold").mkdir(exist_ok=True)
pilot = J(HERE / "data/pilot300.jsonl"); text = {r["id"]: r["text"] for r in pilot}
sel_f = out / "q50_items.jsonl"
if not sel_f.exists():
    flag = {}
    for r in pilot: flag[r["id"]] = backends.ask("clef-flash-q4km", "News item:\n" + r["text"], {"change": Q["change"]}, timeout=60)["change"]["choice"] == "yes"
    rnd = random.Random(20261030); allids = [r["id"] for r in pilot]; rnd.shuffle(allids)
    rand25 = allids[:25]; pos = [i for i in allids[25:] if flag[i]][:25]; rest = [i for i in allids[25:] if i not in pos]
    pick = rand25 + pos + rest[:25 - len(pos)]
    sel_f.write_text("".join(json.dumps({"id": i, "text": text[i], "date": next(r["date"] for r in pilot if r["id"] == i)}) + "\n" for i in pick))
    print(f"selected {len(pick)} items: 25 random + {len(pos)} Clef-flagged (+{25-len(pos)} filler)")
items = J(sel_f)
latest = max(glob.glob(str(HERE / "specs/waves/w*_haiku.json")), key=lambda p: int(pathlib.Path(p).stem.split("_")[0][1:]))
for fam in ("haiku", "sonnet"):
    spec = pathlib.Path(latest.replace("haiku", fam)); dst = HERE / f"specs/gold_q_{fam}.json"; shutil.copy(spec, dst)
    if not (out / fam / "labels.jsonl").exists():
        subprocess.run([str(HERE.parent / ".venv/bin/python"), str(HERE.parents[1] / "kit/teacher/claude_batch.py"), "--spec", str(dst), "--items", str(sel_f), "--out", str(out / fam), "--key-file", "/workspace/secrets/vault.env", "--sync", "--limit", "50", "--cap-usd", "3"], check=False)
R = {i["id"]: {} for i in items}
for fam in ("haiku", "sonnet"):
    for r in J(out / fam / "labels.jsonl"): L = r["label"]; R[r["item_id"]][fam] = {"topic": L["topic"], "story": L["story_type"], "change": bool(L["conditions"]), "conditions": [c["condition"] for c in L["conditions"]]}
for bid, name in (("clef-flash-q4km", "clef"), ("jev", "jev")):
    for i in items:
        a = {}
        for k in Q: a.update(backends.ask(bid, "News item:\n" + i["text"], {k: Q[k]}, timeout=90))
        R[i["id"]][name] = {"topic": a["topic"]["choice"], "story": a["story"]["choice"], "change": a["change"]["choice"] == "yes", "p_topic": max(a["topic"]["probabilities"].values())}
with open(HERE / "gold/q50_jury.jsonl", "w") as f:
    for i in items: f.write(json.dumps({"id": i["id"], "text": i["text"], "raters": R[i["id"]]}) + "\n")
raters = ["haiku", "sonnet", "clef", "jev"]; res = {}
for q in ("topic", "story", "change"):
    res[q] = {f"{a}|{b}": round(sum(R[i["id"]].get(a, {}).get(q) == R[i["id"]].get(b, {}).get(q) for i in items) / len(items), 3) for a, b in itertools.combinations(raters, 2)}
    v = list(res[q].values()); res[q]["mean_pairwise"] = round(sum(v) / len(v), 3); res[q]["provisional_gate_0.8x"] = round(0.8 * res[q]["mean_pairwise"], 3)
json.dump(res, open(out / "jury_agreement.json", "w"), indent=1)
for q, d in res.items(): print(q, d)
