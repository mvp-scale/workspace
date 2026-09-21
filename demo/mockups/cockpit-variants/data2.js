/* Adds the "us" side to the invented scripts: who we are, our own signals (guidance), key-point checklists.
   Loaded after ../data.js. All tags are scripted MOCK annotations. */
(function () {
  const by = (id) => window.MockScenarios.find((s) => s.id === id);
  const GUIDE = [
    { code: "ASK", label: "Questions asked", prompt: "We ask a direct or open question", side: "us" },
    { code: "KEY", label: "Key points made", prompt: "We state one of the points we planned to make", side: "us" },
    { code: "HDG", label: "Hedging", prompt: "We soften or hedge what we say", side: "us" }];
  const setup = (s, us, checklist, drop, extra) => {
    s.us = us; s.watch.forEach((w) => { w.side = "them"; }); s.watch.push(...GUIDE.map((g) => ({ ...g })));
    s.marks = s.marks.filter((m) => !drop.includes(m.turn)).concat(extra); s.checklist = checklist;
  };

  /* sales: we are the Rep */
  let s = by("sales"); s.turns[4].text = "Understood. If we could maybe get you live in a week, would that change things?";
  setup(s, ["Rep"], [{ id: "pain", label: "Ask about their pain" }, { id: "pitch", label: "Position one-week go-live" }, { id: "signer", label: "Find who signs" }, { id: "next", label: "Secure a next step" }], [],
    [{ turn: 0, phrase: "what is slowing your team down", code: "ASK", p: 0.9, note: "Open question about pain", check: "pain" },
     { turn: 2, phrase: "Have you looked at anything to fix it?", code: "ASK", p: 0.86, note: "Explores alternatives" },
     { turn: 4, phrase: "maybe", code: "HDG", p: 0.72, note: "Hedge on the one-week promise" },
     { turn: 4, phrase: "get you live in a week", code: "KEY", p: 0.9, note: "Value point: live in a week", check: "pitch" },
     { turn: 6, phrase: "Who else needs to be involved in the decision?", code: "ASK", p: 0.93, note: "Finds the signer", check: "signer" },
     { turn: 8, phrase: "Could we get her on a call this week?", code: "KEY", p: 0.88, note: "Asks for the next step", check: "next" }]);

  /* meeting: we are the buyers (Dana, Sam) */
  s = by("meeting"); s.turns[2].text = "Your competitor quoted us 92 thousand. Can you explain the gap?";
  setup(s, ["Dana (Buyer)", "Sam (Buyer)"], [{ id: "anchor", label: "Anchor with the competitor quote" }, { id: "writing", label: "Get terms in writing" }, { id: "constraint", label: "State the signing constraint" }], [2, 4, 7, 9],
    [{ turn: 0, phrase: "if we can", code: "HDG", p: 0.7, note: "Softens the ask" },
     { turn: 2, phrase: "competitor quoted us 92 thousand", code: "KEY", p: 0.88, note: "Competitor anchor stated", fact: ["Competitor quote", "92k"], check: "anchor" },
     { turn: 2, phrase: "Can you explain the gap?", code: "ASK", p: 0.9, note: "Direct question" },
     { turn: 4, phrase: "What is the gap made of?", code: "ASK", p: 0.88, note: "Follow-up when dodged" },
     { turn: 7, phrase: "I need it in writing today", code: "KEY", p: 0.87, note: "Written terms requested", check: "writing" },
     { turn: 9, phrase: "we cannot sign before the twentieth", code: "KEY", p: 0.8, note: "Signing constraint stated", fact: ["Earliest signature", "the 20th (legal review)"], check: "constraint" }]);

  /* support: we are the Agent */
  s = by("callcenter");
  setup(s, ["Agent"], [{ id: "ack", label: "Acknowledge the problem" }, { id: "verify", label: "Verify the account" }, { id: "confirm", label: "Confirm the issue" }, { id: "offer", label: "Make an offer" }], [4, 6],
    [{ turn: 0, phrase: "how can I help today?", code: "ASK", p: 0.85, note: "Opens the call" },
     { turn: 2, phrase: "I am sorry about that", code: "KEY", p: 0.86, note: "Acknowledges the problem", check: "ack" },
     { turn: 2, phrase: "Can I have your account number?", code: "ASK", p: 0.9, note: "Verification question", check: "verify" },
     { turn: 4, phrase: "two charges of 79 dollars on the fourth", code: "KEY", p: 0.84, note: "Confirms the duplicate charge", fact: ["Issue", "Duplicate 79 USD charge on the 4th"], check: "confirm" },
     { turn: 6, phrase: "refund one charge now", code: "KEY", p: 0.9, note: "Offers a refund", fact: ["Offer made", "Refund now + 2nd within 2 days + 1 month free"], check: "offer" }]);
  s.marks.push({ turn: 6, phrase: "add a month free", code: "KEY", p: 0.7, note: "Adds goodwill" });

  /* emergency: we are the Dispatcher */
  s = by("dispatch");
  setup(s, ["Dispatcher"], [{ id: "addr", label: "Get the address" }, { id: "breath", label: "Check breathing" }, { id: "others", label: "Ask who else is there" }, { id: "safety", label: "Give the safety instruction" }, { id: "units", label: "Confirm units on the way" }], [],
    [{ turn: 0, phrase: "what is the address of the emergency?", code: "ASK", p: 0.92, note: "Asks for location", check: "addr" },
     { turn: 2, phrase: "Is your father breathing?", code: "ASK", p: 0.94, note: "Breathing check", check: "breath" },
     { turn: 4, phrase: "Are there other people in the house?", code: "ASK", p: 0.9, note: "Who else is there", check: "others" },
     { turn: 6, phrase: "Get the children out of the house now", code: "KEY", p: 0.93, note: "Safety instruction", check: "safety" },
     { turn: 6, phrase: "do not use any switches", code: "KEY", p: 0.86, note: "Gas safety instruction" },
     { turn: 8, phrase: "Units are on the way", code: "KEY", p: 0.9, note: "Confirms dispatch", check: "units" }]);

  window.MockCockpit = ["sales", "meeting", "callcenter", "dispatch"].map(by);
})();
