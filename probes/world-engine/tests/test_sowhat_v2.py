"""So-what v2 backend fields (spec/so-what-v2-contract.md): impact.if_true, impact.significance_rows, story.topic, story.seed, v2 tables, the plain frame.
   Offline part (no server, no model; the 22 design fixtures):
     /workspace/kev/.venv/bin/python -m unittest discover -s /workspace/probes/world-engine/tests -p 'test_sowhat_v2.py' -v
   Live part (own engine on :8140, never :8112):  cd /workspace && WE_RULES=rules_v2 ./service.sh start world --port 8140     (stop: ./service.sh stop world --port 8140 -y)
     WE2_TEST_PORT=8140 python3 tests/test_sowhat_v2.py          prints every new field and every difference from the golden-v2 estimates."""
import os, sys, json, csv, unittest, urllib.request
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); WE = os.path.dirname(HERE); SPEC = f"{WE}/spec"; PERSONA = "/workspace/probes/persona"; V2 = f"{PERSONA}/rules_v2"
sys.path.insert(0, PERSONA); sys.path.insert(0, WE)
import sowhat_story as SS, rules as RU, world_service2 as W
ND = len(W.E.DECS)
TIERS = ["Negligible", "Minor", "Notable", "Major", "Historic"]
def rows(n, d=V2): return list(csv.DictReader(open(f"{d}/{n}.csv")))
FRAMES2 = rows("sowhat2_frames"); FRAMES1 = rows("sowhat_frames"); PHR = {r["dial_id"]: r for r in rows("impact_phrases")}; DPHR = {r["decision_id"]: r for r in rows("decision_phrases")}
GOLD = {c["id"]: c for c in json.load(open(f"{SPEC}/sowhat-golden.json"))["cases"]}
def fixture(n): return json.load(open(f"{SPEC}/sowhat-fixtures/{n}.json"))
def fake_ask(case):
    def ask(jobs):
        out = {}
        for name, state, q in jobs:
            src = case["story"]["frame_choice"]["p"] if name == "sowhat_frame" else case["story"]["trigger_choice"]
            pr = {k: float(src.get(k, 0.0)) for k in q["criteria"]}; out[name] = {"choice": max(pr, key=pr.get), "probabilities": pr}
        return out
    return ask
def story(n, version, frames):
    f = fixture(n); return SS.build_story(f["_text"], f["identify"], f["impact"], frames, PHR, DPHR, fake_ask(GOLD[n]), today="2026-10-06", version=version), f
def tier_ok(score, tier): return tier in (W.Session.tier(score - 0.05), W.Session.tier(score + 0.05))      # scores are sent rounded to 0.1; the tier comes from the unrounded score
def nomsg(s): s = json.loads(json.dumps(s)); s["cost"]["ms"] = 0; return s

