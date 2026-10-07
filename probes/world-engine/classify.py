"""Semantic sensor: reads one evidence item into typed yes/no readings with the local classifier (Winnow), then applies the fixed rules to get dial readings.
Rule changes since the 100-headline test, made after seeing results (exploratory): one present attribute is enough; 'announced' counts as an event; story must be recent; story focus (US or abroad) routes the entry level."""
import json, sys, datetime, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "/workspace/probes/persona")
import offline as O
from rules import load, load_opt
from world_model import GENRE, SCOPE
YES, ATTR_MIN = 0.65, 0.65
EXTRA = {"us_focus": "This story is mainly about the United States.", "foreign_focus": "This story is mainly about events in another country.", "recent": "This story reports a development from the last few days."}
def attributes():
    rows = [r for r in load_opt("dial_attributes") if r["attribute"] != "todo"] + load_opt("dial_attributes_extra"); idx = defaultdict(list)
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
def _country_rows():
    import csv, os
    return list(csv.DictReader(open(os.environ.get("WORLD_COUNTRIES", "/workspace/probes/world-engine/data/countries_world100.csv"))))
def countries(): return [(r["id"], r["name"]) for r in _country_rows()]
def region_text(region, rows, max_chars=300, top=12):
    """Option text for the region step: the region's name plus its member countries from the data, so the model does not place a country by geography alone (Mexico is Latin America here, Turkey is Europe & Central Asia).
    All members when the text stays under max_chars, else the `top` most populous. The option key stays the region label; no threshold is involved."""
    mem = sorted(((float(r["pop_m"] or 0), r["name"]) for r in rows if r["region"] == region), reverse=True); names = [n for _, n in mem]
    full = f"{region.strip()}: " + ", ".join(names)
    return full if len(full) <= max_chars else f"{region.strip()}: " + ", ".join(names[:top]) + ", and others"
def ask_country(ev, today=None):
    """Which country is the story mainly about? Returns (country id or 'global', probabilities). Same return as ever; ask_country_detailed adds the numbers behind it."""
    r = ask_country_detailed(ev, today); return r[0], r[1]
def ask_country_detailed(ev, today=None):
    """The server allows 2 to 64 options per question, so with many countries it asks which part of the world first, then which country in it.
    Returns (country id or 'global', probabilities, detail). detail: path 'flat' or 'region'; region_choice; global_p = the region step's GLOBAL probability (None on the flat path, where it is the 'global' option);
    other_here_p = the country step's own 'other_here' probability (None unless the country step ran); chose_global, chose_other_here."""
    today = today or datetime.date.today().isoformat(); st = f"News item (published {ev['published_at']}; today is {today}):\n{ev['title']}. {ev['description']}"; rows = _country_rows()
    if len(rows) <= 63 or "region" not in rows[0]:
        crit = {r["id"]: r["name"] for r in rows}; crit["global"] = "No single country in this list, or the whole world"
        a = O.call(st, {"c": {"type": "choice", "instructions": "Which country is this story mainly about?", "criteria": crit}})["c"]; pr = {k: round(float(v), 3) for k, v in a["probabilities"].items()}
        return a["choice"], pr, {"path": "flat", "region_choice": None, "global_p": pr.get("global"), "other_here_p": None, "chose_global": a["choice"] == "global", "chose_other_here": False}
    regions = sorted({r["region"] for r in rows}); crit = {g: region_text(g, rows) for g in regions}; crit["GLOBAL"] = "The whole world, or no single part of it"
    g = O.call(st, {"g": {"type": "choice", "instructions": "Which part of the world is this story mainly about?", "criteria": crit}})["g"]; pg = {k: float(v) for k, v in g["probabilities"].items()}
    det = {"path": "region", "region_choice": g["choice"], "global_p": round(pg["GLOBAL"], 3), "other_here_p": None, "chose_global": g["choice"] == "GLOBAL", "chose_other_here": False}
    if g["choice"] == "GLOBAL": return "global", {"global": round(pg["GLOBAL"], 3)}, det
    inr = {r["id"]: r["name"] for r in rows if r["region"] == g["choice"]}; inr["other_here"] = "A different country in this part of the world, or no single country"
    c = O.call(st, {"c": {"type": "choice", "instructions": "Which country is this story mainly about?", "criteria": inr}})["c"]; pc = {k: round(float(v) * pg[g["choice"]], 3) for k, v in c["probabilities"].items()}
    det["other_here_p"] = round(float(c["probabilities"].get("other_here", 0.0)), 3); det["chose_other_here"] = c["choice"] == "other_here"
    return ("global" if c["choice"] == "other_here" else c["choice"]), pc, det
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

