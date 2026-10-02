# Layered cascade pilot results

Generated 2026-10-02 by cascade.py. RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE. Pilot sets of 48 to 100 images (pilots.py); the 25-image lab tasks are a separate sample. Thresholds were fixed before the first run. The 'relative votes' variant was added after seeing the first results, so treat it as exploratory.

## Pre-specified thresholds (absolute votes)
```

== skin: 100 images, chance 25% ==
single original question      : 37/100 = 37%
plain average of the layer's answers: 28/100 = 28%
cascade, forced best guess    : 28/100 = 28% (2 images had no guess: gate failed)
cascade, CONSENSUS only       : handled 56/100 = 56%, right on 18/56 = 32%
single question, most confident first while precision >= 95%: handled 5/100 = 5%
where the problems sit (outcome: images, right if forced):
  NOT_USABLE   2   right 0/0
  UNCLEAR      1   right 1/1
  CONFLICT    30   right 7/30
  WEAK        11   right 2/11
  CONSENSUS   56   right 18/56
questions per image: 1 baseline + 20 gate/characteristics + 9.8 follow-ups

== dental: 48 images, chance 50% ==
single original question      : 29/48 = 60%
plain average of the layer's answers: 24/48 = 50%
cascade, forced best guess    : 24/48 = 50% (2 images had no guess: gate failed)
cascade, CONSENSUS only       : handled 40/48 = 83%, right on 22/40 = 55%
single question, most confident first while precision >= 95%: handled 1/48 = 2%
where the problems sit (outcome: images, right if forced):
  NOT_USABLE   2   right 0/0
  UNCLEAR      1   right 0/1
  WEAK         5   right 2/5
  CONSENSUS   40   right 22/40
false positives (said caries present, was not): single 19, cascade-forced 22, consensus-handled 18
questions per image: 1 baseline + 18 gate/characteristics + 6.0 follow-ups

== chest: 100 images, chance 50% ==
single original question      : 64/100 = 64%
plain average of the layer's answers: 75/100 = 75%
cascade, forced best guess    : 79/100 = 79% (1 images had no guess: gate failed)
cascade, CONSENSUS only       : handled 53/100 = 53%, right on 46/53 = 87%
single question, most confident first while precision >= 95%: handled 15/100 = 15%
where the problems sit (outcome: images, right if forced):
  NOT_USABLE   1   right 0/0
  UNCLEAR      4   right 1/4
  WEAK        42   right 32/42
  CONSENSUS   53   right 46/53
false positives (said pneumonia, was not): single 36, cascade-forced 20, consensus-handled 7
questions per image: 1 baseline + 19 gate/characteristics + 6.0 follow-ups
```

## Relative votes (each question centred on its own median over the batch; exploratory)
```
(votes are relative to each question's own median over the batch; no labels used)

== skin: 100 images, chance 25% ==
single original question      : 37/100 = 37%
plain average of the layer's answers: 28/100 = 28%
cascade, forced best guess    : 32/100 = 32% (0 images had no guess: gate failed)
cascade, CONSENSUS only       : handled 0/100 = 0%, right on 0/0
single question, most confident first while precision >= 95%: handled 5/100 = 5%
where the problems sit (outcome: images, right if forced):
  UNCLEAR     88   right 31/88
  CONFLICT    11   right 1/11
  WEAK         1   right 0/1
questions per image: 1 baseline + 20 gate/characteristics + 9.8 follow-ups
(votes are relative to each question's own median over the batch; no labels used)

== dental: 48 images, chance 50% ==
single original question      : 29/48 = 60%
plain average of the layer's answers: 24/48 = 50%
cascade, forced best guess    : 28/48 = 58% (0 images had no guess: gate failed)
cascade, CONSENSUS only       : handled 0/48 = 0%, right on 0/0
single question, most confident first while precision >= 95%: handled 1/48 = 2%
where the problems sit (outcome: images, right if forced):
  UNCLEAR     40   right 23/40
  WEAK         8   right 5/8
false positives (said caries present, was not): single 19, cascade-forced 14, consensus-handled 0
questions per image: 1 baseline + 18 gate/characteristics + 6.0 follow-ups
(votes are relative to each question's own median over the batch; no labels used)

== chest: 100 images, chance 50% ==
single original question      : 64/100 = 64%
plain average of the layer's answers: 75/100 = 75%
cascade, forced best guess    : 80/100 = 80% (3 images had no guess: gate failed)
cascade, CONSENSUS only       : handled 39/100 = 39%, right on 39/39 = 100%
single question, most confident first while precision >= 95%: handled 15/100 = 15%
where the problems sit (outcome: images, right if forced):
  NOT_USABLE   3   right 0/0
  UNCLEAR     57   right 41/57
  WEAK         1   right 0/1
  CONSENSUS   39   right 39/39
false positives (said pneumonia, was not): single 36, cascade-forced 9, consensus-handled 0
questions per image: 1 baseline + 19 gate/characteristics + 6.0 follow-ups
```

## Is the information in the answers at all? (cross-validated logistic regression, supervised upper bound)
```
skin: cross-validated logistic regression on the 20 stage-1 answers: 46/100 = 46%  (chance 25%)
dental: cross-validated logistic regression on the 18 stage-1 answers: 22/48 = 46%  (chance 50%)
chest: cross-validated logistic regression on the 19 stage-1 answers: 84/100 = 84%  (chance 50%)
```
