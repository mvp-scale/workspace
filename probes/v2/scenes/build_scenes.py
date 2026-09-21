#!/usr/bin/env python3
"""Reproducible build of the v2 real-transcript scenes.

Usage:  python build_scenes.py fetch   # download raw sources (retrieved 2026-09-21)
        python build_scenes.py build   # cut excerpts + write <slug>.json
Raw files: /workspace/data/sources/scenes/  (git-ignored)
The NTSB PDF is a text-layer PDF; extraction needs `pypdf` (pip install pypdf,
or set PYPDF_PATH to a dir containing it). Nothing is paraphrased: turns are
verbatim contiguous excerpts; whitespace/line-wrap is collapsed to single spaces.
"""
import html, json, os, re, subprocess, sys
RAW = "/workspace/data/sources/scenes"
OUT = os.path.dirname(os.path.abspath(__file__))
U_ROGERS = "https://history.nasa.gov/rogersrep/v1ch5.htm"
U_A13 = "https://web.archive.org/web/20240311202646id_/https://www.nasa.gov/history/afj/ap13fj/08day3-problem.html"
U_A13_CANON = "https://www.nasa.gov/history/afj/ap13fj/08day3-problem.html"
U_WSPF = "https://web.archive.org/web/2020id_/https://www.nixonlibrary.gov/forresearchers/find/tapes/watergate/wspf/741-002.pdf"
U_WSPF_CANON = "https://www.nixonlibrary.gov/forresearchers/find/tapes/watergate/wspf/741-002.pdf"
U_NIXLIB = "https://www.nixonlibrary.gov/watergate-trial-tapes"
U_SOI2 = "https://archive.org/download/statementofinfor02unit/statementofinfor02unit_djvu.txt"
U_NTSB = "https://www.ntsb.gov/investigations/AccidentReports/Reports/AAR1001.pdf"

def sh(*a): subprocess.check_call(a)
def fetch():
    os.makedirs(RAW, exist_ok=True)
    sh("curl", "-sL", "--compressed", "-m", "120", "-o", f"{RAW}/rogers_ch5.html", U_ROGERS)
    sh("curl", "-sL", "--compressed", "-m", "120", "-o", f"{RAW}/a13_problem.html", U_A13)
    sh("curl", "-sL", "-m", "300", "-o", f"{RAW}/AAR1001.pdf", U_NTSB)
    detag("rogers_ch5.html", "rogers_ch5.txt"); detag("a13_problem.html", "a13_problem.txt")
    sh("curl", "-sL", "-m", "120", "-o", f"{RAW}/wspf741-002.pdf", U_WSPF)
    sh("curl", "-sL", "--compressed", "-m", "120", "-o", f"{RAW}/nixlib_trial_tapes.html", U_NIXLIB)
    sh("curl", "-sL", "--compressed", "-m", "300", "-o", f"{RAW}/soi2.txt", U_SOI2)
    detag("nixlib_trial_tapes.html", "nixlib_trial_tapes.txt")
    if PYPDF_OK():
        from pypdf import PdfReader
        for pdf, txt in (("AAR1001.pdf", "AAR1001.txt"), ("wspf741-002.pdf", "wspf741-002.txt")):
            r = PdfReader(f"{RAW}/{pdf}")
            open(f"{RAW}/{txt}", "w").write("".join(f"\n=====PAGE {i+1}=====\n" + (p.extract_text() or "") for i, p in enumerate(r.pages)))
def PYPDF_OK():
    if os.environ.get("PYPDF_PATH"): sys.path.insert(0, os.environ["PYPDF_PATH"])
    try: import pypdf; return True
    except ImportError: return False
def detag(src, dst):
    t = open(f"{RAW}/{src}", errors="ignore").read()
    open(f"{RAW}/{dst}", "w").write(html.unescape(re.sub(r"<[^>]+>", "", t)))
def norm(s): return re.sub(r"\s+", " ", s).strip()
def rd(n): return open(f"{RAW}/{n}", errors="ignore").read()

def between(text, a, b, incl_b=True):
    text = norm(text)  # search on whitespace-collapsed text (source is hard-wrapped)
    i = text.index(a); j = text.index(b, i)
    return text[i:j + (len(b) if incl_b else 0)]

