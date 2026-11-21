"""Plan v2 step 1 check: no IPTC label-string joins in the new design's code. Exit 1 if any is found in CHECKED; PENDING files are listed (none since step 2: live_trace.py moved to CHECKED).
    python3 check_id_joins.py"""
import re, sys, os
H = os.path.dirname(os.path.abspath(__file__))
CHECKED = [H + "/pack_view.py", H + "/structure_pack.py", H + "/mnds_codes.py", H + "/../../simulation/server.py", H + "/live_trace.py"]
PENDING = []
PAT = re.compile(r'lab\([^)]*\)\)?\s*==|==\s*self\.pack\.lab|\["l1"\]\s+in\s|L1names\[|l1_guess')
def scan(fs):
    out = []
    for f in fs:
        for n, l in enumerate(open(f), 1):
            if PAT.search(l) and "never label names" not in l: out.append(f"{os.path.relpath(f, H)}:{n}: {l.strip()[:120]}")
    return out
bad = scan(CHECKED); pend = scan(PENDING)
print("checked files, label joins:", len(bad)); [print("  FAIL", b) for b in bad]
print("pending (step 2):", len(pend)); [print("  ", p) for p in pend]
sys.exit(1 if bad else 0)