# ---------- placement: what is this story ABOUT? (added 2026-10-05; see spec/ontology-domains.md) ----------
DOMAINS = load("domains"); TYPE_W = {t["type"]: t for t in load("type_weights")}
def place(ev, today=None, tag_choice=0.2, tag_yes=0.5):
    """Every story gets at least one domain. Forced choice over the closed list (always answers) plus one yes/no per domain (lets a story carry several)."""
    today = today or datetime.date.today().isoformat(); state = f"News item (published {ev['published_at']}; today is {today}):\n{ev['title']}. {ev['description']}"
    qs = {"c": {"type": "choice", "instructions": "Which area is this story mainly about?", "criteria": {d["id"]: d["definition"] for d in DOMAINS}}}
    qs.update({"y|" + d["id"]: {"type": "noul", "instructions": f"Is this story about {d['name']}? ({d['definition']})"} for d in DOMAINS if d["id"] != "other"})
    a = O.call(state, qs); pc = {k: float(v) for k, v in a["c"]["probabilities"].items()}; out = []
    for d in DOMAINS:
        py = float(a["y|" + d["id"]]["noul"]) if d["id"] != "other" else 0.0
        out.append({"id": d["id"], "name": d["name"], "p_choice": round(pc.get(d["id"], 0.0), 3), "p_yes": round(py, 3), "tagged": d["id"] != "other" and (pc.get(d["id"], 0.0) >= tag_choice or py >= tag_yes)})
    if not any(x["tagged"] for x in out): max(out, key=lambda x: x["p_choice"])["tagged"] = True          # never leave a story unplaced
    return sorted(out, key=lambda x: (not x["tagged"], -(x["p_choice"] + x["p_yes"])))
def type_weight(happened, announced, opinion, forecast):
    """A weight, not a wall: how much a story of this type counts. 'fact' keeps the old full weight; refused types now enter at a reduced weight."""
    if (happened >= .5 or announced >= .5) and opinion < .5 and forecast < .5: t = "fact"
    elif forecast >= .5: t = "forecast"
    elif opinion >= .5: t = "opinion"
    else: t = "unclear"
    return float(TYPE_W[t]["weight"]), t, TYPE_W[t]["why"]
def misses(P, k=3):
    """The closest dial checks that did NOT clear the bar, so a non-result can always be explained."""
    rows = []
    for (d, dirn), lst in ATTRS.items():
        for i, r in enumerate(lst):
            a, b = P[f"a|{d}|{dirn}|{i}|0"], P[f"a|{d}|{dirn}|{i}|1"]; m = (a + b) / 2
            if m < ATTR_MIN: rows.append({"dial": d, "direction": dirn, "attribute": r["attribute"], "mean": round(m, 3), "p1": round(a, 3), "p2": round(b, 3), "question": r["question_1"], "bar": ATTR_MIN})
    return sorted(rows, key=lambda x: -x["mean"])[:k]

# ---------- expected impact: what the story is likely to DO if it plays out as reported (added 2026-10-05) ----------
PHRASES = {r["dial_id"]: r for r in load_opt("impact_phrases")}; MODES = {m["mode"]: m for m in load("impact_modes")}; LEVELS = load("impact_levels")
EXPECT_MIN, EXPECT_TOP = 0.5, 4
def allowed_dials(placement):
    """Conditions a story may be expected to move: those plausible for the domains it was placed in (our mapping in domains.csv; guess)."""
    rows = {d["id"]: d for d in DOMAINS}; out = set()
    for t in placement:
        if t["tagged"]: out |= {v for v in rows[t["id"]].get("dials", "").split("; ") if v}
    return out
