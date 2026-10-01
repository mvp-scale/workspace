# t17_logo_present

Status: READY

## Recon

`varun1212/logo-detection-dataset`. Licence is not on the card. Local use only. The repo is about 0.19 GB. `annotations/train.json` was read first; then 25 images were downloaded.

COCO keys: `images` (2,017), `annotations` (2,017), `categories` (213). Every image has exactly one box. Category names are brand names with a `_Logo` suffix, for example Pioneer_Logo, China_Mobile_Logo, GoPro_Logo, T-Mobile_Logo, Lenovo_Logo. A sample image record is `{"id": 0, "file_name": "Pioneer_logo_PNG4.jpg", "width": 300, "height": 182}`.

## Labels

Question: "Which brand logo is shown?" The right answer is `categories.name`. Four options: that name plus three other names from the 25 chosen brands. Seed 17 takes one image from each of 25 brands, skipping any image under 60 px wide (none of the chosen rows were). Chance rate 25%.

`label_origin`: categories.name. URL: https://huggingface.co/datasets/varun1212/logo-detection-dataset

## Caveats

The option text keeps the dataset's `_Logo` suffix. The file name also contains the brand; the label used is the category, not the file name.
