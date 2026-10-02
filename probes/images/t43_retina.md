# t43_retina

RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE

Status: READY

Fundus sets (APTOS 2019 on Kaggle, Messidor-2) need a login or their own terms, so this task uses retinal OCT instead (the fallback in the brief).

## Recon

Source: Kermany et al. 2018, "Large Dataset of Labeled OCT and Chest X-Ray Images" (Mendeley Data rscbjbr9sj, V3), via the ungated Hugging Face mirror `zacharielegault/Kermany2017-OCT` (OCT images only, unedited). Licence on the mirror card: `cc-by-4.0`, and the card says the original was released under CC BY 4.0. Attribution required. Only `data/test-00000-of-00001.parquet` (85 MB) was downloaded to `/workspace/data/sources/image-lab/kermany-oct/`.

Columns: `image` (struct: bytes, path) and `label` (class id 0 CNV, 1 DME, 2 DRUSEN, 3 NORMAL). Test split: 1000 rows, 250 per class. Three rows (no image bytes):

| row | image.path | image bytes | label |
|---|---|---|---|
| 0 | CNV-1032178-1.jpeg | 69392 | 0 (CNV) |
| 1 | CNV-1034361-1.jpeg | 73847 | 0 (CNV) |
| 2 | CNV-1034361-2.jpeg | 87609 | 0 (CNV) |

## Labels

Pick-one: "Which finding does this retinal OCT scan show?" Options CNV, DME, DRUSEN, NORMAL (shuffled per item with seed 43 * 1000 + index). Answer is the dataset's `label` column. Label origin: per the dataset's authors, images were graded by trained graders and the test set was checked by independent ophthalmologists; this is human expert grading, not a model. Seed 43 takes 7 CNV, 6 DME, 6 DRUSEN, 6 NORMAL (max 28%), one scan per patient id (the number in the file name). Chance rate 25%. `rederive(item)` looks up `source_id` (the file name) in the parquet and returns the class.

## Caveats

Do not use for clinical purposes. Scans are single B-scans, so some are ambiguous at the DME/CNV boundary; the dataset's own estimate of grader error is small but not zero. Test split only (the train split was not downloaded). The 1000-image test set is small and widely used, so a model may have seen it. No text is burned in: the images are B-scans and the file name carries only a class, a de-identified number and a scan index (not checked by eye).

## Angle questions (derived from the annotation, not built)

1. Is this scan abnormal? yes unless label is NORMAL (abnormal is 75% of the split, so sample 12 or 13 of each if built).
2. Is this scan neovascular (wet) disease? yes iff label == CNV; no for DME, DRUSEN, NORMAL.
3. Does this scan show fluid-related pathology? yes iff label is CNV or DME; no iff DRUSEN or NORMAL.
4. Does this scan need urgent referral (sight-threatening treatable disease)? yes iff label is CNV or DME; no otherwise. A grouping rule only, not clinical advice.
5. Which of two groups does it belong to: AMD-spectrum (CNV, DRUSEN) vs non-AMD (DME, NORMAL)? Answer from the label by that grouping.
6. Is the scan from a patient with more than one scan in the split? Count rows in the test parquet sharing the patient id (second field of `image.path`); yes if the count is above 1. (Dataset-structure question, not an image finding.)
