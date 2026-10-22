# Free NLP picker tricks (Context7 recon)

Date: 2026-10-22. CPU only, no hosted calls, no GPU, no money. Working folder: `/tmp/claude-0/-workspace/56bd04e1-c166-41e7-b6b1-a8834c019bd6/scratchpad/free_signals/` (new code in `tricks/`, numbers in `tricks_results.json`).

Labels used in this note: **[DOCS]** = read in the library documentation through Context7 (not run by us). **[MEASURED]** = our own run on the 2,000-story test set, with every model fitted on the 2,997 training stories only.

## Plain-language summary

The "picker" ranks news stories by how likely they are to carry a *condition* (a measurable state of the world, such as prices rising or a shortage). We keep the top 11%, 20% or 37% of stories and ask how many of those really carry a condition ("share") and how many of all condition stories we caught ("catch"). The base rate is 29%, so 29% share is a coin-flip. AUC is a single score for the whole ranking (0.5 = random, 1.0 = perfect).

Result [MEASURED]: the tricks that matter are the ones that learn from our own labelled stories (word and word-pair statistics, one small model per condition type, similarity to a "typical story" per condition type). The ones that came from the documentation as "linguistic cleverness" (pattern matching on rise/fall phrases, sentiment, negation, WordNet word families) added little or nothing. Best free-only picker improves from AUC .757 to .783 and from 60% to 64% share at keep-20%. With BitMob (our small fast on-CPU model) the gain is smaller: AUC .792 to .806, share at keep-20% 68% to 70%, and no gain at keep-11%.

## 1. What each tool can do

### compromise (JavaScript, v14.14.4) [DOCS, Context7 /spencermountain/compromise]
- Match by word root: `match('{walk}')` finds walk/walks/walked/walking; `{walk/verb}` restricts to the verb sense (docs/match-syntax.md).
- Match by tag and mix: `#Value`, `(a|b)` alternatives, `word?` optional, `*` any words, `!` negate, `^`/`$` sentence start/end, `~word~` fuzzy spelling.
- Verbs: `.verbs().isNegative()`, `.toInfinitive()`, `.conjugate()`, tense converters (docs/api.md).
- Sentences: `.sentences()`, `.isQuestion()`, `.toNegative()`.
- Numbers, money, percentages through `.numbers()`, `.money()` and the `#Value` tag.
- `compromise-stats` plugin: `.ngrams()` (phrase counts).
- We did not see `.topics()` or a dates/stats plugin in the returned snippets, so we did not use them.

### wink-nlp (v2.3.2) + wink-eng-lite-web-model [DOCS, Context7 /winkjs/wink-nlp, /winkjs/wink-bm25-text-search]
- `its` helpers: `its.lemma`, `its.stem`, `its.type`, `its.pos`, `its.stopWordFlag`, `its.negationFlag`, `its.sentiment` (per sentence, stored with the sentence in `doc.sentences()`).
- `as` reducers: `as.bow`, `as.freqTable`.
- Entities: `doc.entities().out(its.detail)`; custom entities via `learnCustomEntities` (not tested, needs hand-written examples).
- BM25 vectorizer and similarity methods (cosine, Tversky, Sorensen-Dice, Otsuka-Ochiai) are listed in the README.
- `wink-bm25-text-search`: `defineConfig({fldWeights})`, `definePrepTasks`, `addDoc`, `consolidate`, `search`. The docs' own example marks negated words by prefixing `!` to the stem, an easy way to keep "not rising" apart from "rising".

### NLTK WordNet (Python) [DOCS, Context7 /nltk/nltk]
- `synset.hyponyms()`, `synset.hypernyms()`, `synset.closure(lambda s: s.hyponyms(), depth=n)` for all narrower/broader terms.
- Lemma-only relations: `lemma.derivationally_related_forms()` (e.g. noun and verb forms), `pertainyms()`, `antonyms()`.

