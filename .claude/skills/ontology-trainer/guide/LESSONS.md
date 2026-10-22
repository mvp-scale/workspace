# Lessons learned: training classifiers for an ontology

For people setting up the ontology trainer. The skill does not read this file. Situations differ; the principles below are what carried over. Each comes with what it looked like when it went wrong in the first project (the World engine news ontology, October 2026) and how to examine it in yours.

## How to examine a problem: a short checklist

When a result looks wrong, ask in this order. Most problems are found by question 1 or 2, not 5.

1. **Is the definition clear?** Would two careful people, reading the same item and the same question, give the same answer?
2. **Did every judge get the same instructions and the same text?**
3. **Does the input actually contain the evidence?** (A headline may not carry what the full article does.)
4. **Is the measurement sound?** (Right test set, no leakage, enough examples, the right metric.)
5. **Only then: is the model too weak?**

## Principles

### 0. Start with a good source
Everything downstream inherits the source's flaws. A good source for training data:
- **matches the domain and the input you will serve** (same kind of text, same length available: full article versus headline);
- **is filtered for quality** before any labelling: trusted publishers, the right language, enough text per item, no adverts, roundups or live blogs, duplicates removed (syndicated copies are common);
- **is large enough for the rare elements**, not just the common ones;
- **is close in time to the data you will see live**, or the gap is measured and flagged;
- **has a known licence and provenance** (where each item came from, when, which filter it passed).
Check it with automatic rules on every build, and keep a slice of your own live data to compare against.
*Bad looked like:* a live news feed where 12 of 29 stories had little or no text, a shopping post and a sports item were read as economic news, one story was Japanese, and one was a multi-story roundup. A large archive fixed the volume but was from 2017-19: "prices rising" appeared in 3 of 397 archive stories against 123 of 1,736 in the 2026 feed, so archive-only training would under-learn it. The archive's licence was listed as unknown, so it was kept to research use.

