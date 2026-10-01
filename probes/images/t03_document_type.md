# t03_document_type

Status: READY

## Recon

The full RVL-CDIP archive (`aharley/rvl_cdip`) is about 39 GB and was not downloaded. The copy `hf-tuner/rvl-cdip-document-classification` is about 1.04 GB, ungated, and its README has no licence line. Local use only. Only the test parquet is on disk: `data/test-00000-of-00001.parquet` (992 rows, 117 MB).

Columns: `image`, `label` (ClassLabel). Names from the README, id 0 to 15: letter, form, email, handwritten, advertisement, scientific report, scientific publication, specification, file folder, news article, budget, invoice, presentation, questionnaire, resume, memo. The card says 62 test images per class and a long side of at most 1000 px.

## Labels

Question: "What type of document is this?" Four options: the true class name plus three other class names. Seed 3 uses nine classes (eight of them three times, one of them once). Chance rate 25%. No class is the right answer more than 40% of the time.

`label_origin`: label class name. `rederive` reads the test row again. URL: https://huggingface.co/datasets/hf-tuner/rvl-cdip-document-classification

## Caveats

This is a resized subset of RVL-CDIP, not the original 39 GB release. The small copy does not state a licence.
