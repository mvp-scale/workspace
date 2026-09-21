# v2 real-transcript scenes

All text is verbatim from downloaded public-domain sources (retrieval date 2026-09-21). Rebuild: `python build_scenes.py fetch && python build_scenes.py build` (fetch needs `pypdf` for the NTSB PDF). Raw files in /workspace/data/sources/scenes/. Whitespace/line-wrap is collapsed; nothing else is altered. Every `evidence_quote` was extracted from the fetched source by the script (one Colgan quote has a PDF-extraction space repaired: "demonstrat ed" to "demonstrated").

## challenger_lund_hat (216 words, 4 turns, 2 events, control=false)
- Source: https://history.nasa.gov/rogersrep/v1ch5.htm (Rogers Commission Report, Vol. 1, Ch. V). Public domain: US Government work.
- Why: Lund's own explanation of reversing his recommendation after "take off your engineering hat"; documents the inverted burden of proof. Events: Commission finding (management reversed "at the urging of Marshall") and Boisjoly's "prove beyond a shadow of a doubt" testimony.
- Limits: this is TESTIMONY (Feb 25 1986 Q&A), not a recording of the teleconference. Real-time pressure remarks (Hardy "appalled", Mulloy "next April") appear only as second-hand testimony, so were not used as turns. Post-hoc rationalization, not live manipulation.

## apollo13_problem_control (199 words, 25 turns, 2 events, control=true)
- Source: Apollo Flight Journal, Day 3 part 2 (https://www.nasa.gov/history/afj/ap13fj/08day3-problem.html); fetched from web.archive.org snapshot 20240311202646 because the live URL now serves a generic page. Public domain: NASA transcript (US Government work). Journal commentary interleaved on the page is omitted from turns.
- Why: real urgency, terse cooperation, mutual correction, no manipulation; a good false-positive check. Mixes air-to-ground and flight-director loops (labels as printed).
- Limits: both documented events are Flight Journal editorial commentary (NASA-hosted, contributor-written), not the Review Board report. Interleaved overlapping speech at the start.

## colgan3407_icing_chat (223 words, 13 turns, 2 events, control=false)
- Source: NTSB AAR-10-01, https://www.ntsb.gov/investigations/AccidentReports/Reports/AAR1001.pdf, Appendix B CVR transcript 22:11:42.5 to 22:12:37.6. Public domain: US Government work.
- Why: deferential first officer ("I don't know if that's what you want"), confessed inexperience, captain steering to war stories; NTSB names failure to adhere to sterile-cockpit procedures as a contributing factor and notes neither pilot corrected the other.
- Limits: NTSB does not analyse the pitch-hold line itself; the events are about sterile-cockpit conversation and mutual non-correction. Weak-to-moderate hedging test. Speaker labels are mine mapped from CVR codes (HOT-1 Captain, HOT-2 First Officer, APP, RDO-2).

## nixon_haldeman_0623_cia_fbi (154 words, 10 turns, 2 events, control=false)
- Source: Watergate Special Prosecution Force transcript of the 23 June 1972, 10:04-11:39 AM Oval Office conversation, https://www.nixonlibrary.gov/forresearchers/find/tapes/watergate/wspf/741-002.pdf (live URL 404s; fetched from web.archive.org copy, 2020). Public domain: US Government work (WSPF / NARA / Nixon Library).
- Why: the "smoking gun" exchange; Haldeman proposes and Nixon assents to using Helms/Walters to stop the FBI. Events: Nixon Library abstract of the conversation (https://www.nixonlibrary.gov/watergate-trial-tapes) and House Judiciary Committee Statement of Information Book II para. 31 (archive.org statementofinfor02unit; US Congress publication).
- Limits: the HJC paragraph is sourced to Haldeman's testimony and Nixon's 1973 statement, not to the tape. The pressure here is mutual assent, not visible resistance, and the excerpt is the planning stretch, not the later "period!" instruction. Transcript is the prosecution's, not the later, more accurate NARA transcript. Cut ends mid-turn ([...]). One OCR hyphenation ("inves- tigation") repaired in a quote.

## Skipped
- LBJ/Richard Russell (29 Nov 1963): no fetchable public-domain transcript found (Miller Center URLs 404, re-use terms unverified; FRUS search returned nothing relevant on the second pass).
- Air Florida 90 (NTSB AAR-82-8): PDF downloaded but scanned (no text layer), no OCR available.
