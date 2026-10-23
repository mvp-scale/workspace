"""Combined World-engine reader "BitMob + Clef check" (F-0110, F-0111). Library: read_story(text, day, heads, keys, clef) -> the engine's P plus which questions Clef was asked and the Clef seconds.

Who answers what:
  BitMob (CPU; round-6 model for everything, round-7 model for region/country because country passes the 90% bar only there) answers topics, country, severity, scope/focus, and every
  condition/gate value that Clef is not asked about. It also produces the shortlist of conditions: cell is shortlisted when its raw BitMob value >= cond_thr (the 95% cut, fitted on the 894 Clef tune rows).
  Read-or-skip: if BitMob's happened/announced pair is unsure by +-gate_d (rule from diag_gate_expected.py, 'Variant H'), Clef answers the engine's own block holding those two questions (20 questions, 1 call).
  Conditions: Clef answers the engine's own 20-question blocks that contain a shortlisted attribute (variant B). A block is asked once per story even if both rules want it. Every answer Clef gives replaces BitMob's value.
  Expected impact: Clef answers the e questions of the dials the reader itself did not report and the reader's own topics allow, in the engine's usual 20-question calls (incl. 'done').
  Then the engine's rules: classify.read(P) (gate, readings), classify.allowed_dials(place) and the expected rule of classify.expected(); place/country/severity rules are those of score_mh.py applied to BitMob heads.
`heads` = one story's BitMob output (see BitMob.heads): gate, scope, cond, topic_c, topic_y, severity, region, country as lists. `clef(state, qs)` = offline.call-like: {key: {"noul": p}} for noul questions.
Run with WE_RULES=rules_v2 WORLD_GPU=0."""
import os, sys, json, time
os.environ.setdefault("WE_RULES", "rules_v2"); os.environ.setdefault("WORLD_GPU", "0")
for _p in ("/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo"):
    if _p not in sys.path: sys.path.insert(0, _p)
import numpy as np
import classify as C

CFG = {"cond_thr": 0.14275401830673218,   # 95% of Clef's >=.65 condition answers on the 894 tune rows (screen_real_prep.py / diag_screen_tune.py), raw round-6 values
       "gate_d": 0.30}                    # smallest d with tune gate agreement >= 95% (diag_gate_expected.py variant H); d=0.10 is the >=90% one
NAMES = list(C.QS); BLOCKS = [NAMES[j:j + 20] for j in range(0, len(NAMES), 20)]
GATE_BLOCK = next(i for i, b in enumerate(BLOCKS) if "g|happened" in b); assert "g|announced" in BLOCKS[GATE_BLOCK]
MAIN, CTRY = "/workspace/data/kaggle/mh_r6c1/out/mh", "/workspace/data/kaggle/mh_r7/out/mh"


class BitMob:
    """The CPU reader. main = round-6 model (everything), country = round-7 model (region and country heads only). Raw condition values (no cond cut calibration), as used to fit cond_thr."""
    def __init__(self, main=MAIN, country=CTRY, threads=8):
        sys.path.insert(0, "/workspace/newsreader/bitmob/mh")
        import torch; torch.set_num_threads(threads)
        from mh_common import load, predict
        self._predict = predict; self.m, self.tm, self.K = load(main); self.m.cond_cuts = None
        self.c, self.tc, self.Kc = load(country) if country else (None, None, None)
        K = self.K; Kc = self.Kc or K
        self.keys = {"gate": K["gate"], "scope": K["scope"], "cond": K["cond"], "severity": K["severity"], "levels": K["levels"], "topic_c": K["topic_c"], "topic_y": K["topic_y"], "region": Kc["region"], "country": Kc["country"]}

    def heads(self, texts):
        H = self._predict(self.m, self.tm, texts); Hc = self._predict(self.c, self.tc, texts) if self.c else H
        out = []
        for n in range(len(texts)):
            out.append({"gate": H["gate"][n].tolist(), "scope": H["scope"][n].tolist(), "cond": H["cond"][n].tolist(), "topic_c": H["topic_c"][n].tolist(), "topic_y": H["topic_y"][n].tolist(),
                        "severity": H["severity"][n].tolist(), "region": Hc["region"][n].tolist(), "country": Hc["country"][n].tolist()})
        return out


def bitmob_P(h, keys):
    """BitMob's value for every one of the engine's 328 answers (gate/scope/focus/recent keys from the heads, both wordings of an attribute get the same value)."""
    P = {}
    for k, v in zip(keys["gate"], h["gate"]): P[k] = float(v)
    for k, v in zip(keys["scope"], h["scope"]): P[k] = float(v)
    for k, v in zip(keys["cond"], h["cond"]): d, dr, i = k.split("|"); P[f"a|{d}|{dr}|{i}|0"] = P[f"a|{d}|{dr}|{i}|1"] = float(v)
    return P


def bitmob_place(h, keys):
    pc = dict(zip(keys["topic_c"], h["topic_c"])); py = dict(zip(keys["topic_y"], h["topic_y"]))
    tag = {d: (pc[d] >= .2 or py.get(d, 0) >= .5) and d != "other" or (d == "other" and pc[d] >= .2) for d in pc}
    if not any(tag.values()): tag[max(pc, key=pc.get)] = True
    return [{"id": d, "tagged": bool(tag[d]), "p_choice": float(pc[d]), "p_yes": float(py.get(d, 0.0))} for d in pc]