### scikit-learn text tools [DOCS, Context7 /scikit-learn/scikit-learn]
- `TfidfVectorizer(sublinear_tf=True, ngram_range=(1,2), min_df=...)`; `analyzer='char_wb'` builds character n-grams inside word boundaries ("less noisy" than plain `char`, per the docs).
- `HashingVectorizer`: no vocabulary to store, no inverse; no IDF unless a TfidfTransformer is added.
- `SelectKBest(chi2)` for feature selection; docs warn to put it inside a Pipeline so it is fit on training data only (common_pitfalls).
- `CalibratedClassifierCV` (turn scores into probabilities), `ComplementNB`, `LogisticRegression(class_weight=...)`.

## 2. What we tried [MEASURED]

All are new signals, each scored out-of-fold on train, then combined by a small logistic stack (same method as the current picker). Harness reused from `run.py` (not changed).

| Id | Trick | Source of the idea |
|---|---|---|
| T1 / T1b | TF-IDF, sublinear counts, word 1-2 grams (T1b adds character 3-5 grams), class-weighted logistic regression | scikit-learn docs |
| T2 | chi-squared keeps top 2,000 word pairs, then ComplementNB | scikit-learn docs |
| T3 / T3b | One small model per condition type (about 30 of them), combined as "any of them fires" (noisy-or) or "strongest one" (max) | our idea, per-dial scoring |
| T4 | BM25 similarity of each story to one "centroid document" per condition type (all training positives glued together) versus one for no-condition stories | wink-bm25 docs |
| T5a | compromise patterns: `({rise}\|{surge}...) * #Value`, `#Value (percent\|%) ({rise}...)`, shortage words, negated change | compromise docs |
| T5b | wink sentiment (mean/min/max), negation tokens, compromise verb negation/tense | wink + compromise docs |
| T6 / T6b | WordNet hyponym (2 levels) + derivationally related expansion of mined keywords; T6 keeps only terms that are over-represented in training positives, T6b keeps all | NLTK docs |
| Diversity pick | Reserve 30% or 60% of the keep budget for the best story of under-represented condition types | our idea |

Settings (C for the regression) chosen by training-only cross-validation: word C=0.5, word+char C=0.5. Test was used once, for the final table.

## 3. Results on test (2,000 stories, 29% carry a condition)

Share / catch (fraction of all condition stories) / condition types covered out of 38, at keep 11% / 20% / 37%.

| Picker | AUC | keep 11% | keep 20% | keep 37% |
|---|---|---|---|---|
| Current free-only (results.json) | .757 | 68 / 26 / 33 | 60 / 41 / 37 | 49 / 63 / 37 |
| **New free-only: stack of T1-T6 signals (S2)** | **.783** | **73 / 28 / 34** | **64 / 44 / 36** | **53 / 67 / 37** |
| New free-only: old signals + all new (S1) | .782 | 72 / 27 / 34 | 64 / 44 / 36 | 53 / 68 / 37 |
| Old free + T3 only | .773 | 74 / 28 / 35 | 62 / 43 / 35 | 52 / 66 / 37 |
| Old free + T4 only | .770 | 72 / 27 / 34 | 61 / 42 / 37 | 51 / 65 / 37 |
| Current free + BitMob | .792 | 80 / 30 / 34 | 68 / 47 / 36 | 54 / 69 / 37 |
| **New free + BitMob (S2 + BitMob)** | **.806** | 77 / 29 / 33 | **70 / 48 / 36** | **56 / 71 / 37** |
| New (old + all new) + BitMob (S1) | .805 | 78 / 30 / 33 | 70 / 48 / 36 | 55 / 71 / 37 |

Single signals alone (test AUC): T3 per-dial noisy-or .762, T1b .755, T1 .741, T2 .738, T4 .728, T3b (max) .717, T6 .690, T6b .639, T5b .589, T5a .518.

Selection rule: the row marked "new" was picked by training cross-validation AUC (S2 .792, S1 .791), not by test. Training and test AUC for the stack agree in order.

Caveat that applies to both BitMob rows and the current picker: BitMob's scores on training stories may be optimistic (it saw them), so the stack may over-trust it. We kept the same method as the current picker for a fair comparison; a rank average (no fitting) gave .785 for the current picker.