class Fixtures(unittest.TestCase):
    def test_topic_seed_version_frame(self):
        for n in sorted(GOLD):
            with self.subTest(case=n):
                s, f = story(n, 2, FRAMES2); tagged = [x for x in f["identify"]["placement"] if x["tagged"]]
                self.assertEqual(s["version"], 2); self.assertEqual(s["seed"], SS.djb2(f["_text"])); self.assertTrue(0 <= s["seed"] < 2 ** 32)
                if tagged: self.assertEqual(s["topic"], {"id": tagged[0]["id"], "name": tagged[0]["name"], "p": tagged[0]["p_choice"]}); self.assertTrue(0 <= s["topic"]["p"] <= 1)
                else: self.assertIsNone(s["topic"])
                self.assertTrue(s["frame"]["in_table"]); self.assertIn(s["frame"]["id"], {x["id"] for x in FRAMES2})
                self.assertNotIn("plain", s["frame"]["probs"])      # plain is a row of the table, not a classifier option
    def test_plain_row_resolves(self):
        plain = [x for x in FRAMES2 if x["id"] == "plain"]; self.assertEqual(len(plain), 1); self.assertEqual(plain[0]["classifier_option"], "no")
        f = fixture("01"); i = dict(f["impact"]); s = SS.build_story(f["_text"], f["identify"], i, FRAMES2, PHR, DPHR, fake_ask(GOLD["01"]), today="2026-10-06", version=2)
        self.assertEqual(len(s["frame"]["probs"]), 10)
        # force the coherence guard to land on plain: a squeeze frame over a world that spends more is not allowed, and neither is its runner-up
        p = json.loads(json.dumps(f["impact"]["places"])); p["WORLD:world"]["spend"] = [3.0] * 3
        base = fake_ask(GOLD["01"])
        def ask(jobs):
            out = base(jobs); out["sowhat_frame"] = {"choice": "squeeze", "probabilities": {**{k: 0.0 for k in jobs[0][2]["criteria"]}, "squeeze": 0.6, "freeze": 0.4}}; return out
        s = SS.build_story(f["_text"], f["identify"], dict(f["impact"], places=p), FRAMES2, PHR, DPHR, ask, today="2026-10-06", version=2)
        self.assertEqual(s["frame"]["id"], "plain"); self.assertTrue(s["frame"]["guard"]["fired"]); self.assertTrue(s["frame"]["in_table"])
    def test_v1_unchanged(self):
        for n in sorted(GOLD):
            s, f = story(n, 1, FRAMES1); self.assertEqual(s["version"], 1); self.assertNotIn("topic", s); self.assertNotIn("seed", s); self.assertNotIn("in_table", s["frame"])
    def test_determinism(self):
        for n in sorted(GOLD): self.assertEqual(nomsg(story(n, 2, FRAMES2)[0]), nomsg(story(n, 2, FRAMES2)[0]), n)
    def test_if_true_readings(self):
        """Counting a story in full only rescales: sign, basis, mode_weight, size_mult stay; amount x weight gives back the counted amount."""
        hedged = 0
        for n in sorted(GOLD):
            f = fixture(n); rd = f["identify"]["readings"]; w = f["identify"]["weight"]["value"]
            if not rd or w >= 1: continue
            hedged += 1; full = W.full_readings(rd, w)
            for a, b in zip(rd, full):
                self.assertEqual(np.sign(a["amount"]), np.sign(b["amount"])); self.assertAlmostEqual(b["amount"] * w, a["amount"], 9); self.assertGreaterEqual(abs(b["amount"]), abs(a["amount"]))
                for k in ("basis", "mode_weight", "size_mult", "direction", "dial"): self.assertEqual(a[k], b[k])
        self.assertGreater(hedged, 0)
        self.assertIsNone(W.Session.if_true(None, [{"amount": 0.1}], 1.0, "WORLD:world", None)); self.assertIsNone(W.Session.if_true(None, [], 0.3, "WORLD:world", None))