_ROWS = None
def bitmob_country(h, keys):
    global _ROWS
    _ROWS = _ROWS or C._country_rows()
    pr = dict(zip(keys["region"], h["region"])); g = max(pr, key=pr.get)
    if g == "GLOBAL": return "global"
    pc = dict(zip(keys["country"], h["country"])); cand = [x["id"] for x in _ROWS if x["region"] == g] + ["other_here"]; c = max(cand, key=lambda x: pc[x])
    return "global" if c == "other_here" else c


def expected_questions(reported, allowed):
    """Same questions, same order and wording as classify.expected()."""
    qs = {}
    for d, r in C.PHRASES.items():
        if d in reported or (allowed is not None and d not in allowed): continue
        qs[f"e|{d}|up"] = f"Suppose the main development in this story fully plays out (the plan goes ahead, the claim succeeds, the invention works, the event unfolds as described). Is it likely that {r['up']}? Answer yes only if there is a real reason to expect it."
        qs[f"e|{d}|down"] = f"Suppose the main development in this story fully plays out (the plan goes ahead, the claim succeeds, the invention works, the event unfolds as described). Is it likely that {r['down']}? Answer yes only if there is a real reason to expect it."
    qs["done"] = "The consequences this story describes or implies are already in effect. They are NOT merely planned, announced for the future, argued in court, proposed, under review or only possible."
    return qs


def expected_from(P, reported, min_net=0.05):
    """classify.expected()'s rule applied to answers P (e|dial|up/down and done)."""
    done = P["done"]; mode = "expected_in_effect" if done >= .5 else "expected_pending"; out = []
    for d in C.PHRASES:
        if d in reported or f"e|{d}|up" not in P: continue
        pu, pd = P[f"e|{d}|up"], P[f"e|{d}|down"]; net = pu - pd
        if max(pu, pd) >= C.EXPECT_MIN and abs(net) > min_net:
            out.append({"dial": d, "direction": "up" if net > 0 else "down", "strength": round(abs(net), 3), "p_up": round(pu, 3), "p_down": round(pd, 3), "p_done": round(done, 3), "mode": mode, "attributes": ["expected impact"]})
    return sorted(out, key=lambda x: -x["strength"])[:C.EXPECT_TOP]


def read_story(text, day, heads, keys, clef, cfg=None):
    """-> dict: P (engine's 328 answers + e answers), read (classify.read), place, country, expected, severity, asked (list of {phase, n_q, secs}), clef_s, clef_calls, clef_questions."""
    cfg = {**CFG, **(cfg or {})}; state = f"News item (published {day}; today is {day}):\n{text}"; asked = []
    def ask(phase, names, qs=None):
        qs = qs or {k: C.QS[k] for k in names}; t = time.time(); r = clef(state, {k: {"type": "noul", "instructions": v} for k, v in qs.items()}); dt = time.time() - t
        asked.append({"phase": phase, "n_q": len(qs), "secs": round(dt, 3)}); return {k: float(r[k]["noul"]) for k in qs}
    P = bitmob_P(heads, keys); P0 = dict(P)
    # shortlist and read-or-skip
    flag = np.asarray(heads["cond"]) >= cfg["cond_thr"]; sk = {f"a|{d}|{dr}|{i}|{w}" for j, k in enumerate(keys["cond"]) if flag[j] for d, dr, i in [k.split("|")] for w in (0, 1)}
    cond_blocks = {b for b, blk in enumerate(BLOCKS) if sk & set(blk)}
    h, a, d = P["g|happened"], P["g|announced"], cfg["gate_d"]; f = lambda s: (h + s >= .5) or (a + s >= .5); gate_unsure = f(d) != f(-d)
    todo = sorted(cond_blocks | ({GATE_BLOCK} if gate_unsure else set())); answers = {}
    for b in todo: answers.update(ask("gate+cond" if b == GATE_BLOCK and gate_unsure and b in cond_blocks else ("gate" if b == GATE_BLOCK and gate_unsure and b not in cond_blocks else "cond"), BLOCKS[b]))
    P.update(answers); rd = C.read(P)
    reported = {x["dial"] for x in rd["readings"] if x["direction"] != "conflict"}
    pl = bitmob_place(heads, keys); allowed = C.allowed_dials(pl)
    # expected impact: Clef, engine's usual calls
    eq = expected_questions(reported, allowed); names = list(eq); E = {}
    for j in range(0, len(names), 20): E.update(ask("expected", None, {k: eq[k] for k in names[j:j + 20]}))
    exp = expected_from(E, reported)
    sev = {dl: keys["levels"][int(np.argmax(heads["severity"][i]))] for i, dl in enumerate(keys["severity"])}
    return {"P": {**P}, "clef_answers": {**answers}, "e_raw": E, "read": rd, "place": pl, "country": bitmob_country(heads, keys), "expected": exp,
            "severity_level": sev, "gate_unsure": bool(gate_unsure), "shortlist_n": int(flag.sum()), "blocks_asked": todo, "asked": asked,
            "clef_s": round(sum(x["secs"] for x in asked), 3), "clef_calls": len(asked), "clef_questions": sum(x["n_q"] for x in asked)}
