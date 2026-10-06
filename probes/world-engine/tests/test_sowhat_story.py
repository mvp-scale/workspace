"""Offline tests for impact.story (sowhat_story.py): the 22 design fixtures with their stored classifier answers must reproduce the golden story-level beats.
   /workspace/kev/.venv/bin/python -m unittest discover -s /workspace/probes/world-engine/tests -p 'test_sowhat_story.py' -v      (no server, no model)"""
import os, sys, json, csv, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); WE = os.path.dirname(HERE); SPEC = f"{WE}/spec"; V2 = "/workspace/probes/persona/rules_v2"
sys.path.insert(0, "/workspace/probes/persona"); sys.path.insert(0, WE)
import sowhat_story as SS, rules as RU
def rows(n): return list(csv.DictReader(open(f"{V2}/{n}.csv")))
FRAMES = rows("sowhat_frames"); PHR = {r["dial_id"]: r for r in rows("impact_phrases")}; DPHR = {r["decision_id"]: r for r in rows("decision_phrases")}
GOLD = {c["id"]: c for c in json.load(open(f"{SPEC}/sowhat-golden.json"))["cases"]}
def fixture(n): return json.load(open(f"{SPEC}/sowhat-fixtures/{n}.json"))
def fake_ask(case):
    """Stored answers: the golden file keeps the top three of each distribution; the rest is 0."""
    def ask(jobs):
        out = {}
        for name, state, q in jobs:
            src = case["story"]["frame_choice"]["p"] if name == "sowhat_frame" else case["story"]["trigger_choice"]
            pr = {k: float(src.get(k, 0.0)) for k in q["criteria"]}; out[name] = {"choice": max(pr, key=pr.get), "probabilities": pr}
        return out
    return ask
def story_for(n, ask=None):
    f = fixture(n); c = GOLD[n]
    return SS.build_story(f["_text"], f["identify"], f["impact"], FRAMES, PHR, DPHR, ask or fake_ask(c), today="2026-10-06"), f, c
