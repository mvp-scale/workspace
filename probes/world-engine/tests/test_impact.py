"""Checks for the `impact` block of POST /request (event mode). Needs a running test instance:
   cd /workspace/probes/world-engine && WE2_PORT=8122 /workspace/kev/.venv/bin/python world_service2.py
   WE2_TEST_PORT=8122 /workspace/kev/.venv/bin/python tests/test_impact.py        (also runs the rule-file validator, no server needed)"""
import os, sys, json, unittest, urllib.request
sys.path.insert(0, "/workspace/probes/persona")
PORT = int(os.environ.get("WE2_TEST_PORT", "8122")); URL = f"http://127.0.0.1:{PORT}"
STORIES = ["The central bank cut interest rates by half a point today", "A new pandemic virus is spreading fast across several countries", "A big company launched a new phone with a better camera",
           "A record heat wave is hitting Europe with power cuts", "The government announced a major school reform with longer school days"]
TIERS = ["Negligible", "Minor", "Notable", "Major", "Historic"]
def post(path, body):
    r = urllib.request.Request(URL + path, json.dumps(body).encode(), {"Content-Type": "application/json"}); return json.load(urllib.request.urlopen(r, timeout=300))
def alive():
    try: urllib.request.urlopen(URL + "/graph", timeout=5); return True
    except Exception: return False
CACHE = {}
def ask(t, mode="event"):
    if (t, mode) not in CACHE: CACHE[(t, mode)] = post("/request", {"text": t, "mode": mode})
    return CACHE[(t, mode)]
class Rules(unittest.TestCase):
    def test_validator_has_no_resource_issues(self):
        import rules; r = rules.validate(); bad = [i for i in r["issues"] if "resource" in i or "stakes" in i]; self.assertEqual(bad, [])
@unittest.skipUnless(alive(), f"no test instance on {URL}")
class Impact(unittest.TestCase):
    def test_shape(self):
        for t in STORIES:
            im = ask(t)["impact"]; self.assertEqual([h["id"] for h in im["horizons"]], ["now", "next", "later"]); self.assertEqual(im["horizons"][0]["ticks"], 3)
            self.assertTrue(3 < im["horizons"][1]["ticks"] < im["horizons"][2]["ticks"])
            self.assertEqual(len(im["rank"]), 8)
            for r in im["rank"]:
                for k in ("decision", "label", "now", "next", "later", "reach", "persistence", "peak_h", "stakes", "score", "tier", "why"): self.assertIn(k, r)
            for k in ("score", "tier", "top_decision", "summary"): self.assertIn(k, im["significance"])
            self.assertLessEqual(len(im["significance"]["summary"]), 3); self.assertLessEqual(len(im["chain"]), 12)
            for c in im["chain"]: self.assertIn(c["kind"], ("topic", "condition", "resource", "state", "decision", "group", "place")); self.assertTrue(0 <= c["strength"] <= 1)
            for r in im["resources"]:
                self.assertIn(r["direction"], ("strained", "built", "mixed", "none"))
                for k in ("conditions", "states", "decisions"): self.assertLessEqual(len(r["via"][k]), 3)
            p = im["places"]; self.assertIn("WORLD:world", p); self.assertEqual(len(p["WORLD:world"]), 8); self.assertTrue(all(len(v) == 3 for v in p["WORLD:world"].values()))
            self.assertEqual(set(p), {r["id"] for r in ask(t)["read"]["rows"]})
    def test_ranges(self):
        for t in STORIES:
            im = ask(t)["impact"]; sc = [r["score"] for r in im["rank"]]; self.assertEqual(sc, sorted(sc, reverse=True))
            for r in im["rank"]:
                self.assertTrue(0 <= r["score"] <= 100 and 0 <= r["reach"] <= 100 and 0 <= r["persistence"] <= 1 and 1 <= r["stakes"] <= 5 and r["tier"] in TIERS and r["peak_h"] in ("now", "next", "later"))
            self.assertTrue(0 <= im["significance"]["score"] <= 100 and all(0 <= x["score"] <= 100 for x in im["resources"]))
    def test_tier_monotonic_in_score(self):
        rows = sorted((r["score"], TIERS.index(r["tier"])) for t in STORIES for r in ask(t)["impact"]["rank"]); tiers = [x[1] for x in rows]; self.assertEqual(tiers, sorted(tiers))
    def test_horizons_differ(self):
        diff = sum(1 for t in STORIES for r in ask(t)["impact"]["rank"] if abs(r["now"] - r["later"]) > 0.05); self.assertGreater(diff, 5)
        self.assertGreater(len({ask(t)["impact"]["rank"][0]["peak_h"] + str(round(ask(t)["impact"]["rank"][0]["persistence"], 1)) for t in STORIES}), 1)
    def test_stories_vary(self):
        sig = [ask(t)["impact"]["significance"]["score"] for t in STORIES]; self.assertGreater(max(sig) - min(sig), 30); self.assertGreater(len({ask(t)["impact"]["significance"]["tier"] for t in STORIES}), 2)
    def test_deterministic(self):
        a = json.loads(json.dumps(ask(STORIES[0])["impact"])); b = post("/request", {"text": STORIES[0], "mode": "event"})["impact"]
        for x in (a, b): x.pop("ms")
        self.assertEqual(a, b)
    def test_existing_fields_unchanged(self):
        o = ask(STORIES[0]); self.assertTrue({"identify", "propagate", "decide", "read", "impact"} <= set(o))
        self.assertEqual({"mode", "counted", "status", "weight", "placement", "exposure", "readings", "country", "entry", "gate", "evidence"} - set(o["identify"]), set())
        self.assertEqual(o["read"]["mode"], "event"); self.assertEqual(len(o["read"]["cols"]), 8); r0 = o["read"]["rows"][0]; self.assertEqual(r0["id"], "WORLD:world"); self.assertEqual(len(r0["values"]), 8); self.assertIn("parts", r0)
        self.assertEqual(len(o["propagate"]["rows"]), 401); self.assertEqual(o["decide"]["kind"], "state decisions")
        # the 'now' column of the rank is the same number the old read shows for the world row
        for r in o["impact"]["rank"]: self.assertAlmostEqual(r["now"], r0["values"][[c["id"] for c in o["read"]["cols"]].index(r["decision"])], places=2)
    def test_offer_mode_has_null_impact(self):
        o = ask("A monthly meal-kit subscription with a free app for busy families", "offer"); self.assertIn("impact", o); self.assertIsNone(o["impact"])
    def test_graph_links(self):
        g = json.load(urllib.request.urlopen(URL + "/graph")); rl = g["resource_links"]; self.assertTrue(rl["condition_resource"] and rl["state_resource"] and rl["decision_resource"]); self.assertEqual(len(g["decision_stakes"]), 8)
        self.assertEqual({x["a"] for x in rl["condition_resource"]}, {c["id"] for c in g["meaning"]["conditions"]})
if __name__ == "__main__": unittest.main(verbosity=2)
