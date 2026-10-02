# Layered evaluation method (medical and expert image tasks)

RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE. The feature lists in `cascades/*.json` are drafts written from standard published criteria. A clinician must review them before any claim is made on their basis.

## Why this replaces "ask one question, or ask it five ways"

A single broad question ("Which diagnosis is this?") asks the model to do everything in one step. Re-asking it in different words (what `layers.py` did) repeats the same judgment and gains almost nothing (mean accuracy 73.4% to 73.9%). TypeSafe's own guidance says the same: ask atomic, explicit, narrow questions, one property each, and combine the answers in code. Questions are evaluated independently, so send them together as one batch per image.

## The layers

**Layer 0: Is this the right kind of thing to look at? (gate)**
Not "is it good or bad", only "is this an image this task can be applied to": right modality, right body area, in focus, not obscured. Five or so questions. If the gate fails, stop. The level of the problem is the image, not the finding, and the case goes to a person (retake, wrong image type).

**Layer 1: What is visible? (characteristics)**
10 to 15 atomic yes/no questions, each one observation, each worded so a high value means yes (no "free of", no "NOT"), each answerable by a knowledgeable person in a second. Good and bad findings both count: this layer collects information and does not decide anything.

**Layer 2: Consensus, not an average**
Each answer becomes a vote: yes if P(yes) is at least 0.65, no if at most 0.35, unsure in between. Votes are counted per hypothesis (a class, or present / absent). A feature that points toward a class counts as a vote for it when it is yes and against it when it is no; a feature that argues against a class does the reverse. Support for a class is the share of decisive votes that agree with it. Averaging probabilities hides disagreement: ten questions at 0.9 and ten at 0.1 average to a confident-looking 0.5. Counting votes keeps the pattern: how many agree, how many disagree, how many are unsure.

**Layer 3: Cascade into the areas of investigation**
The two best-supported hypotheses from Layer 1 select a second set of discriminating questions (what separates melanoma from a nevus, pneumonia from a normal chest). Only those are asked. This is where the progressive narrowing happens, and it keeps the question count at 10 to 25 per image instead of asking everything about everything.

**Layer 4: Outcome and the level of the problem**
Every image ends in exactly one outcome, so a person can see where it stalled:

| Outcome | Rule | Action |
|---|---|---|
| NOT_USABLE | at least 3 gate votes decided and fewer than 80% passed | route to a person: wrong or poor image |
| UNCLEAR | 40% or more of the Layer 1 votes are unsure | route to a person: the model cannot see the features |
| CONFLICT | two hypotheses both have support of 0.60 or more | route to a person: contradictory evidence |
| CONSENSUS(class) | top support 0.70 or more, at least 5 decisive votes, and a gap of 0.15 over the runner-up | auto-handle, report the class and the support |
| WEAK(class) | a leader exists but below the bar | route to a person with the leading class as a hint |

Thresholds are fixed in advance (they are in the spec files) and are not tuned on the images being scored.

## What gets measured

For each task, on a sample of 100 images the method never saw during design:
- accuracy if forced to pick the best-supported class, against the single original question and against a plain average of the same answers
- **coverage** (share of images that reach CONSENSUS) and **precision** (share of those that are right). This is the triage number: how much can be auto-handled, and how right is it
- the distribution of outcomes and the accuracy within each, which shows which layer the problems sit in
- false positives (yes/no tasks)

## Where the knowledge lives

`cascades/<task>.json` holds the gate, the Layer 1 features, the Layer 3 discriminators, and for each feature which classes it supports (`for`) or argues against (`against`). Features with neither are recorded as information only. That file is the "mapping below": the superset of what is known about the task beforehand, written once per task type (skin, bone, chest, retina, dental, and so on) and reused.

## Limits

- Sample sizes of 100 give an interval of roughly plus or minus 10 points. Differences smaller than that are not findings.
- The feature to class mapping is hand-written from published criteria. It is transparent and testable, but it has not been reviewed by a clinician.
- Absence of a feature counts as evidence against only through the same symmetric rule; some absences are weaker evidence than presences.
- This is a benchmark of a general vision model's observations, not a diagnostic tool.

## Question budget and adaptive drilling (version 2)

Each image has a budget of **100 questions**, spent in rounds of at most 10 (questions in a round are sent as one batch, and are evaluated independently). After every round the votes are recounted and the process stops as soon as the evidence is decisive. The cheapest correct answer is the goal; the rest of the budget is a reserve, not a quota.

| Layer | Budget | Purpose | Stops when |
|---|---|---|---|
| 0 Gate | 10 | Right kind of image? Subject, framing, focus, obstruction, lighting. A balloon in place of a skin lesion ends here | The gate fails (outcome NOT_USABLE, 10 questions spent) |
| 1 Characteristics | about 20 | Broad observations, good and bad findings alike, from a bank of atomic questions | Consensus is already clear |
| 2 Discriminators | up to 30, in batches of 10 | Questions that separate the two leading hypotheses, chosen by what layer 1 showed | Consensus after any batch |
| 3 Deep dive | up to 25, in batches of 10 | Confirm or deny the leading hypothesis feature by feature | Consensus after any batch |
| Reserve | about 15 | Backtrack: go back to layer 1 and re-ask the questions that were unsure or contradictory, this time with the established facts in the state, then come down again | Budget spent (outcome UNRESOLVED) |

**Nothing learned is thrown away.** Every answer is kept. From layer 2 on, the decisive answers so far are passed into the state as established facts ("Answers already established about this image: ..."), because TypeSafe's state is where supporting facts belong. Whether carrying facts helps or biases the model is itself tested (carry on versus off).

**What "dynamic" means here.** The next questions are chosen from a larger bank by the evidence so far (which hypotheses lead, which features are unsure or contradictory). The bank is written once per task; selection is deterministic and auditable. Letting a language model write new questions on the fly is a possible later layer; it needs an outside model and costs money, so it is not part of this version.

**What is reported.** Accuracy with an interval, the share handled on consensus and how right it is, the average and the distribution of questions spent, and where each image stopped (gate, layer 1, 2, 3, backtrack, exhausted), with the accuracy at each stop.