class Golden(unittest.TestCase):
    def test_every_fixture(self):
        for n in sorted(GOLD):
            with self.subTest(case=n):
                s, f, c = story_for(n); beats = {b["kind"]: b for b in c["foci"][0]["expect"]["beats"]}; exp = c["foci"][0]["expect"]
                # certainty: same trace string as the golden beat
                self.assertEqual(s["certainty"]["trace"], beats["certainty"]["trace"]) if "certainty" in beats and f["identify"]["counted"] else None
                self.assertEqual(s["frame"]["state_moves"], c["story"]["frame_choice"]["state_moves"] if c["story"]["frame_choice"]["state_moves"] else [])
                # frame: the classifier's pick leads the trace, and the (guarded) frame is the golden frame where the golden has one
                self.assertTrue(beats["frame"]["trace"].startswith(s["frame"]["trace"].split(";")[0])) if "frame" in beats else None
                if exp["frame"] and exp["frame"] != "plain": self.assertEqual(s["frame"]["id"], exp["frame"].replace("-", "_"))
                self.assertFalse(s["frame"]["guard"]["fired"], "design stories never needed the guard")
                # scale: world Size from the badge
                sig = f["impact"]["significance"]; self.assertEqual((s["scale"]["tier"], s["scale"]["score"]), (sig["tier"], sig["score"]))
                self.assertEqual(s["scale"]["trace"], f"Size {sig['score']} ({sig['tier']})")
                # trigger: same pick as the golden trigger beat (when the story has one), same head of trace
                tb = beats.get("trigger")
                if tb and s["trigger"]["picks"]:
                    head = tb["trace"].split(";")[0]
                    if s["trigger"]["asked"]: self.assertEqual(s["trigger"]["picks"][0]["dial"], head.split("trigger choice: ")[1].split(" ")[0])
                    self.assertEqual(s["trigger"]["trace"].split(";")[0], head)
    def test_trigger_not_asked_for_one_reading(self):
        for n in sorted(GOLD):
            f = fixture(n); k = len(f["identify"]["readings"]) if f["identify"]["counted"] else 0; s, _, _ = story_for(n)
            self.assertEqual(s["trigger"]["asked"], k >= 2, n); self.assertEqual(s["cost"]["questions"], 1 + (k >= 2))
            if k == 0: self.assertEqual(s["trigger"]["picks"], [])
            if k == 1: self.assertEqual(len(s["trigger"]["picks"]), 1)
    def test_second_trigger_only_when_close(self):
        for n in sorted(GOLD):
            s, _, c = story_for(n); t = s["trigger"]
            if t["asked"]:
                self.assertEqual(len(t["picks"]), 2 if t["picks"][0]["p"] - t["runner_up"]["p"] < 0.2 else 1, n)
        self.assertEqual(len(story_for("17")[0]["trigger"]["picks"]), 2)          # bank collapse: market swings 0.52 against asset values 0.44
        self.assertEqual(len(story_for("01")[0]["trigger"]["picks"]), 1)
    def test_contract_shape(self):
        s, f, _ = story_for("01"); self.assertEqual(s["version"], 1); self.assertEqual(s["certainty"]["kind"], "happened"); self.assertEqual(s["certainty"]["modal"], "")
        self.assertEqual(s["frame"]["id"], "relief"); self.assertEqual(s["frame"]["runner_up"]["id"], "boost"); self.assertEqual(len(s["frame"]["probs"]), 10)
        self.assertEqual(s["frame"]["trace"], "frame choice: relief 0.79, runner-up boost 0.19")
        t = s["trigger"]; self.assertEqual(t["picks"][0]["dial"], "borrowing_cost"); self.assertEqual(t["runner_up"]["dial"], "private_debt")
        self.assertEqual(t["trace"], "trigger choice: borrowing_cost 0.98, runner-up private_debt 0.01; borrowing_cost down: strength 0.996, reported, size notable")
        self.assertEqual(s["scale"], {"tier": "Minor", "score": 20.4, "trace": "Size 20.4 (Minor)"}); self.assertFalse(s["entry"]["local"])
        self.assertEqual(s["cost"]["questions"], 2)
    def test_certainty_kinds(self):
        kinds = {n: story_for(n)[0]["certainty"] for n in GOLD}
        self.assertEqual((kinds["15"]["kind"], kinds["15"]["modal"]), ("announced", "will"))       # gate: forecast 0.83 but announced 0.99 (changed from 'forecast' by review fix 1)
        self.assertEqual((kinds["20"]["kind"], kinds["20"]["modal"]), ("forecast", "would"))       # gate: happened 0.02, forecast 0.99 > announced 0.12; opinion 0.71 is under the 0.9 cut
        self.assertEqual((kinds["13"]["kind"], kinds["13"]["modal"]), ("pending", ""))             # approved, effects pending: plain present for the event
        self.assertEqual(kinds["21"]["kind"], "opinion") if story_for("21")[1]["identify"]["counted"] else None
        self.assertEqual(kinds["22"]["kind"], "no_impact"); self.assertEqual(kinds["22"]["modal"], "")
    def test_no_impact_story(self):
        s, f, _ = story_for("22"); self.assertFalse(f["identify"]["counted"]); self.assertEqual(s["trigger"]["picks"], []); self.assertFalse(s["trigger"]["asked"])
        self.assertEqual(s["frame"]["state_moves"], []); self.assertEqual(s["cost"]["questions"], 1)
    def test_local_entry(self):
        for n in ("03", "05"):
            e = story_for(n)[0]["entry"]; self.assertTrue(e["local"], n); self.assertTrue(e["world_max"] < 0.25 <= e["entry_max"], n)
        self.assertFalse(story_for("02")[0]["entry"]["local"])
    def test_question_text_comes_from_the_rules(self):
        seen = {}
        def ask(jobs):
            for name, st, q in jobs: seen[name] = (st, q)
            return fake_ask(GOLD["01"])(jobs)
        story_for("01", ask); st, q = seen["sowhat_frame"]
        self.assertEqual(q["criteria"], {f["id"]: f["probe_statement"] for f in FRAMES}); self.assertEqual(q["instructions"], "Which statement best describes the effect of this story on ordinary people?")
        self.assertTrue(st.endswith("What our world model found, strongest first: loans get cheaper or easier to get; share, property and savings values rise; people spend more; people buy more new things."), st)
        st2, q2 = seen["sowhat_trigger"]; self.assertNotIn("What our world model found", st2); self.assertEqual(set(q2["criteria"]), {"borrowing_cost", "private_debt", "industrial_output", "housing_cost", "asset_values"})
        self.assertEqual(q2["criteria"]["borrowing_cost"], PHR["borrowing_cost"]["down"])
    def test_determinism(self):
        for n in ("01", "10", "17", "21"):
            a, b = story_for(n)[0], story_for(n)[0]; a["cost"].pop("ms"); b["cost"].pop("ms"); self.assertEqual(json.dumps(a), json.dumps(b))
