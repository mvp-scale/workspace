# Headline classifier test: pre-registered (written before any result)

Question: can the local classifier turn a headline + one-line summary into world-dial readings, only when the evidence is solid ("not reactive")?
Dials classified: 9 (prices, job security, safety fear, health risk, trust in institutions, community, technology pace, daily disruption, optimism). Dial 10, news overload, is not read from content; it comes from report volume in the ledger.
Each dial has 4 yes/no questions for "up" and 4 for "down" (72 questions) + 3 story-type questions (happened / opinion / forecast) = 75 questions per headline, sent in batches of 20.
Vote: yes at P >= 0.65, no at P <= 0.35, else unsure. A direction is PRESENT if >= 3 of its 4 questions vote yes and <= 1 votes no. A dial MOVES only if exactly one direction is present AND the story type 'happened' has P >= 0.5.
100 headlines written by me with known labels: 36 directed (9 dials x up/down x 2), 20 irrelevant, 10 opinion, 10 forecast, 10 ambiguous (contested dial should NOT move), 14 multi-dial.
Pass lines:
 N1 directed: right dial and direction >= 80%; wrong direction <= 5%.
 N2 irrelevant: any dial moves in <= 10% of headlines.
 N3 opinion and forecast: any dial moves in <= 20% of those 20 headlines.
 N4 ambiguous: contested dial does not move in >= 60%.
 N5 multi-dial: >= 60% of the expected dial changes found; on average <= 1 extra dial moved per headline.
 N6 time per headline <= 0.5 s.
 N7 grouping helps: the false-trigger rate on irrelevant+opinion+forecast (30 headlines) is lower with the 4-question group rule than with a single question rule (first question per dial-direction, P >= 0.5) by >= 5 points.
Caveats declared in advance: headlines are written by me in clean newspaper style, easier than real feeds; labels are my own; 100 items, one run; the classifier has not been validated on real news.
