"""Unit tests for xtest/score.py. Run: /workspace/models/embed-zs/.venv/bin/python -I -m unittest discover -s tests -v   (from xtest/)."""
import unittest, sys, os, itertools, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from score import alpha_nominal, verdict, lint
def brute_alpha(M):
    """independent implementation: explicit pair loops over a list of rows (no coincidence matrix tricks)"""
    rows = [list(r) for r in M]; m = len(rows[0]); pairs = []
    for r in rows:
        for u, v in itertools.permutations(range(m), 2): pairs.append((r[u], r[v], 1.0 / (m - 1)))
    N = sum(p[2] for p in pairs); Do = sum(p[2] for p in pairs if p[0] != p[1])
    counts = {}
    for a, b, wt in pairs: counts[a] = counts.get(a, 0) + wt
    De = sum(counts[c] * counts[k] for c in counts for k in counts if c != k) / (N - 1)
    return 1 - Do / De
class T(unittest.TestCase):
    def test_perfect_and_hand_case(self):
        self.assertAlmostEqual(alpha_nominal([[0, 0], [1, 1], [0, 0], [1, 1]]), 1.0)
        # hand case: 10 items, 2 raters, 2 disagreements, 4 yes of 10 for rater A, 4 for B -> Do=0.2, De=(20^2-(12^2+8^2))/(20*19)... computed by hand below
        A = [1, 1, 1, 1, 0, 0, 0, 0, 0, 0]; B = [1, 1, 1, 0, 1, 0, 0, 0, 0, 0]; M = np.stack([A, B], 1)
        n1, n0, N = 8, 12, 20; Do = 2 / 10; De = 2 * n1 * n0 / (N * (N - 1)); self.assertAlmostEqual(alpha_nominal(M), 1 - Do / De, places=12)
    def test_matches_brute_force_random(self):
        rng = np.random.RandomState(1)
        for _ in range(60):
            m = rng.randint(2, 5); K = rng.randint(2, 6); n = rng.randint(8, 40); M = rng.randint(0, K, (n, m)); M[0, 0] = 0; M[1, 0] = 1
            self.assertAlmostEqual(alpha_nominal(M), brute_alpha(M), places=10)
    def test_integer_weight_equals_duplicates(self):
        rng = np.random.RandomState(2); M = rng.randint(0, 3, (30, 3)); w = rng.randint(1, 4, 30); dup = np.repeat(M, w, axis=0)
        self.assertAlmostEqual(alpha_nominal(M, w), alpha_nominal(dup), places=10)
    def test_unit_weights_equal_no_weights(self):
        M = np.random.RandomState(3).randint(0, 4, (50, 2)); self.assertAlmostEqual(alpha_nominal(M), alpha_nominal(M, np.ones(50)))
    def test_symmetric_in_raters_and_labels(self):
        M = np.random.RandomState(4).randint(0, 3, (40, 3)); self.assertAlmostEqual(alpha_nominal(M), alpha_nominal(M[:, ::-1]), places=12); self.assertAlmostEqual(alpha_nominal(M), alpha_nominal((M + 1) % 3), places=12)
    def test_verdict_edges(self):
        self.assertEqual(verdict(0.80, 0.9), "CLEAR"); self.assertEqual(verdict(0.70, 0.9), "TENTATIVE"); self.assertEqual(verdict(0.5, 0.66), "REJECT"); self.assertEqual(verdict(0.55, 0.70), "BORDERLINE"); self.assertEqual(verdict(0.667, 0.7), "TENTATIVE")
    def card(self, **kw):
        c = {"tasks_file_dataset_hash": "H", "instruction_sha256": {"presence": "I"}, "guideline_sha256": "G", "decoding_declared": "t0", "n_tasks": 100, "n_ok": 100, "n_failed": 0, "n_not_attempted": 0, "order_seed": 0}; c.update(kw); return c
    def runs(self, mod=None):
        mod = mod or {}; R = {}
        for r in ("a", "b"):
            R[(r, "A", 0)] = (self.card(**mod.get((r, "A", 0), {})), {}); R[(r, "A", 1)] = (self.card(**{**{"order_seed": 1}, **mod.get((r, "A", 1), {})}), {}); R[(r, "P", 0)] = (self.card(**mod.get((r, "P", 0), {})), {})
        return R
    B = {"dataset_hash": {"A": "H"}, "guideline_sha256": "G", "selection": {"blind": True}, "question_types": {"presence": "noul"}, "n_items": 100}
    def test_lint_passes_clean(self): self.assertEqual(lint(".", self.B, self.runs(), ["a", "b"], ["presence"]), [])
    def test_lint_catches_each_defect(self):
        cases = {"instruction text differs": {("b", "A", 0): {"instruction_sha256": {"presence": "OTHER"}}}, "different task sets": {("b", "A", 0): {"tasks_file_dataset_hash": "X"}}, "decoding not declared": {("a", "A", 0): {"decoding_declared": "unspecified"}},
                 "more than 5%": {("a", "A", 0): {"n_ok": 80, "n_failed": 20}}, "under 95%": {("a", "P", 0): {"n_ok": 80}}, "order seeds": {("a", "A", 1): {"order_seed": 0}}, "guideline sha": {("a", "A", 0): {"guideline_sha256": "Z"}}}
        for why, mod in cases.items():
            out = lint(".", self.B, self.runs(mod), ["a", "b"], ["presence"]); self.assertTrue(any(why in x for x in out), (why, out))
    def test_lint_missing_control_and_unblind_selection(self):
        R = self.runs(); del R[("b", "P", 0)]; self.assertTrue(any("missing paraphrase" in x for x in lint(".", self.B, R, ["a", "b"], ["presence"])))
        B2 = dict(self.B, selection={"blind": False, "design": {"weights": {}}}); self.assertTrue(any("F2" in x for x in lint(".", B2, self.runs(), ["a", "b"], ["presence"])))
if __name__ == "__main__": unittest.main()
