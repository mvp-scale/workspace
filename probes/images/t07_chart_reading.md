# t07_chart_reading

Status: READY

## Recon

File: `/workspace/data/sources/image-lab/chartqa/data/test-00000-of-00001-e2cd0b7a0f9eb20d.parquet` (2,500 rows, the test split only; the full repo is about 0.96 GB and was not downloaded). Licence on the card: GPL-3.0. Local use only.

Columns: `image` (struct `bytes`, `path`), `query` (string), `label` (list of string), `human_or_machine` (0 = human, 1 = machine). `image.path` is null on every row. First two rows share nothing but the columns: query "How many food item is shown in the bar graph?" label `["14"]`; query "What is the difference in value between Lamb and Corn?" label `["0.57"]`.

1,915 rows have a single label that is one integer or one decimal. Charts are grouped by a SHA-256 of the image bytes because the path column is empty. Rows whose label is a word, a yes/no, or more than one string are skipped. A word cannot be checked against the drawing without reading the image.

## Labels

One question per chart. The instruction is the dataset's `query`. The right answer is `label[0]`. Three other options are other numeric answers from the same chart, padded with `decoy_numbers` when the chart has fewer than three other numbers. Chance rate 25%. Seed 7.

`label_origin`: label. `rederive` reads that row of the test parquet again. URL: https://huggingface.co/datasets/HuggingFaceM4/ChartQA

## Caveats

GPL-3.0, local use only. The test split mixes human and machine questions; `notes` records which. Difference and comparison questions can be numerically correct in the label and still hard to see. Images are resized to a long side of at most 1536 px.
