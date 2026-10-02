# Morning report: medical and dental family cascade

RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE. Pilot sets of 48 to 100 images per task, 100 questions per image at most, thresholds fixed in advance. All numbers are in the Image Lab under Medical and dental (the family cascade table, and a card on each task page). Code: `cascade3.py`, `ontology_check.py`, `cascades/v3/*.json`, `pilots/*.jsonl`. Results: `/workspace/data/image-lab/runs/winnow-cascade3/`.

## What was built
One ontology per task (8 to 14 predefined families of finding, up to three levels deep, 100 to 147 questions in the whole tree), a 10-question gate, a breadth pass over every family, then depth into the families that look detectable. The order of questions is stored, so accuracy can be read at any number of questions spent.

## Results (accuracy among images that passed the gate, with 95% interval)

| Task | Chance | Single question | After the broad pool | At 100 questions | Fitted combination of family scores (cross-validated) |
|---|---|---|---|---|---|
| Chest X-ray | 50% | 64% (54-73) | 83% (74-89) | 77% (68-84) | 80% |
| Retina OCT | 25% | 81% (72-87) | 57% (47-66) | 62% (52-71) | 85% |
| Endoscopy | 25% | 69% (59-77) | 58% (48-67) | 56% (46-65) | 80% |
| Pathology patch | 50% | 64% (54-73) | 60% (50-69) | 65% (55-74) | 76% |
| Brain MRI | 25% | 64% (54-73) | 36% (27-46) | 41% (32-51) | 62% |
| Bone fracture | 50% | 61% (51-70) | 58% (48-67) | 62% (52-71) | 66% |
| Skin lesion | 25% | 37% (28-47) | 35% (26-45) | 33% (24-42) | 46% |
| Dental caries | 50% | 60% (46-73) | 50% (36-64) | 52% (38-66) | 48% |

## What it says
1. The family cascade with hand-written votes helps on chest only. Where the single question already works (retina, endoscopy, brain) the votes lose to it.
2. The families themselves are detected well in several tasks, so the observations carry information. A cross-validated fit on the family scores beats the single question on chest, retina, endoscopy, pathology, bone and skin. The weak link is my hand-written family-to-class mapping. A fitted combination needs labelled images (about 100 per task here) and has not been tested on a second sample.
3. Extra depth does not add accuracy. Chest peaks at 50 questions (83%) and is flat to lower at 100.
4. Skin and dental stay near chance: the model cannot see the features that separate those classes.

## What the model can detect (family scored against the dataset's own metadata, AUC)
Bone: hand, leg and hip 1.00, lateral view 0.89, fracture line 0.71. Chest: diffuse haze 0.86, focal opacity 0.84. Endoscopy: protruding growth 0.88, esophageal lining 0.85, cecum landmarks 0.82. Brain: focal mass 0.85, mass location 0.80. Dental: impacted or missing teeth 0.79, gap in tooth row 0.72, caries-bearing crown only 0.55. Pathology: stain colour 0.68, fat and empty space 0.65. Skin: nothing bound beyond body site (0.66).

## Caveats
Ontologies are drafts for clinician review. Brain "no tumour" images come from a different source than the tumour classes (image style can leak the class; 23 of 25 no-tumour images are RGB). Retina, chest and pathology sets are widely used and may be in the model's training data. Fitted results are cross-validated on 100 images per task, one sample, not a held-out test.

## Suggested next steps
Fit the combination on one sample and test it on a second held-out sample per task; add the best step count per task to stop early; extend the ontology method to the non-medical tasks.
