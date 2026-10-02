RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE

# t40_skin_lesion

Status: READY

## Recon

Source: HAM10000 (Tschandl, Rosendahl, Kittler 2018, Scientific Data, doi 10.1038/sdata.2018.161). Owner page: Harvard Dataverse, https://doi.org/10.7910/DVN/DBW86T. Licence stated by the dataset card and the owner's citation record: CC BY-NC 4.0 (non-commercial; local testing only, do not redistribute commercially). Files were fetched from the ungated Hugging Face file mirror `ShiroOnigami23/skin-cancer-ham10000-dataset` (card says cc-by-nc-4.0 and points to the Dataverse DOI), no login or form. The mirror's `HAM10000_metadata.csv` is the original metadata file. Only the 25 images used were downloaded (5.8 MB in total with the CSV).

Columns of `HAM10000_metadata.csv`: lesion_id, image_id, dx, dx_type, age, sex, localization. 10,015 rows, 10,015 unique image_id.

Counts of (dx, dx_type): nv/follow_up 3704, nv/histo 2498, mel/histo 1113, bkl/histo 766, bcc/histo 514, nv/consensus 503, akiec/histo 327, bkl/consensus 264, vasc/consensus 75, bkl/confocal 69, vasc/histo 67, df/consensus 60, df/histo 55.

Three annotation rows (no image bytes):

    lesion_id=HAM_0006843 image_id=ISIC_0024457 dx=bcc dx_type=histo age=85.0 sex=male localization=face
    lesion_id=HAM_0006241 image_id=ISIC_0031379 dx=nv  dx_type=histo age=40.0 sex=male localization=back
    lesion_id=HAM_0002803 image_id=ISIC_0028110 dx=nv  dx_type=histo age=40.0 sex=female localization=back

## Labels

Pick-one question: "Which diagnosis best describes this skin lesion?" Options: melanocytic nevus (nv), melanoma (mel), benign keratosis (bkl), basal cell carcinoma (bcc). Answer = the `dx` column, using only rows with `dx_type == histo` (pathology-confirmed); follow_up, consensus and confocal rows are excluded. Seed 40. Only lesions with a single image in the dataset are eligible (no near-duplicate views). Counts: 6 nevus, 6 melanoma, 6 benign keratosis, 7 basal cell carcinoma (max 28%). Chance rate 25%. Option order is shuffled per item. `rederive(item)` re-reads the CSV by image_id.

`label_origin`: dx column, dx_type = histo. The dermatoscopic images carry no faces, names or dates.

## Caveats

- Research benchmark, not for clinical use. Do not use scores for any care decision.
- The images are single-lesion dermatoscopic photos; HAM10000 is skewed to light skin tones and to Vienna and Queensland clinics.
- Benign keratosis is a grouped class in HAM10000 (solar lentigines, seborrheic keratoses, lichen-planus-like keratoses).
- Even histo labels reflect a single pathology report, and some nevi were excised because they were suspicious, so the nevus class is not a random nevus.
- Non-commercial licence: local testing only.

## Angle questions (derived from the annotation, not built)

All use the same images and the metadata row of that image_id.

1. Malignancy grouping (choice: malignant / benign). Rule: malignant if dx is mel or bcc; benign if dx is nv or bkl.
2. Body site region (choice: head and neck / trunk / arm and hand / leg and foot). Rule from `localization`: face, scalp, neck, ear = head and neck; back, chest, abdomen = trunk; upper extremity, hand = arm and hand; lower extremity, foot = leg and foot. Skip genital, acral or unknown.
3. Age band (choice: under 50 / 50 to 69 / 70 and over). Rule from `age`; skip items with empty age.
4. Sex of the patient (choice: female / male). Rule: `sex` column; skip unknown. Note this is not visible in the image, so it measures guessing, a useful control near 50%.
5. Is the lesion on the back? (noul). Rule: yes when `localization == back`.
6. Is the lesion one of the two classes grouped as melanocytic-origin? (noul). Rule: yes when dx is nv or mel; no when bkl or bcc.
