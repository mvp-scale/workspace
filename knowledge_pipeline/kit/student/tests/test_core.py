"""Unit tests for core.py (windows, owner, BIO, layering, decode, snap). Synthetic strings only; numpy only.

    python -m unittest discover -s knowledge_pipeline/kit/student/tests -v
"""
import pathlib
import random
import sys
import unittest

import numpy as np

KIT = pathlib.Path(__file__).resolve().parents[1]
REPO = KIT.parents[2]
sys.path.insert(0, str(KIT))
import core  # noqa: E402


def toy_tokens(text):
    """whitespace/punct split into ~3-char pieces with char offsets (stands in for WordPiece)"""
    offs, i = [], 0
    while i < len(text):
        if text[i].isspace():
            i += 1
            continue
        if not text[i].isalnum():
            offs.append((i, i + 1))
            i += 1
            continue
        j = i
        while j < len(text) and text[j].isalnum():
            j += 1
        for a in range(i, j, 3):
            offs.append((a, min(a + 3, j)))
        i = j
    return offs


class TestWindows(unittest.TestCase):
    def test_short(self):
        self.assertEqual(core.starts_of(10), [0])
        self.assertEqual(core.starts_of(254), [0])

    def test_long_covers_all(self):
        for n in (255, 400, 446, 447, 1000, 2001):
            st = core.starts_of(n)
            self.assertEqual(st[0], 0)
            self.assertEqual(st[-1] + 254, n)          # last window ends at the last token
            covered = np.zeros(n, bool)
            for s in st:
                covered[s:s + 254] = True
            self.assertTrue(covered.all(), n)

    def test_owner_centrality(self):
        n = 600
        st = core.starts_of(n)
        own = core.owner(n, st)
        for p in range(n):
            ds = [min(p - s, min(s + 254, n) - 1 - p) if s <= p < s + 254 else -1 for s in st]
            self.assertEqual(own[p], int(np.argmax(ds)))   # first max wins ties

    def test_small_window(self):
        self.assertEqual(core.starts_of(10, 4, 3), [0, 3, 6])
        self.assertEqual(core.starts_of(11, 4, 3), [0, 3, 6, 7])


class TestBIO(unittest.TestCase):
    def test_bio_roundtrip(self):
        text = "Alpha Beta met Gammaray at the harbour."
        offs = toy_tokens(text)
        spans = [(0, 10), (15, 23)]
        col = core.bio(offs, spans)
        got = [tuple(s) for s in core.bio_spans(offs, col)]
        self.assertEqual(core.snap(text, got), spans)

    def test_orphan_i_starts_span(self):
        offs = [(0, 1), (2, 3), (4, 5)]
        self.assertEqual(core.bio_spans(offs, [0, 2, 2]), [[2, 5]])
        self.assertEqual(core.bio_spans(offs, [1, 1, 0]), [[0, 1], [2, 3]])

    def test_soft_bio(self):
        offs = [(0, 3), (3, 6), (7, 9)]
        t = core.soft_bio(offs, [(0, 6, 0.8)])
        np.testing.assert_allclose(t[0], [0.2, 0.8, 0.0], atol=1e-6)
        np.testing.assert_allclose(t[1], [0.2, 0.0, 0.8], atol=1e-6)
        np.testing.assert_allclose(t[2], [1.0, 0.0, 0.0])


class TestLayering(unittest.TestCase):
    def test_nested(self):
        spans = [(0, 20), (0, 5), (10, 20), (12, 15)]
        ch, drop = core.layer(spans, 2)
        self.assertEqual(ch[0], [(0, 20)])
        self.assertEqual(ch[1], [(0, 5), (10, 20)])
        self.assertEqual(drop, 1)
        self.assertEqual(core.layer(spans, 3)[1], 0)

    def test_channel_layout(self):
        heads = [{"name": "A", "channels": 2}, {"name": "B"}, {"name": "C", "channels": 3}]
        chs = core.channel_heads(heads)
        self.assertEqual(chs, ["A", "B", "C", "A", "C", "C"])
        self.assertEqual(core.head_channels(chs), {"A": [0, 3], "B": [1], "C": [2, 4, 5]})