class Stub:
    """Just enough of a Session for significance_rows: 3 rows (world, two groups) over 40 weighted people, per-person changes at each horizon."""
    SIZE_REF = W.Session.SIZE_REF; SCORE_W = W.Session.SCORE_W; tier = staticmethod(W.Session.tier)
    def __init__(self, seed):
        r = np.random.default_rng(seed); self.n = 40; self.wt = r.uniform(0.5, 2, self.n); g = np.arange(self.n) < 10
        self.rows = [{"id": "WORLD:world"}, {"id": "COUNTRY:a"}, {"id": "AUDIENCE:1"}]; m = np.stack([np.ones(self.n), g, ~g]).astype(float) * self.wt; self.M = m / m.sum(1, keepdims=True)
        base = r.normal(0, 0.01, (self.n, ND)); self.delta = {"now": base * 0.6, "next": base * 1.0 + g[:, None] * r.normal(0, 0.05, (self.n, ND)), "later": base * 0.5}
    def gm(self, X): return self.M @ X
    def core(self):
        ids = ["now", "next", "later"]; snaps = {h: (None, None, np.zeros((self.n, ND)), self.delta[h], None, None) for h in ids}
        D = {h: self.gm(self.delta[h]) * 100 for h in ids}; stakes = {d: 3 for d in W.E.DECS}
        # the world score the long way, as impact() computes it (per decision, with reach over everyone)
        reach = (self.wt[:, None] * (np.abs(self.delta["next"]) * 100 >= 0.5)).sum(0) / self.wt.sum() * 100; scores = []
        for j in range(ND):
            v = {h: float(D[h][0, j]) for h in ids}; pk = v[max(ids, key=lambda h: abs(v[h]))]; pers = 0.0 if abs(pk) < 1e-9 else float(np.clip(v["later"] / pk, 0, 1)); size = 1 - np.exp(-abs(pk) / self.SIZE_REF)
            scores.append(100 * (0.45 * size + 0.15 * reach[j] / 100 + 0.15 * pers + 0.25 * 3 / 5) * float(np.sqrt(size)))
        top = sorted(scores, reverse=True); return {"ids": ids, "D": D, "snaps": snaps, "stakes": stakes, "sig": 0.7 * top[0] + 0.3 * float(np.mean(top[:3]))}

class SignificanceRows(unittest.TestCase):
    def test_world_row_is_the_badge_and_formula_agrees(self):
        for seed in range(6):
            st = Stub(seed); c = st.core(); sr = W.Session.significance_rows(st, c)
            self.assertEqual(sr["WORLD:world"], {"score": round(c["sig"], 1), "tier": W.Session.tier(c["sig"])})
            continue
    def test_vector_equals_scalar_for_the_world(self):
        st = Stub(3); c = st.core(); st.rows[0] = {"id": "ALL"}; sr = W.Session.significance_rows(st, c)
        self.assertAlmostEqual(sr["ALL"]["score"], c["sig"], delta=0.051); self.assertEqual(sr["ALL"]["tier"], W.Session.tier(c["sig"]))
    def test_ranges_and_reach_is_per_row(self):
        st = Stub(1); c = st.core(); sr = W.Session.significance_rows(st, c); self.assertEqual(set(sr), {r["id"] for r in st.rows})
        for v in sr.values(): self.assertTrue(0 <= v["score"] <= 100); self.assertIn(v["tier"], TIERS); self.assertTrue(tier_ok(v["score"], v["tier"]))
        # a group that moves while the world barely does scores higher than the world (reach counted over its own people)
        st = Stub(2); st.delta["next"][:10] += 0.02; st.delta["now"][:10] += 0.01; sr = W.Session.significance_rows(st, st.core()); self.assertGreater(sr["COUNTRY:a"]["score"], sr["WORLD:world"]["score"])
    def test_determinism(self):
        self.assertEqual(W.Session.significance_rows(Stub(5), Stub(5).core()), W.Session.significance_rows(Stub(5), Stub(5).core()))

class PlaceStatus(unittest.TestCase):
    def test_fixtures_by_entry(self):
        for n in sorted(GOLD):
            s, f = story(n, 2, FRAMES2); ent = f["identify"]["entry"]
            self.assertEqual(s["place_status"], "single" if ent.startswith("COUNTRY:") else "worldwide", n); self.assertTrue(s["place_trace"])
            s1, _ = story(n, 1, FRAMES1); self.assertNotIn("place_status", s1)
    def test_three_states(self):
        d = {"path": "region", "region_choice": "Europe", "global_p": 0.1, "other_here_p": 0.8, "chose_global": False, "chose_other_here": True}
        self.assertEqual(SS.place_status("WORLD:world", d)[0], "unresolved"); self.assertIn("0.8", SS.place_status("WORLD:world", d)[1])
        self.assertEqual(SS.place_status("WORLD:world", dict(d, chose_global=True, chose_other_here=False, global_p=0.9, other_here_p=None))[0], "worldwide")
        self.assertEqual(SS.place_status("COUNTRY:ind", dict(d, chose_other_here=False, other_here_p=0.01))[0], "single")
        f = fixture("01"); s = SS.build_story(f["_text"], f["identify"], f["impact"], FRAMES2, PHR, DPHR, fake_ask(GOLD["01"]), today="2026-10-06", version=2, place=d)
        self.assertEqual(s["place_status"], "unresolved"); self.assertEqual(s["entry"]["id"], f["identify"]["entry"]); self.assertEqual(s["place"]["other_here_p"], 0.8)
    def test_ask_country_contract_unchanged(self):
        import classify as C, inspect
        self.assertEqual(list(inspect.signature(C.ask_country).parameters), ["ev", "today"])

