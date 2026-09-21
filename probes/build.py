"""Probe sets that push typed decision models past the JevBench topics. Run: python3 probes/build.py

Every item has a known answer. Sets are built from minimal pairs (a manipulative message and an honest look-alike,
an attack and a benign version) so a model cannot win on surface cues. Authored by one author (Claude Sonnet 5) and
not cross-reviewed, unlike JevBench's hard tier, so read results as a probe, not a benchmark.
"""
import json
from pathlib import Path

OUT = Path(__file__).parent
SRC = {"exclude_reason": None, "source": "authored for this console (Claude Sonnet 5), single author, not cross-reviewed", "license": "MIT"}

def choice(name, family, instr, options, items):
    """options: {label: description}; items: [(label, state)]"""
    rows = []
    for i, (lab, state) in enumerate(items):
        rows.append({"id": f"{name}-{i:02d}", "family": family, "state": state, "group": None, "provenance": SRC, "split": "public",
                     "question": {"type": "choice", "instructions": instr, "criteria": options}, "labels": list(options), "expected": lab})
    return rows

def noul(name, family, instr, items, yes, no):
    rows = []
    for i, (ans, state) in enumerate(items):
        rows.append({"id": f"{name}-{i:02d}", "family": family, "state": state, "group": None, "provenance": SRC, "split": "public",
                     "question": {"type": "noul", "instructions": instr, "criteria": {"true": yes, "false": no}}, "labels": ["no", "yes"], "expected": ans})
    return rows

SETS = {}

SETS["manipulation"] = choice("manip", "manipulation",
    "Which persuasion tactic does this message use? Choose fair_appeal if it persuades honestly.",
    {"fair_appeal": "Honest appeal or information that respects the reader's ability to decide, including real deadlines that are explained",
     "false_urgency": "Manufactured time pressure or scarcity meant to stop the reader thinking",
     "guilt_trip": "Making the reader feel guilty or responsible for the speaker's feelings to get compliance",
     "gaslighting": "Denying or rewriting what the reader remembers so they doubt their own memory or judgement",
     "flattery_lovebomb": "Excessive praise or affection used to lower the reader's guard before a request",
     "false_dilemma": "Presenting only two options, one of them unacceptable, when others exist",
     "fear_threat": "Threatening harm or trouble to force compliance"},
    [("fair_appeal", "Our annual plan costs $120 instead of $10 a month, so it only saves money if you use the tool for 12 months or more. If you're not sure you'll stay a year, monthly is the safer choice."),
     ("fair_appeal", "I'd really like you to come to my talk on Friday. It covers the cache bug that cost us two weeks, and I think it will save your team the same pain. No pressure if the timing doesn't work; the slides will be shared afterwards."),
     ("fair_appeal", "The trial ends on the 30th. After that it converts to the paid plan at $15 a month, and you can cancel any time from Settings before then."),
     ("fair_appeal", "Most of the team switched to the new editor and reported fewer merge conflicts; here is the survey with the numbers. Try it for a week and tell me what you think."),
     ("fair_appeal", "I understand you're worried about the cost. Here is a breakdown of what each line item covers, and two cheaper options with what you'd give up."),
     ("fair_appeal", "If we don't renew the certificate before Monday, the site will show browser warnings to every visitor, because it expires at midnight on Sunday. I've drafted the renewal. Can you approve it?"),
     ("false_urgency", "ONLY 2 LEFT! 14 people are looking at this right now. Your cart will be released in 09:59, so buy now or lose it forever!"),
     ("false_urgency", "This offer disappears tonight and I can never offer it again. Don't think, don't ask anyone. Just sign now before it's too late."),
     ("guilt_trip", "After everything I've sacrificed for you, I can't believe you'd even think about moving out. I guess I'll just sit here alone. Don't worry about me."),
     ("guilt_trip", "Fine, go ahead and take the other job. I only stayed up all night fixing your mistakes, but I'm sure you're busy."),
     ("gaslighting", "That never happened. You always misremember things, you're being dramatic again. Ask anyone, they'll tell you that you're confused."),
     ("gaslighting", "I never said I'd pay for that. You must be imagining it. You have a terrible memory, remember the last time?"),
     ("flattery_lovebomb", "You're honestly the smartest person I've ever met, and only someone as generous as you would help me this once by sharing your login. I trust you completely."),
     ("flattery_lovebomb", "I've never felt this connected to anyone after only two days. You're my soulmate. Since you're so special, I know you'll send me the $800 for my flight."),
     ("false_dilemma", "Either you sign the contract as written today, or you're telling us you don't care about this project. There's no middle ground."),
     ("false_dilemma", "You're either with us on this vote or you're against the whole team. Pick a side."),
     ("fear_threat", "Nice little business you have here. It would be a shame if the health inspector got an anonymous tip about it. Think about renewing our 'protection' contract."),
     ("fear_threat", "Your account has been flagged. Pay the fee in gift cards within the hour or we will send the police to your address.")])

