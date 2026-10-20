# Ontology trainer: a practical guide for people

This folder is for humans. The skill (`../SKILL.md`) does not read it. It explains the premise, what you need, and how to apply the method to any ontology, not only the World engine's.

## The premise

You have an ontology: a fixed set of things you want recognised in text (topics, places, events, conditions, intents, risk types...). A large language model can recognise them, but it is slow or costly to run on everything. The goal is a set of small, fast classifiers (one per ontology area, running on a normal CPU in milliseconds) that agree with careful judges almost as well as the big model does.

Three ideas make it work without a team of human labellers:

1. **Teachers label, students learn.** A fast hosted model labels thousands of examples; small classifiers learn from those labels.
2. **A jury replaces most human checking.** Several models from different vendors label a fixed test set. Where they agree, the label is trusted; where they split, a stronger model investigates; one short human spot check measures how good the jury is.
3. **Pre-stated acceptance criteria steer the work.** Each ontology area gets about ten measurable tests written before training. Each round of training only works on the tests that fail, and every round re-checks the ones that passed so nothing quietly gets worse.

## What you need

| Need | Example from the World engine work | Notes |
|---|---|---|
| An ontology split into areas | story type, scope, topic, country, 78 conditions | Leave out anything that is computed from other areas by rules |
| A large unlabelled text source in your domain | CC-News (708,000 news articles; 70,000 after filtering) | Filter for quality and relevance first; check the licence |
| A bulk teacher | Jev (hosted, ~450 items/min, ~$0.5 per 1,000 items) | Ask all questions in one call per item; check it answers the same twice |
| Jurors from different vendors | Claude Sonnet (subscription subagent), Jev, Clef (local GPU) | Two models from the same family count as one vote |
| An investigator | Claude Opus | Only for splits and surprising failures |
| A person for ~30 minutes | You | Spot-check 50-100 jury answers once |
| A CPU training environment | scikit-learn + sentence-transformers | Frozen encoder first, fine-tuned encoder next |
| Caps | time window, per-step limit, spend cap, GPU plan | Two independent stops on every long job |

## The structure, step by step

1. **Write the acceptance criteria.** About ten per area, each with a number. Example for a place classifier: overall accuracy; place named only in the headline; only a demonym ("French ministers"); only a city ("Lyon factory"); several places; no place ("global"); no invented place on generic text; recall per region; confidence matching accuracy.
2. **Build and check the data.** Filter the source, label it with the bulk teacher from exactly the text the classifier will see, and run automatic checks on every build (duplicates, language, length, labels from the right text, provenance).
3. **Pilot the jury.** 50 items through every juror. Measure how often each pair agrees and how long each takes. Keep one vote per vendor family.
4. **Freeze a test set.** About 2,000 fresh items labelled by the jury. Never train on them.
5. **Run hour-long rounds.** Score every criterion, gather new examples aimed only at failing criteria, retrain, re-score, check for regressions, record. Stop an area when it passes; stop everything when all pass, a cap is hit, or progress stalls.
6. **Report with proof.** Per-item examples and a criteria scorecard, not only averages.

## Applying it to another ontology

- Replace the question set with your ontology's definitions (one clear yes/no or choice question per element, built from the element's own definition).
- Replace the source corpus with text from your domain.
- Keep the jury rule, the frozen test set, the acceptance criteria and the caps unchanged: they are what make the result trustworthy.

## Lessons from the first run

- Asking the same questions in different groupings changed one model's answers; keep a question set's grouping fixed once labels are made.
- Wording changes verdicts; fix the wording before collecting labels at scale.
- Rare elements need targeted mining; random samples barely contain them.
- Simple classifiers find most true cases early but raise too many false alarms; per-label thresholds are an early fix.
