RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE

# t44_dental_xray

Status: READY

## Recon

Source: DENTEX (MICCAI 2023 challenge), `ibrahimhamamci/DENTEX` on Hugging Face, https://huggingface.co/datasets/ibrahimhamamci/DENTEX. Licence on the owner's page: CC-BY-NC-SA-4.0 (non-commercial, share-alike, attribution). Not gated, no login. Allowed for local testing only; do not redistribute the images.

Repo files (sizes): `DENTEX/training_data.zip` 10.9 GB (not downloaded), `DENTEX/test_data.zip` 765 MB, `DENTEX/validation_data.zip` 150 MB, `validation_triple.json` 64 KB. Downloaded: test_data.zip, validation_data.zip, validation_triple.json to `/workspace/data/sources/image-lab/dentex/` (about 0.9 GB). Only test_data.zip is used.

Label origin: expert annotation by dentists, per the card (panoramic X-rays from three institutions, hierarchically annotated, diagnosis classes caries, deep caries, periapical lesion, impacted tooth). `test_data.zip` holds `disease/input/test_N.png` (250 panoramic X-rays) and `disease/label/test_N.json` (LabelMe polygons). Each polygon label reads `<group digit>-<finding>-<FDI tooth number>` with Turkish finding words: çürük (caries), gömülü (impacted), küretaj (curettage, a periapical-type finding), kanal (root canal treatment), lezyon (lesion), çekim (extraction), kırık (fracture), saglam (sound). The card does not translate these words; the translation is ours and çürük = caries is standard Turkish.

Three real annotation rows (no image bytes):
- test_42.json: 11 shapes, 2810x1316 px; labels 1-çürük-15, 1-çürük-16, 6-gömülü-18, 1-çürük-26, 6-gömülü-28, 2-küretaj-31, ...
- test_0.json: 5 shapes, 2829x1316; 3-kanal-36, 6-gömülü-38, 1-çürük-26, 1-çürük-48, 1-çürük-45
- test_1.json: 10 shapes, 1504x2872 (as stored); 1-çürük-27, 1-çürük-26, 1-çürük-35, 2-küretaj-35, 2-küretaj-16, 2-küretaj-15, ...

Pool: 226 test images have at least one çürük polygon, 24 have none.

## Labels

Question (noul): "Is there a cavity (caries) visible on this dental X-ray?" Yes when the label JSON has at least one polygon whose finding word is çürük. No when it has none. Seed 44, 13 yes and 12 no, order shuffled. Chance rate 50%. `rederive` reads the label JSON from the zip again.

Class counts: yes 13, no 12.

## Caveats

- No-answer images are not "healthy": they carry other findings (impacted, curettage, root canal, sound) but no caries polygon. Absence of a polygon is not proof of absence of caries.
- The Turkish-to-English mapping is ours. The English-named validation_triple.json (50 images) has too few caries-free images (6) to use.
- Panoramic X-rays are small-detail images; images are shrunk to 1536 px long side, which may hide small lesions.
- A glance over the 25 for burned-in personal data found only a device mark (VistaPano) and an "R" side marker. No names or dates.
- Research benchmark, not for clinical use.

## Angle questions (derived from the annotation, not built)

All use the same 25 images and the label JSON (`disease/label/test_N.json`), finding word = middle part of each shape label.
1. Impacted tooth present (yes/no): yes iff at least one shape with finding gömülü.
2. Two or more caries (yes/no): yes iff the count of shapes with finding çürük is at least 2.
3. Periapical-type lesion present (yes/no): yes iff at least one shape with finding lezyon.
4. Root canal treatment present (yes/no): yes iff at least one shape with finding kanal.
5. Curettage finding present (yes/no): yes iff at least one shape with finding küretaj.
6. Caries in lower jaw (yes/no): yes iff a çürük shape has FDI tooth number (last part) starting with 3 or 4.
Check the class balance on the 25 before building any of these.
