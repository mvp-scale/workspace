# Item-battery reliability test: pre-registered (written before any result)

Question: is a trait read from ONE question trustworthy, and does reading it from 10 different angles fix that? Truth: the generator's hidden 1-5 trait (400 personas).
Each trait has 10 atomic positive-polarity items (items.py), asked together in one call per trait per persona. Scores are logit(P(yes)), z-scored across the 400 personas per item, then averaged.

Measures: (a) saturation: share of raw P(yes) below 0.05 or above 0.95 (the cliff: where raw probabilities stop carrying information); (b) Cronbach's alpha on the z-scored items;
(c) split-half (odd vs even items) correlation with Spearman-Brown correction; (d) Spearman rho of the score with the hidden trait using 1, 2, 4, 6 and 10 items (mean over 200 random subsets); (e) share of single items with rho < 0.40.

Pass lines:
 R1 alpha >= 0.80 and split-half >= 0.80 for every trait, otherwise the trait is not measured reliably from this profile text.
 R2 10-item rho >= 0.80 for every trait, and exceeds the mean single-item rho by >= 0.10 for the traits where single items are weak (mean single-item rho < 0.75).
 R3 rho at 6 items within 0.03 of rho at 10 items, otherwise more items still help and the battery should be larger.
 R4 saturation reported; if more than 50% of raw P are in the tails for any trait, raw-probability scoring is declared unsafe and logit z-scores are mandatory.
Flag rule to test as a decision tool: mark a persona-trait "unmeasured" if the SD of its z-scored items across the 10 items is above the 90th percentile; report whether flagged persona-traits have larger error vs the hidden trait than unflagged ones.
Caveats declared in advance: profile texts are templated and state many of these facts only indirectly; the hidden trait is our own generator's; one run; truth is the generator, not people.

## Result (2026-10-02, one run, 400 personas x 6 traits x 10 items)

Saturation (R4): 65 to 73% of raw P(yes) sit below 0.05 or above 0.95 for every trait -> raw-probability scoring unsafe, logit z-scores mandatory.
R1 PASS (alpha 0.95 to 0.99, split-half 0.91 to 0.99). R2: 5 of 6 pass (10-item rho: tech 0.75 FAIL, price 0.92, privacy 0.92, social 0.93, time 0.91, novelty 0.85); gain over a single item >= 0.10 for tech (0.64 -> 0.75) PASS.
R3 PASS for all (6 items within 0.03 of 10). Single-item rho ranged 0.64 (tech) to 0.90 (time); one social item in ten was weak (< 0.40).
Flag rule (SD across items above the 90th percentile): helps for tech (rank error 0.28 flagged vs 0.15), novelty (0.22 vs 0.13), social (0.14 vs 0.10); no effect for price, privacy, time (0.10 vs 0.11, 0.12 vs 0.11, 0.11 vs 0.12).
Reliability is not validity: alpha 0.96 for tech with rho 0.75. Not an age stereotype (score~age -0.59 equals hidden~age -0.58; partial rho given age 0.59). Probable cause: the generator renders each trait in the text at only three phrasing levels (1, 3, 5), so levels 2 and 4 are not recoverable; that is a limit of our text, not of the model.
Embedding sensitivity (PCA size k, same data, EMBED-PREREG.md): k=4 B pooled r +0.20, D +0.51; k=8 B +0.54, D +0.67; k=16 B +0.54, D +0.49; k=32 B -0.58, D -0.26 (39 ideas cannot support 32 components). The k=8 "T3 pass" does not hold at k=4, 16 or 32.
