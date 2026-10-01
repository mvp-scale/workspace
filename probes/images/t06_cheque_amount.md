# t06_cheque_amount

Status: READY

## Recon

Two candidates were opened from their dataset cards (2026-09-30).

`jaganadhg/cheque-synthetic-images` (Apache-2.0, about 0.47 GB, not downloaded). Columns include `image` and `amount`, but `amount` is a bounding box `{xmin, ymin, xmax, ymax}`, not the amount written on the cheque. The card says field patches are cropped from real cheques and pasted onto a blank template. There is no readable amount column.

`alpha-brain/ocr-synthetic-cheque-datatset` (no dataset card, licence not stated, about 3.25 GB, so the full set was not downloaded). `metadata.jsonl` (4.3 MB) has `file_name` and `text`. First three rows:

| file_name | amount_in_numbers | bearer (generated) |
|---|---|---|
| train/0.jpg | 39208.0 | Melissa Duncan |
| train/1.jpg | 879813.0 | Sophia Walker |
| train/2.jpg | 153431.0 | Catherine Lambert |

`text` also has `amount_in_words`, `bank_name`, `date`, `account_number` and similar fields. Names and addresses look machine-generated (fake street names, IFSC codes next to US-style addresses). 10,000 rows. Only the 25 chosen JPEG files were downloaded (under `ocr-synthetic-cheque/`).

## Labels

The builder keeps `text.amount_in_numbers` when it matches digits, a dot and more digits, drops duplicate amounts, shuffles with seed 6, and takes 25. The question is "What is the amount on this cheque?" with that string plus three `decoy_numbers` decoys. Chance rate 25%.

`label_origin`: text.amount_in_numbers. `rederive` reads the same metadata row. Licence in provenance: not stated, local use only. URL: https://huggingface.co/datasets/alpha-brain/ocr-synthetic-cheque-datatset

## Caveats

Images are resized so the long side is at most 1536 px. The amount string keeps the trailing `.0` from the file. Account numbers and names are in the metadata and may be printed on the image; they are the dataset's generated fields. The files stay in git-ignored data.
