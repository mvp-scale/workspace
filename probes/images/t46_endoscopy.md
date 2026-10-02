RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE

# t46_endoscopy

Status: READY

Pick-one: "Which finding does this endoscopy image show?" Options: normal cecum, polyp, ulcerative colitis, esophagitis. 25 images: polyp 7, normal cecum 6, ulcerative colitis 6, esophagitis 6. Largest class 28% (limit 40%). Chance rate 25%. Seed 46; the builder is re-runnable with identical output (checked by md5).

## Source and licence

HyperKvasir labelled images (Borgli et al., Scientific Data 2020, doi 10.1038/s41597-020-00622-y), taken from the Hugging Face mirror `sahilur/hyper-kvasir-labeled-images` (ungated). Only `valid.zip` (393 MB) was downloaded to `/workspace/data/sources/image-lab/hyper-kvasir/`; the 3.1 GB `train.zip` was not. The mirror's README and `license.txt` state CC BY 4.0. The Nature paper's metadata lists CC0 for the article; I could not fetch the Simula dataset page (datasets.simula.no) to confirm the dataset licence from the owner directly, so the mirror's CC BY 4.0 statement is what is recorded. The paper's abstract says the data were collected at Baerum Hospital (Norway) and "partly labeled by experienced gastrointestinal endoscopists". Research benchmark, not for clinical use.

## Recon

Archive `valid.zip`: 1,092 entries, folder per class (`valid/<class>/<uuid>.jpg`, no CSV). Class counts in this split: cecum 101, polyps 103, ulcerative-colitis-grade-1/2/3 20/45/14, esophagitis-a 41, esophagitis-b-d 26, plus others (z-line, pylorus, bbps, dyed-lifted-polyps, retroflex, and so on). Three real annotation rows (member path = class label; no image bytes):

1. `valid/polyps/c9ad6395-c08f-4824-8937-62f7d14a283b.jpg` -> class `polyps`
2. `valid/cecum/aecd8059-0145-4487-9295-f47fbaf018dd.jpg` -> class `cecum`
3. `valid/cecum/e74b7947-3725-42d8-97e0-19f9f8f499b9.jpg` -> class `cecum`

## Label rule

`expected` = the dataset's class folder of the image, mapped: `cecum` -> normal cecum; `polyps` -> polyp; `ulcerative-colitis-grade-1|2|3` -> ulcerative colitis; `esophagitis-a|b-d` -> esophagitis. Folders in the picked 25: polyps 7, cecum 6, esophagitis-b-d 5, esophagitis-a 1, ulcerative-colitis-grade-2 4, grade-3 2. `rederive(item)` re-reads the member path. Distractors are the other three options (always the same four, order shuffled per item). No yes/no variant: `cecum` is a landmark, not a polyp-free class, and the set has no pathology-negative labels in the same sense.

## Caveats

- "Partly labelled" by experts: the paper says part of the data was expert labelled; per-image labeller identity is not in the mirror. Treat the labels as the dataset's own, not independently verified.
- Mirror, not the original host; the mirror's split names (`valid`) are the mirror author's.
- Some images contain the dataset's green scope-position inset box; no readable text or personal data was seen in the code path, but images were not individually inspected (no eyeballing by design).
- Folders are classes, not diagnoses: an image in `polyps` is a polyp-class frame, not a confirmed pathology report.
- Cecum is a landmark class, so "normal cecum" means "cecum landmark view".

## Angle questions (derived from the annotation, not built)

All use the class folder name (`provenance.notes` and `source_id`) as the only input.

1. Category: "Is this an anatomical landmark or a pathological finding?" Rule: `cecum` -> landmark; `polyps`, `ulcerative-colitis-*`, `esophagitis-*` -> pathological. (HyperKvasir's own category grouping: landmarks, pathological findings, quality of mucosal views, therapeutic interventions.)
2. Region: "Is this from the upper or lower GI tract?" Rule: `esophagitis-*` -> upper; `cecum`, `polyps`, `ulcerative-colitis-*` -> lower.
3. Inflammation: "Does this image show an inflammatory condition?" (yes/no) Rule: yes for `ulcerative-colitis-*` and `esophagitis-*`; no for `cecum` and `polyps`.
4. Polyp present: "Does this image show a polyp?" (yes/no) Rule: yes for `polyps`; no for the other three folders. Note the negatives are other findings, not confirmed polyp-free colon.
5. Severity: for the 6 ulcerative colitis items, "What grade is shown?" (2 or 3) Rule: grade from the folder suffix. For the 6 esophagitis items, "Is it grade A or grade B-D?" Rule: `esophagitis-a` vs `esophagitis-b-d`. Only 1 grade A in this sample, so a larger draw is needed before using it.