class V1AndTables(unittest.TestCase):
    def test_versions(self):
        self.assertEqual(RU.sowhat_version("rules_v2"), 2); self.assertEqual(RU.sowhat_version("rules"), 0)      # v1 rules: no So-what tables at all, so no story and no v2 fields
        self.assertEqual(RU.sowhat_serve("rules"), {"version": 1, "available": False, "frames": [], "lexicon": [], "templates": []})
        t = RU.sowhat_serve("rules_v2"); self.assertEqual(t["version"], 2); self.assertTrue(t["available"])
        for k, n in (("frames", 11), ("hooks", 79), ("templates", 92), ("lexicon", 450), ("lexicon_v1", 133)): self.assertEqual(len(t[k]), n if k in ("frames",) else len(t[k])); self.assertGreater(len(t[k]), 0)
    def test_fallback_to_v1_tables(self):
        import tempfile, shutil
        d = tempfile.mkdtemp()
        try:
            for n in ("sowhat_frames", "sowhat_lexicon", "sowhat_templates"): shutil.copy(f"{V2}/{n}.csv", d)
            t = RU.sowhat_serve(d); self.assertEqual(t["version"], 1); self.assertTrue(t["available"]); self.assertNotIn("hooks", t); self.assertEqual(RU.sowhat_tables(d)["frames"], FRAMES1)
        finally: shutil.rmtree(d)

