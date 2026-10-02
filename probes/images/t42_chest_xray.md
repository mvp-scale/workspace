RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE

# t42_chest_xray

Status: READY

## Recon

Source: Kermany, Zhang, Goldbaum (2018), "Labeled Optical Coherence Tomography (OCT) and Chest X-Ray Images for Classification", Mendeley Data V2, doi 10.17632/rscbjbr9sj.2; paper Cell 172(5), 2018. Used through the Hugging Face mirror `hf-vision/chest-xray-pneumonia` (not gated, no login). Licence as stated on the mirror card: CC-BY-4.0. Downloaded one shard only: `data/test-00000-of-00001.parquet` (about 79 MB; 624 rows: 234 NORMAL, 390 PNEUMONIA, of which 242 bacteria and 148 virus by file name). The rest of the repo (about 1.2 GB) was not kept.

Columns: `image` (bytes + original file path), `label` (0 NORMAL, 1 PNEUMONIA). First rows (no image bytes):

- `{"image.path": "IM-0001-0001.jpeg", "image.bytes": 252680, "label": 0}`
- `{"image.path": "IM-0003-0001.jpeg", "image.bytes": 329189, "label": 0}`
- `{"image.path": "person97_bacteria_468.jpeg", "image.bytes": 81458, "label": 1}` (a PNEUMONIA row, from the end of the file)

Label origin (from the card and the paper): chest radiographs were first screened for quality; diagnoses were graded by two expert physicians, and the evaluation (test) set was checked by a third expert. This is human expert labelling of the images, not text mining of reports. It passes the label test.

## Labels

Question (noul, labels no/yes): "Does this chest X-ray show pneumonia or another abnormality?" Yes = `label == 1` (PNEUMONIA), no = `label == 0` (NORMAL). Note the dataset only has two classes, so "another abnormality" never occurs apart from pneumonia. Sampling: seed 42, test split, one image per patient id (parsed from the file name), 13 yes (7 bacterial, 6 viral) and 12 no. Chance rate 50%. `rederive(item)` re-reads the parquet row named in `source_id`.

## Caveats

- Pediatric (ages 1 to 5), single hospital (Guangzhou Women and Children's Medical Center), anteroposterior films. Do not generalise to adults.
- Known domain quirk: the NORMAL and PNEUMONIA images differ in file-size and acquisition style, so a model may use shortcuts instead of lung findings.
- Not checked for burned-in text: images were not inspected by eye. The set is anonymised by the owners; some films carry a small laterality marker. If any readable name or date turns up, drop that item.
- Kept local, git-ignored, under `/workspace/data/`. Provenance notes read: research benchmark, not for clinical use.

## Angle questions (derived from the annotation, not built)

All use the original file name stored in `image.path` (kept in each item's `source_id`) and the `label` column.

1. Cause of pneumonia (choice: bacterial / viral / none). Rule: file name contains `_bacteria_` gives bacterial, `_virus_` gives viral, label 0 (name starts `IM-` or `NORMAL2-IM-`) gives none. In this 25: 7 bacterial, 6 viral, 12 none.
2. Is this pneumonia viral rather than bacterial (noul)? Rule: yes if the name contains `_virus_`, no if `_bacteria_`; only defined for the 13 PNEUMONIA items.
3. Is this image a normal chest (noul)? Rule: yes if `label == 0`. The mirror of the main question, for checking answer consistency.
4. Image orientation (choice: portrait / landscape / square). Rule: compare width and height of the saved image file (computed from the pixels, not the label). Tests whether the model's accuracy depends on framing.
5. Which source file style (choice: normal-film-style / pneumonia-film-style). Rule: the same as label 0 or 1; not a medical question, kept as a shortcut probe to compare against question 1 results.
6. Lung side (choice): NOT available. The dataset has no side annotation, so no lung-side question can be derived.
