# t04_signature_present

Status: NEEDS_USER_ACTION

## Recon

Candidate: `tech4humans/signature-detection`. The hub reports `gated=auto`, licence Apache-2.0, about 0.15 GB (`full/train`, `full/test`, `full/validation` parquet files). Nothing was downloaded.

The planned question was yes/no, "Is there a handwritten signature on this page?", with positives taken from images that have a signature box and negatives from images that have none.

## What you need to do

Open https://huggingface.co/datasets/tech4humans/signature-detection while logged in and accept the dataset terms (the gated-access button on that page). After that, this task can be built from the parquet files. Do not try to fetch it without that acceptance.
