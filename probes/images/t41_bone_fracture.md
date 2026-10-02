RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE

# t41_bone_fracture

Status: READY

## Source

FracAtlas (Abedeen, Rahman, Prottyasha, Ahmed, Chowdhury, Shatabda; Scientific Data 2023), figshare: https://figshare.com/articles/dataset/The_dataset/22363012 . Licence as stated on the figshare page (API field `license`): CC BY 4.0. No login, form or terms gate. File used: `FracAtlas.zip` (338 MB) extracted to `/workspace/data/sources/image-lab/fracatlas/`. MURA was not used (it needs registration and terms); the Hugging Face MURA mirror has no licence stated and was not touched.

## Recon

`FracAtlas/dataset.csv`, 4,083 rows. Columns: image_id, hand, leg, hip, shoulder, mixed, hardware, multiscan, fractured, fracture_count, frontal, lateral, oblique. First 3 rows (no image bytes):

```
IMG0000000.jpg,0,1,0,0,0,0,1,0,0,1,1,0
IMG0000001.jpg,0,1,0,0,0,0,1,0,0,1,1,0
IMG0000002.jpg,0,1,0,0,0,0,1,0,0,1,1,0
```

(all three are leg, multiscan, fractured=0, frontal+lateral). Fractured rows (for example IMG0000019.jpg, in `images/Fractured/`) have fractured=1 and fracture_count of 1 or more. Images are in `images/Fractured` and `images/Non_fractured`. The paper describes labelling by radiologists, reviewed by a radiologist and a surgeon, so label origin is human expert.

## Labels

Question (noul): "Does this X-ray show a fracture?" Answer yes when `fractured` = 1, no when `fractured` = 0 (the dataset's own column). Chance rate 50%.

Sampling (seed 41): only images with exactly one of hand/leg/hip/shoulder, mixed=0, hardware=0, multiscan=0, and a fully readable JPEG. 13 yes (hand 4, leg 3, hip 3, shoulder 3) and 12 no (3 per part), so body part is not a cue. Images resized to a 1536 px long side, JPEG q88. Builder is re-runnable; `rederive(item)` re-reads `dataset.csv`.

Provenance notes carry "research benchmark, not for clinical use".

## Caveats

- Question wording was narrowed from "fracture or other bone abnormality" to "fracture" so it matches the label (fractured=1) exactly.
- Non-fractured images were not given a verified "normal" label, they are simply not marked fractured.
- Some images show casts, soft-tissue shadows or large fields with several bones; some have small side markers (R, L, joint name). No names or dates are visible (checked on a contact sheet, no label made by eye).
- Single-site fractures dominate; subtle ones are hard even for experts.

## Angle questions (derived from the annotation, not built)

All computed from `dataset.csv` columns for the same images (image_id is in each item's `provenance.source_id`).

1. Body part (choice: hand, leg, hip, shoulder). Rule: the single column among hand, leg, hip, shoulder equal to 1 (the sample keeps only rows where exactly one is 1).
2. Is this a frontal view? (noul). Rule: yes when `frontal` = 1, else no.
3. Is this a lateral view? (noul). Rule: yes when `lateral` = 1, else no. (Oblique likewise from `oblique`.)
4. How many fractures are visible? (choice: 0, 1, 2 or more). Rule: `fracture_count` = 0 -> "0", 1 -> "1", 2 or more -> "2 or more".
5. Is there more than one fracture site? (noul). Rule: yes when `fracture_count` >= 2, else no (only meaningful on the fractured images, or answer no for 0).
6. Is a lower-limb or hip bone shown? (noul). Rule: yes when `leg` = 1 or `hip` = 1, else no.
