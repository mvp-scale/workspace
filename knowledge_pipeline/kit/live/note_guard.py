"""Pre-check for a ledger note before `node cp.mjs note ...` (owner, 2026-11-04: keep the ledger accurate). Catches the cheap, mechanical error classes only; it cannot check that a number is right.
    python3 note_guard.py "note text"     exit 0 = clean, exit 1 = reasons printed.   python3 note_guard.py --audit   re-checks past notes.
Rules: E1 comparison words (baseline, best, gain, improved, beats, new best) need a cited source (a runs/ or .json/.py path, an L-number or MM3-number).  E2 a hedged figure (~, about, roughly, approx) next to a rate, limit or bar needs the words 'computed' or 'estimate'.  E3 an absolute (cannot, never, impossible, proved, no reader) needs 'Lean', 'MM3-' or 'tried' (the scope).  E4 'Ready' or 'pass' needs the rule cited (L492-L495 or 'Ready rule')."""
import re, sys, json
SRC = re.compile(r"(runs/[\w./-]+|[\w./-]+\.(json|py|npz|lean)|\bL\d{3}\b|MM3-\d{4}|score_end2end)")
def check(t):
    why = []
    if re.search(r"\bbaseline\b|\bnew best\b|\bbest (single|reader|so far)|\bboth up\b|\bfirst (story )?gain\b", t, re.I) and not SRC.search(t): why.append("E1 comparison without a cited source file or note id")
    if re.search(r"(~|\babout\b|\broughly\b|\bapprox\w*)\s*[\d.]+\s*(%|x|times)?", t, re.I) and re.search(r"\b(limit|bar|FPR|AUC)\b", t, re.I) and not re.search(r"computed|estimate|exact|measured|from the|slope|retract", t, re.I): why.append("E2 hedged figure next to a rate or bar without saying computed or estimate")
    if re.search(r"\b(cannot|can't|never|impossible|proved|proven|no reader)\b", t, re.I) and not re.search(r"Lean|MM3-\d|\btried\b|\bwe built\b|\bso far\b", t, re.I): why.append("E3 absolute statement without its scope (Lean, MM3 id, or 'tried')")
    if re.search(r"\b(is|are|now|already) (Ready|ready)\b|\bpasses? the (bar|rule)\b|\bclears? (the )?bars?\b", t) and not re.search(r"Ready rule|L49[2-5]|alpha band|bar rule|L621|L657", t, re.I): why.append("E4 a Ready or pass verdict without the rule it is judged by")
    return why
if __name__ == "__main__":
    if "--audit" in sys.argv:
        rows = [json.loads(l) for l in open("/workspace/knowledge_pipeline/.ledger/ledger.jsonl")]; bad = {"L624", "L626", "L630", "L631", "L644", "L645", "L655", "L657"}
        n = [r for r in rows if r.get("kind") == "note" and r.get("task") == "T21" and r.get("who") == "S3" and int(r["id"][1:]) >= 607]
        hit = [r["id"] for r in n if check(r["text"])]; print("notes checked", len(n), "flagged", len(hit)); print("known-bad caught:", sorted(bad & set(hit)), "missed:", sorted(bad - set(hit))); print("flagged but not on the known-bad list (to read):", sorted(set(hit) - bad))
        for r in n:
            if r["id"] in bad: print(r["id"], check(r["text"]))
        sys.exit(0)
    w = check(sys.argv[1]); [print("BLOCK:", x) for x in w]; sys.exit(1 if w else 0)