def expected(ev, reported_dials, allowed=None, today=None, min_p=None, min_net=0.05):
    """For every condition the story did not report directly, ask whether it is likely to push it up or down if it plays out as reported.
    Net direction = P(up) - P(down), so a story that could go either way gets a small net effect instead of none. Pending items (a hearing, a plan) are weighted lower than items already in effect."""
    today = today or datetime.date.today().isoformat(); state = f"News item (published {ev['published_at']}; today is {today}):\n{ev['title']}. {ev['description']}"; qs = {}
    for d, r in PHRASES.items():
        if d in reported_dials or (allowed is not None and d not in allowed): continue
        qs[f"e|{d}|up"] = f"Suppose the main development in this story fully plays out (the plan goes ahead, the claim succeeds, the invention works, the event unfolds as described). Is it likely that {r['up']}? Answer yes only if there is a real reason to expect it."
        qs[f"e|{d}|down"] = f"Suppose the main development in this story fully plays out (the plan goes ahead, the claim succeeds, the invention works, the event unfolds as described). Is it likely that {r['down']}? Answer yes only if there is a real reason to expect it."
    qs["done"] = "The consequences this story describes or implies are already in effect. They are NOT merely planned, announced for the future, argued in court, proposed, under review or only possible."
    names = list(qs); P = {}
    for j in range(0, len(names), 20):
        a = O.call(state, {k: {"type": "noul", "instructions": qs[k]} for k in names[j:j + 20]}); P.update({k: a[k]["noul"] for k in a})
    done = P["done"]; mode = "expected_in_effect" if done >= .5 else "expected_pending"; out = []
    for d in PHRASES:
        if d in reported_dials or f"e|{d}|up" not in P: continue
        pu, pd = P[f"e|{d}|up"], P[f"e|{d}|down"]; net = pu - pd
        if max(pu, pd) >= (EXPECT_MIN if min_p is None else min_p) and abs(net) > min_net:
            out.append({"dial": d, "direction": "up" if net > 0 else "down", "strength": round(abs(net), 3), "p_up": round(pu, 3), "p_down": round(pd, 3), "p_done": round(done, 3), "mode": mode, "basis": "expected", "mode_weight": float(MODES[mode]["weight"]), "attributes": ["expected impact"]})
    return sorted(out, key=lambda x: -x["strength"])[:EXPECT_TOP]
def severity(ev, dials, today=None):
    """How LARGE would each change be? (The yes/no questions say how sure the model is that a condition moves; this is the separate question of by how much.) One typed choice per condition over the
    levels in rules/impact_levels.csv; the size multiplier is the probability-weighted average of the levels' multipliers, so it varies smoothly. dials: {dial id: 'up' or 'down'}."""
    today = today or datetime.date.today().isoformat(); state = f"News item (published {ev['published_at']}; today is {today}):\n{ev['title']}. {ev['description']}"
    crit = {lv["id"]: lv["definition"] for lv in LEVELS}; mult = {lv["id"]: float(lv["multiplier"]) for lv in LEVELS}
    qs = {d: {"type": "choice", "instructions": f"Suppose the main development in this story plays out as described. How large would the change be in this: {PHRASES[d][dr]}? Judge it for ordinary people worldwide.", "criteria": crit} for d, dr in dials.items()}
    if not qs: return {}
    a = O.call(state, qs); out = {}
    for d in qs:
        pr = {k: float(v) for k, v in a[d]["probabilities"].items()}; out[d] = {"level": a[d]["choice"], "mult": sum(pr.get(k, 0.0) * m for k, m in mult.items()) / (sum(pr.values()) or 1.0), "p": {k: round(v, 3) for k, v in pr.items()}}
    return out

# ---------- So-what story questions (added 2026-10-06; see spec/so-what-contract.md) ----------
def ask_sowhat(jobs):
    """jobs: [(name, state, question)], each one typed choice question in its own short call (the two states differ), run in parallel.
    Same call style as classify_kind: O.call(state, {name: question})[name]. Returns {name: answer} with answer['choice'] and answer['probabilities']."""
    with ThreadPoolExecutor(max(1, len(jobs))) as ex:
        futs = {n: ex.submit(O.call, st, {n: q}) for n, st, q in jobs}
        return {n: f.result()[n] for n, f in futs.items()}