SETS["fallacies"] = choice("fallacy", "reasoning",
    "Which logical fallacy does this argument commit? Choose no_fallacy if the reasoning is sound.",
    {"ad_hominem": "Attacks the person making the argument instead of the argument",
     "straw_man": "Misrepresents the opponent's position and attacks the distorted version",
     "slippery_slope": "Claims one step will inevitably lead to an extreme outcome without support",
     "false_cause": "Treats correlation or sequence as causation",
     "appeal_to_authority": "Relies on someone who is not an expert on the subject as proof",
     "no_fallacy": "The reasoning is sound, or it criticises an argument on its merits"},
    [("ad_hominem", "Dr. Rao's argument for the new tax rule can't be trusted. He was fired from his last job and dresses like a slob."),
     ("ad_hominem", "Why listen to her climate proposal? She drives a big SUV."),
     ("ad_hominem", "You can ignore his critique of our budget. He's just a bitter man who never finished college."),
     ("straw_man", "Marta said we should spend less on office snacks. So she wants our employees to starve and doesn't care about morale at all."),
     ("straw_man", "Senator Lee wants stricter rules for bridge inspections, which means he thinks every engineer is a criminal."),
     ("straw_man", "I said we should test the app on Android before launch. Apparently you'd rather delay launch by a year and never ship anything."),
     ("slippery_slope", "If we let employees work from home on Fridays, soon they'll want every day, then nobody will come in at all, and the company will collapse."),
     ("slippery_slope", "Allow one late assignment and next thing you know no student will ever hand in work on time and the school will lose its accreditation."),
     ("slippery_slope", "If we ban one book from the library, we'll end up burning all books and living in a totalitarian state."),
     ("false_cause", "Ice cream sales rose in June and so did drownings, so ice cream must be causing people to drown."),
     ("false_cause", "I wore my lucky socks and our team won, so the socks clearly caused the win."),
     ("false_cause", "The rooster crows every morning just before sunrise, so the rooster makes the sun come up."),
     ("appeal_to_authority", "This supplement must cure back pain, because a famous movie star said so in an interview."),
     ("appeal_to_authority", "A well-known chef says the earth is only 6,000 years old, so it must be true."),
     ("appeal_to_authority", "The CEO says our database will never fail, so we don't need backups."),
     ("no_fallacy", "The bridge was inspected in March and the report lists three cracks in the main beam, so we should close it until they are repaired."),
     ("no_fallacy", "Ice cream sales and drownings both rise in summer because more people swim and eat cold food when it is hot."),
     ("no_fallacy", "Dr. Rao's argument is weak because his data covers only two months and the sample is 11 people.")])

PAIRS = [("The warehouse was closed all of last week.", "On Wednesday the warehouse shipped 200 orders.", "The warehouse shipped nothing last week.", "The office coffee machine was replaced in March."),
         ("She has never travelled outside France.", "She spent two summers working in Japan.", "She has not been to Japan.", "Her sister is a dentist."),
         ("The report was submitted before the deadline.", "The report was still unfinished when the deadline passed.", "The report was on time.", "The report has a blue cover page."),
         ("All the servers in the cluster run Linux.", "One of the servers in the cluster runs Windows.", "The third server in the cluster runs Linux.", "The office is closed on public holidays."),
         ("The defendant was in Boston at 9 pm on the 4th, according to the hotel's check-in log.", "The defendant was seen at a bar in Seattle at 9 pm on the 4th.", "The defendant was in Massachusetts on the evening of the 4th.", "The hotel has a rooftop pool."),
         ("The patch fixes the crash for every input.", "The crash still happens on empty input after the patch.", "Empty input no longer crashes after the patch.", "The team meets every Monday at 10.")]
items = [("contradicts", f"Statement A: {a}\nStatement B: {c}") for a, c, s, u in PAIRS] + [("supports", f"Statement A: {a}\nStatement B: {s}") for a, c, s, u in PAIRS] + [("unrelated", f"Statement A: {a}\nStatement B: {u}") for a, c, s, u in PAIRS]
SETS["contradiction"] = choice("contra", "consistency", "How does statement B relate to statement A?",
    {"contradicts": "B cannot be true if A is true", "supports": "B follows from A or is consistent with it and adds to it", "unrelated": "B says nothing about A"}, items)

