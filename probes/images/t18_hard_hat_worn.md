# t18_hard_hat_worn

Status: READY

## Recon

Files: `/workspace/data/sources/image-lab/hard-hat/samples.json` (5,000 samples) and images under `data/`. Licence in the local README: CC0-1.0. The README names three classes: Helmet, Person, Head. The detection `label` values in the file are lowercase: `helmet` (18,966), `head` (5,785), `person` (751).

First three samples:

| filepath | detections |
|---|---|
| data/hard_hat_workers0.png | 7 helmet, 6 head (13 boxes), 416×416 |
| data/hard_hat_workers1.png | 9 helmet |
| data/hard_hat_workers10.png | 3 helmet |

A `person` box is on only 158 images. Among images with 1 to 3 `person` boxes there are 4 with a `head` label and 68 without, which cannot fill 12 yes answers. Most people are marked by a `head` or `helmet` box, not by `person`.

## Labels

Question: yes/no, "Is there a person in this image who is NOT wearing a hard hat?"

Right answer is yes when the image has at least one detection labelled `head`. People kept in the set are images with 1, 2 or 3 detections whose label is `head` or `helmet`. Under that rule the pool is 85 yes and 2,293 no. Seed 18 takes 13 yes and 12 no. Chance rate 50%.

`label_origin`: at least one detection labelled head. `rederive` reloads `samples.json` and applies the same rule. URL: https://huggingface.co/datasets/Voxel51/hard-hat-detection

## Caveats

`head` means the dataset's no-helmet class. A helmet worn incorrectly but not labelled `head` is scored as no. Images with more than three head-or-helmet boxes are left out so the question is about a small group.
