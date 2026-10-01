# t01_invoice_fields

Status: BLOCKED

## Recon

Source checked: `/workspace/data/sources/image-lab/fatura2/data/test-00000-of-00001.parquet` (1,400 rows).

Columns match the spec: `image` (struct `bytes`, `path`), `ner_tags` (list of int), `bboxes` (list of lists of int), `tokens` (list of string), `id` (string).

First three rows (image bytes shown as length only):

| id | image bytes | n tokens | first tokens | first ner_tags |
|---|---|---|---|---|
| 191 | 35587 | 69 | table, Bill, to, Michael, Sparks, ... | 10, then many 5, then 13, then 3 |
| 166 | 38385 | 75 | table, Bill, to, Shelley, Silva, ... | 10, then many 5, then 13, then 3 |
| 335 | 35168 | 68 | table, Bill, to, Mary, Rodriguez, ... | 10, then many 5, then 13, then 3 |

Tag ids seen in the first 200 rows: 1, 3, 4, 5, 6, 10, 11, 12, 13. The parquet feature metadata names the column `ner_tags` and says the values are int64. It does not name the ids.

The spec says to take the id-to-name table from `https://huggingface.co/datasets/mathieu1256/FATURA2-invoices/raw/main/README.md`. That page (fetched 2026-09-30) has the card, the CC-BY-4.0 licence, the column list, and a short description. It has no id-to-name table. The dataset page on Hugging Face also shows raw integer tags with no legend.

Without that table, TOTAL and the invoice-number tag cannot be identified from the file. The integers are not guessed from the tokens.

Licence on the card: CC-BY-4.0. URL: https://huggingface.co/datasets/mathieu1256/FATURA2-invoices

## Planned questions (not built)

(a) choice, "What is the total amount on this invoice?" from TOTAL tokens, decoys from `decoy_numbers`.
(b) yes/no, "Is the total more than <threshold>?"
(c) choice, "What is the invoice number?"

Chance rate would have been 25% for four-option choices and 50% for yes/no.

## Why blocked

The label rule depends on a tag-name table that is not in the README or the schema. Building the set would mean assigning meaning to integer ids.