def wc(turns): return sum(len(t["text"].split()) for t in turns)
def write(d):
    d["duration_estimate_seconds"] = d.get("duration_estimate_seconds") or round(wc(d["turns"]) / 2.5)
    json.dump(d, open(f"{OUT}/{d['slug']}.json", "w"), indent=2, ensure_ascii=False)
    print(d["slug"], "words", wc(d["turns"]), "turns", len(d["turns"]), "events", len(d["documented_events"]))

# ---------------- Scene 1: Challenger, Lund testimony (Q&A) ----------------
def challenger():
    t = rd("rogers_ch5.txt")
    t = norm(t)
    seg = t[t.index("Chairman Rogers: How do you explain the fact"):]
    end = "the roles kind of switched."
    seg = seg[:seg.index(end) + len(end)]
    parts = re.split(r"(Chairman Rogers:|Mr\. Lund:)", seg)
    turns = []
    for k in range(1, len(parts), 2):
        turns.append({"speaker": {"Chairman Rogers:": "Chairman Rogers", "Mr. Lund:": "Robert Lund (Thiokol VP Engineering)"}[parts[k]], "text": norm(parts[k + 1])})
    # the source has a stray '.' line after Lund's last sentence block; kept only if inside range
    fin = norm(between(t, "4. The Commission concluded that the Thiokol", "in order to accommodate a major customer."))
    boi = norm(between(t, "One of my colleagues that was in the meeting", "usually exactly opposite that."))
    write({
      "slug": "challenger_lund_hat", "title": "Challenger launch decision: Lund explains changing his position (Rogers Commission testimony)",
      "date": "1986-02-25 (testimony about the 1986-01-27 teleconference)",
      "setting": "Public hearing testimony, Rogers Commission, of Robert Lund (Morton Thiokol VP Engineering), asked by Chairman William Rogers why he changed his recommendation on the night of 27 Jan 1986 after Jerry Mason asked him to 'take off his engineering hat and put on his management hat'. THIS IS TESTIMONY (a Q&A), not a recording of the teleconference.",
      "source_url": U_ROGERS, "public_domain_basis": "Report of a US federal presidential commission published by NASA (US Government work, 17 U.S.C. 105).",
      "control": False, "turns": turns,
      "documented_events": [
        {"turn_index": 1, "what_happened": "Thiokol engineers/management describe being put in the position of having to prove the launch was unsafe (reversal of the usual burden of proof), under Marshall pressure; the Commission concluded Thiokol management reversed its position at Marshall's urging.",
         "evidence_source_url": U_ROGERS, "evidence_quote": fin},
        {"turn_index": 1, "what_happened": "Engineer Roger Boisjoly's testimony independently characterises the meeting as one where the burden of proof was inverted.",
         "evidence_source_url": U_ROGERS, "evidence_quote": boi}],
      "notes": "Scene is post-hoc testimony; it documents rationalisation/role-shift rather than real-time pressure. The pressure remarks themselves (Hardy 'appalled', Mulloy 'next April') appear in the same chapter only as second-hand testimony and are not used as turns. Cut: contiguous Q&A from Chairman Rogers's question to the end of Lund's second answer (source omits a blank/stray period line)."})