Noise: at keep-11% there are 220 stories, so one standard error on share is about 3 points. The keep-11% gains (68 to 73 free-only; 80 to 77 with BitMob) are within noise. The AUC and keep-20% / keep-37% gains are less noisy but still modest (about 2 to 4 points).

## 4. What worked and what did not, and why

Worked [MEASURED]:
- Per-condition-type models, combined as "any fires" (T3): best single new signal (.762 vs .750 for the existing one-model bag of words). Reason: one model for "any condition" has to average over very different vocabularies (prices vs. wars vs. drought); a model per type does not.
- Word + character n-grams with sublinear counts and class weights (T1b): small gain over the existing bag of words (.755 vs .750), mainly by handling word-form variants without a lemmatizer.
- BM25 similarity to per-type centroid documents (T4): adds a different view (a style of "does it read like a typical story of type X"), helps in the stack (.757 to .770).
- Stacking several of these views: they overlap but not completely; the combined gain (+.026 AUC) is bigger than any single one.

Did not work [MEASURED]:
- compromise change patterns (T5a): AUC .518, essentially random. Likely because the labelled "conditions" are often stated without a number-plus-verb phrase, and our patterns require both. Also the input is short (title plus a snippet), so the patterns rarely fire. Not a statement about the library in general.
- Sentiment, negation, tense (T5b): .589 alone, adds nothing in the stack. Condition stories are not systematically more negative.
- WordNet hyponym expansion (T6): no gain over the existing synonym expansion (.690 vs .694). Unfiltered expansion (T6b) hurts (.639): broad word families bring in many irrelevant words. Filtering by training lift is what keeps it safe, and then it is no better than before.
- Diversity picking: no gain in types covered (33 to 35 of 38 at all keep levels; already 36 to 37 at keep-20%) and it cost 1 to 2 points of share. Coverage is not a bottleneck.
- Plain TF-IDF logistic (T1) by itself was no better than the existing bag of words.
- ComplementNB with chi-squared (T2): about the same as the existing model; small gain when stacked.

Not tested: wink `learnCustomEntities`, `HashingVectorizer`, `CalibratedClassifierCV`, compromise `.topics()` and dates plugin (not shown in docs snippets or no time; the first two would not change ranking much).

## 5. Recommendation for the round-5 picker

1. Replace the single bag-of-words model with the new free stack (S2): per-type logistic models (T3), word + character TF-IDF (T1b), chi-squared + ComplementNB (T2), BM25 per-type centroids (T4), plus the existing keyword + WordNet signals. Expected: about +.025 AUC and +3 to 4 points of share at keep-20% and keep-37%.
2. Keep BitMob in the stack; the gain on top of it is smaller (+.014 AUC, +2 points at keep-20%, nothing at keep-11%). If the round-5 budget is tight, the new free stack alone is nearly as good as the current free + BitMob at keep-37% (53 vs 54).
3. Drop the compromise pattern, sentiment and WordNet-closure features; they cost time and add nothing here.
4. Before relying on it, re-check on a larger test or a second test set; the differences are 2 to 4 points on 2,000 stories.

## 6. Reproduce

```
cd /tmp/claude-0/-workspace/56bd04e1-c166-41e7-b6b1-a8834c019bd6/scratchpad/free_signals
node tricks/feat.cjs train_in.jsonl tricks/feat_train.jsonl      # compromise + wink features (about 10 s)
node tricks/feat.cjs test_in.jsonl  tricks/feat_test.jsonl
CUDA_VISIBLE_DEVICES= /workspace/kev/.venv/bin/python tricks/run_tricks.py > tricks/run.log   # about 4 min, writes tricks_results.json
```
`run_tricks.py` executes the first half of `run.py` (data and existing signals) without writing `results.json` or the picker pickle. Doc sources: Context7 ids `/spencermountain/compromise`, `/winkjs/wink-nlp`, `/winkjs/wink-bm25-text-search`, `/nltk/nltk`, `/scikit-learn/scikit-learn`.
