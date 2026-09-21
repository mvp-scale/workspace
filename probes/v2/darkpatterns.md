# darkpatterns probe set

- **Source**: Mathur, Acar, Friedman, Lucherini, Mayer, Chetty, Narayanan. "Dark Patterns at Scale: Findings from a Crawl of 11K Shopping Websites." Proc. ACM HCI 3(CSCW), 2019. arXiv:1907.07032.
- **URLs** (retrieved 2026-09-21):
  - https://github.com/aruneshmathur/dark-patterns, file `data/final-dark-patterns/dark-patterns.csv` (1,818 labelled rows; positives).
  - https://darkpatterns.cs.princeton.edu/data/dark-patterns-output.tar.lz4 (1.3 GB), file `segments_second_pass.csv` (267k crawl segments; negatives).
- **Licence**: GPL-3.0 (repository LICENSE). The data files carry no separate licence.
- **Builder**: `build_darkpatterns.py` (seed 20260921, deterministic).

## Sampling
- Positives: rows with a non-empty `Pattern String`, whitespace-normalised, length 6-600 chars, exact-text duplicates dropped, categories as given by the dataset. 11 sampled per class with `random.Random(20260921)`.
- Negatives (`not_dark_pattern`): the dataset has no labelled negative file. I used segments from `segments_second_pass.csv` that (a) are not in dark-patterns.csv, (b) are in clusters containing no labelled positive, (c) are 25-300 chars, at least 5 words, mostly letters, (d) one per hostname, (e) contain none of a regex list of dark-pattern cue words (see `CUES` in the script). Rule (e) is my mechanical safety filter; it makes negatives easier and text-biased (no promo/cancel/stock/shipping wording), so this class is more separable than a real crawl.
- Counts: scarcity 11, urgency 11, social_proof 11, misdirection 11, obstruction 11, sneaking 11, not_dark_pattern 11 = 77.
- **Forced Action dropped**: only 4 usable strings in the source (below the 8 minimum). Not merged into another class.
- Sneaking is capped at 11 by the source (11 usable strings); all of them are used. 306 source rows have no text (mostly countdown timers described only in comments) and were dropped.

## Criteria
Paraphrased from the paper's Table 1 definitions of Scarcity, Urgency, Social Proof, Misdirection, Obstruction, Sneaking. The `not_dark_pattern` description is mine.

## Label-quality caveats
- Negatives were never individually reviewed by the authors; they are just segments outside the curated list. Some may be dark patterns the authors missed or judged out of scope.
- Misdirection is 129/~194 confirmshaming ("No thanks, I don't want to save"), which is easy from text, but the sample also includes Pressured Selling ("Customers also bought") that is hard from text alone.
- Obstruction (mostly "call/email to cancel") and Sneaking (hidden costs, default add-ons, hidden subscriptions) really depend on page context (what is visible, what is default, what the alternative cancel path is). Text-only, these are inherently ambiguous and overlap with each other and with ordinary policy text.
- Scarcity and Social Proof are dominated by templated widgets (low-stock, "X just bought") so they are near-trivial.
- Category labels come from the authors' cluster review; the paper reports no per-item inter-rater agreement.

## Contamination risk
High: the repo and paper are public and old (2019), and likely in LLM training data. Segments are verbatim, so memorisation is possible, though the per-string labels are unlikely to be memorised.
