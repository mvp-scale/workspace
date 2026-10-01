# t13_shelf_out_of_stock

Status: BLOCKED

## Recon

Candidate: `adnankhan-11/smart-retail-shelf-auditing-v1`. No licence on the card. The repo is 9.74 GB, so only one shard was downloaded: `data/valid-00000-of-00010.parquet` (200 rows).

Columns: `image`, `image_id`, `width`, `height`, `objects`. `objects` has `id`, `category_id`, `bbox`, `area`, `iscrowd`. The first two rows are image_id 0 (2448×3264) and image_id 1 (1920×2560). Every `category_id` in the shard is `1` (29,876 boxes). No image has an empty object list. The feature metadata does not name category 1.

## Why blocked

There is no per-image yes/no for an empty shelf gap, and both answers are not present. Category 1 is not named in the file, so it is not treated as "product" or as "gap".
