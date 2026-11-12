"""Checks a round card against loop_permissions.json before run_round.py runs it. Exit 0 = free to run, exit 2 = needs the owner's yes (reasons printed).
    python3 loop_gate.py card.json"""
import json, sys, pathlib
P = json.load(open(pathlib.Path(__file__).with_name("loop_permissions.json"))); card = json.load(open(sys.argv[1]))
text = " ".join(str(card.get(k, "")) for k in ("command", "one_change", "question")).lower(); why = []
why += [f"mentions '{w}'" for w in P["keyword_flags"] if w in text]
if int(card.get("cap_minutes", 999)) > 60: why.append("cap_minutes over 60")
if card.get("needs_yes"): why.append("card marks needs_yes: " + str(card["needs_yes"]))
print("NEEDS OWNER YES: " + "; ".join(why) if why else "free to run"); sys.exit(2 if why else 0)
