# Presence, round 2: three options (ledger T32, L752)

Evidence so far: rewording the timing rule left the spread of yes-rates at 0.188 and alpha at 0.590 (L752). Each model keeps its own strictness (Clef loose, Gemma strict). The MAVEN-FACT check found no gross false-yes errors for any rater (L730) but cannot show misses. Rater answers changed on 23 to 30 of 597 items by rewording alone.

## Option A: require stated evidence
Add to the presence question: answer yes only if words in the item state that the change has already happened. Same typed yes/no structure for every rater. Cost: about 25 minutes local, 0 USD. Tests check 5 of the field qualifier (playbook 13: evidence directly in the input). Weakness: the model self-checks; no span is returned.

## Option B: accept the spread, calibrate per rater
Keep the wording. Give each rater its own yes-threshold, set on an outside anchor, and combine raters by routing: all agree means accept, split means a soft target (T27). Cost: needs probabilities from each rater and an anchor with positives; the only anchor so far is one-sided (no positives). Weakness: cannot set a threshold without positives.

## Option C: park presence as a yes/no field
Report presence as not ready, keep the CPU reader's 'finds 32.5 percent of real cases' as the stated limit, and move effort to the fields that can pass. Cost: none. Weakness: leaves condition, and with it which, direction and size, unfinished.

## Rule for choosing
Pick the option that can still change the outcome cheaply and is testable now. If it fails its pre-registered line, the next option in the order B then C applies.
