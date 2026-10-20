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

## A good breakdown for a new ontology

1. Split the ontology into areas read from text versus areas computed from others.
2. For each element, write the codebook entry and test it for agreement (principles 1-3).
3. Pilot every judge on ~50 items with a strict format (4-5); keep one vote per family.
4. Check the input holds the signal (7); choose the input length on evidence.
5. Build a frozen, jury-labelled test set with a human spot check (6).
6. Write ~10 acceptance criteria per area, pre-registered (10).
7. Train in capped, hour-long rounds aimed at failing criteria, with regression checks (8, 12).
8. Report per-item examples and a criteria scorecard (9).
