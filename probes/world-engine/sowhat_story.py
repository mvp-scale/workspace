"""So-what, backend half: the story-level beats added to an event /request as `impact.story` (spec/so-what-contract.md, so-what-ontology.md).
Pure functions: numbers from the engine response plus two typed classifier answers (frame, trigger). Every phrase used in a question comes from the active rules dir
(sowhat_frames.csv probe statements, impact_phrases.csv, decision_phrases.csv); nothing is written here. The classifier call is injected (`ask`), so tests run offline."""
import sys, time, datetime, math
sys.path.insert(0, "/workspace/probes/persona")
VERSION = 1; MIN_MOVE = 0.25; CLOSE = 0.2; MAX_TRIGGER_READINGS = 6
SENSE_NEEDED = {"squeeze": "not_up", "relief": "not_down", "scare": "not_up", "blow": "not_up", "freeze": "not_up", "boost": "not_down"}      # ontology 1.7; the rest need nothing
MODAL = {"forecast": "would", "opinion": "could", "unclear": "may", "announced": "will", "pending": ""}      # pending = the event happened, only its effects are not felt yet: plain present for the event
FRAME_Q = "Which statement best describes the effect of this story on ordinary people?"; TRIGGER_Q = "Which of these changes is this story mainly about?"
def f2(x): return f"{x:.2f}"
def num(x): return str(round(float(x), 3))
def peak(v): return max(v, key=abs)          # largest |change| over Now, Next, Later, sign kept (first wins a tie)
def row_peaks(places, row): return {d: peak(v) for d, v in places.get(row, {}).items()}
def max_abs(places, row): return max([abs(x) for x in row_peaks(places, row).values()] + [0.0])
def story_state(text, today): return f"News item (published {today}; today is {today}):\n{text}. "          # same shape as classify.ask: title, description (empty for a typed request)
def sorted_readings(readings): return sorted(readings, key=lambda x: -abs(x["amount"]))
def moves_line(readings, places, entry, phr, dphr, counted):
    """Q1's extra line: top two readings (impact_phrases wording) and top two decisions at the entry row (decision_phrases wording, |peak| >= 0.25)."""
    parts = []
    if counted:
        parts += [phr[x["dial"]][x["direction"]] for x in sorted_readings(readings)[:2] if x["dial"] in phr]
        pk = sorted(row_peaks(places, entry).items(), key=lambda x: -abs(x[1]))
        parts += [f"people {dphr[d]['down' if v < 0 else 'up']}" for d, v in pk if abs(v) >= MIN_MOVE and d in dphr][:2]
    return parts, ("What our world model found, strongest first: " + "; ".join(parts) + "." if parts else "Our world model found no change.")
def certainty(ident):
    """Kind from the GATE (ontology 1.2): opinion >= 0.9 -> opinion; happened < 0.5 (not yet done) -> forecast when forecast > announced, else announced; happened >= 0.5 -> happened (pending when every reading is expected_pending).
    weight.type only says how much to count the story. Same order in sowhat.js deriveStory."""
    g = ident.get("gate", {}); w = ident.get("weight", {}); wtype = w.get("type", "unclear"); rd = ident.get("readings", []); gv = lambda k: g.get(k) or 0
    if not ident.get("counted"): kind = "no_impact"
    elif gv("opinion") >= 0.9: kind = "opinion"
    elif gv("happened") < 0.5: kind = "forecast" if gv("forecast") > gv("announced") else "announced"
    else: kind = "pending" if rd and all(x.get("mode") == "expected_pending" for x in rd) else "happened"
    gate = {k: g.get(k) for k in ("happened", "announced", "opinion", "forecast", "recent")}
    trace = f"weight {wtype} {num(w.get('value', 0))}; gate happened {num(g.get('happened', 0))}, announced {num(g.get('announced', 0))}, opinion {num(g.get('opinion', 0))}, forecast {num(g.get('forecast', 0))}"
    return {"kind": kind, "modal": MODAL.get(kind, ""), "weight_type": wtype, "weight": w.get("value"), "gate": gate, "trace": trace}
def place_kind(ident, entry):
    """Where the story is: 'country' (entry is a country row), 'world' (ask_country answered the whole world: country_p is its probability) or 'unresolved' (ask_country named a part of the world but no country in it: country 'global' with country_p None).
    Only 'country' lets the so-what name a place (ontology 1.8)."""
    if entry.startswith("COUNTRY:"): return "country"
    return "unresolved" if ident.get("country") == "global" and ident.get("country_p") is None and "country" in ident else "world"
def sense(places, row):
    pk = row_peaks(places, row); v = sum(pk.get(d, 0.0) for d in ("spend", "buy_new", "subscribe", "travel"))
    return ("down" if v <= -MIN_MOVE else "up" if v >= MIN_MOVE else "flat"), v
def passes(frame, sn): need = SENSE_NEEDED.get(frame); return need is None or (need == "not_up" and sn != "up") or (need == "not_down" and sn != "down")
def guard(probs, places, row, label):
    """Coherence guard (ontology 1.7): the top frame must not contradict what people do. Runner-up if it passes, else plain. Run here for the response row (world, or the entry row of a local story); the browser re-runs it per focus."""
    order = sorted(probs.items(), key=lambda x: (-x[1], x[0])); top, ru = order[0][0], order[1][0]; sn, v = sense(places, row)
    g = {"row": row, "sense": sn, "sense_pts": round(v, 2), "fired": False, "from": top, "to": top}
    if passes(top, sn): return top, g
    g["fired"] = True; g["to"] = ru if passes(ru, sn) else "plain"
    g["trace"] = f"{top} needs {SENSE_NEEDED[top].replace('_', ' ')} but sense is {sn} ({v:+.2f}); {'runner-up ' + ru if g['to'] == ru else 'plain'}"
    return g["to"], g
