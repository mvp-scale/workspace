"""One coverage table for the whole ontology from every battery's eval file (data/mm3-train/eval-*.json).
Per condition: its best atom (highest teacher self-agreement), that atom's CPU F1 (potion, held-out), positives, and a tier:
  CPU     teacher self-agreement >= 0.75 and CPU F1 >= 0.6          -> can run on CPU now (re-check against the 0.85 bar per atom)
  DATA    teacher self-agreement >= 0.6, CPU F1 below 0.6 or unmeasured -> the atom is clear; the student needs more positives
  WORDING teacher self-agreement < 0.6                               -> reword the atom (the teacher does not agree with itself)
The first battery's four concrete conditions use states~concrete as their self-agreement. Writes data/mm3-train/coverage.json and .md."""
import json, glob, csv
D = "/workspace/data/mm3-train"; names = {r["id"]: r["name"] for r in csv.DictReader(open("/workspace/probes/persona/rules_v2/dials.csv"))}
best = {}
def offer(cond, atom, teacher, cpu, pos, src):
    if teacher is None: return
    if cond not in best or teacher > best[cond]["teacher"]: best[cond] = {"atom": atom, "teacher": teacher, "cpu": cpu, "positives": pos, "battery": src}
for f in sorted(glob.glob(f"{D}/eval-evidence-v*.json")):
    e = json.load(open(f)); B = json.load(open(f"/workspace/newsreader/bitmob/batteries/{e['battery']}.json"))
    cond_of = {c["atom"]: c["condition"] for c in B["concerns"]}
    for atom, a in e["atoms"].items(): offer(cond_of[atom], atom, a["teacher_self_f1"], a["cpu_f1"], a["both_yes"], e["battery"])
first_self = {"civil_unrest|up": 0.85, "war_terror|up": 0.80, "crime|up": 0.66, "cyber_insecurity|up": 0.64}     # first battery, 880 stories (NIGHT.md)
first_cpu = json.load(open(f"{D}/results-atoms.json"))["A potion"]["atoms"]
for c, t in first_self.items(): offer(c, c + " (states+concrete)", t, first_cpu.get(c), None, "first")
rows = []
for cond, b in best.items():
    tier = "CPU" if b["teacher"] >= .75 and (b["cpu"] or 0) >= .6 else "DATA" if b["teacher"] >= .6 else "WORDING"
    rows.append({"condition": cond, "name": names.get(cond.split("|")[0], cond), **b, "tier": tier})
order = {"CPU": 0, "DATA": 1, "WORDING": 2}; rows.sort(key=lambda r: (order[r["tier"]], -r["teacher"]))
missing = sorted(set(names) - {r["condition"].split("|")[0] for r in rows})
json.dump({"rows": rows, "not_covered": missing}, open(f"{D}/coverage.json", "w"), indent=1)
L = ["| Tier | Condition | Best atom | Clef agrees with itself | CPU F1 | Positives |", "|---|---|---|---|---|---|"]
L += [f"| {r['tier']} | {r['name']} ({r['condition'].split('|')[1]}) | `{r['atom']}` | {r['teacher']:.2f} | {'-' if r['cpu'] is None else format(r['cpu'], '.2f')} | {r['positives'] if r['positives'] is not None else '-'} |" for r in rows]
L.append(f"\nNot covered: {', '.join(names[m] for m in missing) or 'none'}.")
open(f"{D}/coverage.md", "w").write("\n".join(L) + "\n"); print("\n".join(L))
from collections import Counter; print(Counter(r["tier"] for r in rows))
