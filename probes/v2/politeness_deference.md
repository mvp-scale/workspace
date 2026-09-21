# politeness_deference (Stanford Politeness Corpus, Wikipedia)

- Files: politeness_deference.jsonl (100 rows: 50 yes / 50 no); builder build_politeness_deference.py (seed 20260921).
- Source: ConvoKit release, https://zissou.infosci.cornell.edu/convokit/datasets/wikipedia-politeness-corpus/wikipedia-politeness-corpus.zip (docs https://convokit.cornell.edu/documentation/wiki_politeness.html). Licence CC BY 4.0 (per ConvoKit docs). Retrieved 2026-09-21. Read directly from the zip, no convokit install needed (a scratch venv /workspace/data/sources/ckvenv exists but is unused).
- Citation: Danescu-Niculescu-Mizil, Sudhof, Jurafsky, Leskovec, Potts. A Computational Approach to Politeness with Application to Social Factors. ACL 2013.
- Labels: the corpus's own Binary field: +1 (top quartile of annotator politeness score) = yes, -1 (bottom quartile) = no; middle 50% dropped. 1039 yes / 1015 no usable (20-300 chars, unique) of 2178 quartile items; 50 each sampled randomly.
- Caveats: labels rate politeness of the request, not "deference" strictly. Wikipedia talk-page requests with URLs replaced by <url>. In a 20-item sample, no clear mislabels but several yes items are only mildly polite (thanks, greetings, "have you finished the books I suggested?"), and some no items are merely direct questions (e.g. "What is a wall these days?") rather than rude. Model may be confused by scattered no items that are neutral.
- Contamination: public 2013 corpus, possibly seen in training.