class Gate(unittest.TestCase):
    """Review fix 1: the kind comes from the gate in a fixed order; same order as deriveStory in sowhat.js."""
    def kind(self, **g):
        gate = dict(happened=0, announced=0, opinion=0, forecast=0); gate.update(g)
        return SS.certainty({"counted": True, "gate": gate, "weight": {"type": "forecast", "value": 0.3}, "readings": [{"mode": "reported"}]})["kind"]
    def test_order(self):
        self.assertEqual(self.kind(opinion=.95, forecast=.9, announced=.9, happened=.9), "opinion")
        self.assertEqual(self.kind(opinion=.71, forecast=.99, announced=.12, happened=.02), "forecast")
        self.assertEqual(self.kind(forecast=.99, announced=.94, happened=.03), "forecast")        # a warning
        self.assertEqual(self.kind(forecast=.83, announced=.99, happened=.1), "announced")
        self.assertEqual(self.kind(forecast=.1, announced=.1, happened=.1), "announced")
        self.assertEqual(self.kind(forecast=.8, announced=.7, happened=.9), "happened")
        self.assertEqual(SS.certainty({"counted": False, "gate": {}})["kind"], "no_impact")
    def test_weight_type_does_not_decide(self):
        for t in ("forecast", "opinion", "unclear", "fact"):
            self.assertEqual(SS.certainty({"counted": True, "gate": {"happened": .97, "announced": .99, "opinion": 1.0 if t == "opinion" else 0, "forecast": .83 if t == "forecast" else 0}, "weight": {"type": t, "value": 1}, "readings": []})["kind"], "opinion" if t == "opinion" else "happened")
    def test_pending_only_when_happened_and_all_pending(self):
        rd = lambda *m: [{"mode": x} for x in m]; g = {"happened": .98, "announced": .99, "opinion": 0, "forecast": 0}
        self.assertEqual(SS.certainty({"counted": True, "gate": g, "weight": {}, "readings": rd("expected_pending", "expected_pending")})["kind"], "pending")
        self.assertEqual(SS.certainty({"counted": True, "gate": g, "weight": {}, "readings": rd("expected_pending", "reported")})["kind"], "happened")
        self.assertEqual(SS.MODAL["pending"], "")
    def test_old_modal_for_other_kinds(self):
        self.assertEqual([SS.MODAL[k] for k in ("forecast", "opinion", "unclear", "announced")], ["would", "could", "may", "will"])
class Place(unittest.TestCase):
    """Honesty about place (ontology 1.8): country row / world / unresolved, from ask_country's own answer."""
    def test_kinds(self):
        self.assertEqual(SS.place_kind({"country": "mex", "country_p": .9}, "COUNTRY:mex"), "country")
        self.assertEqual(SS.place_kind({"country": "global", "country_p": .99}, "WORLD:world"), "world")           # ask_country chose the whole world
        self.assertEqual(SS.place_kind({"country": "global", "country_p": None}, "WORLD:world"), "unresolved")      # a part of the world, no country in it (the EU, Ireland, the Gulf, two countries)
        self.assertEqual(SS.place_kind({}, "WORLD:world"), "world")
    def test_in_stories(self):
        self.assertEqual(story_for("14")[0]["entry"]["place"], "unresolved"); self.assertEqual(story_for("01")[0]["entry"]["place"], "world"); self.assertEqual(story_for("03")[0]["entry"]["place"], "country")