# ---------------- Scene 2: Apollo 13 (control) ----------------
def apollo13():
    t = rd("a13_problem.txt")
    lines = t.split("\n")
    pat = re.compile(r"^(\d{3}:\d\d:\d\d) ([A-Za-z]+)(?: \(([A-Z]+)\))?: (.*)$")
    start, end = "055:55:19", "055:56:40"
    on = False; turns = []
    for ln in lines:
        m = pat.match(ln.strip())
        if not m: continue
        if m.group(1) == start: on = True
        if on:
            sp = m.group(2) + (f" ({m.group(3)})" if m.group(3) else "")
            turns.append({"speaker": sp, "text": norm(m.group(4))})
        if on and m.group(1) == end: break
    idx = {tt["text"][:12]: i for i, tt in enumerate(turns)}
    i_lovell = next(i for i, x in enumerate(turns) if x["text"].startswith("[Garble.] Ah, Houston"))
    i_haise = next(i for i, x in enumerate(turns) if x["speaker"] == "Haise")
    q1 = norm(between(t, "The legendary line delivered by Lovell is", "putting it into the top three of misquoted movies"))
    q2 = norm(between(t, "Although both the crew and the mission controllers are suspecting", "the bang is a genuine worry."))
    write({
      "slug": "apollo13_problem_control", "title": "Apollo 13: 'Houston, we've had a problem' (control)",
      "date": "1970-04-13 (GET 055:55:19 to 055:56:40)",
      "setting": "Air-to-ground loop plus Mission Control flight-director loop, minutes after the oxygen tank explosion. Speaker labels are as printed in the Apollo Flight Journal. Journal commentary and photo captions interleaved in the web page are omitted (transcript lines only, in original order, one contiguous time range).",
      "source_url": U_A13_CANON, "public_domain_basis": "NASA mission transcript (US Government work). The Journal's editorial commentary is not used except as evidence quotes. Retrieved via a web.archive.org copy (%s) because the live NASA URL now redirects to a generic page." % U_A13,
      "control": True, "turns": turns,
      "documented_events": [
        {"turn_index": i_lovell, "what_happened": "Lovell's report of the anomaly; the actual wording was 'Houston, we've had a problem', a calm cooperative report, not the film's 'we have a problem'.", "evidence_source_url": U_A13_CANON, "evidence_quote": q1},
        {"turn_index": i_haise, "what_happened": "Crew and controllers initially treat the event as a probable instrumentation false alarm while the crew report a real bang.", "evidence_source_url": U_A13_CANON, "evidence_quote": q2}],
      "notes": "Real urgency, terse cooperation, no manipulation. Both documented events are commentary from the Apollo Flight Journal (NASA-hosted, contributor-written), not an official investigation; the Apollo 13 Review Board report was not fetched. Timestamps stripped from turns. Overlap in first two turns is in the source."})

# ---------------- Scene 3: Colgan 3407 CVR ----------------
def colgan():
    p = f"{RAW}/AAR1001.txt"
    if not os.path.exists(p):
        sys.exit("AAR1001.txt missing: need pypdf to extract AAR1001.pdf (see docstring)")
    t = rd("AAR1001.txt")
    i = t.index("22:11:42.5"); j = t.index("22:12:37.6", i)
    j = t.index("yeah uh I I spent the first three months", j)
    # end after the captain's line at 22:12:37.6
    tail = t[j:]; k = tail.index("flew—.") + len("flew—.")
    seg = t[i:j + k]
    seg = re.sub(r"=====PAGE \d+=====\s*NTSB Aircraft Accident Report\s*INTRA-AIRCRAFT COMMUNICATION AIR-GROUND COMMUNICATION\s*TIME and\s*TIME and\s*SOURCE CONTENT\s*SOURCE\s+CONTENT\s*\d+\s*", "", seg)
    blocks = re.findall(r"(\d\d:\d\d:\d\d\.\d)\s*\n\s*([A-Z]+-?\d?)\s*\n(.*?)(?=\n\s*\d\d:\d\d:\d\d\.\d\s*\n|\Z)", seg, re.S)
    names = {"HOT-1": "Captain (cockpit)", "HOT-2": "First Officer (cockpit)", "APP": "Approach controller (radio)", "RDO-2": "First Officer (radio)"}
    turns = [{"speaker": names[s], "text": norm(x)} for _, s, x in blocks]
    i_ice = next(n for n, x in enumerate(turns) if x["text"].startswith("I've never seen icing"))
    i_pitch = next(n for n, x in enumerate(turns) if "pitch hold" in x["text"])
    q = norm(between(t, "The pilots were involved in nonpertinent conversation during all phases of flight", "distracted them from their operational tasks."))
    q2 = norm(between(t, "The NTSB is concerned that, during the accident flight, neither pilot seemed hesitant", "was not unusual.")).replace("demonstrat ed", "demonstrated")  # pypdf extraction artifact (source PDF reads "demonstrated")
    write({
      "slug": "colgan3407_icing_chat", "title": "Colgan 3407: first officer's icing confession and pitch-hold hedge",
      "date": "2009-02-12 UTC (CVR 22:11:42.5 to 22:12:37.6, about five minutes before the stall)",
      "setting": "Cockpit voice recorder transcript (Appendix B of NTSB AAR-10-01), Bombardier Q400, descending toward Buffalo in icing conditions. HOT = cockpit area/hot mic; radio calls interleaved in original time order. Time stamps and page-break headers removed.",
      "source_url": U_NTSB, "public_domain_basis": "NTSB accident report (US Government work, 17 U.S.C. 105).",
      "control": False, "turns": turns,
      "documented_events": [
        {"turn_index": i_ice, "what_happened": "Non-pertinent conversation during descent (sterile-cockpit violation) about the first officer's lack of icing experience; the NTSB lists the failure to adhere to sterile cockpit procedures as a contributing factor.", "evidence_source_url": U_NTSB, "evidence_quote": q},
        {"turn_index": i_pitch, "what_happened": "First officer flags the autopilot mode to the captain in hedged form; NTSB notes neither pilot corrected the other's procedural deviations.", "evidence_source_url": U_NTSB, "evidence_quote": q2}],
      "notes": "Honest limits: this is a hedge of a different kind (deferential, low-assertiveness phrasing 'I don't know if that's what you want'), not the stall-phase failure. The second event's quote is about sterile cockpit deference in general; NTSB does not specifically analyse the 'pitch hold' line. Consider it a weak-to-moderate test."})

