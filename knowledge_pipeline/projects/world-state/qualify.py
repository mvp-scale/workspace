"""Field checks: Consensus verdict (sourced bands only). Krippendorff 2004 p.241: alpha >= 0.800 reliable, 0.667 to 0.800 tentative, below 0.667 discard.
Lean model and proofs: lean/Verdict.lean. Differential test: lean/verdict_test.py."""
def consensus_verdict(alpha):
    if alpha is None:
        return "Not measured"
    p = round(alpha * 1000)
    return "Clear" if p >= 800 else "Tentative" if p >= 667 else "Reject"