# ------------------------------ live (own engine, rules_v2)
PORT = int(os.environ.get("WE2_TEST_PORT", "8140")); URL = f"http://127.0.0.1:{PORT}"
def get(path): return json.load(urllib.request.urlopen(URL + path, timeout=30))
def post(path, body): return json.load(urllib.request.urlopen(urllib.request.Request(URL + path, json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=600))
def alive():
    try: return get("/sowhat").get("version") == 2
    except Exception: return False
GV2 = {c["id"]: c for c in json.load(open(f"{SPEC}/sowhat-golden-v2.json"))["cases"]}
LIVE = ["G14", "G20", "G15", "G12", "G11", "G05", "G13", "G07"]; CACHE = {}
def ask(i):
    if i not in CACHE: CACHE[i] = post("/request", {"text": GV2[i]["text"], "mode": "event"})
    return CACHE[i]
@unittest.skipUnless(alive(), f"no rules_v2 engine on {URL}")
class Live(unittest.TestCase):
    def test_get_sowhat(self):
        t = get("/sowhat"); self.assertEqual(t["version"], 2); self.assertTrue(t["available"]); self.assertIn("plain", [f["id"] for f in t["frames"]])
        for k in ("frames", "hooks", "templates", "lexicon", "lexicon_v1"): self.assertTrue(t[k])
    def test_fields(self):
        for i in LIVE:
            with self.subTest(story=i):
                r = ask(i); im = r["impact"]; st = im["story"]; w = r["identify"]["weight"]["value"]; ids = {x["id"] for x in r["read"]["rows"]}
                self.assertEqual(st["version"], 2); self.assertEqual(st["seed"], SS.djb2(GV2[i]["text"])); self.assertTrue(st["frame"]["in_table"])
                self.assertTrue(st["topic"] is None or (0 <= st["topic"]["p"] <= 1 and st["topic"]["id"]))
                sr = im["significance_rows"]; self.assertEqual(set(sr), ids); self.assertEqual(sr["WORLD:world"], {"score": im["significance"]["score"], "tier": im["significance"]["tier"]})
                for v in sr.values(): self.assertTrue(0 <= v["score"] <= 100); self.assertTrue(tier_ok(v["score"], v["tier"]))
                if w < 1:
                    it = im["if_true"]; self.assertEqual(it["method"], "branch"); self.assertEqual(it["type_weight_removed"], w); self.assertEqual(set(it["places"]), set(im["places"]))
                    self.assertEqual(set(it["significance_rows"]), ids); self.assertEqual(it["significance_rows"]["WORLD:world"]["score"], it["significance"]["score"]); self.assertEqual(len(it["rank"]), len(im["rank"]))
                    for x in it["rank"]: self.assertTrue(0 <= x["reach"] <= 100 and 0 <= x["persistence"] <= 1 and 0 <= x["score"] <= 100 and x["tier"] in TIERS)
                    self.assertEqual(it["significance"]["top_decision"], it["rank"][0]["decision"])
                    for row, dd in im["places"].items():
                        for d, real in dd.items():
                            full = it["places"][row][d]; pr = max(real, key=abs); pf = max(full, key=abs)
                            if abs(pr) >= 0.25: self.assertGreater(pr * pf, 0, f"{row} {d}: sign differs ({real} vs {full})"); self.assertGreaterEqual(abs(pf), abs(pr) - 0.011)      # below 0.25 pts (the composer's own floor) a move is numerical noise and may flip sign
                else: self.assertNotIn("if_true", im)
    def test_place_status_live(self):
        for text, want in (("Brazil's central bank raised interest rates again to fight inflation", "single"), ("Global oil prices spiked after attacks on tankers", "worldwide"), ("Malta's only power cable fails, causing an island-wide blackout", "unresolved"), ("Iceland doubles the tourist hotel tax", "unresolved"), ("Colombia and Venezuela reopen their border after years", "unresolved")):
            r = post("/request", {"text": text, "mode": "event"}); st = r["impact"]["story"]; self.assertEqual(st["place_status"], want, text); self.assertTrue(st["place_trace"])
            if want == "unresolved": self.assertEqual(r["identify"]["entry"], "WORLD:world"); self.assertGreater(st["place"]["other_here_p"], 0.5)
    def test_determinism(self):
        a = ask("G12"); b = post("/request", {"text": GV2["G12"]["text"], "mode": "event"})
        for k in ("if_true", "significance_rows", "places", "significance"): self.assertEqual(a["impact"][k], b["impact"][k])
    def test_report(self):
        for i in LIVE:
            r = ask(i); im = r["impact"]; g = GV2[i]["input"]; ent = r["identify"]["entry"]; print(f"\n== {i} {GV2[i]['text'][:70]} | weight {r['identify']['weight']['value']} | impact.ms {im['ms']}")
            print(f"  topic {im['story']['topic']} (golden {g['topic']}) seed {im['story']['seed']} (golden {GV2[i]['seed']})")
            print(f"  world Size {im['significance']['score']} {im['significance']['tier']}; entry {ent} Size {im['significance_rows'][ent]}; golden entry row {(g['significance_rows'] or {}).get(ent)}")
            it = im.get("if_true")
            if it:
                print(f"  if_true Size {it['significance']} (golden estimate {g['if_true']['significance']}); entry row {it['significance_rows'][ent]}")
                for d, real in it["places"]["WORLD:world"].items():
                    est = g["if_true"]["places"]["WORLD:world"][d]
                    if max(abs(x) for x in real + est) >= 0.25 or real != est: print(f"    {d:13s} real {real} estimate {est}  peak diff {max(real, key=abs) - max(est, key=abs):+.2f}")
if __name__ == "__main__": unittest.main(verbosity=2)
