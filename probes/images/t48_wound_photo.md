RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE

# t48_wound_photo

Status: READY

Read this as a skin-condition set, not a wound-type set. No open wound dataset with clinician labels and a stated licence was found (see "Checked and rejected"). The pick-one question asks which of four skin conditions a clinical photograph shows.

## Question

"Which skin condition does this clinical photograph show?" Options: scabies, tungiasis, lichen planus, psoriasis (order shuffled per item). Answers: scabies 7, tungiasis 6, lichen planus 6, psoriasis 6 (largest class 28%). Chance rate 25%. Seed 48.

## Source and licence

Fitzpatrick17k, https://github.com/mattgroh/fitzpatrick17k (CSV of 16,577 rows with image URLs). Licence as stated on the repo: Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported. The repo says the original images were collected from Atlas Dermatologico and DermaAmin. Non-commercial: local testing only. Do not redistribute the images. The 25 images were fetched from atlasdermatologico.com.br (3.9 MB total in `/workspace/data/sources/image-lab/fitz17k/`). The DermaAmin host (www.dermaamin.com) did not resolve from this machine, so only Atlas images (3,905 rows) are used.

## Recon

Columns: md5hash, fitzpatrick_scale, fitzpatrick_centaur, label, nine_partition_label, three_partition_label, qc, url, url_alphanum. Three real rows (no image bytes):

1. md5hash 5e82a45bc5d78bd24ae9202d194423f8, fitzpatrick_scale 3, fitzpatrick_centaur 3, label "drug induced pigmentary changes", nine_partition "inflammatory", three_partition "non-neoplastic", qc "", url https://www.dermaamin.com/site/images/clinical-pic/m/minocycline-pigmentation/minocycline-pigmentation1.jpg
2. md5hash d2bac3c9e4499032ca8e9b07c7d3bc40, scale 2, centaur 3, label "dermatofibroma", nine_partition "benign dermal", three_partition "benign", url https://www.dermaamin.com/site/images/clinical-pic/d/dermatofibroma/dermatofibroma71.jpg
3. md5hash 119d712798a653799adaf8e5e08ce66e, scale 4, centaur 3, label "hailey hailey disease", nine_partition "genodermatoses", three_partition "non-neoplastic", url http://atlasdermatologico.com.br/img?imageId=2409

## Label origin

`label` is the diagnosis the atlas gives each photograph. The atlas is a dermatology teaching atlas whose entries are physician-curated; the Fitzpatrick17k paper (Groh et al., CVPR-W 2021) takes the label from the atlas and has a dermatologist-reviewed `qc` subset. I could not verify per image that a named clinician assigned each label, and the atlas page does not say; the label is the source's own diagnosis, not a model's and not mine. Nothing was labelled by eye.

## Privacy screen

48 candidates (12 per class, seeded shuffle) were screened by eye for identifiable people only, not for labels. Skipped 6: 3 showed the lower face, beard or eyes (psoriasis), 2 showed genitals (scabies 1, lichen planus 1), and 1 lichen planus pubic-area close-up. Faces: 3 skipped. Photos carry a small atlas watermark ("SFS"), no readable names. Tattoos: none seen.

## Distractors

The three other classes of the four. All four are inflammatory or infestation conditions that the source files under non-neoplastic.

## Caveats

- Skin conditions, not wounds. Tungiasis and scabies are infestations; lichen planus and psoriasis are inflammatory. This is not diabetic ulcer, pressure injury or infection staging.
- Only four classes of 114, picked by me for sample size and for few face images. Many photographs are close-ups where the condition is characteristic, so this may be easier than a broad dermatology set.
- Atlas diagnoses are not biopsy-proven in every case; no per-image evidence is given.
- Tungiasis photos include macro shots of the parasite and eggs.
- Images are small (as hosted), saved at max 1536 px.

## Checked and rejected

- rupeshsah/wound (HF, apache-2.0, 1,564 images, 10 types incl. pressure, diabetic, venous, surgical): rejected. The card does not say where the images or labels came from, only "expert-level" text descriptions that include things no photo shows (odour, pain, warmth), so the labels look machine or scraped; all images are re-rendered to 350x350; the card gives no original licence for the photos. Label origin cannot be shown to be a clinician. This would be the ideal question (wound type) if its origin were documented.
- Fitzpatrick17k mirror ZYXue/Fitzpatrick_17k (HF): rejected, adds model-style reasoning paths and 9 coarse classes; used the original CSV instead.
- AbishekFranklin/medai-vision-dataset-wound_classification_detection and Kanden1112 wound sets (HF): no licence and no label provenance on the card; not downloaded.
- Medetec wound database, DFUC 2020/2021, DermNet: not attempted. Medetec images are copyright and not for commercial use; DFUC is gated by registration; DermNet is licensed for paid use. All would need the user.
- Fitzpatrick17k DermaAmin images (12,631 rows): host did not resolve from this machine.

## Needs from the user, optional upgrade

To get a true wound-type task: obtain DFUC (registration at the challenge site) or the Medetec database with its own terms, or confirm the origin of rupeshsah/wound, then drop it into the data folder.

## Angle questions (derived from the annotation, not built)

1. Is this a parasitic infestation? yes for scabies and tungiasis, no for lichen planus and psoriasis (rule: label in {scabies, tungiasis}).
2. Is the skin tone of the patient light, medium or dark? Rule: `fitzpatrick_scale` 1-2 light, 3-4 medium, 5-6 dark (crowd label from Scale AI, not clinician).
3. Did the two skin-tone annotators agree? Yes when `fitzpatrick_scale` equals `fitzpatrick_centaur`, else no.
4. Which broad category is this? `nine_partition_label` (all four classes here are "inflammatory", so use it only with a wider set) or `three_partition_label` (neoplastic vs non-neoplastic, same caveat).
5. Is the photograph in portrait orientation? Rule: height greater than width, read from the file, not the annotation.
6. Which Fitzpatrick skin-type number (1 to 6) is it? Rule: `fitzpatrick_scale` as a six-option choice (crowd label).
