# Image lab status

12 tasks are built and included below. Disk used under `/workspace/data/sources/image-lab` stayed under the 15 GB cap (see the note at the bottom). No login was attempted for a gated dataset.

## Tasks

| Task | Status | Items | Source | Licence | Chance | Note if not a finished READY set |
|---|---|---|---|---|---|---|
| t01_invoice_fields | BLOCKED | 0 | FATURA2 test (on disk) | CC-BY-4.0 | — | README has no id-to-name table for `ner_tags` |
| t02_receipt_capture | READY | 25 | CORD v2 test | CC-BY-4.0 | 25% total; 12.5% item count | |
| t03_document_type | READY | 25 | hf-tuner RVL-CDIP test | not stated, local use only | 25% | |
| t04_signature_present | NEEDS_USER_ACTION | 0 | tech4humans/signature-detection | Apache-2.0 | 50% planned | Gated. Accept terms on the dataset page |
| t05_form_completeness | SYNTH | 25 | render_form / degrade | generated here | 50% yes/no; 20% tick count | Drawn from known generator values |
| t06_cheque_amount | READY | 25 | alpha-brain synthetic cheques | not stated, local use only | 25% | Amount column used; the other cheque set has boxes only |
| t07_chart_reading | READY | 25 | ChartQA test | GPL-3.0, local use only | 25% | |
| t08_handwritten_line | READY | 25 | IAM via FineVision | cc (version not stated), local use only | 25% | |
| t09_vehicle_damage | READY | 25 | DrBimmer car parts and damage | MIT | 50% | Negatives are parts-only annotations |
| t10_damaged_part | BLOCKED | 0 | same as t09 | MIT | — | No image has both a part and a damage object |
| t11_property_damage | NEEDS_USER_IMAGES | 0 | none | supplied later | 50% planned | Drop photos in `data/image-lab/user/t11_property_damage/` |
| t12_package_condition | NEEDS_USER_IMAGES | 0 | none | supplied later | 25% planned | Drop photos in the matching user folder |
| t13_shelf_out_of_stock | BLOCKED | 0 | smart-retail-shelf-auditing-v1, one val shard | not stated | — | Every box is category_id 1; no empty-gap label |
| t14_count_items | READY | 25 | CountBench | not stated, local use only | 11.1% (9 options) | |
| t15_produce_fresh_rotten | READY | 25 | fresh/rotten fruit, raw shards 0 and 2 | CC-BY-4.0 | 50% | |
| t16_license_plate | BLOCKED | 0 | license-plates-700k | MIT | — | No plate-text column; repo is 12.4 GB of JPEGs |
| t17_logo_present | READY | 25 | logo-detection-dataset | not stated, local use only | 25% | |
| t18_hard_hat_worn | READY | 25 | hard-hat-detection | CC0-1.0 | 50% | People counted as head or helmet boxes |
| t19_fire_smoke | BLOCKED | 0 | CCTV smoke/fire (the small set) | CC-BY-NC-4.0 | — | Only fire and smoke, no negatives. The other corpus is 28 GB |
| t20_floor_hazard | NEEDS_USER_IMAGES | 0 | none | supplied later | 50% planned | Drop photos in the matching user folder |
| t21_surface_defect | BLOCKED | 0 | ybli NEU-DET repo | not stated | — | Hub repo has no images, only a link off-site |
| t22_gauge_reading | NEEDS_USER_IMAGES | 0 | none | supplied later | 25% planned | User supplies four options per photo |
| t23_crop_disease | READY | 25 | plant leaf disease, first shard | CC-BY-4.0 | 25% | |
| t24_screenshot_triage | NEEDS_USER_ACTION | 0 | lmms-lab-encoder/ScreenSpot-v2 | unknown | — | Hub returned 401 for that id |
| t25_room_type | NEEDS_USER_IMAGES | 0 | none | supplied later | 20% planned | Five room classes |

## How a later run should be scored

For each built task the runner reports correct/25, the 95% Wilson interval (`wilson` in `_imgcommon.py`), and the chance rate in the table.

| Label | Rule |
|---|---|
| Works | point estimate 85% or more, and the lower end of the interval above 70% |
| Assist only | point estimate 60% to 85% (human review needed) |
| Not ready | below 60%, or the interval includes the chance rate |
| Could not run | any image rejected by the server; count these separately, never as wrong |

A yes/no task at 60% is not a good result: chance is 50%. A nine-option count task at 60% is well above its 11% chance and is Assist only only if the point estimate is in that band and the interval does not include the chance rate.

## Not built, and why

- **Needs you:** t04 (accept signature-detection terms), t24 (ScreenSpot-v2 is not publicly readable), t11, t12, t20, t22, t25 (photos you are allowed to use, plus `labels.csv`). `ingest_user.py` turns a filled folder into a jsonl. It was not run.
- **Blocked on the data:** t01 (no tag legend), t10 (damage and parts are never on the same image), t13 (no empty-shelf label), t16 (no plate text), t19 (no negatives), t21 (no files in the repo).

Disk after downloads: `/workspace/data/sources/image-lab` is 4.5 GB of the 15 GB cap. Full sets larger than 3 GB were not downloaded; one shard or the annotation files were used instead.
