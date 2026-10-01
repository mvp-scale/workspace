# t15_produce_fresh_rotten

Status: READY

## Recon

Source: `Project-AgML/fresh_rotten_fruit_classification`, config `raw` (CC-BY-4.0). The raw download is about 2.86 GB across four shards. Three shards are on disk:

| shard | rows | label | fruit_type |
|---|---|---|---|
| train-00000-of-00004 | 800 | all 0 fresh | apple, banana, grape, guava (200 each) |
| train-00001-of-00004 | 800 | all 0 fresh | jujube, orange, pomegranate, strawberry (200 each) |
| train-00002-of-00004 | 800 | all 1 rotten | apple, banana, grape, guava (200 each) |

Columns: `image`, `label` (ClassLabel names `fresh`, `rotten`), `fruit_type`. The names are in the parquet metadata, not a string column. A fresh apple in shard 0 is 4160×3120 pixels. Saved copies are resized.

The class name is `rotten` or `fresh`, not `rotten_apple`. `rotten` contains the substring the spec uses.

## Labels

Yes/no: "Is this fruit rotten?" Yes when the class name contains `rotten`. Seed 15 takes 13 rotten images from shard 2 and 12 fresh images from shard 0, spread across apple, banana, grape and guava (3 each, plus one extra rotten fruit type). Chance rate 50%.

`label_origin`: label class name. URL: https://huggingface.co/datasets/Project-AgML/fresh_rotten_fruit_classification

## Caveats

Shard 1 is also entirely fresh and is not used in the 25. Shard 3 was not downloaded. Rotten and fresh photos of the same four fruits come from different shards.
