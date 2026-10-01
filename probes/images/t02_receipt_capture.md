# t02_receipt_capture

Status: READY

## Recon

File: `/workspace/data/sources/image-lab/cord-v2/data/test-00000-of-00001-9c204eb3f4e11791.parquet` (100 rows).

Columns: `image` (struct `bytes`, `path`), `ground_truth` (JSON string). That matches the spec.

First three rows (image bytes as length; `ground_truth` parsed):

| image bytes | size | gt_parse keys | total.total_price | menu |
|---|---|---|---|---|
| 338392 | 432×648 | menu, sub_total, total | 60.000 | dict (one item; keys nm, num, cnt, price, itemsubtotal) |
| 734233 | 960×1280 | menu, total | 91000 | list of 3 (first item keys nm, price) |
| 1387299 | 864×1296 | menu, sub_total, total | 28,000 | dict (one item; keys nm, cnt, price, sub) |

Across 100 rows: 95 have a `total_price` that is only digits, commas and dots. 95 have a menu count from 1 to 8 (a dict counts as 1 item, a list uses its length). Counts present: 1 (39), 2 (28), 3 (16), 4 (6), 5 (1), 6 (5). No receipt in this split has 7 or 8 items. 21 images have a long side over 1536 px; every saved image is resized.

Licence: CC-BY-4.0. URL: https://huggingface.co/datasets/naver-clova-ix/cord-v2

## Labels

- Total questions (13): `expected` is `gt_parse.total.total_price`. Three decoys from `decoy_numbers` (same punctuation, one or two digits changed). Chance rate 25% (4 options).
- Item-count questions (12): `expected` is the length of `gt_parse.menu` (1 when `menu` is a dict). Options are the strings `1` through `8`. Chance rate 12.5% (8 options). The general item format says 2 to 6 options; this task asks for 1 to 8, so the builder and the validator allow 8 here.
- No discount question.
- Seed 2. Count classes are taken in a round-robin so no count is the right answer in more than 40% of the 12 count items. Each row is used once.
- `label_origin` is the field name above. `rederive` reads that row again and recomputes it.

## Caveats

Amounts keep the dataset's own spelling (`60.000`, `28,000`), so the same money can look different across receipts. Options `7` and `8` never occur as the right answer in this split. Receipts are photographs of real tickets; the field used is the dataset's annotation, not a reading of the image.
