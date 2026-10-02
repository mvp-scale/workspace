RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE

# t47_brain_mri

Status: READY

## Source and licence

`AIOmarRehan/Brain_Tumor_MRI_Dataset` on Hugging Face (ungated, no login). Only the test-split parquet was downloaded (26 MB) to `/workspace/data/sources/image-lab/brain-mri-aiomar/`. URL: https://huggingface.co/datasets/AIOmarRehan/Brain_Tumor_MRI_Dataset

Licence as stated on the owner's card: CC0 1.0 (public domain). The card says the data combines Figshare (Cheng et al.), SARTAJ and Br35H; this is the Kaggle "Brain Tumor MRI" set. Upstream Figshare licence is reported as CC BY 4.0 (not re-checked on Figshare). The card does not give per-image provenance, so treat the CC0 statement as the mirror owner's claim.

## Recon

Columns: `image` (struct: `bytes`, `path`), `label` (class_label: 0 glioma, 1 meningioma, 2 notumor, 3 pituitary). 1,311 rows (glioma 300, meningioma 306, notumor 405, pituitary 300). Most images are 512x512 PNG; some are about 225x225.

First 3 annotation rows (no image bytes):
- row 0: path `test1.png`, bytes 25826, label 0 (glioma)
- row 1: path `test10.png`, bytes 20819, label 0 (glioma)
- row 2: path `test100.png`, bytes 18634, label 0 (glioma)

## Label rule

Question (choice, 4 options, shuffled by seed): "Which type of brain tumour is shown, if any?" Options: glioma, meningioma, pituitary tumour, no tumour. Answer = the `label` column. Seed 47. Sample: 6 glioma, 6 meningioma, 7 no tumour, 6 pituitary tumour (largest class 28%). Chance rate 25%. `rederive(item)` re-reads the parquet row named in `source_id` and maps its label.

## Label origin and caveats

Human labels inherited from the source datasets: Figshare (Cheng et al.) tumour types come from clinical records and were confirmed by radiologists; Br35H supplies the no-tumour class; SARTAJ labels are community-made, and the card admits some SARTAJ glioma labels were wrong and were replaced from Figshare. So label quality is high but not guaranteed for every image. The no-tumour class comes from a different source than the tumour classes, so image style (crop, margins, scanner) may leak the class. Slices are not necessarily the same plane or sequence. No patient identifiers are legible in what was built, but this was not checked image by image. Research benchmark, not for clinical use.

## Angle questions (derived from the annotation, not built)

The dataset has only the `label` column (no plane, no bounding boxes), so all derive from it.
1. Is a tumour present? (yes/no) Rule: yes if label is glioma, meningioma or pituitary; no if notumor. Chance 50%.
2. Is this tumour a glioma? (yes/no) Rule: yes iff label == glioma.
3. Is the tumour in the pituitary region? (yes/no) Rule: yes iff label == pituitary (class definition, not a location measurement).
4. Which of these two tumour types is shown, glioma or meningioma? (choice of 2) Rule: restrict to items with label glioma or meningioma; answer = label.
5. Does this scan show a tumour that is NOT a pituitary tumour? (yes/no) Rule: yes iff label in {glioma, meningioma}.
6. Is the scan normal or abnormal? (choice of 2) Rule: normal iff label == notumor.
