# t08_handwritten_line

Status: READY

## Recon

`Voxel51/iam_handwriting_finevision`. The card's licence field is only `cc` (no version). Local use only. The full image tree is about 1.09 GB; `samples.json` (5,663 samples) was downloaded, then 25 PNGs.

Each sample has `filepath` and `assistant`. `assistant` is one string, the transcription. First lines:

- data/00000.png: "Some plain tapered legs have the taper on the two inner faces only, the outer surfaces being vertical as at ( B ), Fig. 1."
- data/00002.png: "Over here I 've always used brass screws, which are more expensive."

1,876 strings are a single line under 60 characters. The field is a plain string, not a nested column.

## Labels

Question: "Which text is written in the image?" The right answer is `assistant`. Three other options are other short lines from the same file. Seed 8. Chance rate 25%. Only lines under 60 characters are kept, and duplicate strings are dropped.

`label_origin`: assistant. URL: https://huggingface.co/datasets/Voxel51/iam_handwriting_finevision

## Caveats

The card does not say which Creative Commons licence. The description says the lines come from the IAM Handwriting Database via FineVision. IAM's own terms are not copied onto this card.
