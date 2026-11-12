"""Python mirror of lean/Admit.lean (T53). Markers: 0 notAdmissible, 1 tooFewItems, 2 belowBar, 3 meets. Numbers in thousandths. Checked against Admit.lean's own cases on import; route.py holds the same rule inline (not importable: it runs on import). Proves nothing about model accuracy; it fixes what a result may be called."""
MARKERS = {0: "notAdmissible", 1: "tooFewItems", 2: "belowBar", 3: "meets"}
def sized(n, e, low): return 384 * (low + e) * (1000 - (low + e)) <= 100 * n * e * e
def mark(judge, n, e, low, guess, bar, confirmed, rare):
    if judge not in ("validator", "outsideGold") or not confirmed: return 0
    if not sized(n, e, low): return 1
    return 3 if (bar <= low and guess < low and bar <= rare) else 2
_CASES = [(("outsideGold", 3000, 20, 850, 300, 800, True, 820), 3), (("outsideGold", 100, 20, 850, 300, 800, True, 0), 1), (("validator", 3000, 20, 850, 900, 800, True, 0), 2),
          (("outsideGold", 3000, 20, 850, 300, 800, True, 0), 2), (("claudeAgreement", 3000, 20, 842, 784, 800, True, 0), 0), (("outsideGold", 3312, 22, 663, 250, 800, False, 0), 0), (("outsideGold", 1600, 20, 779, 100, 800, True, 0), 2)]
assert all(mark(*a) == b for a, b in _CASES), "Admit mirror differs from the Lean examples"
def stamp(judge_kind, n, lo, hi, guess, confirmed, bar=0.80, rare=0.0):
    """Row field: marker plus the words a page may use. lo, hi, guess, bar, rare are rates 0..1."""
    m = mark(judge_kind, n, round((hi - lo) / 2 * 1000), int(lo * 1000), int(guess * 1000), int(bar * 1000), confirmed, int(rare * 1000))
    ok = judge_kind in ("validator", "outsideGold")
    return {"judge_kind": judge_kind, "marker": MARKERS[m], "extractable": ok, "report_as": ("accuracy against an outside judge" if ok else "agreement with Sonnet only, not accuracy"), "mirror_of": "lean/Admit.lean"}
