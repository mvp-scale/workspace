# Image lab status

35 tasks are built and included below. t26–t30 are the real-photo sets from the gap. t01, t04, t10–t13, t16, t19, t20, t22, t24, t25, t31, t32, and t36–t38 are later 25-image sets from labelled files. Disk used under `/workspace/data/sources/image-lab` stayed under the 15 GB cap (see the note at the bottom). No login was attempted for a gated dataset.

## Tasks

| Task | Status | Items | Source | Licence | Chance | Note if not a finished READY set |
|---|---|---|---|---|---|---|
| t01_invoice_fields | READY | 25 | Cruz and Castelli photographed invoices | CC-BY-4.0 | 25% | Invoice total. FATURA2 tags had no legend |
| t02_receipt_capture | READY | 25 | CORD v2 test | CC-BY-4.0 | 25% total; 12.5% item count | |
| t03_document_type | READY | 25 | hf-tuner RVL-CDIP test | not stated, local use only | 25% | |
| t04_signature_present | READY | 25 | SignverOD lease scans | CC0 on the Kaggle card | 50% | Handwritten signature vs none |
| t05_form_completeness | SYNTH | 25 | render_form / degrade | generated here | 50% yes/no; 20% tick count | Drawn from known generator values |
| t06_cheque_amount | READY | 25 | alpha-brain synthetic cheques | not stated, local use only | 25% | Amount column used; the other cheque set has boxes only |
| t07_chart_reading | READY | 25 | ChartQA test | GPL-3.0, local use only | 25% | |
| t08_handwritten_line | READY | 25 | IAM via FineVision | cc (version not stated), local use only | 25% | |
| t09_vehicle_damage | READY | 25 | DrBimmer car parts and damage | MIT | 50% | Negatives are parts-only annotations |
| t10_damaged_part | READY | 25 | CarDD, 25 single-class photos | Flickr/Shutterstock, local use | 25% | dent, glass shatter, scratch, tire flat |
| t11_property_damage | READY | 25 | concrete crack images, test zip | CC BY 4.0 | 50% | Crack vs no crack |
| t12_package_condition | READY | 25 | cardboard box anomaly photos | CC BY-NC-SA 4.0, local use | 50% | Defective vs intact |
| t13_shelf_out_of_stock | READY | 25 | Grocery Dataset shelf photos | research only, local use | 25% | Product count in four bins. The old shard had no empty-gap label |
| t14_count_items | READY | 25 | CountBench | not stated, local use only | 11.1% (9 options) | |
| t15_produce_fresh_rotten | READY | 25 | fresh/rotten fruit, raw shards 0 and 2 | CC-BY-4.0 | 50% | |
| t16_license_plate | READY | 25 | Persian plates, test split | not stated, local use only | 25% | Plate text is in the jsonl only |
| t17_logo_present | READY | 25 | logo-detection-dataset | not stated, local use only | 25% | |
| t18_hard_hat_worn | READY | 25 | hard-hat-detection | CC0-1.0 | 50% | People counted as head or helmet boxes |
| t19_fire_smoke | READY | 25 | D-Fire test shard 0 | not stated, local use only | 50% | Empty label vs a boxed region. Class ids are not named |
| t20_floor_hazard | READY | 25 | HD10K robot floor photos | not stated, local use only | 50% | Spill or dirt vs a clean floor |
| t21_surface_defect | READY | 25 | newguyme/neu_det_caption | not stated, local use only | 25% | Four defect names from label_str |
| t22_gauge_reading | READY | 25 | photographed water meters | not stated, local use only | 25% | The printed reading |
| t23_crop_disease | READY | 25 | plant leaf disease, first shard | CC-BY-4.0 | 25% | |
| t24_screenshot_triage | READY | 25 | ScreenSpot-v2 | Apache-2.0 | 50% | Whether the target is an icon. The file has no element name |
| t25_room_type | READY | 25 | indoor-scene test zip | MIT on the export README; local use | 25% | kitchen, living room, dining room, pantry. No bathroom, bedroom, or exterior in that zip |
| t26_parking_free | READY | 25 | PKLot valid | CC-BY-4.0 | 25% | Free labelled spaces, four bins |
| t27_herd_count | READY | 25 | AGRARIAN sheep and goats | Apache-2.0 | 25% | Animal count on one patch per drone frame |
| t28_pigs_standing | READY | 25 | pig posture train | CC-BY-4.0 | 25% | Standing pigs, class 3 |
| t29_floorplan_doors | READY | 25 | CubiCasa5K val | CC BY-NC-SA 4.0, local use | 25% | Door polygons on a scanned plan |
| t30_damage_severity | READY | 25 | CrisisMMD damage test | CC BY-NC-SA 4.0, local use | 33% | little / mild / severe; tweet text omitted |
| t31_receipt_lines | READY | 25 | CORD v2 test | CC-BY-4.0 | 25% | Line count, receipts not used in t02 |
| t32_receipt_total | READY | 25 | CORD v2 test | CC-BY-4.0 | 25% | Total only, receipts not used in t02 or t31 |
| t36_meter_reading | READY | 25 | photographed electricity meters | not stated, local use only | 25% | The printed reading. Different photos from the water meters |
| t37_road_damage | READY | 25 | pothole severity folders | MIT | 25% | none, low, medium, severe |
| t38_cattle_count | READY | 25 | UAV cattle photos | not stated, local use only | 25% | How many cattle, four bins |

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

- **Floor-plan rooms:** CubiCasa labels only walls, doors, and windows, so a bedroom count was not added. Door count is already t29.
- **Weak set left in place:** t09 items 013–024 are parts-only photos scored as "not damaged". They need a labelled set of whole undamaged cars before they can be replaced.

Disk after downloads: `/workspace/data/sources/image-lab` is 4.5 GB of the 15 GB cap. Full sets larger than 3 GB were not downloaded; one shard or the annotation files were used instead.
