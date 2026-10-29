"""Unit tests for kit/eval on synthetic fixtures only (made-up ids and offsets, no corpus text).
Run: python -m unittest discover -s knowledge_pipeline/kit/eval/tests
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import agreement as A  # noqa: E402
import compare as C  # noqa: E402
import consensus as K  # noqa: E402
import gate as G  # noqa: E402
import score_spans as S  # noqa: E402


def doc(*items):
    """doc(("i1", [(0, 4, "X")], [(10, 12)]), ...) -> span doc; ignore list optional."""
    return {"items": [{"id": it[0], "spans": [{"start": s, "end": e, "label": l} for s, e, l in it[1]],
                       "ignore": [{"start": s, "end": e} for s, e in (it[2] if len(it) > 2 else [])]} for it in items]}


def labels(rows):
    return {"items": [{"id": f"q{i}", "labels": [x] if x else []} for i, x in enumerate(rows)]}


def many(n=20, shift=0, drop_every=0):
    out = []
    for i in range(n):
        sp = [(0, 4, "X"), (10, 15, "Y"), (20, 22, "X")]
        if drop_every and i % drop_every == 0:
            sp = sp[:1]
        out.append((f"i{i}", [(s + shift, e + shift, l) for s, e, l in sp]))
    return doc(*out)


class TestScore(unittest.TestCase):
    def test_perfect(self):
        d = many(10)
        r = S.score(d, d, n=200)["layers"]
        for L in ("X", "Y", "ALL"):
            for m in S.MODES:
                self.assertEqual((r[L][m]["f1"], r[L][m]["lo"], r[L][m]["hi"]), (1.0, 1.0, 1.0))

    def test_disjoint(self):
        r = S.score(doc(("a", [(0, 4, "X")])), doc(("a", [(50, 60, "X")])), n=50)["layers"]
        self.assertEqual(r["X"]["exact"]["f1"], 0.0)
        self.assertEqual(r["X"]["overlap"]["f1"], 0.0)
        self.assertEqual(r["X"]["overlap"]["hi"], 0.0)

    def test_overlap_vs_exact(self):
        r = S.score(doc(("a", [(0, 5, "X"), (10, 14, "Y")])), doc(("a", [(0, 4, "X"), (10, 14, "Y")])), n=50)["layers"]
        self.assertEqual(r["X"]["exact"]["f1"], 0.0)
        self.assertEqual(r["X"]["overlap"]["f1"], 1.0)
        self.assertEqual(r["ALL"]["exact"]["f1"], 0.5)
        self.assertEqual(r["ALL"]["overlap"]["f1"], 1.0)

    def test_label_must_match(self):
        r = S.score(doc(("a", [(0, 4, "X")])), doc(("a", [(0, 4, "Y")])), n=10)["layers"]
        self.assertEqual(r["ALL"]["overlap"]["f1"], 0.0)

    def test_greedy_one_to_one(self):
        r = S.score(doc(("a", [(0, 10, "X")])), doc(("a", [(0, 4, "X"), (5, 10, "X")])), n=10)["layers"]
        o = r["X"]["overlap"]
        self.assertEqual((o["tp"], o["n_cand"], o["n_ref"], o["p"], o["r"]), (1, 1, 2, 1.0, 0.5))

    def test_ignore_regions(self):
        cand = doc(("a", [(0, 4, "X"), (30, 34, "X")]))
        ref = doc(("a", [(0, 4, "X")], [(28, 40)]))
        self.assertEqual(S.score(cand, ref, n=10)["layers"]["X"]["exact"]["f1"], 1.0)
        ign = doc(("a", [], [(28, 40)]))
        self.assertEqual(S.score(cand, doc(("a", [(0, 4, "X")])), ign, n=10)["layers"]["X"]["exact"]["f1"], 1.0)

    def test_missing_cand_item_is_empty(self):
        r = S.score(doc(("a", [(0, 4, "X")])), doc(("a", [(0, 4, "X")]), ("b", [(0, 4, "X")])), n=10)
        self.assertEqual(r["layers"]["X"]["exact"]["r"], 0.5)
        self.assertEqual(r["meta"]["ref_items_missing_in_cand"], 1)

    def test_bootstrap_deterministic(self):
        cand, ref = many(20, drop_every=3), many(20)
        a, b = S.score(cand, ref, n=300, seed=7), S.score(cand, ref, n=300, seed=7)
        self.assertEqual(a, b)
        r = a["layers"]["ALL"]["exact"]
        self.assertTrue(r["lo"] <= r["f1"] <= r["hi"] and r["lo"] < r["hi"])
        c = S.score(cand, ref, n=300, seed=8)
        self.assertEqual(c["layers"]["ALL"]["exact"]["f1"], r["f1"])

    def test_sha(self):
        h = S.sha()
        self.assertEqual(len(h), 8)
        int(h, 16)


class TestAgreement(unittest.TestCase):
    def test_kappa_hand(self):
        # 2x2: both Y 20, A only 5, B only 10, both N 15 (n=50). po=.7, pA=.5, pB=.6, pe=.5 -> kappa=.4
        pairs = [("Y", "Y")] * 20 + [("Y", "N")] * 5 + [("N", "Y")] * 10 + [("N", "N")] * 15
        self.assertAlmostEqual(A.kappa(pairs), 0.4)
        self.assertIsNone(A.kappa([("Y", "Y")] * 4))

    def test_label_agreement(self):
        a = ["P"] * 20 + ["P"] * 5 + [None] * 10 + [None] * 15
        b = ["P"] * 20 + [None] * 5 + ["P"] * 10 + [None] * 15
        r = A.label_agreement(labels(a), labels(b), n=200)
        P = r["layers"]["P"]
        self.assertAlmostEqual(P["kappa"], 0.4)
        self.assertAlmostEqual(P["gate"], 0.32)
        self.assertEqual(P["verdict"], "review")
        self.assertTrue(P["lo"] <= 0.4 <= P["hi"])
        self.assertTrue(r["D1"]["ok"])
        self.assertNotIn("ALL", r["layers"])            # some items have no label -> not single-label

    def test_multiclass_kappa_and_verdicts(self):
        a = ["u", "v", "w", "u", "v", "w"] * 6
        r = A.label_agreement(labels(a), labels(a), n=50)
        self.assertEqual(r["layers"]["ALL"]["kappa"], 1.0)
        self.assertEqual(r["layers"]["ALL"]["verdict"], "go")
        self.assertEqual(A.verdict(0.39), "fix")

    def test_span_agreement(self):
        r = A.span_agreement(many(10), many(10, shift=1), n=50)
        self.assertEqual(r["layers"]["X"]["exact"]["f1"], 0.0)
        self.assertEqual(r["layers"]["X"]["overlap"]["f1"], 1.0)
        self.assertEqual(r["layers"]["X"]["overlap"]["gate"], 0.8)
        self.assertFalse(r["D1"]["ok"])


class TestConsensus(unittest.TestCase):
    def test_merge(self):
        a = doc(("a", [(0, 6, "X"), (10, 14, "Y"), (30, 33, "X")]))
        b = doc(("a", [(2, 8, "X"), (10, 14, "X"), (50, 55, "Y")]))
        merged, dis, st = K.consensus(a, b, n=20)
        it = merged["items"][0]
        self.assertEqual([(s["start"], s["end"], s["label"]) for s in it["spans"]], [(2, 6, "X")])
        kinds = sorted((d["teacher"], d["kind"]) for d in dis)
        self.assertEqual(kinds, [("a", "a_only"), ("a", "label_conflict"), ("b", "b_only"), ("b", "label_conflict")])
        self.assertEqual(len(it["ignore"]), 3)            # (10,14) once, (30,33), (50,55)
        self.assertEqual(st["agreed_spans"], 1)
        ex, dis2, _ = K.consensus(a, b, mode="exact", n=20)
        self.assertEqual(ex["items"][0]["spans"], [])
        self.assertEqual(len(dis2), 6)

    def test_union_and_scorable(self):
        a = doc(("a", [(0, 6, "X")]))
        b = doc(("a", [(2, 8, "X")]))
        merged, _, _ = K.consensus(a, b, how="union", n=10)
        self.assertEqual(merged["items"][0]["spans"][0], {"start": 0, "end": 8, "label": "X"})
        self.assertEqual(S.score(merged, merged, n=10)["layers"]["X"]["exact"]["f1"], 1.0)


class TestGateCompare(unittest.TestCase):
    def test_gate(self):
        sc = S.score(many(20, drop_every=4), many(20), n=200)
        lo = sc["layers"]["X"]["overlap"]["lo"]
        gates = {"layers": {"X": {"mode": "overlap", "gate": lo}, "Y": {"mode": "overlap", "iaa": 1.0},
                            "Z": {"mode": "exact", "gate": 0.1}}}
        r = G.check(sc, gates)["M1"]
        self.assertTrue(r["layers"]["X"]["pass"])
        self.assertEqual(r["layers"]["Y"]["gate"], 0.8)
        self.assertFalse(r["layers"]["Z"]["pass"])
        self.assertFalse(r["pass"])
        md = G.report({"M1": r}, sc, {"task": "T0"})
        self.assertIn("| Layer | Metric | Score | 95% interval", md)
        self.assertIn("FAIL (layer missing from score)", md)
        iaa = A.span_agreement(many(20), many(20), n=20)
        self.assertTrue(G.check(S.score(many(20), many(20), n=20), G.gates_from_agreement(iaa, "exact"))["M1"]["pass"])

    def test_compare(self):
        ref = many(20)
        empty = doc(*[(f"i{i}", []) for i in range(20)])
        r = C.compare(ref, [empty], [ref], n=200)["layers"]["ALL"]["overlap"]
        self.assertEqual((r["diff"], r["verdict"]), (1.0, "better"))
        r = C.compare(ref, [ref], [empty], n=200)["layers"]["ALL"]["overlap"]
        self.assertEqual(r["verdict"], "worse")
        r = C.compare(ref, [ref], [ref], n=200)["layers"]["ALL"]["exact"]
        self.assertEqual((r["diff"], r["verdict"]), (0.0, "no-difference"))
        self.assertEqual(C.compare(ref, [empty], [ref], n=50, seed=3), C.compare(ref, [empty], [ref], n=50, seed=3))

    def test_compare_m8_noise(self):
        ref = many(20)
        a = [many(20, drop_every=k) for k in (2, 3, 5)]
        b = [many(20, drop_every=k) for k in (3, 4, 6)]
        res = C.compare(ref, a, b, n=200)
        r = res["layers"]["ALL"]["exact"]
        self.assertIn("run_sd", r)
        self.assertTrue(res["meta"]["m8_seeds_ok"])
        if not r["m8_exceeds_noise"]:
            self.assertEqual(r["verdict"], "no-difference")


if __name__ == "__main__":
    unittest.main()