class TestDecode(unittest.TestCase):
    def test_snap_widens_and_merges(self):
        text = "foobar baz"
        self.assertEqual(core.snap(text, [(1, 4)]), [(0, 6)])
        self.assertEqual(core.snap(text, [(0, 3), (3, 6)]), [(0, 6)])
        self.assertEqual(core.snap(text, [(7, 9)]), [(7, 10)])

    def test_union_of_channels(self):
        text = "Big Red Fox ran"
        offs = toy_tokens(text)          # Big Red Fox ran
        tags = np.zeros((len(offs), 3), np.int64)
        tags[0:3, 0] = [1, 2, 2]         # A: Big Red Fox
        tags[1, 2] = 1                   # A#2: Red
        tags[3, 1] = 1                   # B: ran
        out = core.decode(text, offs, tags, ["A", "B", "A"])
        self.assertEqual(out["A"], [(0, 11), (4, 7)])
        self.assertEqual(out["B"], [(12, 15)])

    def test_empty(self):
        self.assertEqual(core.decode("", [], None, ["A", "B"]), {"A": [], "B": []})

    def test_predict_windows_owner(self):
        rng = np.random.default_rng(1)
        n, nch = 700, 2
        truth = rng.integers(0, 3, (n, nch))

        def run_fn(x):   # logits that reproduce truth for the tokens of this window (CLS/SEP rows ignored)
            ids = x[0][1:-1]
            lg = np.zeros((len(ids) + 2, nch * 3), np.float32)
            for k, i in enumerate(ids):
                for c in range(nch):
                    lg[k + 1, c * 3 + truth[i, c]] = 1.0
            return lg, None
        tags, seqs = core.predict(run_fn, list(range(n)), -1, -2)
        np.testing.assert_array_equal(tags, truth)
        self.assertEqual(seqs, [])


class TestScore(unittest.TestCase):
    def test_f1(self):
        self.assertEqual(core.span_f1([[(0, 1)]], [[(0, 1)]]), 1.0)
        self.assertEqual(core.span_f1([[]], [[]]), 1.0)
        self.assertAlmostEqual(core.span_f1([[(0, 1), (2, 3)]], [[(0, 1)]]), 2 / 3, places=5)


class TestMatchesShippedClassifier(unittest.TestCase):
    """core vs pipeline/ship/we_classifier.py on random synthetic tags: same windows, owner and decode."""

    @classmethod
    def setUpClass(cls):
        sys.dont_write_bytecode = True   # read-only use of the shipped code: leave no .pyc next to it
        try:
            sys.path.insert(0, str(REPO / "pipeline" / "ship"))
            import we_classifier as WC
            cls.WC = WC
        except Exception as e:  # noqa: BLE001
            raise unittest.SkipTest(f"we_classifier not importable here: {e!r}")

    def test_windows_owner(self):
        for n in (1, 254, 255, 500, 1337):
            self.assertEqual(core.starts_of(n), self.WC.starts_of(n))
            np.testing.assert_array_equal(core.owner(n, core.starts_of(n)), self.WC.owner(n, self.WC.starts_of(n)))

    def test_decode(self):
        rnd = random.Random(7)
        words = ["alpha", "beta", "x", "Gamma", "delta-9", "eps,", "zeta.", "42", "eta's"]
        kinds = self.WC.KINDS
        for trial in range(30):
            text = " ".join(rnd.choice(words) for _ in range(40))
            offs = toy_tokens(text)
            nch = 6
            tags = np.array([[rnd.choice([0, 0, 0, 1, 2]) for _ in range(nch)] for _ in offs], np.int64)
            ref = self.WC.decode(text, offs, tags)
            chs = core.channel_heads([{"name": kinds[0], "channels": 2}] + [{"name": k} for k in kinds[1:]])
            got = core.decode(text, offs, tags, chs)
            self.assertEqual({k: [tuple(x) for x in v] for k, v in got.items()}, ref)


if __name__ == "__main__":
    unittest.main()
