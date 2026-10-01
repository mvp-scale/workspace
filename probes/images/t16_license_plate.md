# t16_license_plate

Status: BLOCKED

## Recon

Candidate: `mabo7237/license-plates-700k`.

The README is only the line `license: mit`. The repo has that README, a `.gitattributes`, and 99,998 JPEG files (about 12.4 GB). There is no CSV, JSON, or parquet of labels.

A sample of paths:

- `images/event/0378da73-2f30-48c5-a5a2-c25334ffc7cb/0.4/509-20210428143821-263-03-731717-18-1140-670-552-335.jpg`
- `images/event/0378da73-2f30-48c5-a5a2-c25334ffc7cb/0.4/.ipynb_checkpoints/509-20210514122819-191-01-296990-22-1228-534-642-341-checkpoint.jpg`

Filenames are timestamps and integers. They are not a plate string, and nothing on the card says which field is the plate text. The spec asks for a text column (true plate plus three plates from other rows), and to skip empty text or images under 60 px wide. That column is not in the repo.

The full tree is larger than 3 GB, so it was not downloaded.

## Why blocked

There is no plate-text field to read. The task is not built.
