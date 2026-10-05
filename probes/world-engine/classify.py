"""Semantic sensor: reads one evidence item into typed yes/no readings with the local classifier (Winnow), then applies the fixed rules to get dial readings.
Rule changes since the 100-headline test, made after seeing results (exploratory): one present attribute is enough; 'announced' counts as an event; story must be recent; story focus (US or abroad) routes the entry level."""
import json, sys, datetime, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "/workspace/probes/persona")
import offline as O
from rules import load
from world_model import GENRE, SCOPE
YES, ATTR_MIN = 0.65, 0.65
EXTRA = {"us_focus": "This story is mainly about the United States.", "foreign_focus": "This story is mainly about events in another country.", "recent": "This story reports a development from the last few days."}
def attributes():
    rows = [r for r in load("dial_attributes") if r["attribute"] != "todo"] + load("dial_attributes_extra"); idx = defaultdict(list)
    for r in rows: idx[(r["dial_id"], r["direction"])].append(r)
    return idx
ATTRS = attributes()
def questions():
    q = {}
    for (d, dirn), lst in ATTRS.items():
        for ai, r in enumerate(lst):
            q[f"a|{d}|{dirn}|{ai}|0"] = r["question_1"]; q[f"a|{d}|{dirn}|{ai}|1"] = r["question_2"]
    q.update({f"g|{k}": v for k, v in GENRE.items()}); q.update({f"s|{k}": v for k, v in SCOPE.items()}); q.update({f"x|{k}": v for k, v in EXTRA.items()}); return q
QS = questions()
def ask(ev, today=None):
    today = today or datetime.date.today().isoformat(); names = list(QS); P = {}
    state = f"News item (published {ev['published_at']}; today is {today}):\n{ev['title']}. {ev['description']}"
    for j in range(0, len(names), 20):
        a = O.call(state, {k: {"type": "noul", "instructions": QS[k]} for k in names[j:j + 20]}); P.update({k: a[k]["noul"] for k in a})
    return P
def countries():
    import csv
    return [(r["id"], r["name"]) for r in csv.DictReader(open("/workspace/probes/world-engine/data/countries.csv"))]
def ask_country(ev, today=None):
    """Typed choice question: which country is the story mainly about? (one of the simulated countries, or 'global' for none or all)."""
    today = today or datetime.date.today().isoformat(); crit = {i: n for i, n in countries()}; crit["global"] = "No single country in this list, or the whole world"
    a = O.call(f"News item (published {ev['published_at']}; today is {today}):\n{ev['title']}. {ev['description']}", {"c": {"type": "choice", "instructions": "Which country is this story mainly about?", "criteria": crit}})["c"]
    return a["choice"], {k: round(float(v), 3) for k, v in a["probabilities"].items()}
def read(P):
    g = {k: P[f"g|{k}"] for k in GENRE}; gate = (g["happened"] >= .5 or g["announced"] >= .5) and g["opinion"] < .5 and P["x|recent"] >= .3
    entry = "COUNTRY:usa" if P["x|us_focus"] >= .5 else ("WORLD:world" if P["x|foreign_focus"] >= .5 else "COUNTRY:usa")
    readings = []
    for d in sorted({k[0] for k in ATTRS}):
        present = {}
        for dirn in ("up", "down"):
            ps = [(r["attribute"], (P[f"a|{d}|{dirn}|{i}|0"] + P[f"a|{d}|{dirn}|{i}|1"]) / 2) for i, r in enumerate(ATTRS.get((d, dirn), []))]
            ps = [(n, m) for n, m in ps if m >= ATTR_MIN]
            if ps: present[dirn] = ps
        if len(present) == 1:
            dirn, ps = next(iter(present.items())); strength = max(m for _, m in ps)
            readings.append({"dial": d, "direction": dirn, "strength": round(strength, 3), "attributes": [n for n, _ in ps], "amount": (0.10 if dirn == "up" else -0.10) * strength * P["x|recent"]})
        elif len(present) == 2: readings.append({"dial": d, "direction": "conflict", "strength": 0.0, "attributes": [n for v in present.values() for n, _ in v], "amount": 0.0})
    return {"gate_ok": bool(gate), "gate": {"happened": round(g["happened"], 2), "announced": round(g["announced"], 2), "opinion": round(g["opinion"], 2), "recent": round(P["x|recent"], 2)}, "entry": entry, "readings": readings}
def run(evidence, workers=2):
    t0 = time.time()
    with ThreadPoolExecutor(workers) as ex: Ps = list(ex.map(ask, evidence))
    with ThreadPoolExecutor(workers) as ex: cs = list(ex.map(ask_country, evidence))
    out = [{"evidence_id": e["evidence_id"], "title": e["title"], "p": P, "country": c[0], "country_p": c[1], **read(P)} for e, P, c in zip(evidence, Ps, cs)]
    return out, time.time() - t0
if __name__ == "__main__":
    ev = [json.loads(l) for l in open("/workspace/probes/world-engine/ledger/evidence.jsonl")]
    out, dt = run(ev); open("/workspace/probes/world-engine/ledger/measurements.jsonl", "w").write("\n".join(json.dumps(o) for o in out) + "\n")
    print(f"{len(out)} items classified in {dt:.0f}s ({dt/len(out):.1f}s each, {len(QS)} questions per item)")