### 1. Define before you measure
A label is only as good as the question that produced it. Write a short codebook entry for each element: definition, what counts, what does not, one example of each from real items. Test it on ~50 items with independent judges, measure agreement per element (Krippendorff's alpha; 0.8 reliable, below 0.667 reject), and rewrite until it passes. Then label at scale.
*Bad looked like:* three models agreed on topic (84-90%) and country (92-94%) but overlapped only 34-41% on which conditions a story reports. The questions said "Does the story report any of these: ..." without saying whether a passing mention counts.

### 2. Every judge gets identical instructions
Put rules inside the question text itself, not in a side note to some judges.
*Bad looked like:* the Claude jurors were told "a passing hint is not enough"; the hosted model saw only the question. Their disagreement was partly the brief, not the models.

### 3. Wording and grouping are part of the label
The same model can flip its answer when a question is reworded or asked alongside different questions. Fix the wording and the grouping before collecting labels, and keep them fixed.
*Bad looked like:* one story scored 0.15, 0.88 and 0.37 on three reasonable wordings of the same question. Asking the same questions in different groups shifted answers by a median 0.03 and broke 23 of 100 stories' readings, until the original grouping was restored (99 of 100).

### 4. One vote per family
Models from the same vendor share blind spots. Two of them are closer to one vote than two.
*Bad looked like:* Haiku and Sonnet agreed with each other (0.70) far more than either did with a model from another vendor (0.34-0.41). A jury of two Claude models plus one other would let the Claude pair outvote the third.

### 5. A strict machine format, checked by a script
Free-form or positional output from a model judge fails silently. Use lists of identifiers or schema-checked JSON, and validate every file before use.
*Bad looked like:* 88-character 0/1 strings came back 86 characters long, or shifted by hand-counting; one judge's two runs agreed only 10%. Lists of question ids had zero errors.

### 6. Agreement is not correctness
Two models agreeing can both be wrong. Keep one human step: someone spot-checks 50-100 jury answers to measure the jury's own accuracy, and resolves the cases the investigator cannot.

### 7. Look where the signal is
Check how much of the information the classifier's input actually holds before blaming the classifier.
*Bad looked like:* a headline plus description carried only about 35-40% of what the same model found in the full article; 250 words carried 68%, 600 words 92%. Main points appeared early; later text added side mentions.

### 8. Rare things need targeted data
Random samples barely contain rare elements; no model can learn from three examples.
*Bad looked like:* 7 of 16 priority elements had 3 or fewer positives in 1,736 random stories; 34 of 78 elements had too few examples to train on at all.

### 9. Report examples, not only averages
Show items side by side: the text, the label, the prediction, the probability, match or not.
*Bad looked like:* an average score looked fine while the per-item table showed the classifier caught 17 of 17 true cases but raised 33 false alarms on 20 stories.

### 10. Pre-register, then don't move the goalposts
Write pass bars and predictions before each run. If you change the method after seeing a result, say so, and confirm the change on fresh data.
*Bad looked like:* a fix made after seeing a failed run (restoring question grouping) passed every bar, and an independent reviewer correctly flagged it as a post-hoc change needing a fresh confirmation run.

### 11. Check the engine before tuning it
Find out what the serving software can and cannot do before turning its settings.
*Bad looked like:* hours of llama.cpp tuning moved speed by 6%; the reason was a documented limit ("single sequence per batch" for this model type). Switching to a batching engine and a quantized model gave 2.6x, and asking fewer questions per item (a two-step screen) gave 5.3x.

### 12. Cap every resource twice
Time, spend, GPU, memory: each job gets its own limit and an independent stop that does not depend on the job staying healthy.
*Bad looked like:* an unbounded queue of model outputs grew to about 42 GB of RAM and was killed by the operating system.

### 13. Verify what a tool says about itself
Status screens and logs can be wrong.
*Bad looked like:* a tool's status page and log said its checks ran on a hosted model; testing showed they ran on the local one.

### 14. Gaps in the ontology are findings
When judges cannot place an item, the ontology may be missing something.
*Bad looked like:* stories about Ireland, Switzerland, Singapore and Denmark could only be labelled "global" because the 100-country list did not include them.

### 15. Smart extraction: use what you know about how the item got here
Some labels are facts a script can read, and some can be filled from the item's context: who sent it, through which channel, and sometimes where it is going. Read named facts with a script first (place lists, entity recognition, cue words). Where the text says nothing, fall back to a stated default from the context instead of guessing from clues or saying nothing. What the text states always overrides the default; never record both. Keep judges and trained models for what is left.
*Bad looked like:* in 13 of 50 stories no place was named, yet every judge gave a country by inference ("RCMP" means Canada, "the Fed" means the US), and the judges split on some (Wimbledon: France or UK). A place-name script (11 ms per story, no model) plus the outlet's home country (news agencies count as "world") gave every story a country by a rule anyone can check. It also showed that a country label might not need a trained model at all.

### 16. Extract openly, map with a judge, not with raw similarity
For a closed list (topics, conditions), let a model describe the item in its own words first, then map those words onto the list. The mapping is the hard part: use a judge or a learned map, and treat words that map to nothing as possible gaps in the ontology. Test every stage on its own; a failure in one stage can look like a failure of the whole idea.
*Bad looked like:* open topic phrases from a model that never saw the list were good ("Asian shares rally"), but mapping them by embedding similarity to the topic definitions matched the reference on 21 of 42 stories ("Asian shares rally" went to energy, rugby previews to climate change). The same phrases mapped by a judge from the phrase alone matched 39 of 42, as well as asking the topic question directly (38 of 42). Noun phrases pulled by a parser were not topic phrases at all (9 of 42). The lowest-matching phrases were all sport, which showed the ontology had no sport topic: one in five stories was being filed under culture.

### 17. Know what each detection is for
A detection that only restates words already in the text adds nothing as an input to a text classifier. Its value lies elsewhere: as a check on outputs, a search key for rare cases, a label the text model cannot compute on its own, or a fallback from context. Also check the downstream rules before "fixing" a labeller: a contradiction in raw answers may already be resolved by the system that consumes them.
*Bad looked like:* adding significance and rise/fall word counts to a text classifier lowered condition quality (mean AP 0.485 to 0.437, or 0.475 rescaled), while simply combining two text representations raised it from 0.447 to 0.485 and doubled the keys above 0.70 (6 to 10). One judge marked the same condition both up and down on 6 of 50 stories, but the engine's own net rule left 0 such cases in 10,000 labels.

### 18. Score against the system you are replacing
When the goal is to copy an existing system on cheaper hardware, its outputs are the target, flaws included. Use richer internal labels only if they map back to its labels. Log the system's flaws for a separate fix instead of training around them.
*Bad looked like:* the engine's size question ("for ordinary people worldwide") rated 87 of 112 answers minor, so a better size scale looked tempting; but a reader built on it would no longer match the engine it is meant to replace.

### 19. Size the test set before reading a round
A round's gain is only visible if the test set can see it. Per element, the noise in a score shrinks with the number of positive examples in the test set (for average precision, roughly 0.44 divided by the square root of the positives). Check that number before reading any change, and grow the test set first if the expected gain is smaller than the noise. Never fill the test set with stories the classifier itself picked; draw it at random.
*Bad looked like:* after a second round of 1,000 stories the mean score stayed at 0.499, one element "regressed" from 0.718 to 0.682, and 16 of 33 elements changed direction between rounds. The median element had only 12 positives in the 2,000-story test set, so each score carried a noise of about +-0.13: the rounds' per-element changes were invisible. Coverage gains (elements going from too rare to scorable: 44 to 30) were real.

## A good breakdown for a new ontology

1. Choose and filter a good source (principle 0); keep a slice of live data beside it.
2. Split the ontology into areas read from text versus areas computed from others. For each area, ask what a script or the item's context can supply before any model (15).
3. For each element, write the codebook entry and test it for agreement (principles 1-3).
4. Pilot every judge on ~50 items with a strict format (4-5); keep one vote per family.
5. Check the input holds the signal (7); choose the input length on evidence.
6. Build a frozen, jury-labelled test set with a human spot check (6).
7. Write ~10 acceptance criteria per area, pre-registered (10).
8. Train in rounds of a fixed number of new items (1,000 here), half random and half aimed at failing criteria; score every candidate model on every criterion each round, with regression checks; time caps are only a safety stop (8, 12).
9. Report per-item examples and a criteria scorecard (9).
