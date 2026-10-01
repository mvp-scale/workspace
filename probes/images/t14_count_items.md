# t14_count_items

Status: READY

## Recon

File: `/workspace/data/sources/image-lab/countbench/data/train-00000-of-00001-cf54c241ba947306.parquet` (540 rows).

Columns: `image_url` (string), `text` (string), `number` (int), `image` (struct `bytes`, `path`). That matches the spec.

First three rows (image bytes as length):

| number | text | image bytes |
|---|---|---|
| 10 | We review the ten best gaming headsets in the market | 63117 |
| 3 | background photo of three light bulbs | 66124 |
| 3 | City prints: Set of three big prints - $150.00 USD | 116834 |

`number` is 2 through 10, 60 rows each. 49 rows have `image` null and are skipped. 491 rows have a caption that contains the number as a digit or as its English word.

Licence is not stated on the local files or on the feature metadata. Local use only, as in the spec. The set was introduced in Paiss et al., Teaching CLIP to Count to Ten (ICCV 2023), and the files match the Hugging Face copy at https://huggingface.co/datasets/nielsr/countbench.

## Labels

`expected` is the string of the `number` column. The caption is copied with the first matching number word or digit replaced by `___`. The question is "Which number belongs in the blank?" with options `2` through `10` (nine options; the task asks for that range). Chance rate 11.1%.

Seed 14. The nine numbers are shuffled, then the first seven get 3 photos and the last two get 2, so each number is the right answer 2 or 3 times. `rederive` reads that row and returns `number` again.

## Caveats

The caption can mention a number that is a price or a list position rather than a count of objects (the third sample says "three" and "$150.00"). The label is still the dataset's `number`. Some source photos come from the open web; they stay in git-ignored data and are not copied into a tracked folder.
