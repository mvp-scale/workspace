#!/usr/bin/env python3
"""Guess a topic for each library dialogue (6+ turns) with a local model (SEMIF4), one `choice` question per dialogue.
Writes demo/static/dialogue-topics.json ({id: {topic, p}}). Topics are model guesses, shown as such in the cockpit.
Uses the demo server's /api/batch with a local backend only (never the hosted one). Re-run: python3 demo/build_dialogue_topics.py [backend] [out.json]"""
import json, sys, urllib.request
BASE, BACKEND, MIN_TURNS = "http://127.0.0.1:8100", (sys.argv[1] if len(sys.argv) > 1 else "semif"), 6
OUT = sys.argv[2] if len(sys.argv) > 2 else "/workspace/demo/static/dialogue-topics.json"
TOPICS = {
    "Family": "Parents, children, siblings or home life",
    "Romance": "A romantic relationship: dating, marriage, a breakup or jealousy",
    "Friends": "Friends or acquaintances talking, joking or falling out",
    "Work and business": "A job, a boss, a deal or a workplace",
    "Money": "Money, debt, a bribe or a payment",
    "Crime and violence": "Crime, violence, a threat, a killing or a cover-up",
    "Law and order": "Police, courts, prison or the law",
    "Health": "Illness, a doctor, addiction or medical care",
    "School": "School, teachers, students or studying",
    "War and mission": "War, the military, a mission or a rescue",
    "Other": "None of the above",
}
Q = {"type": "choice", "instructions": "What is the main setting or subject of this conversation?", "criteria": TOPICS}

def call(path, body=None):
    req = urllib.request.Request(BASE + path, json.dumps(body).encode() if body else None, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r: return json.load(r)

dl = [d for d in call("/api/dialogues")["dialogues"] if d["n_turns"] >= MIN_TURNS]
items = [{"state": "\n".join(f"{t['speaker']}: {t['text']}" for t in d["turns"]), "questions": {"topic": Q}} for d in dl]
out, res = {}, []
for i in range(0, len(items), 20): res += call("/api/batch", {"backend": BACKEND, "items": items[i:i + 20]})
for d, r in zip(dl, res):
    a = (r.get("answers") or {}).get("topic")
    if not a: print("no answer for", d["id"], r.get("error"), file=sys.stderr); continue
    pr = a["probabilities"]; top = max(pr, key=pr.get)
    out[d["id"]] = {"topic": top if pr[top] >= 0.5 else "Other", "p": round(pr[top], 2)}
json.dump({"model": BACKEND, "note": "Topics are guesses from a local model, one choice question per dialogue.", "min_turns": MIN_TURNS, "topics": out}, open(OUT, "w"), indent=1)
import collections; print(len(out), "dialogues;", dict(collections.Counter(v["topic"] for v in out.values())))