def build_story(text, ident, impact, frames, phr, dphr, ask=None, today=None):
    """ident: the `identify` block, impact: the `impact` block (places, significance), frames: sowhat_frames rows, phr: {dial: {up, down}}, dphr: {decision: {up, down}}.
    ask(jobs) -> {name: answer}, jobs = [(name, state, question)]. Returns the `story` dict of the contract."""
    if ask is None:
        import classify as C; ask = C.ask_sowhat
    today = today or datetime.date.today().isoformat(); counted = bool(ident.get("counted")); readings = ident.get("readings", []) if counted else []
    places = impact["places"]; entry = ident.get("entry", "WORLD:world"); state = story_state(text, today)
    parts, line = moves_line(ident.get("readings", []), places, entry, phr, dphr, counted)
    fcrit = {f["id"]: f["probe_statement"] for f in frames}; jobs = [("sowhat_frame", state + "\n" + line, {"type": "choice", "instructions": FRAME_Q, "criteria": fcrit})]
    usable = [x for x in readings if x.get("direction") in ("up", "down") and (phr.get(x["dial"]) or {}).get(x["direction"])]       # a dial without an impact_phrases row cannot be offered (and cannot crash)
    top_r = (sorted_readings([x for x in usable if x.get("basis") != "expected"]) + sorted_readings([x for x in usable if x.get("basis") == "expected"]))[:MAX_TRIGGER_READINGS]; asked = len(top_r) >= 2      # reported readings first, expected ones fill the rest
    if asked: jobs.append(("sowhat_trigger", state, {"type": "choice", "instructions": TRIGGER_Q, "criteria": {x["dial"]: phr[x["dial"]][x["direction"]] for x in top_r}}))
    t0 = time.time(); ans = ask(jobs); ms = round((time.time() - t0) * 1000)
    fp = {k: float(ans["sowhat_frame"]["probabilities"].get(k, 0.0)) for k in fcrit}; order = sorted(fp.items(), key=lambda x: (-x[1], x[0]))
    world_max, entry_max = max_abs(places, "WORLD:world"), max_abs(places, entry)
    local = entry.startswith("COUNTRY:") and world_max < MIN_MOVE and entry_max >= MIN_MOVE
    row = entry if local else "WORLD:world"; fid, g = guard(fp, places, row, row)
    ftrace = f"frame choice: {order[0][0]} {f2(order[0][1])}, runner-up {order[1][0]} {f2(order[1][1])}" + (f"; guard: {g['trace']}" if g["fired"] else "")
    frame = {"id": fid, "p": round(fp[fid], 3) if fid in fp else None, "raw_id": order[0][0], "raw_p": round(order[0][1], 3), "runner_up": {"id": order[1][0], "p": round(order[1][1], 3)},
             "probs": {k: round(v, 3) for k, v in order}, "state_moves": parts, "guard": g, "question": "sowhat_frame", "trace": ftrace}
    trig = {"asked": asked, "picks": [], "runner_up": None, "probs": {}, "question": "sowhat_trigger", "trace": ""}
    if counted and top_r:
        by = {x["dial"]: x for x in top_r}
        if asked:
            tp = {k: float(v) for k, v in ans["sowhat_trigger"]["probabilities"].items() if k in by}; to = sorted(tp.items(), key=lambda x: (-x[1], x[0]))
            chosen = [to[0]] + ([to[1]] if to[0][1] - to[1][1] < CLOSE else []); trig["runner_up"] = {"dial": to[1][0], "p": round(to[1][1], 3)}; trig["probs"] = {k: round(v, 3) for k, v in to}
            head = f"trigger choice: {to[0][0]} {f2(to[0][1])}, runner-up {to[1][0]} {f2(to[1][1])}"
        else:
            chosen = [(top_r[0]["dial"], 1.0)]; head = f"only reading: {top_r[0]['dial']} {top_r[0]['direction']}"
        notes = []
        for d, p in chosen:
            x = by[d]; mode = x.get("mode", "reported"); how = x["basis"] if mode == x["basis"] else f"{x['basis']} ({mode})"
            trig["picks"].append({"dial": d, "direction": x["direction"], "basis": x["basis"], "mode": mode, "strength": x["strength"], "severity": x.get("severity"), "p": round(p, 3)})
            notes.append(f"{d} {x['direction']}: strength {num(x['strength'])}, {how}, size {x.get('severity')}")
        trig["trace"] = head + "; " + "; ".join(notes)
    sig = impact.get("significance") or {}
    scale = {"tier": sig.get("tier"), "score": sig.get("score"), "trace": f"Size {sig.get('score')} ({sig.get('tier')})"}
    return {"version": VERSION, "certainty": certainty(ident), "frame": frame, "trigger": trig, "scale": scale,
            "entry": {"id": entry, "place": place_kind(ident, entry), "local": bool(local), "world_max": round(world_max, 2), "entry_max": round(entry_max, 2)}, "cost": {"questions": len(jobs), "calls": len(jobs), "ms": ms}}