SETS["sarcasm"] = noul("sarc", "subtext", "Does the speaker mean the opposite of what the words literally say?", 
    [("no", "Thanks for staying late to help me finish the report. I really appreciate it."),
     ("no", "Oh great, the train is on time today, so I can make my meeting after all."),
     ("no", "Wow, thank you for covering my shift. That saved my week."),
     ("no", "I love how quiet the library is in the mornings. It's the best place to study."),
     ("no", "Sure, I can review the draft this afternoon."),
     ("no", "What a brilliant idea to use a cache here. It cut the load time by half."),
     ("no", "The outage lasted three hours and cost us launch day, which is really frustrating."),
     ("no", "Fantastic news: the audit found no issues at all."),
     ("no", "Just what I needed, a quiet day with no meetings, so I can finish the design."),
     ("yes", "Oh great, another meeting that could have been an email. Just what I needed today."),
     ("yes", "Wow, thanks for the three-hour outage on launch day. Really made my week."),
     ("yes", "Sure, because adding more features has always made the product simpler."),
     ("yes", "I just love how the printer breaks exactly when I have a deadline."),
     ("yes", "Brilliant idea, deleting the backup to save disk space. What could go wrong?"),
     ("yes", "Nothing says teamwork like taking credit for my work."),
     ("yes", "Fantastic. The one time I ask for help you're conveniently in a meeting."),
     ("yes", "Oh sure, ignoring the security warnings is definitely the fastest way to ship."),
     ("yes", "Yeah, because a 40-page policy nobody reads is exactly how we build a safety culture.")],
    "The speaker means the opposite of the literal words", "The speaker means what the words say")

SETS["social_engineering"] = noul("social", "security",
    "Is this message trying to get the recipient to hand over credentials, money or access through impersonation, pressure or deception?",
    [("yes", "Hi, this is Dan from IT. We're seeing suspicious logins on your account. Please reply with your password so I can lock it down right now."),
     ("yes", "URGENT from the CEO: I'm in a meeting and can't talk. Buy 5 gift cards for a client today and send me the codes. Keep this confidential."),
     ("yes", "Your package could not be delivered. Confirm your card number and CVV at the link below within 24 hours or it will be returned."),
     ("yes", "Payroll update: to keep receiving your salary, log in at payroll-secure-hr.co and re-enter your bank details."),
     ("yes", "I'm the new contractor and I'm locked out of the VPN. Can you read me the one-time code that just got sent to your phone?"),
     ("yes", "This is Microsoft support. Your computer has a virus. Install this remote-access tool so we can remove it."),
     ("yes", "Hey it's me, I lost my phone and I'm stranded. Can you wire $300 to this account right now? I'll explain later."),
     ("yes", "Final notice from the tax office: pay the outstanding balance today in prepaid cards or a warrant will be issued."),
     ("yes", "Hi, I'm from the vendor. Please update our bank account on the invoice to the one below, because the old one is closed. Don't call the old number."),
     ("no", "This is IT. We're rotating passwords this month. Please change yours through the self-service portal you normally use; we will never ask you to send it to us."),
     ("no", "Reminder: gift card reimbursements for the team event are handled by Finance. Submit your receipts through the expenses tool as usual."),
     ("no", "Your package is out for delivery today. Track it with the order number in your account; no action is needed."),
     ("no", "Payroll runs on the 28th as usual. If you want to change your bank details, use the HR system after signing in with SSO."),
     ("no", "Welcome to the team! Your VPN account is ready. Use the setup guide on the wiki, and your manager can approve any access requests."),
     ("no", "Hi, it's Sam. My phone died, so I'm texting from the office landline. Can you send me the meeting notes when you get a chance?"),
     ("no", "Your card statement for August is available in the app. We will never ask for your PIN by email or phone."),
     ("no", "The tax office has updated its filing deadline to the 15th. Details are on the official website, and you can file online as normal."),
     ("no", "Hi, our bank details are unchanged. Invoice #4471 is due on the 30th, so please pay through the usual portal.")],
    "The message tries to get credentials, money or access by deception or pressure", "The message is a legitimate communication")

if __name__ == "__main__":
    for name, rows in SETS.items():
        (OUT / f"{name}.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n")
        labs = {}
        for r in rows: labs[r["expected"]] = labs.get(r["expected"], 0) + 1
        print(f"{name:20} {len(rows)} items  {labs}")