# ---------------- Scene 4: Nixon-Haldeman 23 June 1972 ----------------
def nixon():
    t = rd("wspf741-002.txt")
    t = re.sub(r"=====PAGE \d+=====\s*(JUNE 23, 1972 FROM 10:04 TO 11:39 AM \d+)?", " ", t)  # page headers only
    t = norm(t)
    a = t.index("HALDEMAN: and they seem to feel the thing to do is get")
    endm = "have nothing to do with ourselves."
    b = t.index(endm, a) + len(endm)
    seg = t[a:b]
    parts = re.split(r"(?:(?<=\s)|^)(HALDEMAN|PRESIDENT):", seg)
    turns = []
    for k in range(1, len(parts), 2):
        turns.append({"speaker": {"HALDEMAN": "H. R. Haldeman", "PRESIDENT": "President Nixon"}[parts[k]], "text": norm(parts[k + 1])})
    turns[-1]["text"] += " [...]"  # cut mid-turn: the President's turn continues in the source
    i_appr = next(i for i, x in enumerate(turns) if x["text"].startswith("All right, fine.") and i > 0 and "call them in" in turns[i-1]["text"])
    i_hunt = next(i for i, x in enumerate(turns) if "very detrimental" in x["text"])
    lib = norm(between(rd("nixlib_trial_tapes.txt"), "Haldeman and Nixon discuss the progress of the FBI", "national security operation."))
    hjc = norm(between(rd("soi2.txt"), "The President directed Haldeman to ask Walters to meet with Gray", "earlier activities of the Watergate principals.")).replace("inves- tigation", "investigation")  # OCR line-end hyphenation
    write({
      "slug": "nixon_haldeman_0623_cia_fbi", "title": "Nixon and Haldeman plan to use the CIA against the FBI (\"smoking gun\", 23 June 1972)",
      "date": "1972-06-23 (Oval Office, 10:04 to 11:39 AM conversation)",
      "setting": "Oval Office tape, Watergate Special Prosecution Force transcript (NARA / Nixon Library). Excerpt is one contiguous stretch in the middle of the conversation; page-break headers removed; '(unintelligible)/(REMOVED)' marks, if any, are the transcript's own. Speaker labels expanded from PRESIDENT / HALDEMAN.",
      "source_url": U_WSPF_CANON, "public_domain_basis": "Official transcript prepared by the Watergate Special Prosecution Force (US Government work) of a recording made by the White House; held by NARA / Nixon Presidential Library. Fetched via a web.archive.org copy (%s) because the live Nixon Library URL now returns 404." % U_WSPF,
      "control": False, "turns": turns,
      "documented_events": [
        {"turn_index": i_appr, "what_happened": "President approves Haldeman's plan to have the CIA (Helms/Walters) tell the FBI to hold off its Watergate inquiry.", "evidence_source_url": U_NIXLIB, "evidence_quote": lib},
        {"turn_index": i_hunt, "what_happened": "President frames the request in terms of concealing earlier covert activities (Hunt) so the FBI investigation would not expand.", "evidence_source_url": U_SOI2, "evidence_quote": hjc}],
      "notes": "This is a WSPF transcript of a difficult recording; the Nixon Library abstract quoted is the archive's own. Evidence quote 2 is the House Judiciary Committee Statement of Information (Book II, para. 31) description of the President's directions to Haldeman, sourced there to Haldeman's testimony and the President's May 22 1973 statement, not to this tape. Neither source labels the dynamic as manipulation; the scene is a plan to obstruct, with mutual assent and no visible resistance. Cut ends mid-turn ([...])."})

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "fetch": fetch()
    else:
        challenger(); apollo13(); colgan(); nixon()