class Trigger(unittest.TestCase):
    def test_reported_first_and_missing_phrase_cannot_crash(self):
        f = fixture("09"); seen = {}
        def ask(jobs):
            for name, st, q in jobs: seen[name] = q
            return fake_ask(GOLD["09"])(jobs)
        SS.build_story(f["_text"], f["identify"], f["impact"], FRAMES, PHR, DPHR, ask, today="2026-10-06")
        order = list(seen["sowhat_trigger"]["criteria"]); basis = {x["dial"]: x["basis"] for x in f["identify"]["readings"]}
        flags = [basis[d] == "expected" for d in order]; self.assertEqual(flags, sorted(flags), "reported readings are offered before expected ones")
        phr = {k: v for k, v in PHR.items() if k != "prices"}; ident = json.loads(json.dumps(f["identify"])); ident["readings"].append({"dial": "not_a_dial", "direction": "up", "amount": 9, "strength": .9, "basis": "reported", "mode": "reported", "severity": "x"})
        s = SS.build_story(f["_text"], ident, f["impact"], FRAMES, phr, DPHR, lambda jobs: fake_ask(GOLD["09"])(jobs), today="2026-10-06")
        self.assertNotIn("prices", [p["dial"] for p in s["trigger"]["picks"]]); self.assertNotIn("not_a_dial", [p["dial"] for p in s["trigger"]["picks"]])
class Guard(unittest.TestCase):
    PL = lambda self, **peaks: {"R": {d: [0, v, 0] for d, v in peaks.items()}}
    def test_pass(self):
        fid, g = SS.guard({"squeeze": .7, "relief": .2, "ripple": .1}, self.PL(spend=-2.0), "R", "R"); self.assertEqual((fid, g["fired"]), ("squeeze", False))
    def test_runner_up(self):
        fid, g = SS.guard({"squeeze": .7, "relief": .2, "ripple": .1}, self.PL(spend=2.0, buy_new=1.0), "R", "R")
        self.assertEqual((fid, g["fired"], g["from"], g["to"], g["sense"]), ("relief", True, "squeeze", "relief", "up")); self.assertIn("squeeze needs not up", g["trace"])
    def test_plain(self):
        fid, g = SS.guard({"squeeze": .7, "surge_": 0, "scare": .2, "ripple": .1}, self.PL(spend=2.0), "R", "R"); self.assertEqual((fid, g["to"]), ("plain", "plain"))
    def test_any_frames_never_fire(self):
        for f in ("shake_up", "surge", "rift", "ripple"):
            for v in (-3.0, 0.0, 3.0): self.assertFalse(SS.guard({f: .9, "squeeze": .1}, self.PL(spend=v), "R", "R")[1]["fired"])
    def test_flat_passes_everything(self):
        for f in ("squeeze", "relief", "scare", "blow", "freeze", "boost"): self.assertFalse(SS.guard({f: .9, "ripple": .1}, self.PL(spend=0.1), "R", "R")[1]["fired"])
    def test_sense_uses_peak_not_now(self):
        self.assertEqual(SS.sense({"R": {"spend": [0.1, -1.0, -0.4]}}, "R")[0], "down")
    def test_guard_inside_story(self):
        f = fixture("07"); f["impact"]["places"]["WORLD:world"]["spend"] = [3.0, 4.0, 2.0]; f["impact"]["places"]["WORLD:world"]["buy_new"] = [1, 1, 1]
        s = SS.build_story(f["_text"], f["identify"], f["impact"], FRAMES, PHR, DPHR, fake_ask(GOLD["07"]), today="2026-10-06")
        self.assertTrue(s["frame"]["guard"]["fired"]); self.assertEqual(s["frame"]["raw_id"], "squeeze"); self.assertEqual(s["frame"]["id"], "plain"); self.assertIn("guard:", s["frame"]["trace"])
class Rulesets(unittest.TestCase):
    def test_v1_has_no_sowhat_tables(self):
        t = RU.sowhat_tables("rules"); self.assertEqual(t, {"frames": [], "lexicon": [], "templates": []})
    def test_v2_tables(self):
        t = RU.sowhat_tables("rules_v2"); self.assertEqual((len(t["frames"]), len(t["templates"])), (10, 48)); self.assertGreater(len(t["lexicon"]), 100)
    def test_service_has_no_story_for_v1(self):
        with open(f"{WE}/world_service2.py") as fh: src = fh.read()
        self.assertIn('if not t["frames"]: return None', src); self.assertIn("if st_ is not None: impact[\"story\"] = st_", src)
if __name__ == "__main__": unittest.main()
