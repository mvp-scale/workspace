# Fifty-four open datasets unlock 98 business tasks

The merged atlas lists **277 typed image tasks across all 50 business domains**. **98 tasks (35%) have at least one dataset rated `USE`.** These come from **54 unique USE datasets**, and 5 of the 98 tasks are covered through a cross-reference to a dataset carded in another domain. Of the other tasks, **60 can realistically be drawn by a generator**, **28 need human photos**, and **91 stay blocked** because their only candidates are `MAYBE` or `GATED` or the generator route was never assessed. I re-opened the `sample_proof_url` of the 20 most important USE candidates, plus 7 more, on 2026-10-01. **All 27 matched the pasted rows, so nothing was downgraded.** Three of those proofs are weaker than they look: two expose labels without filenames, and one never showed its negatives again (details in the re-check table). The recommended **first build is 25 tasks in 25 different domains, 13 yes/no and 12 pick-one**. Each has a smallest fetch of 19.5 MB or less, and all 25 use datasets that passed the re-check. **Licences need attention before anything goes beyond internal testing.** Four first-build datasets are non-commercial (CrisisMMD, KolektorSDD, the cardboard-box set, CubiCasa5K-YOLO). One has research-only wording next to an MIT file (DeepPCB). Two have share-alike or conflicting licence variants (RDD2022, NEON beetles). Two rest on upstream licences nobody checked (HARIS weapons and its UCF-Crime negatives; the fake W-2 set, whose CC0 comes only from a Kaggle page). **Nine domains have no USE data at all:** health billing (5), HR (10), food-service hygiene (14), last-mile delivery (17), hospitality (18), aviation (24), rail (25), oil, gas and mining (29), and maps and satellite (44). The paperwork-heavy ones among them (5, 10) can be closed with form generators. The others need human photos or a licence decision.

*Method note.* This report merges five slice reports (`slice1`–`slice5` in `research_notes/Image lab task atlas/`) following Part 3 of the spec. No new datasets were added. Every licence, size, class count and row below comes from those notes, and keeps their evidence tags (`[ROW]`, `[CARD]`, `[PAPER]`, `[INFERRED]`, `[UNVERIFIED]`, `[UNVERIFIED-snippet]`). The only new evidence is the re-check fetches made for step 2 of the merge. Training-overlap statements are `[INFERRED]` throughout: no contamination test was run.

## Licence caveats come first: nine of the 25 first-build tasks carry a material one

Every USE rating in the notes treats non-commercial (NC) licences as acceptable for a research test bench, and the slice-1 notes say so explicitly. That holds only while the bench stays internal. If the bench, its images or derived question sets are ever sold, shipped in a product or published under a permissive licence, the NC and share-alike (SA) sets below have to be reviewed or dropped. **CrisisMMD** is `cc-by-nc-sa-4.0` ([QCRI/CrisisMMD](https://huggingface.co/datasets/QCRI/CrisisMMD)). **KolektorSDD** is "CC BY-NC-SA 4.0 (non-commercial; contact Danijel Skočaj for commercial use)" ([Voxel51/Kolektor_Surface_Defect](https://huggingface.co/datasets/Voxel51/Kolektor_Surface_Defect)). The **cardboard-box anomaly** set states CC BY-NC-SA-4.0 in Portuguese ([Gabriel8](https://huggingface.co/datasets/Gabriel8/cardboard-box-anomaly-detection)). **CubiCasa5K-YOLO** declares CC BY-NC 4.0, but the upstream Zenodo record says CC BY-NC-SA 4.0, so it should be treated as NC-SA ([Zenodo 2613548](https://zenodo.org/records/2613548)). **DeepPCB** ships an MIT `LICENSE` while its README says "You can only use this dataset for research purpose" ([DeepPCB](https://github.com/tangsanli5201/DeepPCB)).

| Dataset (tasks) | Licence as recorded | Caveat | In first build? |
|---|---|---|---|
| CrisisMMD (D4.1, D4.3) | CC BY-NC-SA 4.0 [CARD] | **NC + SA** | yes (D4.1) |
| KolektorSDD (D21.3) | CC BY-NC-SA 4.0; commercial use by contact [CARD] | **NC + SA** | yes |
| Gabriel8 cardboard box (D15.2, D16.3) | CC BY-NC-SA 4.0 [CARD] | **NC + SA** | yes (D16.3) |
| CubiCasa5K-YOLO (D19.1) | CC BY-NC 4.0 (mirror) vs CC BY-NC-SA 4.0 (Zenodo) [CARD] | **NC; licence conflict** | yes |
| DeepPCB (D22.1) | MIT file + "research purpose only" README [CARD] | **research-only conflict** | yes |
| RDD2022 (D30.1, D30.2) | CC BY 4.0 (Figshare) vs CC BY-SA 4.0 (HF card) [CARD] | licence conflict (both open) | yes |
| NEON beetles (D40.2, D40.3) | CC BY-SA 4.0 [CARD] | SA | yes |
| HARIS weapons (D35.3, D35.4) | CC BY 4.0 (YAML only); UCF-Crime hard negatives, upstream terms UNVERIFIED [CARD] | **upstream may be research-only** | yes |
| Fake W-2 (D9.2, D9.3) | no licence on HF card; CC0 from upstream Kaggle API [CARD] | licence from third party only | yes |
| Early printed books fonts (D46.4) | CC BY-NC-SA 4.0 (Zenodo not confirmed) [CARD] | **NC + SA** | no |
| ScienceQA (D45.1/3/4) | owner README CC BY-NC-SA 4.0 vs HF `cc-by-sa-4.0` [CARD] | **NC (treat as); conflict** | no |
| Open Images V7 (D47–D50) | annotations CC BY 4.0; images "listed as" CC BY 2.0, "no representations or warranties" [CARD] | per-image licence not warranted | no (reserve) |
| price-tag-detection, plant seedlings, Oxford-IIIT Pet, CharXiv | CC BY-SA 4.0 [CARD] | SA; CharXiv figures have varying arXiv copyright [INFERRED] | no |
| TrashNet, goodcoffee meters, powerline faults, jaganadhg cheques, katanaml invoices, NIST SD2 | licence only in YAML, only in README body, or upstream terms unread [CARD] | provenance thin | powerline, goodcoffee yes |
| cloverx-id ID cards (D8.1) | CC BY 4.0, but faces are "real human faces… (UTKFace)… morphed" [CARD] | personal-data derivative | no |
| ChartBench (D43) | MIT plus an `extra_gated_prompt` harm clause; API `gated: False` [CARD] | read the clause | yes (D43.1) |

Several MAYBE candidates fail mainly on licence. If they are promoted later, these caveats come with them. FGVC-Aircraft is "non-commercial research purposes only". Food-101 is "scientific fair use" only. MIT Indoor-67 is "research purposes only" despite an MIT tag. RPC is CC BY-NC-SA 4.0 in its text but `cc-by-nc-sa-2.0` in its tag. VisDrone, FloorPlanCAD and the Simuletic wildfire set each have a YAML tag that contradicts the card body. CheckboxQA is CC BY-NC and "solely for evaluation". ELPV, LISA and FishEye8K are NC-SA. The UniData water-meter preview is CC BY-NC-ND. The ABO S3 bucket also contains a `LICENSE-CC-BY-NC-4.0.txt`. All of these are quoted in the cards and the CSV (Appendix D).

## All 27 re-checked sample proofs match their pasted rows

The spec's merge step asks for the 20 USE candidates that matter most to be re-opened and compared with the rows pasted in the notes. I chose the 20 datasets that feed the most first-build tasks or the most domains, then added 7 more so that every dataset in the first-build list was checked. Every fetch stayed under 50 MB. The largest was the 28.39 MB Open Images validation label CSV. Fetches used only `huggingface.co`, `datasets-server.huggingface.co`, `raw.githubusercontent.com` and the Open Images Google Cloud Storage bucket, with no login. **No candidate failed, so no downgrades were made.** The re-check did surface three findings that matter. The **HARIS weapons** and **CubiCasa5K-YOLO** first-rows proofs serve bare YOLO label lines in a `text` column with no filename, so the rows cannot be tied to images from that URL alone; the per-file label paths must be used when building. The **cardboard-box** proof (test rows 0–99) contains only `bad` images, so the 166 `good` negatives the card reports sit at later offsets and were not seen again. Enrico's card names a 6-image topic "dialer", but the CSV calls it "calculator".

| # | Tasks | Dataset | sample_proof_url re-opened | What was compared | Result |
|---|---|---|---|---|---|
| 1 | D2.4, D2.5 | HV09 synthetic invoices | [metadata.jsonl](https://huggingface.co/datasets/HV09/synthetic-bilingual-invoices-200/resolve/main/data/metadata.jsonl) | rows INV-1080, SUP-1158, FF-1323 (PO-7919 / PO-9399 / null; totals 44548.35 / 6945.75 / 4701.38); full counts PO 130/70, gregorian 185 / hijri 15, AED 150 / AUD 50 | **match** |
| 2 | D41.1–41.3 | ScreenSpot-Pro | [illustrator_windows.json](https://huggingface.co/datasets/likaixin/ScreenSpot-Pro/resolve/main/annotations/illustrator_windows.json) | 31 entries; 3 rows identical (bbox, instruction, application, platform, img_size 5120×1440, group) | **match** |
| 3 | D22.1 | DeepPCB | [00041000.txt](https://raw.githubusercontent.com/tangsanli5201/DeepPCB/master/PCBData/group00041/00041_not/00041000.txt) | the 3 pasted lines are present; the file has 10 defect lines in all | **match** |
| 4 | D27.1 | goodcoffee Meter_Reading | [first-rows](https://datasets-server.huggingface.co/first-rows?dataset=goodcoffee/Meter_Reading&config=default&split=train) | 3 rows identical; row 2 reads −1.2 on a −1 to 6 scale, which confirms the card's below-minimum (clipping) caveat | **match** |
| 5 | D38.2 | RF100 pills | [test/labels](https://huggingface.co/datasets/LibreYOLO/pills-sxdht/tree/main/test/labels) | 3 label files identical (classes 7 white, 6 red, 4 blue); `data.yaml` names and "CC BY 4.0" confirmed; 45 test files | **match** |
| 6 | D36.1 | PKLot | [first-rows](https://datasets-server.huggingface.co/first-rows?dataset=dronefreak/PKLot&config=default&split=train) | 3 PUCPR frames, 99 spaces each, categories start [1,0,1,0,1,1,0,0] | **match** |
| 7 | D35.3, D35.4 | HARIS weapons | [first-rows](https://datasets-server.huggingface.co/first-rows?dataset=Turki-Alshuaibi/haris-weapon-detection-dataset-curated&config=default&split=train) | 3 YOLO lines identical | **match**, but the viewer exposes label text only, with no filename |
| 8 | D3.1–3.3 | DrBimmer comprehensive-car-damage | [first-rows](https://datasets-server.huggingface.co/first-rows?dataset=DrBimmer/comprehensive-car-damage&config=default&split=train) + `/statistics` | `{"label":0}` ×3 at 800 px; class counts 500/400/500/300/300/300 = 2,300 | **match** |
| 9 | D42.1, D42.2 | Enrico | [design_topics.csv](https://raw.githubusercontent.com/luileito/enrico/master/design_topics.csv) | header + 3 rows identical; 1,460 screens; login 141 | **match** (topic "dialer 6" in the card is "calculator" in the CSV) |
| 10 | D34.1, D34.2 | VincentGOURBIN PPE | [valid/labels](https://huggingface.co/datasets/VincentGOURBIN/ppe-detection/tree/main/valid/labels) | 3 files identical; recounted all 164 validation files: no-vest 69, no-helmet 31 | **match** |
| 11 | D37.1–37.3 | morzel85 synthetic medical docs | [blob listing](https://huggingface.co/api/datasets/morzel85/synthetic-medical-document-recognition-benchmark?blobs=true) | 3 filenames present; 7,384 PNG; `cc-by-4.0` | **match** |
| 12 | D21.3 | KolektorSDD | [samples.json](https://huggingface.co/datasets/Voxel51/Kolektor_Surface_Defect/resolve/main/samples.json) | Part0/Part1 `false`, Part5 `true`, board kos01; 399 samples, 347 / 52 | **match** |
| 13 | D30.1, D30.2 | RDD2022 | [shard_000 metadata.jsonl](https://huggingface.co/datasets/dronefreak/RDD2022/resolve/main/data/images/train/shard_000/metadata.jsonl) | 3 rows identical; 3,000 rows, 74 empty; images per class 1,664 / 1,202 / 520 / 551 | **match** |
| 14 | D32.1 | AGRARIAN sheep & goats | [label txt](https://huggingface.co/datasets/AGRARIAN/greek_sheep_goats_dataset/resolve/main/train/labels/0058dd32-DJI_20250224121827_0005_D_2260_6.txt) | 3 lines identical | **match** |
| 15 | D46.3 | LoC Beyond Words | [val_20_percent.json](https://huggingface.co/datasets/biglam/loc_beyond_words/resolve/main/data/val_20_percent.json) | image 7 and annotations 1790/2186 identical; per-class "yes" pages 489/154/32/109/53/618/510 of 712 | **match** |
| 16 | D28.2, D28.3 | Powerline faults | [first-rows](https://datasets-server.huggingface.co/first-rows?dataset=docmhvr/powerline-components-and-faults&config=default&split=train) | label lists [0], [1,3,3,4,4,4,0], [1,1,1,1,3,1,3,3,4]; class names | **match** (the 1,794-row balance was not re-run) |
| 17 | D15.1, D34.3 | keremberke forklift | [first-rows](https://datasets-server.huggingface.co/first-rows?dataset=keremberke/forklift-object-detection&config=full&split=train) | image_ids 278/76/46, sizes, boxes, categories identical | **match** |
| 18 | D4.1 | CrisisMMD (damage) | [first-rows](https://datasets-server.huggingface.co/first-rows?dataset=QCRI/CrisisMMD&config=damage&split=train) | 3 rows identical (event, image_id, path, label 2) | **match** (D4.3 `label_image` not re-checked) |
| 19 | D43.1–43.3 | ChartBench | [test.jsonl](https://huggingface.co/datasets/SincereX/ChartBench/resolve/main/test.jsonl) | ids 1000–1002 identical; 10,500 records; chart counts; Yes 8,456 / No 8,444 | **match** |
| 20 | D47.3, D47.5, D48.5, D49.1, D49.2, D50.1–50.3 | Open Images V7 val labels | [oidv7-val-annotations-human-imagelabels.csv](https://storage.googleapis.com/openimages/v7/oidv7-val-annotations-human-imagelabels.csv) | all 18 pasted rows present with the same Source and Confidence; 539,987 + 78,197 rows; 41,620 images; positive/negative counts for all 10 classes identical | **match** |
| 21 | D23.1 | Tyres (NMiriams) | [/size Good](https://datasets-server.huggingface.co/size?dataset=NMiriams/Good_Tires), [/size Defective](https://datasets-server.huggingface.co/size?dataset=NMiriams/Defective_Tires) | 828 and 1,028 rows | **match** (repo-level proof only) |
| 22 | D15.2, D16.3 | cardboard box anomaly | [/rows test 0–99](https://datasets-server.huggingface.co/rows?dataset=Gabriel8/cardboard-box-anomaly-detection&config=default&split=test&offset=0&length=100) | rows 0, 1, 99 = label 0 (`bad`) at 3072×4080 / 4080×3072 | **match**; all 100 rows are `bad`, so the negatives were not seen again |
| 23 | D19.1 | CubiCasa5K-YOLO | [first-rows](https://datasets-server.huggingface.co/first-rows?dataset=v1nz/cubicasa5k-yolo&config=default&split=train) | 3 polygon lines identical | **match**, but bare `text` lines with no filename |
| 24 | D9.2, D9.3 | fake W-2 | [/rows test 0](https://datasets-server.huggingface.co/rows?dataset=singhsays/fake-w2-us-tax-form-dataset&config=default&split=test&offset=0&length=1) | box_1 126589.34, box_2 43873.99, 12a E, 12b None, 12c D, box 13 statutory "x", 15_1 HI, 15_2 WI | **match** |
| 25 | D6.2, D6.3, D7.2, D46.1, D46.2 | DocLayNet-base | [/rows test 0–2](https://datasets-server.huggingface.co/rows?dataset=pierreguillou/DocLayNet-base&config=DocLayNet_2022.08_processed_on_2023.01&split=test&offset=0&length=3) | doc_category, collection, filename, page_no, 1025×1025, category lists identical | **match** |
| 26 | D40.2, D40.3 | NEON beetles | [first-rows](https://datasets-server.huggingface.co/first-rows?dataset=imageomics/2018-NEON-beetles&config=individual_specimens&split=train) | 3 rows identical (sample id, species, site, paths) | **match** |
| 27 | D12.3, D48.1–48.3 | Fashionpedia | [first-rows](https://datasets-server.huggingface.co/first-rows?dataset=detection-datasets/fashionpedia&config=default&split=train) | image_ids 23/25/26, sizes, category lists identical | **match** |

## Merging collapsed 212 candidate rows onto about 177 datasets

The five CSV blocks hold **212 candidate rows**. Two rows in the slice-5 CSV had unquoted commas inside `answer_rule` and were repaired. After merging, the rows map onto about **177 distinct datasets**: **54 USE, 78 MAYBE, 34 SKIP and 11 GATED**, each counted at its best verdict. CrisisMMD gets two USE cards, one per answer source (the damage label and the TSV `label_image`). The cloverx-id ID-card repo is USE for its `flat` config and MAYBE for `augmented`. Six datasets appeared in more than one slice. For each, I kept the card with the strongest evidence, copied its dataset-level CSV fields onto the other rows, and kept each row's task-specific answer rule.

| Dataset | Appeared in | Card kept | Why | Facts carried over from the other card |
|---|---|---|---|---|
| DocLayNet | slice 1 (D6.2, D6.3, D7.2), slice 5 (D46.1, D46.2) | slice 5 | owner `LICENSE` quoted from GitHub; 499-page class counts from `/rows` | slice 1: v1.1 card licence line; DocLayNet-small 17.0 MB test parquet (49 pages); D6.3/D7.2 rules; v1.2 COCO id base `[UNVERIFIED]` |
| Fashionpedia | slice 2 (D12.3), slice 5 (D48.1–48.3) | slice 5 | val-split counts over 1,158 images (dress 506, bag 205, single-garment 496) | slice 2: smallest unit is the 84.85 MB val parquet; D12.3 4-way garment rule |
| keremberke forklift | slice 2 (D15.1), slice 4 (D34.3) | slice 2 | all rows counted: 194 forklift-only real negatives; smallest unit is the 2.77 MB `test.zip` | slice 4: OSHA/NIOSH value source |
| Stanford Cars (`tanganke`) | slice 1 (D3.5), slice 3 (D23.3) | slice 1 | shows tiny 85×64 rows and the 3.74 MB pixelate parquet | — (MAYBE either way) |
| darthraider fruit ripeness | slice 2 (D13.2), slice 4 (D31.5) | slice 2 | balanced test counts (250 per class) | — (MAYBE either way) |
| ashraq fashion-product-images-small | slice 2 (D12.2), slice 5 (D48.4) | slice 5 | masterCategory statistics; notes that the Kaggle original is login-gated | — (SKIP either way) |

**Open Images appears as a candidate only in slice 5.** Slice 2 mentions it only as an upstream source of the rejected OliseNS home-security set, so there was nothing to remove. The merge also linked cards across slices. Slice 1's **DrBimmer/comprehensive-car-damage** (USE, 800 undamaged negatives) answers slice 3's D23.4 "body damage present", which slice 3 had listed as a gap because it knew only the already-used DrBimmer parts set. The **Gabriel8 cardboard** card already listed D16.3 "parcel damaged" in its heading. PPE (D34) covers D26.5. Pig posture (D32.3) covers D39.4. The goodcoffee generator covers D27.5 as a Tier B question. These five links are marked with `*` in the coverage matrix.

## Coverage matrix: paperwork, inspection and moderation are covered; field operations are not

The matrix sorts every one of the 277 tasks into exactly one column. "With USE" means a USE dataset answers the task. "Generator only" means no USE data exists, but a slice Gaps table judges a drawn version realistic (yes, partly or medium). "Human photos" means the Gaps table says a generator is not realistic. The last column holds tasks whose candidates are only MAYBE or GATED, plus a few tasks the notes never assessed for a generator. Labels marked `(inf.)` are my classification of a task the notes grouped with others.

| Domain | Tasks | With USE | Generator only | Human photos | MAYBE / GATED / unassessed | USE task ids | Generator task ids | Human-photo task ids |
|---|---|---|---|---|---|---|---|---|
| 1 Banking and payments | 6 | 1 | 2 | 0 | 3 | 1.1 | 1.3, 1.4 | — |
| 2 Accounting / AP | 6 | 6 | 0 | 0 | 0 | 2.1–2.6 | — | — |
| 3 Insurance, motor | 6 | 3 | 1 | 0 | 2 | 3.1–3.3 | 3.6 | — |
| 4 Insurance, property / cat | 5 | 2 | 0 | 1 | 2 | 4.1, 4.3 | — | 4.5 |
| 5 Health billing docs | 5 | 0 | 4 | 0 | 1 | — | 5.1, 5.3, 5.4, 5.5 | — |
| 6 Legal and contracts | 5 | 2 | 3 | 0 | 0 | 6.2, 6.3 | 6.1, 6.4, 6.5 | — |
| 7 Government forms | 5 | 1 | 1 | 0 | 3 | 7.2 | 7.5 | — |
| 8 Identity and KYC | 6 | 3 | 1 | 0 | 2 | 8.1–8.3 | 8.6 | — |
| 9 Tax and customs | 5 | 3 | 1 | 0 | 1 | 9.1–9.3 | 9.5 | — |
| 10 HR and recruiting | 5 | 0 | 3 | 0 | 2 | — | 10.1, 10.4, 10.5 | — |
| 11 Retail shelves | 6 | 1 | 3 | 0 | 2 | 11.3 | 11.1, 11.4, 11.6 | — |
| 12 E-commerce listings | 6 | 2 | 1 | 0 | 3 | 12.3, 12.4 | 12.2 | — |
| 13 Grocery / produce | 6 | 1 | 1 | 2 | 2 | 13.4 | 13.6 | 13.1, 13.5 |
| 14 Food service hygiene | 5 | 0 | 0 | 4 | 1 | — | — | 14.2, 14.3, 14.4, 14.5 (inf.) |
| 15 Warehousing | 5 | 2 | 3 | 0 | 0 | 15.1, 15.2 | 15.3, 15.4, 15.5 | — |
| 16 Parcel / freight / container | 5 | 1 | 2 | 0 | 2 | 16.3 | 16.4, 16.5 | — |
| 17 Last-mile proof | 5 | 0 | 2 | 1 | 2 | — | 17.1, 17.3 | 17.2 |
| 18 Hospitality | 5 | 0 | 3 | 1 | 1 | — | 18.2, 18.3, 18.4 | 18.5 |
| 19 Real estate | 6 | 1 | 1 | 0 | 4 | 19.1 | 19.2 | — |
| 20 Facilities / waste | 5 | 1 | 1 | 1 | 2 | 20.1 | 20.5 | 20.4 |
| 21 Manufacturing quality | 7 | 1 | 1 | 0 | 5 | 21.3 | 21.7 | — |
| 22 Electronics / PCB | 5 | 1 | 1 | 1 | 2 | 22.1 | 22.4 | 22.5 |
| 23 Automotive repair | 6 | 3* | 2 | 0 | 1 | 23.1, 23.2*, 23.4* | 23.5, 23.6 | — |
| 24 Aviation maintenance | 5 | 0 | 1 | 2 | 2 | — | 24.4 | 24.2, 24.3 |
| 25 Rail and transit | 5 | 0 | 2 | 0 | 3 | — | 25.2, 25.3 | — |
| 26 Construction | 5 | 1* | 0 | 1 | 3 | 26.5* | — | 26.4 |
| 27 Meters and gauges | 5 | 2 | 1 | 0 | 2 | 27.1, 27.5* | 27.4 | — |
| 28 Energy assets | 6 | 2 | 1 | 1 | 2 | 28.2, 28.3 | 28.6 | 28.5 |
| 29 Oil, gas, mining | 5 | 0 | 0 | 2 | 3 | — | — | 29.4, 29.5 |
| 30 Roads and bridges | 6 | 2 | 0 | 0 | 4 | 30.1, 30.2 | — | — |
| 31 Agriculture | 7 | 3 | 0 | 2 | 2 | 31.1–31.3 | — | 31.6, 31.7 |
| 32 Livestock / fisheries | 6 | 3 | 0 | 1 | 2 | 32.1–32.3 | — | 32.6 |
| 33 Forestry / environment | 6 | 2 | 0 | 3 | 1 | 33.1, 33.3 | — | 33.2, 33.5, 33.6 |
| 34 Workplace safety / PPE | 7 | 4 | 1 | 1 | 1 | 34.1–34.4 | 34.6 | 34.7 |
| 35 Fire, smoke, security | 6 | 2 | 2 | 0 | 2 | 35.3, 35.4 | 35.5, 35.6 | — |
| 36 Traffic and parking | 6 | 2 | 2 | 0 | 2 | 36.1, 36.2 | 36.4, 36.5 | — |
| 37 Healthcare admin | 5 | 3 | 1 | 0 | 1 | 37.1–37.3 | 37.5 | — |
| 38 Pharmacy | 5 | 3 | 1 | 0 | 1 | 38.1–38.3 | 38.5 | — |
| 39 Veterinary and pets | 5 | 3* | 0 | 1 | 1 | 39.1, 39.2, 39.4* | — | 39.5 |
| 40 Laboratory | 5 | 2 | 1 | 0 | 2 | 40.2, 40.3 | 40.4 | — |
| 41 IT support screenshots | 5 | 3 | 2 | 0 | 0 | 41.1–41.3 | 41.4, 41.5 | — |
| 42 Web / mobile UI | 6 | 2 | 3 | 0 | 1 | 42.1, 42.2 | 42.4–42.6 | — |
| 43 Dashboards / charts | 6 | 5 | 0 | 0 | 1 | 43.1–43.5 | — | — |
| 44 Maps / satellite / drone | 6 | 0 | 0 | 1 | 5 | — | — | 44.6 |
| 45 Education | 5 | 3 | 1 | 0 | 1 | 45.1, 45.3, 45.4 | 45.5 | — |
| 46 Publishing / archives | 7 | 5 | 1 | 0 | 1 | 46.1–46.5 | 46.7 | — |
| 47 Marketing / ad compliance | 5 | 2 | 1 | 0 | 2 | 47.3, 47.5 | 47.4 | — |
| 48 Fashion and beauty | 5 | 4 | 0 | 0 | 1 | 48.1–48.3, 48.5 | — | — |
| 49 Customer service | 5 | 2 | 2 | 1 | 0 | 49.1, 49.2 | 49.3, 49.5 | 49.4 |
| 50 Moderation / brand safety | 6 | 3 | 0 | 1 | 2 | 50.1–50.3 | — | 50.6 |
| **Total** | **277** | **98** | **60** | **28** | **91** | | | |

`*` marks cross-references. D23.2 is answered by RDD2022 via D30.1; D23.4 by DrBimmer/comprehensive-car-damage via D3.1; D26.5 by the D34 PPE sets; D39.4 by pig posture via D32.3; D27.5 by goodcoffee as a Tier B question. D12.6 is a Tier C-only task and sits in the last column.

The pattern is clear. **Document and digital domains are close to done.** Domains 2, 43, 46 and 48 have four to six USE tasks each, and domains 5 and 10 are realistic to generate in full, since CMS-1500, I-9, W-2 and CN22 are public forms. **Inspection domains are half covered.** Each has one or two strong USE sets (KolektorSDD, DeepPCB, powerline faults, RDD2022), but most other candidates fail on label origin, because Roboflow exports rarely say who drew the boxes. **Field-operation domains are the real hole.** Food-service hygiene, aviation, oil, gas and mining, and maps all depend on human photos or on licence decisions. Domain 44 is a special case: FloodNet's human VQA labels are good, but the only licence is on the mirror, so a single owner-licence check would unlock three tasks.

## Build these 25 tasks first

The list is USE-only, uses one task per domain, is ordered by smallest fetch, and splits **13 yes/no and 12 pick-one**. Where a domain had several USE tasks, I chose the one with the highest decision frequency in the atlas, and switched two tasks to their pick-one form (PKLot free-space bins, AGRARIAN majority animal) to keep the balance. The first 25 entries in fetch order cover 25 domains. The reserve list under the table covers the other USE domains and is the natural second wave.

| # | Task | Typed question | Options | Shape | Dataset | Smallest fetch (MB) | Licence flag | Re-checked |
|---|---|---|---|---|---|---|---|---|
| 1 | D38.2 | "Which product is this tablet?" | Cipro 500 / Ibuphil 600 / Ibuphil Cold / Xyzall 5 mg | pick-one | [LibreYOLO/pills-sxdht](https://huggingface.co/datasets/LibreYOLO/pills-sxdht) | 0.001 (label txt) | — | yes |
| 2 | D36.1 | "About how many labelled spaces are free?" | 0–10 / 11–30 / 31–60 / 61+ | pick-one | [dronefreak/PKLot](https://huggingface.co/datasets/dronefreak/PKLot) | 0.001 (txt); all train labels in a 15.5 MB jsonl | — | yes |
| 3 | D35.3 | "Is a weapon visible?" | yes / no | yes/no | [HARIS weapons](https://huggingface.co/datasets/Turki-Alshuaibi/haris-weapon-detection-dataset-curated) | 0.001 | UCF-Crime upstream | yes |
| 4 | D3.1 | "Is this car visibly damaged?" | yes / no | yes/no | [DrBimmer/comprehensive-car-damage](https://huggingface.co/datasets/DrBimmer/comprehensive-car-damage) | 0.01 (one image) | — | yes |
| 5 | D41.1 | "Which application is shown in this screenshot?" | 4–6 app names | pick-one | [likaixin/ScreenSpot-Pro](https://huggingface.co/datasets/likaixin/ScreenSpot-Pro) | 0.02 | — | yes |
| 6 | D27.1 | "What does the gauge read?" | true value + 3 tick-spaced distractors | pick-one | [goodcoffee/Meter_Reading](https://huggingface.co/datasets/goodcoffee/Meter_Reading) | 0.022 | licence is the whole card | yes |
| 7 | D22.1 | "Does this bare PCB image contain a manufacturing defect?" | yes / no | yes/no | [DeepPCB](https://github.com/tangsanli5201/DeepPCB) | 0.023 | research-only wording | yes |
| 8 | D34.1 | "Is any worker without a safety vest?" | yes / no | yes/no | [VincentGOURBIN/ppe-detection](https://huggingface.co/datasets/VincentGOURBIN/ppe-detection) | 0.05 | faces | yes |
| 9 | D42.1 | "What type of screen is this?" | login / list / form / gallery / settings / tutorial | pick-one | [Enrico](https://github.com/luileito/enrico) | 0.05 (labels CSV) | — | yes |
| 10 | D37.1 | "What kind of document is this page?" | contact info / observation / vaccination history / report / survey / notes | pick-one | [morzel85 synthetic medical docs](https://huggingface.co/datasets/morzel85/synthetic-medical-document-recognition-benchmark) | 0.08 | admin questions only | yes |
| 11 | D2.4 | "Does this invoice show a purchase-order number?" | yes / no | yes/no | [HV09 synthetic invoices](https://huggingface.co/datasets/HV09/synthetic-bilingual-invoices-200) | 0.1 | — | yes |
| 12 | D21.3 | "Does this commutator surface show a crack or defect?" | yes / no | yes/no | [KolektorSDD](https://huggingface.co/datasets/Voxel51/Kolektor_Surface_Defect) | 0.27 | **NC-SA** | yes |
| 13 | D30.1 | "Is there a pothole in this road image?" | yes / no | yes/no | [RDD2022](https://huggingface.co/datasets/dronefreak/RDD2022) | 0.37 (shard metadata) | BY vs BY-SA | yes |
| 14 | D32.1 | "Which animal is most numerous?" | goat / sheep / none visible | pick-one | [AGRARIAN sheep & goats](https://huggingface.co/datasets/AGRARIAN/greek_sheep_goats_dataset) | 0.5 | — | yes |
| 15 | D16.3 | "Is this parcel (cardboard box) damaged?" | yes / no | yes/no | [Gabriel8 cardboard box](https://huggingface.co/datasets/Gabriel8/cardboard-box-anomaly-detection) | 1.42 (one image) | **NC-SA** | yes |
| 16 | D46.3 | "Does this newspaper page contain a photograph?" | yes / no | yes/no | [LoC Beyond Words](https://huggingface.co/datasets/biglam/loc_beyond_words) | 1.43 (val JSON) | — | yes |
| 17 | D23.1 | "Is this tyre defective?" | yes / no | yes/no | [NMiriams tyres / Mendeley bn7ch8tvyp](https://data.mendeley.com/datasets/bn7ch8tvyp) | ~1.5 (one image) | — | yes |
| 18 | D28.2 | "Is there a broken insulator in this image?" | yes / no | yes/no | [docmhvr powerline faults](https://huggingface.co/datasets/docmhvr/powerline-components-and-faults) | 2.29 (test parquet) | MIT in README body only | yes |
| 19 | D15.1 | "Is a person visible together with the forklift?" | yes / no | yes/no | [keremberke forklift](https://huggingface.co/datasets/keremberke/forklift-object-detection) | 2.77 (test.zip) | faces | yes |
| 20 | D4.1 | "How severe is the damage to buildings or infrastructure?" | little or none / mild / severe | pick-one | [QCRI/CrisisMMD](https://huggingface.co/datasets/QCRI/CrisisMMD) | 3.07 (split zip) | **NC-SA** | yes |
| 21 | D43.1 | "What type of chart is this?" | bar / line / pie / area / scatter / box | pick-one | [SincereX/ChartBench](https://huggingface.co/datasets/SincereX/ChartBench) | 3.86 (jsonl) + range read into a 227.67 MB zip | harm clause | yes |
| 22 | D19.1 | "How many doors does this floorplan show?" | 0–3 / 4–6 / 7–9 / 10+ | pick-one | [v1nz/cubicasa5k-yolo](https://huggingface.co/datasets/v1nz/cubicasa5k-yolo) | ~4.4 (one PNG + txt) | **NC; conflict** | yes |
| 23 | D9.3 | "Is the 'statutory employee' box in box 13 ticked?" | yes / no | yes/no | [singhsays fake W-2](https://huggingface.co/datasets/singhsays/fake-w2-us-tax-form-dataset) | 15.47 (test parquet) | licence via upstream Kaggle | yes |
| 24 | D6.2 | "What kind of document is this page from?" | laws / financial report / tender / manual / patent / scientific article | pick-one | [DocLayNet](https://github.com/DS4SD/DocLayNet) | 17.0 (DocLayNet-small test) | — | yes |
| 25 | D40.2 | "How many beetles are in this tray image?" | 1–5 / 6–15 / 16–40 / 41+ | pick-one | [imageomics/2018-NEON-beetles](https://huggingface.co/datasets/imageomics/2018-NEON-beetles) | 19.5 (CSV) | SA | yes |

Several items need build-time care, all taken from the cards. For D38.2, use only images whose label is a product class (0–3), because the taxonomy mixes product names and colours. For D36.1, phrase the question as *labelled* spaces: PKLot leaves 25,773 spaces unlabelled. For D3.1, the 800 undamaged images are the negatives. For D22.1, rename the `_temp`/`_test` files so the filename cannot leak the answer. For D21.3, sample 52 negatives to match the 52 positives. For D30.1, never ask "any damage?", because "empty" RDD images can still contain dropped class-4 damage. For D32.1, drop ties and treat an empty label file as "none". For D16.3, sample one image per box and position: there are only 43 physical boxes. For D46.3, prefer Photograph, Map and Comics, where crowd marks are least likely to be missed. For D4.1, never show the tweet text. For D43.1, exclude the "combination" type. For D19.1, spot-check 20 plans for conversion errors. For D9.3, accept that values are internally inconsistent; the box itself is still generator truth. For D40.2, use group images only, because single-specimen crops are about 130×200 px.

**Reserve list (second wave, in fetch order).** D13.4 grocery item (0.17 MB per file; low business realism). D8.2 passport expiry after issue (10.05 MB `samples.json`). D7.2 government tender page yes/no (same DocLayNet fetch as #24). D50.1 weapon present, D49.1 screenshot yes/no and D47.3 advertising present (the same 28.4 MB Open Images CSV, with verified negatives). D20.1 recycling stream (42.83 MB zip). D11.3 price-tag count (44.16 MB). D1.1 cheque bank (76.11 MB). D48.2 main garment (84.85 MB parquet or `/rows`). D45.1 worksheet MCQ (122.4 MB). D31.2 seedling species, D39.1 cat or dog and D33.1 camera-trap species (309–415 MB shards; sample via `/rows`). D12.4 white-background main image (505 MB shards; `/rows`).

## Eleven GATED candidates wait on a person, and nine MAYBEs could be promoted the same way

The rule throughout was to never log in, accept terms, fill forms or request access. The 11 GATED candidates below each need one human decision. I add the cases where a single human action would turn a MAYBE into a likely USE.

| Candidate | Task(s) | URL | What a person must do | What it would unlock (from the notes) |
|---|---|---|---|---|
| Symage/coherent-forms-1040-cms1500-i9 | D5.1 (name suggests D9, D10.1 too [INFERRED]) | https://huggingface.co/datasets/Symage/coherent-forms-1040-cms1500-i9 | Log in, accept the terms (`gated: "auto"`), read the `license:other` text | 1,971.4 MB parquet (train 1,576.94 / test 394.46); README and viewer return 401 |
| tech4humans/signature-detection | D6.1 | https://huggingface.co/datasets/tech4humans/signature-detection | Log in, accept the terms (`gated: "auto"`; tag apache-2.0) | 147.4 MB; smallest parquet 17.21 MB |
| konfuzio/funsd_plus | D7.3 | https://huggingface.co/datasets/konfuzio/funsd_plus (licence: …/blob/main/LICENSE) | Read the FUNSD+ LICENSE. Decide whether to submit the `extra_gated_prompt` (Name, Company, Country, Email; agree not to identify individuals). The API says not gated, but the card asks for consent | 195.2 MB; test 19.78 MB; 18.3% of questions unanswered (real yes/no material) |
| Guztavu/container-damage | D16.2 | https://huggingface.co/datasets/Guztavu/container-damage | Log in, accept the terms (`gated: auto`), read the licence (README 401) | `bbox_nodmg.zip` 241.29 MB suggests real negatives |
| LouisChen15/ConstructionSite | D26.4 | https://huggingface.co/datasets/LouisChen15/ConstructionSite | Log in, accept the terms; licence CC BY-NC 4.0 | 4,497.7 MB construction-site VQA |
| utilitimetersai/Annotated-Mechanical-And-LCD-Utility-Meter-Dials-Dataset | D27.4 | https://huggingface.co/datasets/utilitimetersai/Annotated-Mechanical-And-LCD-Utility-Meter-Dials-Dataset | Request access (`gated=manual`) and wait for approval; CC BY-NC 4.0 | mechanical vs LCD meter labels |
| Mileeena/synthetic-analog-gauges | D27.1 alt | https://huggingface.co/datasets/Mileeena/synthetic-analog-gauges | Log in, accept the terms (`gated=auto`); CC BY 4.0 | 2,545 MB generator gauges with COCO annotations |
| CODEBRIM (Zenodo 2620293; mirror h4tem/codebrim) | D30.5 | https://zenodo.org/records/2620293 (license.md) | Accept the licence agreement: "non-commercial research and educational purposes only… shall not distribute". Then fetch a 7.9–12.2 GB single archive. The mirror may hold the same data | concrete defect classes |
| FigureQA | D43.2, D43.6 | https://www.microsoft.com/en-us/research/project/figureqa-dataset/ | Read the "Licensing" tab and click "Agree & Download". Decide whether the open mirror `vikhyatk/figureqa` (no licence) may be used | generator charts with yes/no QA |
| wony98/healtheat-pill-yolo | D38.x | https://huggingface.co/datasets/wony98/healtheat-pill-yolo | Check the upstream AI Hub / Kaggle terms the card says also apply (AI Hub normally needs an account) | 18,793 MB pill detection |
| rotsl/colony-cfu-counting-coco | D40.4 | https://huggingface.co/datasets/rotsl/colony-cfu-counting-coco | Request access (`gated: manual`); MIT on the card | colony counts (287.1 MB) |

| MAYBE candidate | Task(s) | Human action that would unblock it |
|---|---|---|
| D-Fire (`badsaarow/d-fire`; owner https://github.com/gaiasd/DFireDataset) | D35.1, D35.2 | Email the GAIA authors for licence terms. It has the slice's strongest fire/smoke negatives (9,838 "none" images per its README) |
| Severstal steel (Voxel51 mirror) | D21.1, D21.2 | Read the Kaggle competition rules at https://www.kaggle.com/competitions/severstal-steel-defect-detection (needs login) |
| FloodNet Track 2 (mirror `takara-ai/...`) | D44.1–44.3 | Confirm the owner licence at https://github.com/BinaLab/FloodNet-Challenge-EARTHVISION2021 (none found). This would open domain 44 |
| IDNet-2025 | D8.4 | Approve fetching one country archive (`EST.tar.gz`, 1,354.22 MB) to sample its generator tamper labels |
| SKUs_on_shelves_PL | D11.1, D11.6 | Pull only the COCO JSON out of the 11,422 MB single archive |
| CubiCasa5K original; Parcel3D | D19.2; D16.3 | Pull a subset of the 5,469.5 MB / 45,838.3 MB archives |
| Wood defects, ELPV, dacl10k, RPC, MEDIC | D21.4/5, D28.1, D30.4/6, D11.5, D4.2/4.4 | Read each paper's annotation section; each card says it upgrades to USE if human labelling is confirmed |
| LILA Channel Islands full metadata | D33.2 | Fetch the full metadata JSON with `empty` frames from lila.science (the HF subset dropped empties) |
| Fashion Product Images (Kaggle original) | D48.4 | Kaggle login for full-resolution images; the HF copy is 60×80 px |

## Recommendations: derived counts and verified negatives first, model-written questions last

**Tier B: build in this order.** First, **verified-negative presence and "which is NOT present"** on Open Images V7. Its Confidence 0 rows are human-checked absences, so "Which of these is present?" (one verified positive, the others verified 0) and the brand-safety OR-composite ("alcohol or a weapon?", answering no only if both are verified 0) come out trustworthy at scale. This is the only Tier B family whose negatives are explicitly human-verified ([Open Images V7](https://storage.googleapis.com/openimages/web/factsfigures_v7.html)). Second, **count buckets from complete per-image annotations**, which turn detection sets into pick-one questions with no new labelling: PKLot free spaces, RDD2022 instances (0 / 1–2 / 3+), DeepPCB defects (1–3 / 4–7 / 8+), PPE person counts, medication-box counts, NEON tray "more than 20", LoC photographs per page, CubiCasa windows. Third, **arithmetic and date logic over generator fields**, the cheapest route to hard but exact questions: HV09 "Is VAT about 5% of subtotal?", W-2 "Is federal withholding above 30% of wages?", passport "expired as of 2026-10-01?" and "holder over 18 on the issue date?", meter "above half of full scale?". Fourth, **class roll-ups through a fixed lookup** (crop vs weed, conifer vs broadleaf, recyclable vs trash, blackletter yes/no, cat vs dog from breed). These are cheap, but each lookup is `[INFERRED]` in the notes, so a person should sign off on every table. Hold back two families. Bounding-box geometry questions (left/right, quadrant, "larger than") must survive resizing to 1536 px and boxes clipped at the edge (OFF price tags have negative coordinates). "Which is NOT worn/present" on Fashionpedia, LoC and MIT Indoor assumes exhaustive annotation that the notes do not verify. Metadata that is not visible (CrisisMMD event name, RDD country prefix, illustrated_ads place of publication, ScreenSpot `img_size`) belongs only in control questions.

**Tier C fits where the trusted label is coarse but the image holds more.** The best candidates are tyre defect type (D23.1: the label is only good/defective), cardboard-box defect type (crushed corner, tear, wet, open flap; D15.2/D16.3), shelf-tag price reading (D11.3), moderation-policy rewordings over Open Images (D47–D50), ticket-style rewordings and confusable-app distractors for ScreenSpot-Pro (D41), look-alike breed distractors for Oxford-IIIT Pet (D39), and material and colour questions for ABO-Edit (D12.4). Every slice's Part C applies the same rules. Store each Tier C item with `label_origin: model` in a separate table and score column. Keep it only if a second model from a different family gives the same answer blind. Never let the model under test write or validate questions. Never let Tier C introduce a new fact. Keep Tier C away from judgement wording such as "Does this road need urgent repair?" or "Should this span be scheduled?" (RDD2022, powerline), and away from severity on the weapons set.

**Training-data overlap: assume it for the famous benchmarks; the 2025–26 generators are the clean controls.** Every overlap claim in the notes is `[INFERRED]`. The notes call overlap likely or high for Open Images, Oxford-IIIT Pet, PKLot, SROIE, DocLayNet, RICO-based Enrico, ScienceQA, AI2D, Food-101, TrashNet, MIT Indoor-67, FGVC-Aircraft, Stanford Cars, the plant-seedlings Kaggle set, Fashionpedia, RDD2022, DeepPCB, the images.cv forklift photos, the Pexels stock in the grocery set, and Kaggle-style folder sets such as DrBimmer. ScreenSpot-Pro is a popular GUI benchmark with high contamination risk, and CharXiv's arXiv figures are likely in pretraining. They call overlap moderate or possible for KolektorSDD, NIST SD2, CrisisMMD (published 2018) and the tyre set (also on Kaggle). They call it low for the albertobarnabo receipts, the jaganadhg cheques (2025-era repo) and the early-printed-books pages ("little web overlap"). The notes make no overlap claim for the HV09 invoices, the morzel85 medical documents, the goodcoffee gauges, the AGRARIAN 2025 drone frames, the 2025 pig-posture frames or the cardboard boxes. My own inference, from their recent dates and synthetic or newly photographed content, is that they are low-overlap too. The practical consequence: report each first-build task's score next to a low-overlap twin from the same domain where one exists (for example DocLayNet vs morzel85, or Open Images vs a generator task), so that memorisation shows up as a gap between the two.

## Conclusion

The merge changes the picture more than any single slice suggested. Cross-slice reuse is worth more than more searching. One document-layout set (DocLayNet) serves three domains, one image-label CSV (Open Images) serves four, and a car-damage set carded for insurance fills an automotive gap. The highest-yield next step is therefore not more dataset hunting. It is three cheap human actions: an email to the D-Fire authors, an owner-licence check on FloodNet, and a decision on the FUNSD+ and signature-detection gates. Together these would open the fire, maps and legal domains.

The atlas also shows that "trustworthy" divides cleanly along label origin, not modality. Generator-made documents and gauges give exact answers and little contamination, but drawn images lack realism. Human-labelled photo sets give realism but carry NC licences, Roboflow-style provenance gaps and benchmark contamination. A bench that pairs one of each per domain (the first-build list already contains 5 generator-labelled tasks and 20 human-labelled tasks) will separate reading skill from memorisation better than either kind alone.

---

# Appendices

The appendices carry the slice material that the spec requires, merged and de-duplicated. Content is reproduced from the slice notes with their evidence tags. Appendix headings name the source slice.


## Appendix A. Task atlas, one table per domain

Reproduced from each slice's Part A. Value-reason sources and tags are as the researchers recorded them. Tags such as `[UNVERIFIED-snippet]` mean the source page was seen only as a search-result snippet.


### A1. Slice 1 — Money and paperwork (D1–D10)

#### D1 Banking and payments documents
| id | task | typed question | options | image type | value reason (one source) |
|---|---|---|---|---|---|
| D1.1 | Cheque issuing bank | "Which bank's cheque is this?" | Axis / Canara / ICICI / Syndicate | scan | Check fraud is a leading fraud type: check-fraud Suspicious Activity Reports (SARs) nearly doubled to over 680,000 in 2022 ([FinCEN alert FIN-2023-Alert003, via ABA Banking Journal](https://bankingjournal.aba.com/2023/02/fincen-issues-alert-for-check-fraud-via-usps/)). Routing the cheque to the right bank template comes first. |
| D1.2 | Courtesy and legal amount agree | "Does the amount in words match the amount in figures?" | yes / no | scan | Same FinCEN source: altered cheques lead the list of check-fraud methods ([ACAMS](https://www.acams.org/en/news/fincen-lists-check-fraud-methods-alteration-tops-the-list)). |
| D1.3 | Cheque signed | "Is the drawer's signature present?" | yes / no | scan | Same FinCEN source. An unsigned item is returned (no separate source fetched). |
| D1.4 | Cheque stale-dated | "Is the cheque date more than 6 months before <reference date>?" | yes / no | scan | No source fetched. |
| D1.5 | Statement type | "Is this a bank-account statement or a credit-card statement?" | bank statement / credit card | scan, PDF render | No source fetched. Statement intake for lending and KYC is a common vendor use case, with no primary source found. |
| D1.6 | Transaction table on page | "Does this statement page contain a transaction table?" | yes / no | PDF render | No source fetched. |

#### D2 Accounting and accounts payable
| id | task | typed question | options | image type | value reason |
|---|---|---|---|---|---|
| D2.1 | Receipt total | "Which amount is the receipt's final total?" | 4 amounts printed on the receipt | scan | APQC cross-industry median cost to process accounts payable is $6.00 per invoice. The bottom quartile pays $10 or more ([APQC via CFO.com](https://www.cfo.com/news/metric-of-the-month-accounts-payable-cost/659393/)). |
| D2.2 | Payment method | "How was this receipt paid?" | cash / card / contactless / mobile wallet | photo (simulated) | Same APQC source (expense audit). |
| D2.3 | Receipt country | "Which country is this receipt from?" | US / UK / DE / IT / FR | photo (simulated) | Same APQC source. Country decides the VAT reclaim rules [INFERRED]. |
| D2.4 | PO reference present | "Does this invoice show a purchase-order number?" | yes / no | rendered scan | Same APQC source. Three-way match needs a PO [INFERRED]. |
| D2.5 | Hijri-dated invoice | "Is the invoice date written in the Hijri calendar?" | yes / no | rendered scan | Same APQC source. |
| D2.6 | Line-item count | "How many line items does this invoice list?" | 1 / 2 / 3 / 4 / 5+ | rendered scan | Same APQC source. |

#### D3 Insurance, motor
| id | task | typed question | options | image type | value reason |
|---|---|---|---|---|---|
| D3.1 | Vehicle damaged | "Is this car visibly damaged?" | yes / no | photo | The Coalition Against Insurance Fraud estimates insurance fraud at $308.6 B a year across all lines ([Reinsurance News](https://www.reinsurancene.ws/insurance-fraud-costs-308-6bn-annually-coalition-reports/); critics question the method, per [Rutgers CRR](https://crr.rutgers.edu/wp-content/uploads/sites/22/Misinformation-About-Insurance-Fraud-11-2024.pdf)). Photo triage of first notice of loss (FNOL) is the first gate. |
| D3.2 | Which end is shown | "Is this the front or the rear of the car?" | front / rear | photo | Same source. Point of impact must match the claim [INFERRED]. |
| D3.3 | Damage kind | "What damage is visible?" | none / breakage / crushed | photo | Same source. |
| D3.4 | Damage type | "Which damage type is shown?" | crack / dent / glass shatter / lamp broken / scratch / flat tyre | photo | Same source. |
| D3.5 | Body style | "What body style is this vehicle?" | sedan / SUV / coupe / convertible / hatchback / wagon | photo | No source fetched. Underwriting checks vehicle type. |
| D3.6 | Odometer reading | "Which reading does the odometer show?" | 4 numeric options | photo | No source fetched. |

#### D4 Insurance, property and catastrophe
| id | task | typed question | options | image type | value reason |
|---|---|---|---|---|---|
| D4.1 | Damage severity | "How severe is the damage to buildings or infrastructure?" | little or none / mild / severe | photo (ground level, social media) | Global insured nat-cat losses were USD 137 B in 2024 ([Swiss Re sigma 1/2025](https://www.swissre.com/institute/research/sigma-research/sigma-2025-01-natural-catastrophes-trend.html)). |
| D4.2 | Disaster type | "What kind of disaster is shown?" | earthquake / flood / hurricane / fire / landslide / none | photo | Same Swiss Re source. Peril assignment drives the claim route [INFERRED]. |
| D4.3 | Infrastructure damage | "Does the image show damage to buildings, roads or utilities?" | yes / no | photo | Same Swiss Re source. |
| D4.4 | Flooding | "Is flooding visible?" | yes / no | photo | Same Swiss Re source. |
| D4.5 | Roof damage (ground level) | "Is the roof damaged?" | yes / no | photo | Same source. No dataset (see Gaps). |

#### D5 Insurance, health and medical billing documents (no diagnosis)
| id | task | typed question | options | image type | value reason |
|---|---|---|---|---|---|
| D5.1 | Claim form type | "Which claim form is this?" | CMS-1500 / UB-04 / 1040 / I-9 / other | scan | The FY2024 Medicare FFS improper payment rate is 7.66%, or $31.70 B ([CMS fact sheet](https://www.cms.gov/newsroom/fact-sheets/fiscal-year-2024-improper-payments-fact-sheet)). |
| D5.2 | Medication count on prescription | "How many medications are listed?" | 1 / 2 / 3 / 4+ | scan or render | Same CMS source. |
| D5.3 | Claim form signed | "Is the patient or physician signature box filled?" | yes / no | scan | Same CMS source. Missing documentation is a main improper-payment cause [UNVERIFIED]. |
| D5.4 | Itemised bill | "Is this bill itemised by service line?" | yes / no | scan | Same CMS source. |
| D5.5 | Insurance card plan type | "Which plan type is printed on the member card?" | HMO / PPO / EPO / POS / other | photo | Same source. No dataset. |

#### D6 Legal and contracts
| id | task | typed question | options | image type | value reason |
|---|---|---|---|---|---|
| D6.1 | Signed | "Is the document page signed?" | yes / no | scan | Poor contract management costs the average business almost 9% of annual revenue ([WorldCC, via CFO.com](https://www.cfo.com/press-release/20250819-the-multi-million-dollar-leak-in-your-contracts-and-how-to-stop-it/)). |
| D6.2 | Page category | "What kind of document is this page from?" | laws & regulations / financial report / government tender / manual / patent / scientific article | scan or render | Same WorldCC source (routing for legal review). |
| D6.3 | Table present | "Does this page contain a table?" | yes / no | render | Same source. Schedules of fees and obligations sit in tables [INFERRED]. |
| D6.4 | Stamp or seal present | "Does the page carry a stamp or seal?" | yes / no | scan | Same source. No usable dataset. |
| D6.5 | Redaction present | "Is any text redacted (black-boxed)?" | yes / no | scan | Same source. No dataset. |

#### D7 Government forms and permits
| id | task | typed question | options | image type | value reason |
|---|---|---|---|---|---|
| D7.1 | Checkbox state | "Is the box for <question> ticked Yes or No?" | yes / no | scan of government form | The APQC public-sector median is $9.43 per invoice, the costliest industry ([APQC via CFO.com](https://www.cfo.com/news/metric-of-the-month-accounts-payable-cost/659393/)). This is a proxy for public paperwork cost. A form-specific source was not found. |
| D7.2 | Government tender page | "Is this page from a government tender?" | yes / no | render | Same proxy source. |
| D7.3 | Unanswered field | "Does this form contain a question with no answer filled in?" | yes / no | scan | No source fetched. |
| D7.4 | Is it a form | "Is this document a form, a letter, a memo, an invoice or a report?" | form / letter / memo / invoice / report | scan | No source fetched. |
| D7.5 | Permit validity | "Is the permit's expiry date before <reference date>?" | yes / no | scan | No dataset. |

#### D8 Identity and KYC (specimen or synthetic documents only)
| id | task | typed question | options | image type | value reason |
|---|---|---|---|---|---|
| D8.1 | Printed sex field | "What sex is printed on this (synthetic) ID card?" | M / F (LAKI-LAKI / PEREMPUAN) | render | FATF requires verifying identity with "reliable, independent" documents, data or information ([FATF Digital ID guidance](https://www.fatf-gafi.org/media/fatf/documents/recommendations/pdfs/Guidance-on-Digital-Identity-report.pdf)). |
| D8.2 | Date consistency | "Is the expiry date later than the issue date?" | yes / no | photo or scan (synthetic) | Same FATF source. Inconsistent dates flag a forgery [INFERRED]. |
| D8.3 | Nationality or issuing country | "Which nationality is printed?" | 4–6 countries | photo (synthetic) | Same FATF source. |
| D8.4 | Tampered document | "Has this ID document been tampered with?" | yes / no | scan (synthetic) | Same FATF source. |
| D8.5 | Document type | "Is this a passport or an ID card?" | passport / ID card | photo (specimen) | Same FATF source. |
| D8.6 | ID present in photo | "Is there an Indonesian KTP card in this photo?" | yes / no | photo | Same FATF source. |

#### D9 Tax and customs documents
| id | task | typed question | options | image type | value reason |
|---|---|---|---|---|---|
| D9.1 | Tax form page | "Which tax form page is this?" | e.g. 1040 p1 / 1040 p2 / Sch A / Sch B / Sch E p1 / Sch D p2 | scan | The IRS projected gross tax gap for TY2022 is $696 B, with underreporting at 77% ([IRS IR-2024-262](https://irs.gov/newsroom/irs-releases-2022-tax-gap-projections-voluntary-compliance-rate-among-taxpayers-remains-steady)). |
| D9.2 | W-2 state | "Which state is in box 15 (first line)?" | 4 state codes | render | Same IRS source. |
| D9.3 | W-2 box 13 | "Is the 'statutory employee' box in box 13 ticked?" | yes / no | render | Same IRS source. |
| D9.4 | IRS form family | "Which IRS form is this?" | 1040 / W-2 / W-4 / W-9 / 1099-NEC / 941 | render | Same IRS source. |
| D9.5 | Customs declaration goods category | "Which category is ticked on the CN22/CN23?" | gift / documents / commercial sample / returned goods / other | scan | WCO Time Release Study measures release time and is endorsed by WTO TFA Art. 7.6 ([WCO TRS excerpt](https://www.carecprogram.org/uploads/Day2-WCO-Time-Release-Study.pdf)). No dataset. |

#### D10 HR and recruiting
| id | task | typed question | options | image type | value reason |
|---|---|---|---|---|---|
| D10.1 | I-9 form completeness | "Is Section 2 of the I-9 signed?" | yes / no | scan | I-9 paperwork violations draw per-form fines ([Experian Employer Services summary](https://www.experian.com/blogs/employer-services/how-to-avoid-form-i-9-fines-and-violations/); amounts there are secondary and change yearly) [UNVERIFIED primary]. |
| D10.2 | Business card has email | "Does this business card show an email address?" | yes / no | photo (simulated) | No source fetched. |
| D10.3 | Business card has mobile number | "Does this card list a mobile number?" | yes / no | photo (simulated) | No source fetched. |
| D10.4 | Timesheet total hours | "What total hours does the timesheet show?" | 4 numeric options | scan | No dataset. |
| D10.5 | Badge expired | "Is the badge expiry date before <reference date>?" | yes / no | photo | No dataset. |

### A2. Slice 2 — Goods, places and logistics (D11–D20)

Value reasons come from web-search result snippets. The URLs were returned by the search tool and I did not open them in full, so each sentence is tagged [UNVERIFIED-snippet] unless noted. "No source" means none was found or fetched.

#### Domain 11: Retail shelves and merchandising
| # | Task | Typed question | Options | Image type | Value reason (source) |
|---|---|---|---|---|---|
| 11.1 | Out-of-stock gap | "Is there an empty facing (gap) on this shelf?" | yes/no | photo | IHL Group puts the global cost of inventory distortion at about $1.77T in 2025, of which about $1.2T is out-of-stocks [UNVERIFIED-snippet] ([IHL](https://www.ihlservices.com/product/inventory-distortion/); [Chain Store Age](https://chainstoreage.com/study-global-retail-losses-due-inventory-distortion-hit-177-trillion)) |
| 11.2 | Price-tag photo usable | "How readable is this price tag crop?" | invalid / medium-quality / high-quality | photo crop | Open Prices uses this exact class to triage crowd price photos before extraction ([OFF report](https://github.com/openfoodfacts/openfoodfacts-ai/blob/develop/docs/reports/2026-03-price-tag-classification.md)) [PAPER] |
| 11.3 | Shelf-edge label count | "How many price tags are visible?" | 0–2 / 3–5 / 6–10 / 11+ | photo | Same IHL source (label audits feed availability checks) [UNVERIFIED-snippet] |
| 11.4 | Discount flag on tag | "Does this price tag show a promotional/discounted price?" | yes/no | photo crop | No source fetched |
| 11.5 | Checkout basket count | "How many products are on the checkout tray?" | 3–4 / 5–6 / 7–8 / 9+ | photo (top-down) | RPC paper motivates automatic checkout (arXiv 1901.07249) [UNVERIFIED: abstract not fetched] |
| 11.6 | Planogram category block | "Which product category occupies this shelf?" | drinks / snacks / dairy / household / other | photo | No source fetched |

#### Domain 12: E-commerce product listings and catalogues
| # | Task | Typed question | Options | Image type | Value reason |
|---|---|---|---|---|---|
| 12.1 | Category check of listing image | "What product type is shown?" | e.g. SHOES / CHAIR / LAMP / SOFA / HARDWARE / other | photo (catalogue) | No source fetched (catalogue mis-categorisation cost) |
| 12.2 | Colour attribute check | "What is the main colour of the product?" | 4–6 colour names | photo | No source fetched |
| 12.3 | Garment present in model shot | "Which of these garments is worn: dress / pants / skirt / shorts?" | 4 options | photo | No source fetched |
| 12.4 | Main-image compliance (white background) | "Is the product shown alone on a plain white background?" | yes/no | photo / render | No source fetched (marketplace main-image rules; not fetched) |
| 12.5 | View/angle check | "Is the product shown front-on or turned?" | front / three-quarter-or-other | render | No source |
| 12.6 | Product colour/size text vs image | (Tier C only) | n/a | photo | No source |

#### Domain 13: Grocery and produce quality
| # | Task | Typed question | Options | Image type | Value reason |
|---|---|---|---|---|---|
| 13.1 | Fresh vs rotten | "Is this fruit/vegetable rotten?" | yes/no | photo | USDA ERS: average supermarket loss is 11.6% for 31 fresh vegetables and fresh-fruit shrink is 12.6% [UNVERIFIED-snippet] ([USDA ERS](https://ers.usda.gov/data-products/food-availability-per-capita-data-system/food-loss)) |
| 13.2 | Ripeness | "Is this banana/mango ripe or unripe?" | ripe / unripe (× banana / mango) | photo | Same USDA ERS source [UNVERIFIED-snippet] |
| 13.3 | Variety identification at till | "Which variety is this?" | e.g. Golden-Delicious / Granny-Smith / Pink-Lady … | photo (in-store) | No source fetched (PLU mis-keying) |
| 13.4 | Item identification | "Which grocery item is this?" | apple / banana / bread_roll / cheese / tomato | photo | No source |
| 13.5 | Bruise/defect grade | "Grade of this produce item?" | Extra / I / II | photo | No source (UNECE marketing standards, not fetched) |
| 13.6 | Date-label legible | "Is the use-by date legible?" | yes/no | photo | No source |

#### Domain 14: Food service and restaurant hygiene
| # | Task | Typed question | Options | Image type | Value reason |
|---|---|---|---|---|---|
| 14.1 | Dish matches order | "Which dish is this?" | 2–6 of 101 Food-101 classes | photo | No source fetched |
| 14.2 | Glove / hairnet worn by food handler | "Is the food handler wearing gloves?" | yes/no | photo / CCTV frame | No source fetched |
| 14.3 | Plate waste | "How much of the meal is left?" | none / some / most | photo | No source fetched |
| 14.4 | Pest sighting | "Is a rodent or cockroach visible?" | yes/no | CCTV frame | No source |
| 14.5 | Kitchen surface clean | "Is the prep surface clear of debris?" | yes/no | photo | No source |

#### Domain 15: Warehousing and inventory
| # | Task | Typed question | Options | Image type | Value reason |
|---|---|---|---|---|---|
| 15.1 | Pedestrian near forklift | "Is a person visible together with the forklift?" | yes/no | photo | OSHA, as cited in snippets: about 85 forklift deaths and about 34,900 serious injuries a year [UNVERIFIED-snippet] ([OSHA PIT material](https://obis.osha.gov/dte/grant_materials/fy09/sh-18794-09/power_industrial_trucks.pdf)) |
| 15.2 | Damaged carton | "Is this cardboard box damaged?" | yes/no | photo | No source fetched |
| 15.3 | Pallet count | "How many pallets are in view?" | 0 / 1 / 2–3 / 4+ | photo | No source |
| 15.4 | Boxes on pallet | "How many boxes on this pallet?" | ranges | photo / render | No source |
| 15.5 | Aisle obstruction | "Is the aisle blocked?" | yes/no | photo | Same OSHA source |

#### Domain 16: Parcel, freight and container logistics
| # | Task | Typed question | Options | Image type | Value reason |
|---|---|---|---|---|---|
| 16.1 | Container defect type | "What defect is on this container?" | Dent / Rusty / Scratch / Deframe / Hole | photo | No source fetched |
| 16.2 | Container damaged | "Is this container damaged?" | yes/no | photo | No source |
| 16.3 | Parcel damaged | "Is this parcel damaged?" | yes/no | photo | No source |
| 16.4 | Container ID read | "What is the check digit / owner code?" | 4–6 options | photo | No source |
| 16.5 | Shipping-label barcode present | "Is a readable barcode visible?" | yes/no | photo | No source |

#### Domain 17: Last-mile delivery proof
| # | Task | Typed question | Options | Image type | Value reason |
|---|---|---|---|---|---|
| 17.1 | Parcel visible at door | "Is a parcel visible in the delivery photo?" | yes/no | photo | SafeWise, as reported: about 104M packages stolen in 2024 (~$15B) [UNVERIFIED-snippet] ([RetailWire](https://retailwire.com/porch-pirates-holiday-season/)) |
| 17.2 | Placement | "Where was the parcel left?" | doorstep / mailbox / lobby / locker | photo | Same source |
| 17.3 | Photo usable | "Is the proof photo sharp enough to see the parcel?" | yes/no | photo | No source |
| 17.4 | House number visible | "Is a house number visible?" | yes/no | photo | No source |
| 17.5 | Person in photo (privacy) | "Does the photo contain a person?" | yes/no | photo | No source |

#### Domain 18: Hospitality and room condition
| # | Task | Typed question | Options | Image type | Value reason |
|---|---|---|---|---|---|
| 18.1 | Room type tag for listing | "Which room is this?" | bedroom / bathroom / kitchen / livingroom / dining_room | photo | No source fetched |
| 18.2 | Amenity visible | "Is a towel visible?" (bathroom) | yes/no | photo | No source |
| 18.3 | Bed made | "Is the bed made?" | yes/no | photo | No source |
| 18.4 | Room tidy | "Is the room ready for the next guest?" | yes/no | photo | No source |
| 18.5 | Visible damage/stain | "Is there visible damage?" | yes/no | photo | No source |

#### Domain 19: Real estate (exteriors, interiors, floorplans)
| # | Task | Typed question | Options | Image type | Value reason |
|---|---|---|---|---|---|
| 19.1 | Floorplan door count | "How many doors does this floorplan show?" | ranges | drawing (scan/raster) | NAR, as reported: 55% of buyers find floor plans "very useful" [UNVERIFIED-snippet] ([F8 summary of NAR](https://www.f8re.com/post/the-surprising-importance-of-floor-plans-in-the-home-search-process)) |
| 19.2 | Bedroom count from plan | "How many bedrooms?" | 1 / 2 / 3 / 4+ | drawing | Same source |
| 19.3 | Construction era of house | "When was this house built?" | pre-1940 / 1941–70 / 1971–90 / post-1990 | photo (street) | No source fetched |
| 19.4 | Architectural style | "Which style is this facade?" | 4–6 of 20 styles | photo / generated | No source |
| 19.5 | Interior room type | (same as 18.1) | | photo | |
| 19.6 | CAD symbol count | "How many doors/windows in this CAD sheet?" | ranges | drawing | No source |

#### Domain 20: Facilities, cleaning and waste
| # | Task | Typed question | Options | Image type | Value reason |
|---|---|---|---|---|---|
| 20.1 | Recycling stream | "Which bin does this item go in?" | cardboard / glass / metal / paper / plastic / trash | photo | Recycling Partnership: California cities see about 20% average inbound contamination [UNVERIFIED-snippet] ([Resource Recycling](https://dev.resource-recycling.com/recycling/2020/05/05/west-coast-study-recycling-zeal-doesnt-erase-contamination/)) |
| 20.2 | Illegal dumping in aerial tile | "Is dumped waste visible in this tile?" | yes/no | aerial | No source fetched |
| 20.3 | Litter material | "What is the main litter item?" | bottle / can / cigarette / plastic bag / cup | photo | No source |
| 20.4 | Bin overflowing | "Is the bin overflowing?" | yes/no | photo | No source |
| 20.5 | Wet floor / spill | "Is there a spill on the floor?" | yes/no | photo | No source |

### A3. Slice 3 — Industry and infrastructure (D21–D30)

Each value-reason source is either a page I found in this session or is marked "No source fetched". Where the source was only seen as a search-result snippet, it is tagged [UNVERIFIED-snippet].

#### D21 Manufacturing quality (surfaces, assembly)
| id | task | typed question | options | image type | value reason (source) |
|---|---|---|---|---|---|
| D21.1 | Steel sheet defect screening | "Does this steel-sheet image show a surface defect?" | yes / no | photo (line-scan, 1600×256) | Cost of poor quality is often cited at 15–20% of sales revenue at many manufacturers (ASQ rule of thumb, quoted at [IISE "Measuring the cost of quality"](https://iise.org/details.aspx?id=22118)) [UNVERIFIED-snippet] |
| D21.2 | Steel defect class | "Which Severstal defect class is present?" | class 1 / 2 / 3 / 4 | photo | same as D21.1 |
| D21.3 | Molded/commutator part crack check | "Does this commutator surface show a crack or defect?" | yes / no | photo (grayscale) | same as D21.1. Kolektor's own end-of-line inspection is the data source [CARD] |
| D21.4 | Lumber surface grading: defect present | "Does this wood board surface show any defect (knot, crack, resin, etc.)?" | yes / no | photo (2800×1024) | Wood paper: "manual inspection rarely achieves 70% reliability" ([F1000Research 10:581](https://f1000research.com/articles/10-581/v2)) [PAPER] |
| D21.5 | Lumber defect type | "Which defect type is visible on this board?" | e.g. Live_Knot / Dead_Knot / Crack / Resin / … (2–6 chosen from the class list) | photo | same as D21.4 |
| D21.6 | Weld acceptance | "Is this weld acceptable (good weld) or not (bad weld/defect)?" | good / bad | photo | No source fetched |
| D21.7 | Assembly completeness (missing part, e.g. screw or clip) | "Is any required part missing from this assembly?" | yes / no | photo | No source fetched. No qualifying dataset (see Gaps) |

#### D22 Electronics and PCB inspection
| id | task | typed question | options | image type | value reason |
|---|---|---|---|---|---|
| D22.1 | Bare-PCB defect screening (AOI review) | "Does this bare PCB image contain a manufacturing defect?" | yes / no | scan (binarised CCD, 640×640) | DeepPCB card: images come from "a linear scan CCD" used for AOI [CARD]. No business-cost source fetched |
| D22.2 | Bare-PCB defect type | "Which defect type is present on this board?" | missing hole / mouse bite / open circuit / short / spur / spurious copper | photo (≈2.5–3k px) | No source fetched |
| D22.3 | Assembled-board defect type | "Which defect is shown: dry joint, incorrect installation, PCB damage, or short circuit?" | 4 options | photo (640×480) | No source fetched |
| D22.4 | Component presence | "Is a <component type> present on this board?" | yes / no | photo | No source fetched. No licensed dataset (see Gaps) |
| D22.5 | Solder joint quality | "Is this solder joint acceptable?" | yes / no | photo | No source fetched. Gap |

#### D23 Automotive repair and parts
| id | task | typed question | options | image type | value reason |
|---|---|---|---|---|---|
| D23.1 | Tyre condition check | "Is this tyre defective or in good condition?" | defective / good | photo | NHTSA counted 733 traffic deaths in 2016 where tyre malfunction contributed (reported in [Salon/Center for Public Integrity](https://www.salon.com/2018/11/18/federal-regulators-deflated-numbers-on-tire-related-crash-deaths_partner/)) [UNVERIFIED-snippet] |
| D23.2 | Pothole-type tyre/wheel damage triage | see D30.1 | | | UK drivers: tyres were the most common pothole repair, 4.2 M repairs ([Kwik Fit](https://www.kwik-fit.com/press/the-state-of-the-nations-roads)) [UNVERIFIED-snippet] |
| D23.3 | Vehicle make identification (parts lookup) | "Which make is this car?" | 4–6 makes | photo | No source fetched |
| D23.4 | Body damage present | "Is this vehicle damaged?" | yes / no | photo | Already covered by DrBimmer (used). CarDD rejected. No new candidate (see Gaps) |
| D23.5 | Dashboard warning light identification | "Which warning light is lit?" | 4–6 icons | photo | No source fetched. Gap, drawable |
| D23.6 | Brake-pad wear | "Is this brake pad below the wear limit?" | yes / no | photo | No source fetched. Gap |

#### D24 Aviation and aerospace maintenance
| id | task | typed question | options | image type | value reason |
|---|---|---|---|---|---|
| D24.1 | Aircraft type check (ramp/MRO paperwork vs aircraft) | "Which manufacturer built this aircraft?" or "Which family is this?" | 4–6 manufacturers/families | photo | No source fetched |
| D24.2 | Fuselage/skin corrosion or dent | "Does this skin panel show corrosion?" | yes / no | photo | No source fetched. Gap (generic corrosion data in D29.1) |
| D24.3 | Borescope blade damage | "Does this engine blade show damage?" | yes / no | video frame | No source fetched. Gap |
| D24.4 | Foreign object debris on apron/runway | "Is there foreign object debris in this image?" | yes / no | photo | No source fetched. Gap |
| D24.5 | Tyre/landing-gear wear | "Is this aircraft tyre worn to limit?" | yes / no | photo | No source fetched. Gap |

#### D25 Rail and transit
| id | task | typed question | options | image type | value reason |
|---|---|---|---|---|---|
| D25.1 | Rail-head defect type | "Which rail-head defect is visible?" | crack / spalling / squat / corrugation / break | photo | No source fetched |
| D25.2 | Track obstruction | "Is there an object on the track?" | yes / no | video frame | No source fetched. Gap |
| D25.3 | Missing fastener/clip | "Is any rail fastener missing?" | yes / no | photo | No source fetched. Gap |
| D25.4 | Overhead catenary fault | "Is the catenary dropper/insulator damaged?" | yes / no | photo | No source fetched. Gap |
| D25.5 | Platform/rolling-stock graffiti | "Does this car exterior have graffiti?" | yes / no | photo | No source fetched. dacl10k has a `Graffiti` class on bridges (D30.4) |

#### D26 Construction progress and sites
| id | task | typed question | options | image type | value reason |
|---|---|---|---|---|---|
| D26.1 | Site equipment type | "Which machine is shown: excavator, dump truck, or wheel loader?" | 3 options | photo | No source fetched |
| D26.2 | Concrete surface crack | "Does this concrete surface show a crack?" | yes / no | photo | see D30 (FHWA NBIS) |
| D26.3 | Rebar installed and visible | "Is rebar of type <straight-N> present?" | yes / no | photo | No source fetched |
| D26.4 | Construction stage | "Which stage: foundation / frame / enclosure / finishing?" | 4 | photo | No source fetched. Gap |
| D26.5 | PPE compliance | (covered by slice 4 / D34; Voxel51 hard-hat already used) | | | |

#### D27 Utilities meters and gauges
| id | task | typed question | options | image type | value reason |
|---|---|---|---|---|---|
| D27.1 | Analog gauge reading (bucketed) | "Which range is the needle in?" or "What does the gauge read?" | 4–6 numeric options | photo/render | No source fetched |
| D27.2 | Water meter reading | "Which value does this meter show?" | 4 numeric options (1 true + 3 distractors) | photo | No source fetched |
| D27.3 | Electricity meter reading | "Which reading is shown?" | 4 numeric options | photo | No source fetched |
| D27.4 | Meter type | "Is this a mechanical or LCD meter?" | mechanical / LCD | photo | No source fetched. Only candidate GATED |
| D27.5 | Gauge out of range | "Is the needle above X?" | yes / no | render | No source fetched. Derived from D27.1 |

#### D28 Energy assets (solar, wind, power lines)
| id | task | typed question | options | image type | value reason |
|---|---|---|---|---|---|
| D28.1 | PV cell EL defect check | "Is this solar cell defective?" | yes / no | EL image (300×300) | Cracks are "among the defects that can lead to the highest power losses" ([Sensors 2024, PMC10933771](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10933771/)) [UNVERIFIED-snippet] |
| D28.2 | Broken insulator on line | "Is there a broken insulator in this image?" | yes / no | aerial (drone) | Weather-related outages are cited at $28 bn/yr in the US ([Oxmaint](https://oxmaint.com/industries/power-plant/power-line-inspection-robots-and-drones-transmission-and-distribution-maintenance-cmms), a vendor page) [UNVERIFIED-snippet] |
| D28.3 | Broken cable/conductor | "Is there a broken cable in this image?" | yes / no | aerial | same as D28.2 |
| D28.4 | Solar panel soiling/damage | "What condition: clean / dusty / bird-drop / snow / electrical damage / physical damage?" | 6 | photo | No source fetched |
| D28.5 | Wind turbine blade damage | "Does this blade show damage?" | yes / no | drone photo | No source fetched. Gap |
| D28.6 | Thermal hotspot | "Does this thermal image show a hotspot?" | yes / no | thermal aerial | No source fetched. Candidate unlabeled |

#### D29 Oil, gas and mining inspection
| id | task | typed question | options | image type | value reason |
|---|---|---|---|---|---|
| D29.1 | Corrosion on steel asset | "Which is shown: corrosion, crack, or slippage?" or "Is corrosion present?" | 3 / yes-no | photo | No source fetched |
| D29.2 | Pipe/sewer CCTV defect type | "Which defect: blockage, corrosion, or crack?" | 3 | video frame | No source fetched |
| D29.3 | Gas leak plume (OGI camera) | "Is a gas plume visible?" | yes / no | IR video frame | No source fetched. Positives-only candidate |
| D29.4 | Oil spill present | "Is there an oil spill?" | yes / no | aerial/SAR | Not probed |
| D29.5 | Conveyor belt damage (mining) | "Is the belt torn?" | yes / no | photo | Gap |

#### D30 Roads, bridges and public infrastructure
| id | task | typed question | options | image type | value reason |
|---|---|---|---|---|---|
| D30.1 | Pothole present | "Is there a pothole in this road image?" | yes / no | photo (vehicle/drone) | UK pothole repair bill £1.25 bn/yr ([Yorkshire Evening Post / RAC-Kwik Fit](https://www.yorkshireeveningpost.co.uk/lifestyle/cars/pothole-damage-cost-uk-drivers-ps125bn-in-vehicle-repairs-last-year-2524106)) [UNVERIFIED-snippet] |
| D30.2 | Road damage type | "Which damage type: longitudinal crack, transverse crack, alligator crack, pothole?" | 4 | photo | same as D30.1 |
| D30.3 | Pothole severity | "How severe is the pothole: none / low / medium / severe?" | 4 | photo | same as D30.1 |
| D30.4 | Bridge defect type | "Which damage is shown: spalling / rust / crack / efflorescence / exposed rebar / …?" | 2–6 | photo | US bridges must be inspected at least every 24 months under NBIS ([FHWA NBIS Q&A](https://www.fhwa.dot.gov/bridge/nbis2022/qanda/07.cfm)) [UNVERIFIED-snippet] |
| D30.5 | Concrete crack present | "Does this concrete surface show a crack?" | yes / no | photo | same as D30.4 |
| D30.6 | Exposed rebar present (urgent repair) | "Is exposed reinforcement visible?" | yes / no | photo | same as D30.4 |

### A4. Slice 4 — Living systems and safety (D31–D40)

#### D31 Agriculture and crops
| id | task | typed question | options | image type | value reason (source) |
|---|---|---|---|---|---|
| 31.1 | Pest / disease present on crop plant | "Is this crop plant healthy?" | yes / no | photo | FAO: up to 40% of global crop production is lost to pests each year; plant diseases cost over $220 bn ([FAO via DownToEarth](https://www.downtoearth.org.in/news/agriculture/at-least-40-global-crops-lost-to-pests-every-year-fao-77252)) |
| 31.2 | Seedling is crop or weed (spot-spraying) | "Which plant is this seedling?" | 4–6 of the 12 Aarhus species (e.g. maize, sugar beet, common wheat, charlock, fat hen, black-grass) | photo (top-down) | same FAO pest-loss figure; weeds are among the "pests" in IPPC usage [INFERRED] |
| 31.3 | Oil-palm bunch ripeness grading at the mill | "What ripeness grade is this fresh fruit bunch?" | unripe / ripe / overripe / empty / damaged | photo | Unripe fruit lowers oil extraction rate by 0.13% or more; a 0.13% OER drop is about RM 340 m to Malaysia ([PMC review](https://pmc.ncbi.nlm.nih.gov/articles/PMC7038324)) |
| 31.4 | Weed count in a maize field image | "How many weeds are visible?" | 0 / 1–2 / 3–5 / 6+ | photo | FAO pest-loss source above |
| 31.5 | Banana/mango ripeness | "Is this fruit ripe?" | yes / no (+ banana / mango) | photo | No dedicated source found |
| 31.6 | Insect pest species on trap/leaf | "Which pest is this?" | 4–6 species | photo | FAO source above (invasive insects at least $70 bn) |
| 31.7 | Crop field vs other land cover from satellite | "Is this tile annual cropland?" | yes / no | aerial | No source fetched |

#### D32 Livestock and fisheries
| id | task | typed question | options | image type | value reason (source) |
|---|---|---|---|---|---|
| 32.1 | Herd composition from drone | "Are there goats in this image?" / "Which animal is most numerous?" | yes/no ; goat / sheep / none | aerial (drone) | No source found (flock counting for subsidy and insurance claims, [INFERRED]) |
| 32.2 | Flock headcount from drone | "How many sheep are visible?" | 0–5 / 6–10 / 11–20 / 21+ | aerial | No source found |
| 32.3 | Pig posture (welfare: lying vs standing) | "How many pigs in this pen image are standing?" / "Is any pig sitting?" | count bins ; yes/no | video frame (barn CCTV) | No source fetched |
| 32.4 | Fish species ID at landing or audit | "Which family is this fish?" | 4–6 families | photo (specimen) | No source fetched |
| 32.5 | Aquatic animal type in tank/aquarium | "Which animal is shown?" | fish / jellyfish / penguin / shark / stingray / starfish | photo | No source |
| 32.6 | Cattle present / count in pasture | "How many cattle?" | bins | aerial/photo | No source. **Gap** (no verified dataset) |

#### D33 Forestry and environment
| id | task | typed question | options | image type | value reason (source) |
|---|---|---|---|---|---|
| 33.1 | Camera-trap species triage | "Which animal is in this camera-trap image?" | fox / bird / rodent / skunk / other | photo (trail camera, incl. IR night) | About 70% of camera-trap images are empty; manual review takes up to 5 s per image ([MegaDetector docs](https://megadetector.readthedocs.io/en/latest/getting-started.html)) |
| 33.2 | Camera-trap empty frame filter | "Is there an animal in this image?" | yes / no | photo | same source. **Gap**: the HF subset dropped the empty frames |
| 33.3 | Tree species in forest inventory | "Which tree species is this?" | European beech / silver fir / Norway spruce / sessile oak | photo | No source fetched |
| 33.4 | Wildfire smoke on horizon | "Is there wildfire smoke in this view?" | yes / no | photo (tower camera) | NFPA: in 2018 the US had 1.3 m fires and about $25 bn property loss ([NFPA via FireEngineering](https://www.fireengineering.com/fire-safety/nfpa-fire-loss-report/)) |
| 33.5 | Land-cover class of satellite tile | "What is the main land cover?" | forest / annual crop / pasture / river / residential / industrial | aerial | No source. EuroSAT is 64 px (trap) |
| 33.6 | Flooded area in aerial image | "Is any road flooded?" | yes / no | aerial | No source. FloodNet is a 12.8 GB single archive |

#### D34 Workplace safety and PPE
| id | task | typed question | options | image type | value reason (source) |
|---|---|---|---|---|---|
| 34.1 | Hi-vis vest missing | "Is any worker without a safety vest?" | yes / no | photo / CCTV frame | OSHA's top-10 cited standards include eye/face PPE (1926.102, 1,665 violations) and respiratory protection ([Safety+Health / OSHA Top 10](https://safetyandhealthmagazine.com/articles/24670-fall-protection-again-leads-oshas-annual-top-10-list-of-most-frequently-cited-standards)) |
| 34.2 | Hard hat missing (non-Voxel51 source) | "Is any worker without a helmet?" | yes / no | photo | same OSHA Top-10 source |
| 34.3 | Pedestrian near forklift | "Is a person present together with the forklift?" | yes / no | photo | OSHA: about 85 forklift fatalities and 34,900 serious injuries a year; powered industrial trucks are #8 in OSHA's Top 10 ([NIOSH/CDC](https://Cdc.gov/niosh/docs/2001-109/pdfs/2001-109.pdf); [OSHA Top 10](https://safetyandhealthmagazine.com/articles/24670-fall-protection-again-leads-oshas-annual-top-10-list-of-most-frequently-cited-standards)) |
| 34.4 | Construction-site PPE audit (mask, gloves, vest, hat) | "Which PPE item is missing on someone?" | hardhat / mask / safety vest / none | photo | OSHA Top-10 source |
| 34.5 | Seat belt fastened (fleet driver) | "Is the occupant wearing a seat belt?" | yes / no | photo (in-cab) | NHTSA: seat belts saved about 14,955 lives in 2017 ([NHTSA](https://crashstats.nhtsa.dot.gov/Api/Public/Publication/812683)) |
| 34.6 | Person down / fall incident | "Is a person lying on the floor?" | yes / no | CCTV frame | Falls lead OSHA's most-cited list for 15 years ([OSHA Top 10](https://safetyandhealthmagazine.com/articles/24670-fall-protection-again-leads-oshas-annual-top-10-list-of-most-frequently-cited-standards)) |
| 34.7 | Smoking in no-smoking zone | "Is someone smoking?" | yes / no | photo | No source |

#### D35 Fire, smoke and security video
| id | task | typed question | options | image type | value reason (source) |
|---|---|---|---|---|---|
| 35.1 | Fire or smoke in frame | "Is there fire or smoke in this image?" | yes / no | CCTV frame / photo | NFPA fire-loss report ([FireEngineering](https://www.fireengineering.com/fire-safety/nfpa-fire-loss-report/)) |
| 35.2 | Fire vs smoke only (alarm type) | "What is visible?" | fire only / smoke only / both / neither | photo | same |
| 35.3 | Weapon visible (CCTV) | "Is a weapon visible?" | yes / no | CCTV frame / photo | No regulator source fetched |
| 35.4 | Weapon type | "Which weapon is visible?" | gun / knife / none | photo | No source |
| 35.5 | Person lying in monitored space | see 34.6 | yes / no | CCTV | see 34.6 |
| 35.6 | Intrusion: person in restricted zone at night | "Is a person present?" | yes / no | CCTV | No source. **Gap** |

#### D36 Traffic, parking and smart city
| id | task | typed question | options | image type | value reason (source) |
|---|---|---|---|---|---|
| 36.1 | Parking occupancy | "Is this parking lot more than half full?" / "How many vacant spaces are labelled?" | yes/no ; bins | CCTV frame | INRIX: US drivers spend 17 h/yr searching for parking, $72.7 bn total ([INRIX](https://inrix.com/press-releases/parking-pain-us/)) |
| 36.2 | Motorcyclist helmet compliance | "Is every rider wearing a helmet?" | yes / no | photo / CCTV | No source fetched |
| 36.3 | Vehicle class count (tolling, planning) | "Which vehicle class is most common?" | car / bus / truck | CCTV frame | No source |
| 36.4 | Traffic light state | "What colour is the light facing the camera?" | red / yellow / green | dashcam frame | No source |
| 36.5 | Traffic sign identification | "Which sign is this?" | stop / yield / no entry / speed limit … | photo | No source. **Gap** (GTSRB is tiny) |
| 36.6 | Road-user count from fisheye pole camera | "How many pedestrians are visible?" | bins | CCTV fisheye | No source |

#### D37 Healthcare administration (documents only, no diagnosis)
| id | task | typed question | options | image type | value reason (source) |
|---|---|---|---|---|---|
| 37.1 | Route incoming medical page by document type | "What kind of document is this page?" | contact info / observation / vaccination history / report / survey / notes | scan / photo of page | No source fetched |
| 37.2 | Capture-quality triage | "How was this page captured?" | clean digital / photocopy / phone photo | scan / photo | No source |
| 37.3 | Page clipped / incomplete | "Is part of the page cut off?" | yes / no | photo | No source |
| 37.4 | Bill vs discharge summary | "Is this a hospital bill?" | yes / no | scan | No source |
| 37.5 | Insurance card / wristband field read | "Does the wristband show a date of birth?" | yes / no | photo | **Gap**. A generator is realistic |

#### D38 Pharmacy
| id | task | typed question | options | image type | value reason (source) |
|---|---|---|---|---|---|
| 38.1 | Package vs package-insert sorting; import vs domestic licence | "Is this an outer carton or a leaflet?" ; "Is this an imported drug (licence prefix 輸)?" | carton / leaflet ; yes/no | scan (rendered PDF) | Similar labels/packaging is the most-reported factor in medication errors (16.6%); labelling, packaging and nomenclature play a role in about half of FDA MedWatch error reports ([ECRI/ISMP](https://home.ecri.org/blogs/ismp-alerts-and-articles-library/merp-annual-review-exposes-how-manufacturer-labeling-quality-issues-impact-medication-safety)) |
| 38.2 | Pill identity on tray | "Which product is this tablet?" | Cipro 500 / Ibuphil 600 / Ibuphil Cold / Xyzall 5 mg | photo | same ECRI/ISMP source |
| 38.3 | Count of medication boxes (dispensing check) | "How many medicine boxes are in the photo?" | 1 / 2 / 3 / 4+ | photo | same |
| 38.4 | Pill reference match | "Which shape/colour is this pill?" | — | photo | **Gap**: labels only via the NDC filename |
| 38.5 | Blister pack completeness | "Is any blister cavity empty?" | yes / no | photo | **Gap** |

#### D39 Veterinary and pets
| id | task | typed question | options | image type | value reason (source) |
|---|---|---|---|---|---|
| 39.1 | Cat or dog (intake, listings) | "Is this a cat or a dog?" | cat / dog | photo | No source fetched |
| 39.2 | Breed for listing/insurance quote | "Which breed is this?" | 4–6 of 37 Oxford breeds | photo | No source fetched |
| 39.3 | Dog breed, fine-grained | "Which breed?" | 4–6 of 120 | photo | No source |
| 39.4 | Livestock welfare posture | see 32.3 | | | |
| 39.5 | Animal count in photo | "How many animals?" | bins | photo | **Gap** |

#### D40 Laboratory and scientific (no diagnosis)
| id | task | typed question | options | image type | value reason (source) |
|---|---|---|---|---|---|
| 40.1 | Harmful-algal-bloom taxon in water sample | "Is this phytoplankton cell Alexandrium?" / pick taxon | yes/no ; 4–6 taxa | microscopy | HABs cost many millions of dollars a year (e.g. $10.3 m Texas oyster loss in 2011) ([NOAA Fisheries](https://www.fisheries.noaa.gov/west-coast/science-data/hitting-us-where-it-hurts-untold-story-harmful-algal-blooms)) |
| 40.2 | Specimen tray count (biodiversity lab) | "How many beetles are in this tray image?" | 1–5 / 6–15 / 16–40 / 41+ | photo (lab) | No source fetched |
| 40.3 | Specimen genus/species (single specimen) | "Which genus is this beetle?" | 4–6 genera | photo (lab) | No source |
| 40.4 | Colony count on agar plate | "How many colonies?" | bins | photo | No source. GATED candidate |
| 40.5 | Pollen grain taxon | pick | | microscopy render | No source. SKIP candidate |

### A5. Slice 5 — Digital and knowledge work (D41–D50)

#### D41: IT support and software screenshots
| id | task | typed question | options | image type | value reason (source) |
|---|---|---|---|---|---|
| D41.1 | Identify the application in a ticket screenshot | "Which application is shown in this screenshot?" | 4–6 app names (e.g. Excel, Word, PowerPoint, VS Code, PyCharm, MATLAB) | screenshot | Routing a ticket to the right resolver group is the main lever on cost. Tier-1 tickets cost about $6 and Tier-3 escalations can exceed $35 per ticket; average resolution is 82 h (vendor blog, secondary) — [unthread](https://unthread.io/blog/support-ticket-resolution-statistics/) |
| D41.2 | Identify the operating system | "Which operating system is this screenshot from?" | Windows / macOS / Linux | screenshot | Same routing value. OS decides the troubleshooting script — same source as D41.1 |
| D41.3 | Software category for queue routing | "What kind of software is open?" | Development / Creative / CAD / Scientific / Office / Operating system | screenshot | Same as D41.1 |
| D41.4 | Error dialog present | "Does the screenshot show an error or warning dialog?" | yes / no | screenshot | Same as D41.1. No dataset found (see Gaps) |
| D41.5 | Dark mode / theme | "Is the application in dark mode?" | yes / no | screenshot | No business source found. Low value, kept as a cheap generator task |

#### D42: Web and mobile UI quality
| id | task | typed question | options | image type | value reason (source) |
|---|---|---|---|---|---|
| D42.1 | Screen type classification for QA coverage | "What type of screen is this?" | e.g. login / list / form / gallery / settings / tutorial | screenshot (mobile) | Apple Guideline 2.1 (app completeness) rejects incomplete or placeholder screens. Reviewers report it as the most common rejection group — [Apple App Review Guidelines PDF](https://developer.apple.com/support/downloads/terms/app-review-guidelines/App-Review-Guidelines-English-UK.pdf); [RevenueCat summary](https://revenuecat.com/blog/growth/the-ultimate-guide-to-app-store-rejections/) |
| D42.2 | Login / sign-up screen detection | "Is this a login or sign-up screen?" | yes / no | screenshot | Same as D42.1. Login flows must work for review, and a demo account is required |
| D42.3 | Website vertical | "Which kind of website is this?" | Travel / Shopping / Entertainment | screenshot (web, long) | Ad and compliance routing. No direct source found |
| D42.4 | Visual defect (overlap, truncation, occlusion) | "Does any text or component overlap or get cut off?" | yes / no | screenshot | 94.8% of the top 1M home pages have detectable WCAG failures — [WebAIM Million 2025](https://webaim.org/projects/million/2025) |
| D42.5 | Placeholder content left in UI | "Is placeholder text (e.g. 'Lorem ipsum') visible?" | yes / no | screenshot | Apple rejects apps with placeholder content (Guideline 2.1) — [Apple PDF](https://developer.apple.com/support/downloads/terms/app-review-guidelines/App-Review-Guidelines-English-UK.pdf) |
| D42.6 | Low-contrast text | "Is there text with insufficient contrast against its background?" | yes / no | screenshot | 79.1% of home pages have low-contrast text — [WebAIM Million 2025](https://webaim.org/projects/million/2025) |

#### D43: Dashboards, charts and BI
| id | task | typed question | options | image type | value reason (source) |
|---|---|---|---|---|---|
| D43.1 | Chart type | "What type of chart is this?" | bar / line / pie / area / scatter / box (subset of 9) | rendered chart | Poor data quality costs organisations about $12.9M/yr (Gartner, via secondary page) — [Verato citing Gartner](https://verato.com/resources/gartner-dq) |
| D43.2 | Pairwise comparison check | "At <x>, is series A higher than series B?" | yes / no | rendered chart | Same as D43.1. Misread dashboards drive wrong decisions |
| D43.3 | Value-claim verification | "Does the chart show <series> at <x> = <value>?" | yes / no | rendered chart | Same as D43.1. This is the "does the slide match the number?" check |
| D43.4 | Do lines cross | "Do any lines intersect?" | yes / no | real chart (arXiv figure) | Same as D43.1 |
| D43.5 | Panel count | "How many subplots does this figure have?" | 1 / 2 / 3 / 4 / 5+ | real chart | Same as D43.1 |
| D43.6 | Max/min series | "Which series is the maximum?" | 2–6 legend names | rendered chart | Same as D43.1 |

#### D44: Maps, satellite and drone imagery
| id | task | typed question | options | image type | value reason (source) |
|---|---|---|---|---|---|
| D44.1 | Post-flood scene triage | "Is this area flooded?" | yes / no | aerial (UAV) | FEMA uses aerial imagery for damage assessment and relief-funding decisions. Nearmap captured 57,000 sq mi of disaster areas in 2024 — [DroneLife](https://dronelife.com/2026/02/11/nearmap-and-new-light-deploy-fema-disaster-response-system/); [NOAA](https://oceanservice.noaa.gov/news/jul25/ngs-texas-flooding.html) |
| D44.2 | Road passability | "Is the entire road flooded?" | yes / no | aerial (UAV) | Same as D44.1 |
| D44.3 | Building count bucket | "How many buildings are visible?" | 0 / 1–3 / 4–6 / 7+ | aerial (UAV) | Same as D44.1 (exposure counting) |
| D44.4 | Land-use type | "What land use does this tile show?" | 4–6 of airport / port / parking / residential / industrial / farmland … | satellite | No source fetched. Common in insurance and site selection [UNVERIFIED] |
| D44.5 | Vehicle presence in drone frame | "Is there a truck in this image?" | yes / no | aerial (drone, oblique) | No source fetched |
| D44.6 | Rooftop solar present | "Does this roof have solar panels?" | yes / no | aerial | No source fetched. Gap |

#### D45: Education (worksheets, handwriting, diagrams)
| id | task | typed question | options | image type | value reason (source) |
|---|---|---|---|---|---|
| D45.1 | Auto-mark multiple-choice worksheet item | "Which option correctly answers the question shown?" | 2–5 given choices | drawing / worksheet image | English teachers spend 9.4–9.7 h/week marking (DfE survey of 44,000 teachers, reported by SecEd) — [SecEd](https://www.sec-ed.co.uk/content/news/teachers-spend-nine-hours-a-week-marking-despite-lack-of-evidence-that-it-works) |
| D45.2 | Diagram comprehension item | "Which option answers the diagram question?" | 4 choices | textbook diagram | Same as D45.1 |
| D45.3 | Worksheet subject routing | "What subject is this worksheet item?" | natural science / language science / social science | worksheet image | Same as D45.1 |
| D45.4 | Yes/no worksheet item | "Answer this yes/no item" | yes / no | worksheet image | Same as D45.1 |
| D45.5 | Handwritten answer correct | "Does the handwritten answer equal <value>?" | yes / no | handwriting scan | Same as D45.1. No dataset (Gap) |

#### D46: Publishing, media and archives
| id | task | typed question | options | image type | value reason (source) |
|---|---|---|---|---|---|
| D46.1 | Document category triage | "What kind of document is this page from?" | financial report / scientific article / law or regulation / government tender / manual / patent | scan/render | NARA aims to digitise 500M pages by FY2026 and holds more than 13 billion analog pages — [FedScoop](https://fedscoop.com/nara-targets-digitization-of-500-million-pages-by-2026-in-draft-strategic-plan/); [archives.gov](https://www.archives.gov/digitization) |
| D46.2 | Table present (routes to table extraction) | "Does this page contain a table?" | yes / no | scan/render | Same as D46.1 |
| D46.3 | Newspaper page content (photograph, map, advert) | "Does this newspaper page contain a photograph?" (or map / advertisement) | yes / no | historical scan | Same as D46.1 |
| D46.4 | Typeface group of early printed page | "Which typeface group is used on this page?" | antiqua / italic / textura / fraktur / schwabacher / rotunda … | photo of book page | Same as D46.1 (cataloguing) |
| D46.5 | Illustrated advert | "Does this advert contain an illustration?" | yes / no | newspaper crop | Same as D46.1 |
| D46.6 | Manuscript dating | "In which century was this manuscript written?" | 3–6 centuries | photo of manuscript | Same as D46.1 |
| D46.7 | Page orientation | "Is this page rotated?" | 0° / 90° / 180° / 270° | scan | Same as D46.1. Generator task |

#### D47: Marketing and ad compliance
| id | task | typed question | options | image type | value reason (source) |
|---|---|---|---|---|---|
| D47.1 | Restricted-category ad | "Is this an ad for alcohol, gambling or tobacco/smoking?" | yes / no | ad image | Google restricts alcohol and gambling ads by certification and geography. Violations can suspend accounts — [Google Ads policy](https://support.google.com/adspolicy/answer/2684542); [summary](https://stubgroup.com/glossary/restricted-content-policy/) |
| D47.2 | Ad topic routing | "What is this ad selling?" | e.g. clothing / cars / beauty / soda / restaurant / electronics | ad image | Same as D47.1 |
| D47.3 | Image contains advertising | "Does this image contain advertising?" | yes / no | photo | Same as D47.1 |
| D47.4 | Sponsored-content disclosure visible | "Is an '#ad' / 'Sponsored' disclosure visible?" | yes / no | social post screenshot | FTC Endorsement Guides: disclosures must be "clear and conspicuous" and visual when the endorsement is visual (law-firm summary) — [Quarles](https://quarles.com/newsroom/publications/deciphering-the-ftcs-updated-guidance-for-advertisers) |
| D47.5 | Billboard present (OOH audit) | "Is there a billboard in this photo?" | yes / no | photo | No source fetched |

#### D48: Fashion and beauty
| id | task | typed question | options | image type | value reason (source) |
|---|---|---|---|---|---|
| D48.1 | Attribute tagging: dress | "Is the person wearing a dress?" | yes / no | photo | Fashion return rates of 20–40%+ are driven by inaccurate product data (vendor blog) — [Bluestone PIM](https://www.bluestonepim.com/blog/how-fashion-retailers-reduce-returns-with-pim) |
| D48.2 | Main garment category | "What is the main garment in this photo?" | dress / pants / skirt / jacket / shirt / coat | photo | Same as D48.1 |
| D48.3 | Accessory present | "Is there a bag or wallet in the image?" | yes / no | photo | Same as D48.1 |
| D48.4 | Catalogue category | "Which product category is this?" | Apparel / Footwear / Accessories / Personal Care | product photo | Same as D48.1 |
| D48.5 | Cosmetics present | "Is there lipstick in the image?" | yes / no | photo | Same as D48.1 |

#### D49: Customer service (photos of faults, error screens)
| id | task | typed question | options | image type | value reason (source) |
|---|---|---|---|---|---|
| D49.1 | Screenshot vs camera photo intake triage | "Is this image a screenshot?" | yes / no | mixed | Visual support cuts truck rolls by 15–47% (vendor) — [Grypp](https://grypp.io/visual-support-reduces-truck-rolls/) |
| D49.2 | Which device is in the photo | "Which device is shown?" | mobile phone / laptop / computer monitor | photo | Same as D49.1 |
| D49.3 | Photo usable for diagnosis | "Is this photo sharp enough to read?" | yes / no | photo | Same as D49.1. Generator task |
| D49.4 | Cracked screen | "Is the device screen cracked?" | yes / no | photo | Same as D49.1. Gap |
| D49.5 | Error message on device screen | "Is an error message displayed?" | yes / no | photo or screenshot | Same as D49.1. Gap |

#### D50: Content moderation and brand safety
| id | task | typed question | options | image type | value reason (source) |
|---|---|---|---|---|---|
| D50.1 | Weapon present | "Does the image contain a weapon?" | yes / no | photo | No primary brand-safety source fetched (a GARM search returned nothing relevant) |
| D50.2 | Alcohol present | "Does the image show an alcoholic beverage?" | yes / no | photo | Google restricted-content policy — [Google Ads](https://support.google.com/adspolicy/answer/2684542) |
| D50.3 | Brand/logo visible | "Is a brand logo visible?" | yes / no | photo | Counterfeit trade is USD 467bn (2.3% of world imports); clothing, footwear and leather make up 62% of seizures — [OECD/EUIPO 2025](https://www.oecd.org/en/about/news/press-releases/2025/05/global-trade-in-fake-goods-reached-USD-467-billion-posing-risks-to-consumer-safety-and-compromising-intellectual-property.html) |
| D50.4 | Logo's industry | "Which industry does this logo's brand belong to?" | Food / Clothes / Necessities / Electronic / Transportation / Leisure | photo/crop | Same as D50.3 |
| D50.5 | Visible watermark (rights check) | "Does the image have a visible watermark?" | yes / no | photo | No source fetched |
| D50.6 | Counterfeit product | "Is this product counterfeit?" | yes / no | photo | OECD/EUIPO as D50.3. No open data (Gap) |


## Appendix B. Qualification cards

### B1. USE candidates: full cards (fields 1–13, pasted rows kept)

These are the slice cards for every candidate rated USE, after de-duplication. Field 13 (evidence tags) is inline on every claim. Cards from slices 2 and 4 end with a verdict line, numbered 13 in slice 2. A *Merge note* follows each card that absorbed facts from a duplicate card. The pasted rows are exactly as fetched by the slice researchers. Appendix-level re-check results are in the main re-check table.


#### D1.1 — candidate 1: jaganadhg/cheque-synthetic-images (IDRBT synthetic cheques) — **USE**  _(slice 1)_
1. **Landing:** https://huggingface.co/datasets/jaganadhg/cheque-synthetic-images. File listing: https://huggingface.co/datasets/jaganadhg/cheque-synthetic-images/tree/main/data. Repo id `jaganadhg/cheque-synthetic-images` [CARD].
2. **Licence:** card YAML `license: apache-2.0` [CARD] (https://huggingface.co/datasets/jaganadhg/cheque-synthetic-images/raw/main/README.md). The card does not forbid research or testing. It notes the source "IDRBT Cheque Image Dataset… original TIFF images are **not** distributed" [CARD]. The IDRBT source terms were not checked [UNVERIFIED].
3. **Access:** open (API `gated: False`) [CARD].
4. **Size:** 466.1 MB total. Smallest unit: `data/validation-00000-of-00001.parquet` 76.11 MB, and test 95.25 MB [CARD]. Both exceed 50 MB, so sample through `/rows`.
5. **Sample-first proof:** `https://datasets-server.huggingface.co/first-rows?dataset=jaganadhg/cheque-synthetic-images&config=default&split=train` [ROW]
   - `{"image_id":"axis_syn_0086","bank":"axis","image_width":2365,"image_height":1065,"date":{"xmin":1694,"ymin":89,"xmax":2346,"ymax":229},"amount":{"xmin":1672,"ymin":425,"xmax":2308,"ymax":548},"sign":{"xmin":1803,"ymin":617,"xmax":2294,"ymax":927},...}`
   - `{"image_id":"axis_syn_0035","bank":"axis","image_width":2365,"image_height":1065,"amount":{"xmin":1677,"ymin":375,"xmax":2315,"ymax":525},"sign":{"xmin":2001,"ymin":660,"xmax":2303,"ymax":882},...}`
   - `{"image_id":"syndicate_syn_0004","bank":"syndicate","image_width":2365,"image_height":1100,"ifsc":{"xmin":781,"ymin":134,"xmax":1100,"ymax":215},...}`
6. **Schema:** `image_id` str, `filename` str, `bank` str (template bank), `image_width/height` int, `image`, and six boxes `date`, `amount`, `ifsc`, `acno`, `sign`, `name`, each `{xmin,ymin,xmax,ymax}` in absolute px [CARD][ROW]. Field text values are absent.
7. **Label origin:** generator for `bank`; carried-over human boxes for fields. Card: "For each of the four bank types… one blank canvas template… cropped patches are pasted onto the canvas template… The bounding-box annotations are carried over unchanged from the original"; YAML `annotations_creators: derived` [CARD].
8. **Answer rule:** answer = `bank` (axis→Axis, canara→Canara, icici→ICICI, syndicate→Syndicate).
9. **Classes and balance:** test split: axis 8, canara 8, icici 6, syndicate 8 (`/statistics`) [ROW]. Card totals: synthetic Axis 79, Canara 91, ICICI 63, Syndicate 62 (295 in all) [CARD].
10. **Per-image fit:** exactly one bank per image [CARD].
11. **Risks:** field patches come from real cheques, so real names, account numbers and signatures may appear [CARD][INFERRED]. Images are large (2365×~1065, good) [ROW]. Only 4 templates, so the bank may be readable from the printed logo alone (easy) [INFERRED]. Overlap with model training data is low (2025-era repo) [INFERRED].
12. **Question templates:** (a) "Which bank's cheque is this? Axis / Canara / ICICI / Syndicate". (b) "Is the amount box in the right half of the cheque? yes/no" (from `amount.xmin > width/2`). (c) "Which field is nearest the bottom-right corner? signature / amount / date / account number".
13. Tags are inline above.


#### D2.1 — candidate 1: jsdnrs/ICDAR2019-SROIE — **USE**  _(slice 1)_
1. **Landing:** https://huggingface.co/datasets/jsdnrs/ICDAR2019-SROIE. Owner: https://rrc.cvc.uab.es/?ch=13. GitHub: https://github.com/jsdnrs/ICDAR2019-SROIE. Listing: /tree/main/data [CARD].
2. **Licence:** "The original dataset is licensed under the CC-BY-4.0 as noted on the ICDAR's Robust Reading Competition website… redistributed annotations and metadata remain under the CC-BY-4.0" [CARD] (https://huggingface.co/datasets/jsdnrs/ICDAR2019-SROIE/raw/main/README.md). No research restriction is stated.
3. **Access:** open [CARD].
4. **Size:** 509.8 MB. Smallest unit: `data/test-00000-of-00001.parquet` 191.05 MB, and train 318.62 MB [CARD]. Sample through `/rows`.
5. **Proof:** `https://datasets-server.huggingface.co/first-rows?dataset=jsdnrs/ICDAR2019-SROIE&config=default&split=train` [ROW]
   - `{"key":"X00016469612","image_size":{"width":463,"height":1013},"entities":{"company":"BOOK TA .K (TAMAN DAYA) SDN BHD","date":"25/12/2018","address":"NO.53 55,57 & 59, JALAN SAGU 18, ...","total":"9.00"},"words":["TAN WOON YANN","BOOK TA .K(TAMAN DAYA) SDN BND",...]}`
   - `{"key":"X00016469619","image_size":{"width":439,"height":1004},"entities":{"company":"INDAH GIFT & HOME DECO","date":"19/10/2018","total":"60.30"},...}`
   - `{"key":"X00016469620","image_size":{"width":459,"height":949},"entities":{"company":"MR D.I.Y. (JOHOR) SDN BHD","date":"12-01-19","total":"33.90"},"words":[...,"-INVOICE-",...]}`
6. **Schema:** `key` str; `image_size {width,height}`; `entities {company,date,address,total}` str (key fields); `words` list[str] (line transcripts); `bboxes` list[[x0,y0,x1,y1]] [ROW][CARD].
7. **Label origin:** human, from the ICDAR 2019 challenge. The card admits "The original publication… does not provide details about the annotation workflow" [CARD]. The `words` transcripts are human ICDAR ground truth, not OCR output [CARD]. Confidence is medium.
8. **Answer rule:** correct option = `entities.total`. Distractors = other money-format strings in `words` (regex `^\d+\.\d{2}$`) that differ from the total.
9. **Classes:** not a class task. 987 rows (`/size`) [ROW].
10. **Per-image fit:** one total per receipt [CARD].
11. **Risks:** the card says some fields "are blurred" for privacy, but it "still includes many" personal items (cashier names, e.g. "TAN WOON YANN") [CARD][ROW]. Width is about 440–460 px (low, a near-tiny trap at 1536) [ROW]. SROIE is very widely used, so training overlap is high [INFERRED].
12. **Templates:** (a) "Which amount is the final total? 4 amounts". (b) "Which date is printed? 4 dates" (`entities.date` plus shifted dates). (c) "Which company issued this receipt? 4 company names" (distractors drawn from other rows).


#### D2.2 / D2.3 — candidate 1: albertobarnabo/synthetic-receipts-ocr — **USE**  _(slice 1)_
1. **Landing:** https://huggingface.co/datasets/albertobarnabo/synthetic-receipts-ocr. Listing: /tree/main/data (17 train shards plus eval). The generator ships in `generator/` [CARD].
2. **Licence:** `license: apache-2.0` [CARD] (raw README). No research restriction.
3. **Access:** open.
4. **Size:** 4,084.7 MB. Shards about 227–229 MB each [CARD]. Sample through `/rows`.
5. **Proof:** `https://datasets-server.huggingface.co/rows?dataset=albertobarnabo/synthetic-receipts-ocr&config=default&split=eval&offset=0&length=100` [ROW]
   - `{"id":"eval-000000","locale":"UK","degradations":"perspective,lighting,jpeg65","n_items":6} fields: {"currency":"GBP","total":184.89,"payment":"MASTERCARD","tax_included":true,"loyalty":"LOYALTY PTS +85"}`
   - `{"id":"eval-000001","locale":"FR","degradations":"perspective,lighting,shadow,noise,blur,jpeg84","n_items":6} fields: {"currency":"EUR","total":62.41,"payment":"SANS CONTACT","tax_included":true}`
   - `{"id":"eval-000002","locale":"IT","degradations":"perspective,lighting,thermal_fade,noise,jpeg60","n_items":4} fields: {"currency":"EUR","total":26.75,"payment":"MASTERCARD","tax_included":true,"loyalty":null}`
6. **Schema:** `image_clean`, `image_photo` (degraded twin); `full_text`; `words` (exact boxes); `fields` (JSON string: merchant, address, phone, tax_id, date, time, receipt_no, lines[name,qty,unit_price,total,tax_rate], subtotal, taxes, total, payment, tendered, change, loyalty, currency, tax_included); `locale`; `font`; `degradations`; `n_items` [CARD][ROW].
7. **Label origin:** generator. "words… exact by construction (captured during rendering, never re-OCR'd)"; "a field is non-null if and only if its value is printed on the image"; "Every receipt is a pure function of (seed, index)" [CARD].
8. **Answer rules:** D2.2 maps `fields.payment`: {CASH, BAR, ESPECES, CONTANTI} → cash; {CONTACTLESS, SANS CONTACT, KONTAKTLOS, CARTA CONTACTLESS} → contactless; {APPLE PAY} → mobile wallet; all other card brands → card. D2.3: answer = `locale`.
9. **Classes (eval sample of 100 rows):** locale US 38, UK 19, FR 15, IT 15, DE 13. Payment: MASTERCARD 16, CASH 10, CONTACTLESS 8, VISA 7, AMEX 7, VISA DEBIT 7, CARTA CONTACTLESS 6, APPLE PAY 6, … BAR 3, ESPECES 2, CONTANTI 2. n_items ranges 1–13 [ROW]. Full counts are UNVERIFIED (`/statistics` returned 500).
10. **Per-image fit:** one payment and one locale per receipt [CARD].
11. **Risks:** synthetic data, so no personal data. Images are about 600–900 px wide [ROW] (borderline for 1536). Card limitation: "monospace thermal-style receipts only… degradations are parametric, not photographs" [CARD]. Training overlap is low [INFERRED].
12. **Templates:** payment method (4 options); country (5); "Is tax included in the prices? yes/no" (`tax_included`).


#### D2.4 / D2.5 — candidate 1: HV09/synthetic-bilingual-invoices-200 — **USE**  _(slice 1)_
1. **Landing:** https://huggingface.co/datasets/HV09/synthetic-bilingual-invoices-200. Listing: /tree/main/data. Raw annotation file: `data/metadata.jsonl` (0.1 MB) [CARD].
2. **Licence:** `license: cc-by-4.0` [CARD].
3. **Access:** open.
4. **Size:** 7.4 MB total. Smallest unit: metadata.jsonl 0.1 MB; each PNG about 0.03–0.05 MB [CARD].
5. **Proof:** downloaded `https://huggingface.co/datasets/HV09/synthetic-bilingual-invoices-200/resolve/main/data/metadata.jsonl` [ROW]
   - `{"file_name":"INV-1080.png","invoice_number":"INV-1080","supplier_trn":"100647382910003","invoice_date":"2026-06-10","invoice_date_raw":"١٠ يونيو ٢٠٢٦","date_calendar":"gregorian","po_reference":"PO-7919","qty":308,"unit_price":137.75,"subtotal":42427,"vat_amount":2121.35,"total":44548.35,"currency":"AED","language":"ar"}`
   - `{"file_name":"SUP-1158.png","date_calendar":"gregorian","po_reference":"PO-9399","qty":140,"total":6945.75,"currency":"AED","language":"ar"}`
   - `{"file_name":"FF-1323.png","date_calendar":"gregorian","po_reference":null,"qty":199,"total":4701.38,"currency":"AED","language":"ar"}`
6. **Schema:** 17 fields (invoice_number, supplier, supplier_ar, supplier_trn, invoice_date, invoice_date_raw, date_calendar, po_reference, description, qty, unit_price, subtotal, vat_amount, total, total_raw, currency, language) [CARD].
7. **Label origin:** generator. "A seeded generator renders HTML to PNG… No LLM is involved in generation, so the ground truth is the input to rendering" [CARD].
8. **Answer rules:** D2.4 is yes if `po_reference` is not null. D2.5 is yes if `date_calendar == "hijri"`.
9. **Classes (all 200 rows):** po_reference null 70 / present 130; date_calendar gregorian 185 / hijri 15; language ar 50, bilingual 50, en 50, en-au 50; currency AED 150, AUD 50 [ROW]. Real negatives exist for both yes/no tasks.
10. **Per-image fit:** one value per invoice [CARD].
11. **Risks:** images are 820×600, small for a full invoice [ROW]. Hijri positives are few (15). The data is fictional [CARD].
12. **Templates:** PO present yes/no; Hijri yes/no; "Which currency? AED / AUD / SAR / USD"; "Which language style? Arabic / bilingual / English" (from `language`).


#### D2.6 — candidate 1: katanaml-org/invoices-donut-data-v1 (Sparrow) — **USE** (medium)  _(slice 1)_
1. **Landing:** https://huggingface.co/datasets/katanaml-org/invoices-donut-data-v1. Original: https://data.mendeley.com/datasets/tnj49gpmtz [CARD].
2. **Licence:** `license: mit` [CARD]. The original Mendeley licence was not fetched [UNVERIFIED].
3. **Access:** open.
4. **Size:** 197.5 MB. Smallest unit: test parquet 10.44 MB [CARD].
5. **Proof:** first-rows, train and `/rows` test [ROW]
   - `{"gt_parse":{"header":{"invoice_no":"40378170","invoice_date":"10/15/2012","seller":"Patel, Thompson and Montgomery 356 Kyle Vista New James, MA 46228",...,"seller_tax_id":"958-74-3511",...`
   - `{"gt_parse":{"header":{"invoice_no":"61356291","invoice_date":"09/06/2012","seller":"Chapman, Kim and Green ...","client_tax_id":"939-98-8477",...`
   - test row 0: `{"header":{"invoice_no":"97159829","invoice_date":"09/18/2015",...},"items":[{"item_desc":"12\" Marble Lapis Inlay Chess Table Top ...","item_qty":"2,00","item_net_price":"444,60","item_net_worth":"889,20","item_vat":"10%","item_gross_worth":"978,12"}],"summary":{"total_net_worth":"$ 889,20","total_vat":"$ 88,92","total_gross_worth":"$ 978,12"}}`
6. **Schema:** `image`, `ground_truth` (a JSON string with header{invoice_no, invoice_date, seller, client, seller_tax_id, client_tax_id, iban}, items[...], summary{...}) [ROW].
7. **Label origin:** human: "Annotation and data preparation task was done by Katana ML team" [CARD]. The source invoices look like synthetic electronic invoices (Faker-style names) [INFERRED].
8. **Answer rule:** count = `len(items)`; bucket into 1/2/3/4/5+. Also VAT rate = `items[*].item_vat`.
9. **Classes:** distribution UNVERIFIED (string column). 501 rows [CARD].
10. One count per invoice.
11. **Risks:** fake tax IDs that look like SSNs (###-##-####) [ROW]. Images are 2481×3508 (good) [ROW].
12. **Templates:** line-item count; "What VAT rate is applied? 0% / 5% / 10% / 20%"; "Which is the gross total? 4 amounts".


#### D3.1 / D3.2 / D3.3 — candidate 1: DrBimmer/comprehensive-car-damage — **USE** (medium)  _(slice 1)_
1. **Landing:** https://huggingface.co/datasets/DrBimmer/comprehensive-car-damage. Listing: /tree/main (one folder per class, e.g. `F_Normal/FN_53.jpg`) [CARD]. This is not the "DrBimmer car parts and damage" set that is already used. It is a separate repo.
2. **Licence:** `license: mit` [CARD].
3. **Access:** open.
4. **Size:** 668.8 MB, 2,303 files. Smallest unit: one image, about 0.01–5 MB [CARD]. Single images can be fetched.
5. **Proof:** `/first-rows?dataset=DrBimmer/comprehensive-car-damage&config=default&split=train` gives `{"label":0}` ×3 (F_Breakage) on 800×600 images [ROW]. `/statistics` gives class counts (below) [ROW]. The file listing shows `F_Normal/FN_53.jpg`, `F_Normal/FN_273.png`, `R_Breakage/RB_302.png` [CARD].
6. **Schema:** `image`, `label` ClassLabel [F_Breakage, F_Crushed, F_Normal, R_Breakage, R_Crushed, R_Normal] [ROW].
7. **Label origin:** human: `annotations_creators: - manual` [CARD]. Image provenance is not stated (likely scraped web photos) [UNVERIFIED].
8. **Answer rules:** D3.1 yes if label ∉ {F_Normal, R_Normal}. D3.2 front if label starts "F_". D3.3 none / breakage / crushed from the suffix.
9. **Classes:** F_Breakage 500, F_Crushed 400, F_Normal 500, R_Breakage 300, R_Crushed 300, R_Normal 300 (2,300 rows) [ROW]. **Real negatives: 800 undamaged images** [ROW].
10. **Per-image fit:** one label per image by folder [CARD]. An image could show both breakage and crush; the folder picks one [INFERRED].
11. **Risks:** licence plates and bystanders are possible [INFERRED]. Mixed resolutions, some PNGs at 5 MB [CARD]. Folder classifications like this circulate on Kaggle, so overlap is likely [INFERRED]. There is also a `.DS_Store`, which is harmless.
12. **Templates:** damaged yes/no; front/rear; none/breakage/crushed.


#### D4.1 — candidate 1: QCRI/CrisisMMD (config `damage`) — **USE** (licence NC)  _(slice 1)_
1. **Landing:** https://huggingface.co/datasets/QCRI/CrisisMMD. Owner: https://crisisnlp.qcri.org/crisismmd. Listing: /tree/main (images under `data_image/<event>/<date>/<tweetid>_<n>.jpg`). Original splits: https://crisisnlp.qcri.org/data/crisismmd/crisismmd_datasplit_all.zip [CARD].
2. **Licence:** `license: cc-by-nc-sa-4.0` [CARD]. Non-commercial and share-alike. No consent form. Research testing is allowed.
3. **Access:** open (API `gated: False`) [CARD].
4. **Size:** 1,941 MB in the repo (18,101 files). Smallest units: one image (KB to 3 MB); annotation zip `crisismmd_datasplit_all.zip` 3.07 MB (Content-Length 3072270); `task_damage_text_img_test.tsv` 0.13 MB [ROW].
5. **Proof:** (a) `https://datasets-server.huggingface.co/first-rows?dataset=QCRI/CrisisMMD&config=damage&split=train` [ROW]:
   - `{"event_name":"hurricane_harvey","image_id":"905960092822003712_0","image_path":"data_image/hurricane_harvey/8_9_2017/905960092822003712_0.jpg","label":2}` (severe_damage)
   - `{"event_name":"california_wildfires","image_id":"918008272363368448_0","image_path":"data_image/california_wildfires/11_10_2017/918008272363368448_0.jpg","label":2}`
   - `{"event_name":"hurricane_irma","image_id":"909396901254090752_0","image_path":"data_image/hurricane_irma/17_9_2017/909396901254090752_0.jpg","label":2}`

   (b) Original TSV `task_damage_text_img_test.tsv` [ROW]: `hurricane_maria 912065374929264640_1 … little_or_no_damage`; `hurricane_harvey 905930890735439873_1 … mild_damage`; `hurricane_irma 910225185176997895_0 … severe_damage`.
6. **Schema:** `event_name`, `tweet_id`, `image_id`, `tweet_text`, `image_path`, `image` (null in viewer; image is the repo file), `label` ClassLabel [little_or_no_damage, mild_damage, severe_damage] [ROW].
7. **Label origin:** human. Card: "several thousand manually annotated tweets and images" [CARD]. Datasplit Readme: "for damage task we only have a label for the image" [PAPER/readme in zip]. So the damage label is an **image** label.
8. **Answer rule:** answer = `label` (0 little_or_none, 1 mild, 2 severe).
9. **Classes:** train little 333 / mild 587 / severe 1,548; test 71 / 126 / 332 [ROW]. Little-or-none is a real but minority class.
10. **Per-image fit:** one label per image [readme].
11. **Risks:** Twitter images may show faces, people and text [INFERRED]. Some images are small or low quality (social media) [INFERRED]. The tweet text carries a usernames-in-text risk, so do not show the text. Published in 2018, so moderate training overlap [INFERRED].
12. **Templates:** severity (3); "Is there severe damage? yes/no"; "Which event type? hurricane / wildfire / earthquake / flood" (from `event_name` mapped to its type).


#### D4.3 — candidate 1: CrisisMMD humanitarian task (original TSV `label_image` only) — **USE**; the HF `humanitarian` config alone is a **trap**  _(slice 1)_
- Same landing, licence and access as D4.1.
- **Trap:** the datasplit Readme says "label: for informativeness and humanitarian tasks **randomly selected labels from text and image labels**" [readme]. The HF `humanitarian` config exposes only `label` (features list) [ROW], so its label may describe the tweet text, not the image. **Use `label_image` from `task_humanitarian_text_img_*.tsv`** in the 3.07 MB zip instead (the Readme documents the column `label_image`) [readme].
- HF test `label` counts: affected_individuals 86, infrastructure_and_utility_damage 319, injured_or_dead_people 41, missing_or_found_people 5, not_humanitarian 849, other_relevant_information 578, rescue_volunteering_or_donation_effort 340, vehicle_damage 19 [ROW].
- **Answer rule:** yes if `label_image == "infrastructure_and_utility_damage"`; no if `label_image == "not_humanitarian"` (clean negatives); drop other classes.
- Rows: three HF humanitarian test rows fetched (hurricane_harvey 905952332923338752_0; mexico_earthquake 912022130396672000_0; mexico_earthquake 910700764808564736_0) [ROW]. The `label_image` value of the TSV rows was not printed in this session, so the column's presence rests on the Readme [readme]. Confidence is medium.
- Templates: infrastructure damage yes/no; "Is anyone injured or dead shown? yes/no" (sensitive; avoid); vehicle damage yes/no (19 test rows, too few).


#### D8.1 — candidate 1: cloverx-id/indonesian-id-card-dummy (config `flat`) — **USE**  _(slice 1)_
1. **Landing:** https://huggingface.co/datasets/cloverx-id/indonesian-id-card-dummy. Listing: `data/flat/` (12 shards of about 1,038 MB) and `data/augmented/` (55 shards of about 65–86 MB) [CARD].
2. **Licence:** `license: cc-by-4.0`. Card: "100% safe for commercial-use licensing (CC-BY 4.0)" [CARD].
3. **Access:** open.
4. **Size:** 34,990 MB. Smallest unit: `data/augmented/train-00051-of-00055.parquet` 65.36 MB. Flat shards are about 1 GB [CARD]. Sample through `/rows`.
5. **Proof:** `https://datasets-server.huggingface.co/first-rows?dataset=cloverx-id/indonesian-id-card-dummy&config=flat&split=train` [ROW]
   - `{"image_name":"card_flat_00000.png","image_width":725,"image_height":451,"nik":"3212175503723347","nama":"NABILA PURWANTI","jenis_kelamin":"PEREMPUAN","golongan_darah":"O","agama":"BUDHA","status_perkawinan":"CERAI MATI","pekerjaan":"PETANI/PEKEBUN","provinsi":"PROVINSI JAWA BARAT",...}`
   - `{"image_name":"card_flat_00001.png","nama":"NABILA AYU PURWANTI","jenis_kelamin":"PEREMPUAN","golongan_darah":"AB","status_perkawinan":"CERAI HIDUP","provinsi":"PROVINSI JAWA TIMUR",...}`
   - `{"image_name":"card_flat_00002.png","nama":"OLIVIA TARI HASTUTI","jenis_kelamin":"PEREMPUAN","golongan_darah":"A","status_perkawinan":"KAWIN","provinsi":"PROVINSI SUMATERA UTARA",...}`
6. **Schema:** 20 printed-field columns (nik, nama, tempat_tanggal_lahir, jenis_kelamin = sex, golongan_darah = blood type, alamat, rt_rw, kel_desa, kecamatan, agama, status_perkawinan = marital status, pekerjaan, kewarganegaraan, berlaku_hingga, provinsi, kota, penerbitan_*), `card_bounding_box`, `annotations_json` (per-field text and box) [ROW].
7. **Label origin:** generator (synthetic "dummy" KTP; the fields are the render inputs) [CARD]. Faces are "real human faces from public directories (UTKFace)… dynamically morphed using… GLAM" [CARD]. That is a **risk**: the faces derive from real people.
8. **Answer rules:** D8.1 sex = `jenis_kelamin` (LAKI-LAKI → M, PEREMPUAN → F). Blood type = `golongan_darah`. Marital status = `status_perkawinan`.
9. **Classes (first 100 flat rows):** jenis_kelamin LAKI-LAKI 55 / PEREMPUAN 45; golongan_darah A 29, O 26, AB 25, B 20; status_perkawinan BELUM KAWIN 31, CERAI MATI 26, CERAI HIDUP 22, KAWIN 21; agama 5 values; kewarganegaraan WNI 100 (constant) [ROW]. Full counts UNVERIFIED (`/statistics` 500).
10. **Per-image fit:** one value per field per card.
11. **Risks:** morphed real faces from UTKFace [CARD]. Flat images are 725×451 (small) [ROW]. Questions about religion should be avoided, since that is a sensitive attribute [INFERRED].
12. **Templates:** sex (M/F); blood type (A/B/AB/O); "Which province issued it? 4 provinces" (`provinsi`).


#### D8.2 / D8.3 — candidate 1: Voxel51/synthetic_us_passports_easy — **USE**  _(slice 1)_
1. **Landing:** https://huggingface.co/datasets/Voxel51/synthetic_us_passports_easy. Original: https://huggingface.co/datasets/arnaudstiegler/synthetic_us_passports_easy. Generator repo: https://github.com/arnaudstiegler/synth-doc-AI [CARD].
2. **Licence:** "**License:** Apache-2.0" [CARD].
3. **Access:** open.
4. **Size:** 17,472 MB (9,756 files). Smallest unit: one PNG (up to 12.4 MB). Annotation file `samples.json` 23.38 MB per the listing; the fetched file was 10.05 MB [CARD][ROW].
5. **Proof:** downloaded `https://huggingface.co/datasets/Voxel51/synthetic_us_passports_easy/resolve/main/samples.json` (9,750 samples) [ROW]
   - `{"filepath":"data/data_0/passport_000000.png","nationality":{"label":"Samoa"},"place_of_birth":{"label":"Netherlands Antilles"},"authority":{"label":"Azerbaijan"},"sex":{"label":"F"},"type":"W","code":"s","passport_number":"503056413","surname":"Clayton","given_names":"Ronald Farmer","dob":"13 Jan 1988","date_of_issue":"27 Nov 2006","date_of_expiration":"23 Mar 1983"}`
   - `{"filepath":"data/data_0/passport_000001.png","nationality":{"label":"Italy"},"place_of_birth":{"label":"Timor-Leste"},...}`
   - The third row was not printed in full. Only 2 full rows were pasted; a third requires re-running the same command [UNVERIFIED third row].
6. **Schema:** `filepath`; FiftyOne Classifications `nationality`, `place_of_birth`, `authority`, `sex`; strings `type`, `code`, `passport_number`, `surname`, `given_names`, `dob`, `date_of_issue`, `date_of_expiration` [ROW].
7. **Label origin:** generator ("synthetic dataset of US passport images" built with synth-doc-AI) [CARD].
8. **Answer rules:** D8.2 yes if `parse(date_of_expiration) > parse(date_of_issue)`. Row 0 is a real negative: expiry 1983 is before issue 2006 [ROW]. D8.3 = `nationality.label` plus 3 distractor countries.
9. **Balance:** dates look independently random, so roughly mixed [INFERRED]. A full count is computable from samples.json but was not done [UNVERIFIED].
10. One value per image.
11. **Risks:** "tilted documents and high-resolution images where the passport occupies [a small part]" [CARD], so the passport may be small within a large frame. Images are up to 12 MB [CARD]. Random names. Nationality and authority values are random and inconsistent with a US passport, a realism problem [ROW].
12. **Templates:** expiry after issue yes/no; nationality (4); sex (M/F).


#### D9.1 — candidate 1: hyturing/US_tax_forms_donut (NIST Special Database 2) — **USE**  _(slice 1)_
1. **Landing:** https://huggingface.co/datasets/hyturing/US_tax_forms_donut. Owner: https://www.nist.gov/srd/nist-special-database-2 [CARD].
2. **Licence:** `license: mit` (card) [CARD]. NIST page: "Price: No charge" [CARD]. The NIST SRD terms were not read [UNVERIFIED].
3. **Access:** open (HF). NIST zip download is free [CARD].
4. **Size:** 947.0 MB. Smallest unit: `data/test-00000-of-00001.parquet` 95.3 MB [CARD]. Use `/rows`.
5. **Proof:** first-rows and `/rows` [ROW]: `{"label":"1040_1","ground_truth":"{\"gt_parse\": {\"class\" : \"1040_1\"}}"}` (2560×3300); `{"label":"4562_1",...}`; `{"label":"sch_a",...}`; test row 0 `{"label":"sch_e_2"}`.
6. **Schema:** `image`, `label` str (form face), `ground_truth` (Donut JSON holding only the class in the rows seen; the card's "Full text ground truth" was not seen) [ROW].
7. **Label origin:** generator. NIST: "5,590 pages of binary, black-and-white images of synthesized documents… The document images… appear to be real forms prepared by individuals, but the images have been automatically derived and synthesized using a computer" [CARD].
8. **Answer rule:** answer = `label`. Build 4–6 options from a related family (e.g. {1040_1, 1040_2, sch_a, sch_b, sch_e_1, sch_e_2}).
9. **Classes (test, 559):** 1040_2 105, 1040_1 88, sch_a 54, sch_b 51, sch_e_2 34, sch_e_1 33, sch_d_2 28, sch_d_1 23, 4562_2 21, 4562_1 22, sch_c_1 20, sch_se_2 15, 2106_1 10, sch_c_2 10, sch_se_1 9, 6251 9, sch_f_1 7, sch_f_2 7, 2106_2 7, 2441 6 [ROW].
10. One form face per image.
11. **Risks:** binary B/W 1988 forms. Images are 2560×3300 (good) [ROW]. Synthetic people. NIST SD2 is old and widely distributed (moderate overlap) [INFERRED].
12. **Templates:** form face (6); "Is this page 1 or page 2 of the form? 1/2" (suffix); "Is this a Schedule (A–F, SE) rather than a numbered form? yes/no".


#### D9.2 / D9.3 — candidate 1: singhsays/fake-w2-us-tax-form-dataset — **USE** (medium; the licence comes from the upstream Kaggle page, not the HF card)  _(slice 1)_
1. **Landing:** https://huggingface.co/datasets/singhsays/fake-w2-us-tax-form-dataset. Upstream: https://www.kaggle.com/datasets/mcvishnu1/fake-w2-us-tax-form-dataset [CARD].
2. **Licence:** the HF card has none. The Kaggle API for the upstream gives `"licenseName": "CC0: Public Domain"` [CARD] (https://www.kaggle.com/api/v1/datasets/view/mcvishnu1/fake-w2-us-tax-form-dataset).
3. **Access:** open on HF.
4. **Size:** 309.6 MB. Smallest unit: `data/test-…parquet` 15.47 MB [CARD].
5. **Proof:** first-rows and `/rows` test [ROW]
   - `{"box_b_employer_identification_number":"47-5592725","box_c_employer_name":"Bennett, Allen and Yang Inc","box_a_employee_ssn":"412-88-2525",...}`
   - `{"box_b_employer_identification_number":"87-6351907","box_c_employer_name":"White-Rivera Group",...}`
   - test row 0: `{"box_1_wages":126589.34,"box_2_federal_tax_withheld":43873.99,...,"box_12a_code":"E","box_12b_code":"None","box_12c_code":"D","box_13_statutary_employee":"x","box_13_retirement_plan":"None","box_13_third_part_sick_pay":"x","box_15_1_state":"HI","box_15_2_state":"WI",...}`
6. **Schema:** a `ground_truth` JSON with every W-2 box (box_a … box_20_2) [ROW].
7. **Label origin:** generator: "synthetically generated US Tax Return W2 Forms, with generated fake data such as names, ids, dates and addresses. Only real city, state and zipcodes have been used" [CARD].
8. **Answer rules:** D9.3 yes if `box_13_statutary_employee == "x"`. D9.2 = `box_15_1_state` plus 3 distractor states.
9. **Balance:** "x" and "None" values both occur [ROW]. Counts UNVERIFIED.
10. One value per box.
11. **Risks:** fake SSNs [ROW]. Images are 612×792 (small: a PDF page at 72 dpi) [ROW]. Values are random and internally inconsistent (e.g. SS wages larger than wages) [ROW].
12. **Templates:** box 13 statutory ticked yes/no; state in box 15 (4); "Which code is in box 12a? D / E / C / DD".


#### D11.3: openfoodfacts/price-tag-detection (rank 1 for 11.3)  _(slice 2)_
1. Landing: https://huggingface.co/datasets/openfoodfacts/price-tag-detection. Files: `/tree/main/data`.
2. Licence: "Just like the original images, the images in this dataset are licensed under the Creative Commons Attribution Share Alike license (CC-BY-SA 4.0)." (README) [CARD]. Research and testing are allowed; share-alike applies.
3. Access: open [CARD].
4. Size: 399.2 MB. Smallest unit: `data/val-00000-of-00001.parquet` at 44.16 MB (fits under the cap). Train is 355.08 MB [CARD].
5. Sample proof: `first-rows?dataset=openfoodfacts/price-tag-detection&config=default&split=train` [ROW]
   - `{"image_id":"6485","width":768,"height":1024,"objects":{"bbox":[[0.252,0.894,0.305,0.965],[0.235,0.969,0.280,1.0],[0.441,0.865,0.490,0.942],[0.657,0.886,0.698,0.963],[0.879,0.934,0.931,1.0]],"category_id":[0,0,0,0,0],"category_name":["price-tag"×5]}}`
   - `{"image_id":"12447","width":399,"height":568,"objects":{"bbox":[[0.103,0.166,0.910,1.0],[0.096,-1.3e-17,0.938,0.186]],"category_id":[0,0],"category_name":["price-tag","price-tag"]}}`
   - `{"image_id":"5744","width":766,"height":1024,"objects":{"bbox":[[0.139,0.725,0.226,0.906],[0.031,0.417,0.123,0.582],… (9+ boxes)],"category_id":[0,…]}}`
6. Schema:
   - `image_id`, `image`, `width`, `height`
   - `meta.image_url`
   - `objects.bbox`: list of [y_min, x_min, y_max, x_max], normalised
   - `objects.category_id` / `objects.category_name`: a single class, `price-tag` [CARD]
7. Label origin: human. "Images were collected from the Open Prices database and labeled manually." [CARD]
8. Answer rule: n = len(`objects.category_id`), mapped to a bin.
9. Classes: one class. Val has 247 images; image width is 301–1024 px [ROW, statistics]. Whether any image has zero tags is UNVERIFIED. This does not matter for the count-bin question.
10. Per-image fit: one count per image.
11. Risks:
    - Resized so the longest side is at most 1024 px [CARD]; heights go down to 200 px [ROW].
    - Crowd photos from shops may include shoppers' faces occasionally [INFERRED].
    - Boxes are clipped at the image edge (negative coordinates seen) [ROW].
12. Templates:
    - "How many price tags are visible? (0–2 / 3–5 / 6–10 / 11+)"
    - "Is there more than one price tag? (yes/no)"
    - "Is any price tag cut off at the image edge? (yes/no; a bbox coordinate ≤ 0 or ≥ 1)"
13. Verdict: **USE** (confidence med; the zero-tag negatives question is untested).


#### D12.4 / D12.5: amazon/ABO-Edit  _(slice 2)_
1. https://huggingface.co/datasets/amazon/ABO-Edit
2. Licence: "In accordance with CC BY 4.0, **ABO-Edit** is derived from Amazon Berkeley Objects (ABO) and it is distributed under the same **CC BY 4.0** license" [CARD].
3. Access: open.
4. Size: 18,288.6 MB in Arrow files of about 505 MB each [CARD]. No unit under 50 MB; sample via `/rows`.
5. Rows from `first-rows?dataset=amazon/ABO-Edit&config=default&split=train` [ROW]:
   - `{"xsource_image":"<2560x2560>","xtarget_image":"<1024x1024>","simplified_rotation_prompt":"Rotate the object: front view with a top tilt rotation of 22 degrees.","x_source_image_id":"A13tp5lR-9L","product_type":"LAMP","task":"lifestyle_to_white_with_controlled_rotation","llm_object_category":"lamp"}`
   - `{…"simplified_rotation_prompt":"…front view with a top tilt rotation of 21 degrees.","x_source_image_id":"A1xXv0BmDgL","product_type":"CHAIR","llm_object_category":"Chair"}`
   - `{…"…top tilt rotation of 23 degrees.","x_source_image_id":"91g1BZxBl9L","product_type":"SOFA"}`
6. Schema:
   - `xsource_image`: lifestyle photo
   - `xtarget_image`: the "same product isolated on a white background with realistic shadow, rotated and tilted to a precisely specified angle" [CARD], rendered from ABO 3D assets (`ABO_glb_path`)
   - `product_type`: catalogue enum
   - `simplified_rotation_prompt`: generator angle
   - `full_editing_prompt`, `object_description`, `llm_object_category`: VLM-written, **machine**
7. Label origin: mixed. The white/lifestyle split is **generator**: target images are rendered from 3D assets; "target images from ABO 3D assets and pairing them with lifestyle sources" [CARD]. `product_type` is catalogue (human) [INFERRED]. The prompts and LLM category are machine [CARD: "VLM-generated editing prompts"].
8. Answer rules:
   - "white background?" = yes for `xtarget_image`, no for `xsource_image`
   - product type = `product_type`
   - tilt = the integer in `simplified_rotation_prompt`
9. Balanced 1:1 by construction (each row gives one yes and one no) [INFERRED]. Total row count not fetched [UNVERIFIED].
10. One answer per image.
11. Risks:
    - Lifestyle images (2560 px) may contain people [INFERRED].
    - The render style is easy to spot, so a model may answer the "white background" question from rendering cues rather than the background.
    - Do not use the `llm_*` or prompt fields for answers.
12. Templates:
    - "Is the product shown alone on a plain white background? (yes/no)"
    - "What product type is shown? (LAMP / CHAIR / SOFA / TABLE / other)"
    - (target only) "Is the top tilt about 20° or more? (yes/no)". Check the angle range first.
13. Verdict: **USE** for the white-background and product_type questions (confidence med). No shard is under 50 MB.


#### D13.4: Primusvandalus/grocery-images-5class  _(slice 2)_
1. https://huggingface.co/datasets/Primusvandalus/grocery-images-5class
2. Licence: `license: other`, `license_name: pexels`, `license_link: https://www.pexels.com/license/`. "[Pexels license](https://www.pexels.com/license/). They are redistributed …" [CARD].
3. Open. 4. 63.4 MB total as 1,343 individual JPGs (0.00–0.17 MB each), so per-file fetch works [CARD].
5. Rows [ROW]: `{"image":"<940x629>","label":0}`, `{"image":"<867x650>","label":0}`, `{"image":"<940x627>","label":0}` (0 = apple).
6. `label` ClassLabel: apple, banana, bread_roll, cheese, tomato.
7. Origin: human. "Images were gathered through the Pexels API in April 2026 and hand-labelled with a custom keyboard-driven dashboard; every accept/reject decision was logged, and a written rubric governed edge cases" [CARD].
8. Rule: option = label name.
9. Classes: apple 300, banana 260, bread_roll 260, cheese 260, tomato 260 [CARD].
10. One label per image, but stock photos may show mixed foods. The rubric handled edge cases [CARD].
11. Risks: Pexels stock photos may contain people; they are likely in web-scraped training data; business value is low.
12. Templates:
    - "Which grocery item is this? (5 options)"
    - "Is this a fruit? (yes = apple/banana; no = bread_roll/cheese)" (tomato is ambiguous, so exclude it)
    - "Is this a baked good? (yes/no)"
13. Verdict: **USE** (confidence high on provenance; low on business realism).


#### D15.1: keremberke/forklift-object-detection  _(slice 2)_
1. https://huggingface.co/datasets/keremberke/forklift-object-detection. Roboflow source: https://universe.roboflow.com/mohamed-traore-2ekkp/forklift-dsitv/dataset/1
2. Licence: README "### License CC BY 4.0"; `README.dataset.txt`: "License: CC BY 4.0" [CARD].
3. Open. 4. 20.4 MB total. Smallest units: `data/test.zip` 2.77 MB, `valid.zip` 3.77 MB, `train.zip` 13.53 MB [CARD].
5. Rows from `first-rows?...&config=full&split=train` [ROW]:
   - `{"image_id":278,"width":500,"height":375,"objects":{"id":[586],"area":[120469],"bbox":[[3.0,28.0,420.12,286.75]],"category":[0]}}` (forklift only)
   - `{"image_id":76,"width":450,"height":343,"objects":{"id":[170,171],"bbox":[[285,133,19.02,27.03],[5,0,434.86,339.18]],"category":[1,0]}}` (person + forklift)
   - `{"image_id":46,"width":500,"height":500,"objects":{"id":[90,91],"bbox":[[232,110,129.64,148.91],[40,15,454.65,470.16]],"category":[1,0]}}`
6. Schema: `image_id`, `width`, `height`, `objects{id, area, bbox [x,y,w,h], category: 0 forklift, 1 person}`.
7. Origin: "created by exporting images from images.cv and labeling them as an object detection dataset" [CARD]. Human labelling in Roboflow [INFERRED].
8. Rule: yes if 1 ∈ `objects.category`.
9. Counted from all rows via `/rows` [ROW]:
   - train: person+forklift 158, forklift only 134, person only 2, neither 1
   - val: 39 / 44 / 1 / 0
   - test: 25 / 16 / 1 / 0
   - So there are **real negatives** (forklift with no person): 194 in total.
10. One yes/no per image. Restrict to images containing a forklift.
11. Risks:
    - Images are small (median about 450–500 px, min 130 px) [ROW, statistics], so filter to 400 px or more.
    - People are present (faces possible).
    - Web images from images.cv: watermarks and likely training-data overlap.
    - Exhaustiveness of person boxes is UNVERIFIED (a tiny distant person may be missed).
12. Templates:
    - "Is a person visible with the forklift? (yes/no)"
    - "How many forklifts are visible? (1 / 2 / 3+)"
    - "Does the forklift fill more than half the image? (bbox area / (w·h) > 0.5)"
13. Verdict: **USE** (confidence med).

> **Merge note (forklift).** This card replaces slice 4's D34.3 card, which had fewer counts ("exact count UNVERIFIED"). Slice 4 adds the D34.3 rule (yes iff a person and a forklift are both present) and the OSHA/NIOSH value source in the D34 atlas. Re-checked 2026-10-01: first-rows match.


#### D15.2 / D16.3: Gabriel8/cardboard-box-anomaly-detection  _(slice 2)_
1. https://huggingface.co/datasets/Gabriel8/cardboard-box-anomaly-detection. Files: `/tree/main/test/good`, `/test/bad`.
2. Licence: "Este dataset está sob a licença **CC BY-NC-SA-4.0**. Uso não comercial, com atribuição obrigatória e compartilhamento sob a mesma licença." [CARD] Non-commercial; research testing is allowed.
3. Open. 4. 2,042.9 MB. Individual JPGs of 1.4–5.3 MB each, so per-file fetch works [CARD].
5. Rows from `rows?...&split=test&offset=0&length=100` [ROW]: `{'image':'<3072x4080>','label':0}` (row 0), `{'image':'<4080x3072>','label':0}` (row 1), `{'image':'<3072x4080>','label':0}` (row 99). Label 0 = `bad` per ClassLabel names ["bad","good"] [ROW]. Example filenames from the tree: `test/good/cam1_box32_pos02_ver00_loc-b2.jpg`, `test/bad/cam1_box01_pos04_ver00_loc-chao.jpg` [CARD].
6. Schema:
   - `label` ClassLabel {bad, good}
   - The filename encodes camera, box id (1–43), position, version and location (`chao` = floor, `b1`/`b2` = conveyor belts) [CARD]
7. Origin: human. 43 physical boxes, "13 consideradas normais e 30 anômalas", photographed by the authors with support from Ondupress Embalagens [CARD]. The label is a per-box ground truth.
8. Rule: damaged = `label == bad` (or folder `test/bad`).
9. Test split: good 166, bad 386. Train has 1 good image [CARD]. **Real negatives exist.**
10. One label per image (one box per photo) [CARD].
11. Risks:
    - Many near-duplicate shots of the same 43 boxes, so sample one per box/position.
    - Very large 12 MP images (fine after downscale).
    - The defect type is not labelled.
    - No people.
12. Templates:
    - "Is this cardboard box damaged? (yes/no)"
    - "Is the box on a conveyor belt or the floor? (belt / floor; from `loc-`)"
    - "Which camera view?" (not useful; skip). Use instead: "Same box as reference image? (yes/no; box id)"
13. Verdict: **USE** (confidence high).


#### D19.1: v1nz/cubicasa5k-yolo (CubiCasa5K derivative)  _(slice 2)_
1. https://huggingface.co/datasets/v1nz/cubicasa5k-yolo. Original: https://zenodo.org/records/2613548.
2. Licence:
   - Mirror: `license: cc-by-nc-4.0`, "Converted from CubiCase5K (CC BY-NC 4.0)" [CARD]
   - Zenodo record licence id: **cc-by-nc-sa-4.0** [CARD: Zenodo API]
   - The two conflict; treat it as **CC BY-NC-SA 4.0**. Non-commercial.
3. Open. 4. 1,762.8 MB as 9,261 files: label txt files of about 0 MB, PNGs of about 4.4 MB each, so per-file fetch works [CARD].
5. Rows from `first-rows` (one YOLO polygon line per row) [ROW]:
   - `0 0.535439 0.775000 0.449871 0.775000 0.449871 0.794565 0.462725 0.795109 0.462358 0.869565 0.378259 0.869565 …`
   - `0 0.310320 0.775000 0.310320 0.794565 0.314359 0.794565 0.314359 0.775000`
   - `0 0.098054 0.678804 0.098054 0.794565 0.158281 0.794565 0.158281 0.775000 0.111274 0.774457 0.111274 0.678804`
6. Schema: `labels/<split>/<id>.txt` holds lines of `class x1 y1 x2 y2 …` (normalised polygon). Classes: 0 wall, 1 door (opening polygon only), 2 window [CARD].
7. Origin: human polygons from the CubiCasa5K SVG annotation ("annotated into over 80 floorplan object categories … using polygons" [CARD: Zenodo]), automatically rasterised and traced back to polygons by the mirror author [CARD]. Classed as human (converted); conversion noise is possible.
8. Rule: doors = count of lines starting with `1 `; windows = count starting with `2 `.
9. 105,729 label lines in the viewer split [ROW]. Per-image door distribution not computed [UNVERIFIED].
10. One count per image. Multi-floor plans are possible (the original F1 only is used: "F1_scaled.png") [CARD].
11. Risks:
    - Finnish real-estate floorplans, no personal data.
    - Large PNGs.
    - The trace-back step may split or merge openings, so spot-check 20 images.
12. Templates:
    - "How many doors are drawn? (0–3 / 4–6 / 7–9 / 10+)"
    - "Are there more windows than doors? (yes/no)"
    - "How many windows? (bins)"
13. Verdict: **USE** (confidence med; conversion fidelity unverified).


#### D20.1: garythung/trashnet  _(slice 2)_
1. https://huggingface.co/datasets/garythung/trashnet. GitHub: garythung/trashnet (not fetched).
2. Licence: `license: mit` [CARD].
3. Open. 4. 3,677 MB. Smallest unit: `dataset-resized.zip` at 42.83 MB (fits under the cap). `dataset-original.zip` is 3,634 MB [CARD].
5. Rows from `first-rows` [ROW]: `{"image":"<4032x3024>","label":0}` ×3 (0 = cardboard).
6. `label` ClassLabel: cardboard, glass, metal, paper, plastic, trash.
7. Origin: human. The authors photographed objects by class on a white background (a Stanford CS229 project) [INFERRED; the card has no text, so UNVERIFIED].
8. Rule: option = label name.
9. cardboard 806, glass 1002, metal 820, paper 1188, plastic 964, trash 274 (5,054) [ROW, statistics].
10. One object per image (by design).
11. Plain backgrounds (easy). Widely used, so likely in training data. No people.
12. Templates:
    - "Which recycling stream? (6 options)"
    - "Is this recyclable? (yes = not trash)"
    - "Is this a fibre item (paper/cardboard)? (yes/no)"
13. Verdict: **USE**. Confidence med: the label origin is inferred, the card text is empty and the licence comes from the YAML only.


#### D21.3 — Kolektor Surface-Defect Dataset (KolektorSDD, box release). Verdict **USE**  _(slice 3)_
1. Landing: https://www.vicos.si/resources/kolektorsdd/. HF: https://huggingface.co/datasets/Voxel51/Kolektor_Surface_Defect, repo id `Voxel51/Kolektor_Surface_Defect` [CARD]
2. Licence: "**License:** CC BY-NC-SA 4.0 (non-commercial; contact Danijel Skočaj for commercial use)" (HF card README) [CARD]. Research and testing use is allowed. Commercial use is not.
3. Access: open [CARD api, `gated=False`]
4. Size: 106.6 MB in 405 files. The smallest unit is one JPG (~0.27 MB). `samples.json` is 0.67 MB [CARD api]
5. Sample-first proof: fetched the full `.../resolve/main/samples.json` (0.67 MB) [ROW]:
   - `{"filepath": "data/Part0.jpg", "board_id": "kos01", "has_defect": false, "ground_truth": {"_cls": "Segmentation", mask…}}`
   - `{"filepath": "data/Part1.jpg", "board_id": "kos01", "has_defect": false, …}`
   - `{"filepath": "data/Part5.jpg", "board_id": "kos01", "has_defect": true, …}`
6. Schema: `filepath`; `board_id` (physical item kos01–kos50); `has_defect` (bool); `ground_truth` (box-filled mask) [ROW]
7. Label origin: **human**. Quote: "images provided and annotated by Kolektor Group d.o.o." [CARD]
8. Answer rule: yes if `has_defect == true`.
9. Classes and balance: 399 samples, 52 defective and 347 non-defective [ROW count and CARD table]. **Real negatives: yes.**
10. Per-image fit: one answer per image. Build balanced sets by sampling 52 negatives.
11. Risks: no personal data. Grayscale 500×~1250 px [CARD]. Defects are "microscopic fractures", so the task is hard when the image is downscaled [CARD]. Box-filled masks, not pixel-precise [CARD]. KolektorSDD is a well-known benchmark, so moderate overlap with training data is likely [INFERRED].
12. Templates: (a) "Does this commutator surface show a crack?" yes/no. (b) "Is this part acceptable for shipment?" yes/no (same rule). (c) "Of these 2 surfaces of board kos0N, which one shows the defect?" (multi-image, optional).
13. All fields have evidence. Confidence: high.


#### D22.1 — DeepPCB (GitHub). Verdict **USE**  _(slice 3)_
1. Landing and files: https://github.com/tangsanli5201/DeepPCB. Files under `PCBData/groupNNNNN/` [CARD]
2. Licence: `LICENSE` reads "MIT License, Copyright (c) 2018 tangsanli5201" [CARD]. The README also says "You can only use this dataset for research purpose." [CARD]. **Flag:** research-only wording conflicts with MIT. Testing in research is allowed.
3. Access: open (GitHub raw).
4. Size: total repo size UNVERIFIED (the GitHub API call failed). Smallest unit: one template JPG, e.g. `00041000_temp.jpg` = 22,557 bytes [ROW HEAD], plus one TXT annotation. 1,500 pairs [CARD]
5. Sample-first proof: `https://raw.githubusercontent.com/tangsanli5201/DeepPCB/master/PCBData/group00041/00041_not/00041000.txt` [ROW]:
   - `466 441 493 470 3`
   - `454 300 493 396 2`
   - `539 259 592 316 1`
   - `trainval.txt` row: `group20085/20085/20085000.jpg group20085/20085_not/20085000.txt` [ROW]
6. Schema: one TXT per tested image. Each line is `x1,y1,x2,y2,type` with type 1=open, 2=short, 3=mousebite, 4=spur, 5=copper, 6=pin-hole [CARD]. Each pair has `*_test.jpg` (defective) and `*_temp.jpg` (defect-free template) [CARD]
7. Label origin: **human** (with artificially added defects). Quotes: "We use the axis-aligned bounding box with a class ID for each defect… we annotate six common types" and "we manually argument some artificial defects on each tested image" [CARD]
8. Answer rule: `*_test.jpg` gives yes (every annotation file has ≥1 line). `*_temp.jpg` gives no; the card says these were "manually checked and cleaned" as defect-free [CARD].
9. Classes and balance: 1,500 test images (3–12 defects each) and 1,500 templates [CARD]. **Real negatives: yes** (templates) [CARD].
10. Per-image fit: one yes/no answer per image. Type questions need multi-label handling, so D22.2 should use HRIPCB.
11. Risks: no personal data. Binarised 640×640 images, so pairs are visually easy and "_temp"/"_test" filenames must be hidden. Artificial defects [CARD]. Widely used benchmark [INFERRED].
12. Templates: (a) "Does this PCB image contain a defect?" yes/no. (b) "Is there an open-circuit defect?" yes/no (type 1 present). (c) "How many defects: 1–3 / 4–7 / 8+?"
13. Total size UNVERIFIED.


#### D23.1 — Tyre condition (Mendeley `bn7ch8tvyp`; HF `NMiriams/Good_Tires` + `NMiriams/Defective_Tires`). Verdict **USE** (confidence med)  _(slice 3)_
1. Landing: https://data.mendeley.com/datasets/bn7ch8tvyp (Mendeley public API). HF: https://huggingface.co/datasets/NMiriams/Good_Tires and https://huggingface.co/datasets/NMiriams/Defective_Tires. Kaggle mirror: `warcoder/tyre-quality-classification` [CARD]
2. Licence: Mendeley "CC BY 4.0 — You can share, copy and modify this dataset so long as you give appropriate credit…" [CARD api]. Both HF repos have `license: cc-by-4.0` [CARD]. Kaggle: "Attribution 4.0 International (CC BY 4.0)" [CARD api]
3. Access: open.
4. Size: HF Good 1,254.7 MB (828 JPG) and Defective 1,663.1 MB (1,028 JPG). Smallest unit: one JPG (~1.5 MB average) [CARD api]. Kaggle total is 2,917,776,336 bytes [CARD api]
5. Sample-first proof: datasets-server `/first-rows` for both repos returns image-only rows [ROW]. The label is the repo, not a column. Row counts: Good_Tires train = 828, Defective_Tires train = 1,028 [ROW `/size`]. Mendeley description: "1854 digital tyres images, categorized into two classes: defective and good condition" [CARD]. **Note:** there are no per-row label columns. The rows pasted are image-only, and the label comes from which repo the row is in.
6. Schema: `image` only. Label = source repo (Good/Defective) [ROW]
7. Label origin: human. Quote: "The images are labelled based on their condition, i.e., whether the tyre is defective or in good condition." [CARD Mendeley]. The annotator is not named, but nothing indicates a machine.
8. Answer rule: "good" if the image comes from Good_Tires, "defective" if it comes from Defective_Tires.
9. Classes and balance: 828 good and 1,028 defective (1,856 total vs 1,854 on Mendeley, which is close to exact) [ROW and CARD]. **Real negatives: yes.**
10. Per-image fit: one tyre per image [CARD].
11. Risks: the defect type (crack, bulge, etc.) is not labelled. Large photos (~1.5 MB). The set is also on Kaggle, so training overlap is possible [INFERRED]. The 2-image difference against Mendeley is unexplained.
12. Templates: (a) "Is this tyre defective?" yes/no. (b) "Is this tyre safe to keep in service?" yes/no (same rule). (c) "Defective or good condition?" (2 options).
13. Confidence is med because the proof is repo-level, not row-level.


#### D27.1 — Synthetic meter reading (`goodcoffee/Meter_Reading`). Verdict **USE**  _(slice 3)_
1. Landing: https://huggingface.co/datasets/goodcoffee/Meter_Reading [CARD]
2. Licence: `license: apache-2.0` (the entire card body) [CARD]
3. Access: open.
4. Size: 2,449.3 MB (1,500 PNG + 1,502 JSON). Smallest units: one per-image JSON (~0.022 MB) and `test__vqa_dataset.json` (0.275 MB) [CARD api]
5. Proof: `/first-rows?dataset=goodcoffee/Meter_Reading&config=default&split=train` [ROW]:
   - `{"image_id": 1, "file_name": "data/v_0001_f_0000_rgba.png", "height": 1024, "width": 1024, "measurement_answer": "The result is -0.2", "range_answer": "The range is from 0 to 8", "minmax_answer": "The minimum value is 0 and the maximum value is 8"}`
   - `{"image_id": 2, "file_name": "data/v_0002_f_0000_rgba.png", "measurement_answer": "The result is -1.2", "range_answer": "The range is from -1 to 6"}`
   - `{"image_id": 3, "file_name": "data/v_0003_f_0000_rgba.png", "measurement_answer": "The result is -0.2", "range_answer": "The range is from 0 to 8"}`
   - per-image JSON: `{"category_name": "dial", "bbox": [636.0, 592.0, 207.0, 89.0], "camera_matrix": […], "camera_focal_length": 50.0, "synth_dial_value": -0.2, …}` [ROW]
6. Schema: `needle_bbox`, `casing_bbox`, `face_bbox`, the question/answer string pairs for measurement, range and min/max, and in the JSON `synth_dial_value` (float) [ROW]
7. Label origin: **generator**. The `synth_dial_value` field, `camera_matrix` and the render filenames (`v_0001_f_0000_rgba`) show the images were rendered from known values [ROW]. There is no card text beyond the licence.
8. Answer rule: true value = `synth_dial_value` (or a parse of `measurement_answer`). Pick-one = the true value plus 3 distractors at ±k × tick spacing within [min, max] from `range_answer`.
9. Classes: continuous values. 1,198 train and 302 test [ROW `/size`].
10. One gauge per image [ROW].
11. No personal data. 1024×1024 [ROW]. A reading of -0.2 on a 0–8 range [ROW] suggests the value may sit below the scale minimum, so check for clipping. Small (1,500 images). The first rows repeat the value -0.2, so value diversity is UNVERIFIED.
12. Templates: (a) "What does the gauge read?" (4 numeric options). (b) "What is the maximum on the scale?" (from `range_answer`). (c) "Is the reading above the midpoint of the scale?" yes/no.
13. Confidence: med (generator inferred from fields, not stated on the card).


#### D28.2 / D28.3 — Powerline components and faults (`docmhvr/powerline-components-and-faults`). Verdict **USE**  _(slice 3)_
1. Landing: https://huggingface.co/datasets/docmhvr/powerline-components-and-faults. GitHub: https://github.com/docmhvr/UAV-Based-Powerline-Problem-Inspection-Using-Machine-Learning [CARD]
2. Licence: "This dataset is provided under the [MIT License]" (README body). The YAML metadata licence is empty [CARD]
3. Access: open.
4. Size: 122.2 MB. Smallest units: `test` parquet 2.29 MB and `validation` 4.56 MB [CARD api]
5. Proof: `/first-rows?…split=train` [ROW]:
   - `{"bboxes": [[289.97, 88.20, 435.88, 321.69]], "labels": [0]}`
   - `{"bboxes": [7 boxes], "labels": [1, 3, 3, 4, 4, 4, 0]}`
   - `{"bboxes": [9 boxes], "labels": [1, 1, 1, 1, 3, 1, 3, 3, 4]}`
6. Schema: `labels` is a sequence of ClassLabel [Broken Cable, Broken Insulator, Cable, Insulators, Tower, Vegetation]; `bboxes` in pixel xyxy [ROW]
7. Label origin: **human**. Quote: "Data was collected using DJI Mini drone and manually compiled and annotated using Roboflow." [CARD]
8. Answer rule: D28.2 is yes if 1 ∈ labels (Broken Insulator), no if 3 ∈ labels and 1 ∉ labels. D28.3 is yes if 0 ∈ labels.
9. Balance (all 1,794 train rows scanned via `/rows`): has broken insulator 663; insulators with none broken 830; no insulator 301. Broken cable 907 vs none 887 [ROW computed]. **Real negatives: yes.**
10. Per-image fit: many objects per image (mean 8.0 [ROW-stats]), but yes/no presence is well defined.
11. Images are all 640×640 [ROW-stats], which is low-ish for 1536 px. Roboflow exports often include augmented copies, so near-duplicates are possible [UNVERIFIED]. No people expected.
12. Templates: (a) "Is there a broken insulator?" yes/no. (b) "Is there a broken cable?" yes/no. (c) "Which is present: vegetation encroachment, broken cable, or neither?"
13. Confidence: med-high.


#### D30.1 / D30.2 — RDD2022 (`dronefreak/RDD2022`; official: sekilab/Figshare). Verdict **USE**  _(slice 3)_
1. Landing: https://github.com/sekilab/RoadDamageDetector and Figshare https://figshare.com/articles/dataset/RDD2022_-_The_multi-national_Road_Damage_Dataset_released_through_CRDDC_2022/21431547. HF: https://huggingface.co/datasets/dronefreak/RDD2022 [CARD]
2. Licence: Figshare API gives `{'name': 'CC BY 4.0'}` [CARD api]. The HF card says "released by their creators under the Creative Commons Attribution-ShareAlike 4.0… (CC BY-SA 4.0)" [CARD]. **The sources conflict (BY vs BY-SA)**, but both are open and permit testing.
3. Access: open. The official S3 file list returned AccessDenied [ROW], so use Figshare or HF.
4. Size: official is a SINGLE ARCHIVE, `RDD2022_released_through_CRDDC2022.zip` at 13,264.2 MB [CARD api]. HF is 11,078.8 MB as per-image JPG and TXT, with per-shard `metadata.jsonl` of ~0.37 MB as the smallest annotation unit [CARD api]
5. Proof: fetched `https://huggingface.co/datasets/dronefreak/RDD2022/resolve/main/data/images/train/shard_000/metadata.jsonl` (3,000 rows) and `/first-rows` [ROW]:
   - `{"file_name": "China_Drone_000001.jpg", "objects": {"bbox": [[14, 70, 184, 29], [95, 114, 25, 158]], "categories": [1, 0]}}`
   - `{"file_name": "China_Drone_000003.jpg", "objects": {"bbox": [[9,467,195,22],[199,304,313,46],[199,1,78,296]], "categories": [1, 1, 0]}}`
   - `{"file_name": "China_Drone_000048.jpg", "objects": {"bbox": [], "categories": []}}` (negative)
6. Schema: `file_name` (country_source_id); `objects.categories` with 0 = longitudinal_crack (D00), 1 = transverse_crack (D10), 2 = alligator_crack (D20), 3 = pothole (D40); `objects.bbox` [ROW and CARD]
7. Label origin: **human**. The cvtechniques card (same source data) says "annotations… created by professional researchers in Tokyo" [CARD]. The data article is Arya et al., Geoscience Data Journal [CARD].
8. Answer rule: D30.1 is yes if 3 ∈ categories, no otherwise. D30.2 is the single distinct category when only one class is present.
9. Balance: 26,869 train / 5,758 val / 5,758 test [ROW `/size`]. Instance totals: D00 18,201, D10 8,386, D20 7,526, D40 7,554 [CARD]. Shard_000: 74/3,000 empty; images per class 0:1,664, 1:1,202, 2:520, 3:551 [ROW computed]. Card: "Roughly one third of images have no in-taxonomy damage" [CARD]. **Real negatives for "pothole?": yes** (images without class 3). **Caveat:** "empty" images may still contain dropped class-4 damage such as repairs or block cracks [CARD], so do not phrase the question as "any damage?".
10. Per-image fit: multi-label is common. For pick-one, filter to a single class.
11. Personal data: street scenes from six countries may show faces or plates [INFERRED]. Mixed resolutions (drone, motorbike, car). Public benchmark, so overlap is likely [INFERRED].
12. Templates: (a) "Is there a pothole?" yes/no. (b) "Which damage type is present?" (4). (c) "Is there an alligator (fatigue) crack?" yes/no.
13. Confidence: high (licence variant aside).


#### D31.1 — Project-AgML/crop_pest_disease_classification (rank 1)  _(slice 4)_
1. Landing: https://huggingface.co/datasets/Project-AgML/crop_pest_disease_classification ; files: …/tree/main ; repo id `Project-AgML/crop_pest_disease_classification` [CARD]
2. Licence: `license: cc-by-4.0` (README YAML) [CARD]. Card says "indexed on https://project-agml.github.io/". Original: Mensah Kwabena et al. (CCMT dataset, Ghana) [CARD]. No research restriction stated.
3. Access: open (gated: False) [CARD]
4. Size: 8,427 MB total; configs `raw` (25,170 rows) and `augmented` (105,252 rows). Smallest shard is about 380 MB (`augmented/train-00012-of-00016.parquet`). Not a single archive, but no shard is under 50 MB, so sample via datasets-server [CARD]
5. Sample proof: `https://datasets-server.huggingface.co/first-rows?dataset=Project-AgML/crop_pest_disease_classification&config=raw&split=train` [ROW]
   - `{"image": 400x400, "label": 0, "crop": "Cashew"}`
   - `{"image": 400x400, "label": 0, "crop": "Cashew"}`
   - `{"image": 400x400, "label": 0, "crop": "Cashew"}`
6. Schema: `image` (Image); `label` ClassLabel of 18 names (anthracnose, bacterial blight, brown spot, fall armyworm, grasshoper, green mite, gumosis, healthy, leaf beetle, leaf blight, leaf curl, leaf miner, leaf spot, mosaic, red rust, septoria leaf spot, streak virus, verticulium wilt); `crop` string (Cashew/Cassava/Maize/Tomato) [ROW]
7. Label origin: human [INFERRED]. The source is a field-collected, expert-curated CCMT set, but the card does not describe annotation. UNVERIFIED quote.
8. Answer rule: healthy = yes iff `label == "healthy"`. Crop = `crop` column.
9. Classes (raw split, /statistics): healthy 3,235; septoria 2,743; bacterial blight 2,614; leaf blight 2,292; anthracnose 1,729; red rust 1,682 … fall armyworm 285. Crop: Cassava 7,508, Cashew 6,549, Tomato 5,792, Maize 5,321 [ROW]. **Real negatives: yes** (3,235 healthy) [ROW].
10. One label per image [ROW]. Use the `raw` config only; `augmented` holds synthetic augmentations [CARD].
11. Risks: 400 px images (upscaling to 1536 softens them) [ROW]. Plant pathology is not human medical diagnosis, but **it overlaps the "plant leaf disease" family already used**. Same org (Project-AgML), different source dataset. The merge step should decide [INFERRED]. Duplicate photos in the source are UNVERIFIED.
12. Templates: (a) "Is this {crop} plant healthy?" yes/no. (b) "Which crop is this?" Cashew/Cassava/Maize/Tomato. (c) "Which problem is shown?" 4 options drawn from the same crop's labels.
Verdict: **USE** (provisional, origin inferred), confidence med. Flag the overlap with the used leaf-disease set.


#### D31.2 — Project-AgML/plant_seedlings_aarhus (rank 1)  _(slice 4)_
1. https://huggingface.co/datasets/Project-AgML/plant_seedlings_aarhus ; original https://vision.eng.au.dk/plant-seedlings-dataset/ [CARD]
2. `license: cc-by-sa-4.0` [CARD]. ShareAlike applies to derivatives. No testing restriction.
3. open [CARD]
4. 1,714.5 MB; 3 parquet shards, smallest 309.4 MB (`data/train-00000-of-00003.parquet`) [CARD]
5. Proof: `first-rows?dataset=Project-AgML/plant_seedlings_aarhus&config=default&split=train` [ROW]
   - `{"image": 426x426, "label": 9}`
   - `{"image": 629x629, "label": 9}`
   - `{"image": 404x404, "label": 9}` (9 = shepherds_purse)
6. `image`; `label` ClassLabel: black_grass, charlock, cleavers, common_chickweed, common_wheat, fat_hen, loose_silkybent, maize, scentless_mayweed, shepherds_purse, smallflowered_cranesbill, sugar_beet [ROW]
7. human [INFERRED]: plants were grown and photographed per species by Aarhus University. Card has no annotation section.
8. Species = `label`. Crop-or-weed: yes (crop) iff label ∈ {maize, common_wheat, sugar_beet} [INFERRED from species biology].
9. black_grass 309, charlock 452, cleavers 335, common_chickweed 713, common_wheat 253, fat_hen 538, loose_silkybent 762, maize 257, scentless_mayweed 607, shepherds_purse 274, smallflowered_cranesbill 576, sugar_beet 463 (total 5,539) [ROW]. Crop/weed negatives: 973 crop vs 4,566 weed images.
10. One species per image [CARD/ROW]
11. Variable size 400–630 px (some small) [ROW]. Widely used Kaggle set (training overlap likely) [INFERRED].
12. (a) "Which plant is this seedling?" 4 options. (b) "Is this seedling a crop?" yes/no. (c) "Is this seedling a grass-type weed (black-grass or loose silky-bent)?" yes/no.
Verdict: **USE** (med).


#### D31.3 — Project-AgML/oil_palm_fruit_ripeness_classification (rank 1)  _(slice 4)_
1. https://huggingface.co/datasets/Project-AgML/oil_palm_fruit_ripeness_classification ; source Zenodo https://doi.org/10.5281/zenodo.11114885 [CARD]
2. `license: cc-by-4.0` [CARD]
3. open
4. 1,165.7 MB; smallest shard 182.4 MB [CARD]
5. Proof: first-rows default/train [ROW]: `{"image":757x568,"label":1}`, `{"image":2400x3200,"label":1}`, `{"image":757x568,"label":1}` (1 = Empty)
6. `image`, `label` ClassLabel [Damaged, Empty, Overripe, Ripe, Unripe] [ROW]
7. human [INFERRED]: grading of outdoor Tenera FFB photos (MunirahRosbi Zenodo). UNVERIFIED quote.
8. grade = `label`
9. Damaged 15, Empty 12, Overripe 74, Ripe 201, Unripe 164 (466 total) [ROW]. Imbalanced. Use mainly Ripe/Unripe/Overripe.
10. one bunch per image [INFERRED]
11. Mixed resolutions (757 px to 3200 px) [ROW]. Small set.
12. (a) "What ripeness grade is this bunch?" unripe/ripe/overripe. (b) "Is this bunch ready to harvest (ripe)?" yes/no. (c) "Is this an empty or damaged bunch?" yes/no.
Verdict: **USE** (med).


#### D32.1 — AGRARIAN/greek_sheep_goats_dataset (rank 1)  _(slice 4)_
1. https://huggingface.co/datasets/AGRARIAN/greek_sheep_goats_dataset ; files …/tree/main (YOLO `train/`, `val/`, `data.yaml`)
2. `license: apache-2.0` [CARD]
3. open
4. 3,627.7 MB total, 7,205 files; individual label `.txt` files are about 0 MB and images about 0.5 MB each [CARD]. Not an archive, so files can be fetched one by one.
5. Proof: raw `train/labels/0058dd32-DJI_20250224121827_0005_D_2260_6.txt` [ROW]:
   - `0 0.0046205693651593 0.5696770439906462 0.0092411387303185 0.0727442369364713`
   - `0 0.0112021908022686 0.5921931173281253 0.0224043816045372 0.0914498978629926`
   - `0 0.0254046370612937 0.6091667726133015 0.0508092741225875 0.0866002820672277`
   - data.yaml: `names: ['goat', 'sheep']` [ROW]
6. YOLO lines: `class x_c y_c w h` normalised. Class 0 = goat, 1 = sheep.
7. human. Card: "**Manual Annotation:** Every image has been manually labeled… Label Studio was used" [CARD]
8. goats present = any line with class 0; majority = argmax count by class; none if the file is empty.
9. **Real negatives: yes**. 676 train + 214 val label files are 0 bytes (empty), 2,012 + 698 non-empty [ROW, blob listing].
10. Multi-animal. Use presence or count questions. Majority is ambiguous when counts tie, so drop ties.
11. Source is 450 drone frames cut into 8 **overlapping** 640x640 patches, so near-duplicates exist and the same animal can appear in two patches [CARD]. Animals are small. No people.
12. (a) "Are there goats in this image?" yes/no. (b) "Which animal is more numerous?" goat/sheep/none visible. (c) "How many animals?" 0 / 1–5 / 6–15 / 16+.
Verdict: **USE** (high).


#### D32.2 — keremberke/aerial-sheep-object-detection (rank 1 for count)  _(slice 4)_
1. https://huggingface.co/datasets/keremberke/aerial-sheep-object-detection ; Roboflow https://universe.roboflow.com/riis/aerial-sheep [CARD]
2. README.dataset.txt: "License: Public Domain" [CARD]. HF YAML has no licence field.
3. open
4. 451 MB; `data/train.zip` 393 MB; valid/test zips smaller (sizes not separately printed, UNVERIFIED). It is zip-based, but the datasets-server viewer works.
5. Proof first-rows default/train [ROW]: image_id 28 (600x600) 19 sheep boxes; image_id 1842 17 boxes; image_id 3386 20 boxes, all `category` 0.
6. `objects.{id, area, bbox[x,y,w,h], category∈[sheep]}` [ROW]
7. human [INFERRED] (Roboflow-annotated); README notes "augmentation was applied to create 3 versions of each source image" [CARD]
8. count = len(objects.category)
9. 1 class, 3,609/350/174 images. Negatives UNVERIFIED.
10. count question only
11. **3× augmented copies** inflate the set; dedupe by source. 600 px.
12. "How many sheep?" bins; "More than 10 sheep?" yes/no; "Is any sheep touching the image edge?" (from bbox, x=0 or x+w=600) yes/no.
Verdict: **USE** for counts (med). Dedupe augmentations first.


#### D32.3 — anilbhujel/viewpoint-aware-pig-posture-recognition (rank 1)  _(slice 4)_
1. https://huggingface.co/datasets/anilbhujel/viewpoint-aware-pig-posture-recognition ; code github.com/Anil-Bhujel/viewpoint-aware-pig-posture-recognition [CARD]
2. "released under the Creative Commons Attribution 4.0 (CC BY 4.0) license" [CARD]
3. open
4. 1,357 MB; `train.csv` 7.6 MB; images 0.08 MB and up each [CARD]
5. Proof: raw `viewpoint_aware_pig_posture_recognition/seenVP_test.csv` [ROW]:
   - `test_pen1_tur_cam2_20250920_174649_0000, pen1_tur_cam2_20250920_174649.jpg,1280,720,"[711.7,251.2,280.0,436.0]",0, …azimuth_deg 68.34…`
   - `…_0001, same image, "[378.5,506.0,409.0,210.0]",1, …`
   - `…_0002, same image, "[201.7,388.2,211.0,294.0]",1, …`
6. Columns: row_id, image_id, width, height, bbox [x,y,w,h], class_id, world_x/y, azimuth/elevation (deg, sin, cos), angle_valid, cam_pos_source, arrow_u/v. class_id: 0 Lateral_lying_left, 1 Lateral_lying_right, 2 Sitting, 3 Standing, 4 Sternal_lying [CARD]
7. human. "Pigs were annotated with bounding boxes and posture labels" [CARD]. Viewpoint angles are machine-computed (PnP) and should not be used as labels.
8. Group rows by image_id. standing_count = #class_id==3. any_sitting = exists class_id==2. lying = class_id ∈ {0,1,4}.
9. 5 classes. Per-class counts UNVERIFIED. 3,090 train / 3,000 test images (viewer).
10. Multi-pig per image. Use counts or presence, or crop a single bbox.
11. Fisheye overhead cameras distort the view. Unlabelled pigs possible [UNVERIFIED]. No people expected.
12. (a) "Is any pig standing?" yes/no. (b) "How many pigs are lying down?" bins. (c) "Most common posture?" lying / standing / sitting.
Verdict: **USE** (med; check per-image completeness of the labels).


#### D33.1 — lila-bc-community/channel-islands-camera-traps (rank 1)  _(slice 4)_
1. https://huggingface.co/datasets/lila-bc-community/channel-islands-camera-traps ; source https://lila.science/datasets/channel-islands-camera-traps/ [CARD]
2. "License: Community Data License Agreement — Permissive 1.0" (https://cdla.io/permissive-1-0/) [CARD]
3. open
4. 3,675 MB; 6 shards, smallest 415 MB [CARD]
5. Proof first-rows [ROW]: `{"image_id":"613dd021-…","width":1920,"height":1080,"objects":{"bbox":[[0,543,1773,504]],"category":[1]}}`; `{"image_id":"e8855688-…","objects":{"bbox":[[107,601,678,360]],"category":[1]}}`; `{"image_id":"4398456c-…","objects":{"bbox":[[118,566,527,304]],"category":[1]}}` (1 = fox)
6. objects.bbox [x,y,w,h], objects.category ∈ [bird, fox, other, rodent, skunk], objects.area
7. human (LILA bbox annotations, The Nature Conservancy) [CARD: "Camera-trap images with bounding-box annotations"]. Annotator details UNVERIFIED.
8. species = the unique category if all boxes share it
9. 5 classes; 11,996 images. **No negatives**: "Empty frames… and human labels… are excluded" [CARD]
10. Mostly one species per frame [INFERRED]. Drop mixed frames.
11. Night IR frames. Humans removed for privacy [CARD]. Foxes dominate (class balance UNVERIFIED).
12. "Which animal?" fox/bird/rodent/skunk/other; "Is the animal a fox?" yes/no (within positives only); "How many animals?" 1/2/3+.
Verdict: **USE** for pick-one species. **Not** for "empty vs animal" (33.2 → Gap).


#### D33.3 — Project-AgML/tree_species_classification_slovak_normal_cropped (rank 1)  _(slice 4)_
1. https://huggingface.co/datasets/Project-AgML/tree_species_classification_slovak_normal_cropped ; Zenodo https://doi.org/10.5281/zenodo.14228004 [CARD]
2. `license: cc-by-4.0` [CARD]
3. open
4. 2,431 MB; smallest shard 393.7 MB [CARD]
5. [ROW] `{"image":2480x3508,"label":0}` ×3 (European beech)
6. label ClassLabel [European beech, European silver fir, Norway spruce, Sessile oak]
7. human [INFERRED]. "real RGB images of tree species collected in natural field environments… during field surveys in June and August 2022" [CARD]
8. = label
9. beech 300, silver fir 337, Norway spruce 396, sessile oak 334 [ROW]. Balanced.
10. one tree per image ("cropped") [CARD name]
11. Very large images (2480x3508); downscale. Possible near-duplicates of the same tree [INFERRED].
12. species 4-way; "Is this a conifer?" yes/no (fir, spruce); "Is this an oak?" yes/no.
Verdict: **USE** (med-high).


#### D34.1 / D34.2 — VincentGOURBIN/ppe-detection (rank 1)  _(slice 4)_
1. https://huggingface.co/datasets/VincentGOURBIN/ppe-detection ; Roboflow https://universe.roboflow.com/vincentspace/ppe-detection-1-cniwr/dataset/2 [ROW data.yaml]
2. YAML `license: cc-by-4.0`; data.yaml `roboflow: license: CC BY 4.0` [CARD]
3. open
4. 174.3 MB, 7,431 files, individually fetchable (images about 0.05 MB, labels under 0.01 MB) [CARD]
5. Proof: raw `valid/labels/*.txt` [ROW]:
   - `12_Group_Group_12_…_101…txt`: `3 0.1796875 0.6703125 0.1890625 0.2984375 / 3 0.371875 0.5640625 …` 
   - `…_198…txt`: `3 0.2609375 0.53125 0.134375 0.5421875 / 3 0.40625 …`
   - `…_29…txt`: `3 0.109375 0.5765625 0.18125 0.4859375 … / 1 0.11…`
6. YOLO; classes `['helmet','no-helmet','no-vest','person','vest']` [ROW data.yaml]
7. human [INFERRED] (Roboflow project annotations). No annotation statement on the card.
8. 34.1: yes iff any line has class 2 (no-vest). 34.2: yes iff any line has class 1 (no-helmet).
9. Valid split (164 images, all fetched): has no-vest 69 / none 95; has no-helmet 31 / none 133 [ROW]. **Real negatives yes.** Train 3,447 / test 101.
10. Multi-person. Image-level "any" questions are clean.
11. **Faces**: filenames "12_Group_Group_…" look like WIDER FACE group photos [INFERRED], so personal data risk. 640x640. Not the Voxel51 hard-hat source.
12. (a) "Is any person without a safety vest?" yes/no. (b) "Is any person without a helmet?" yes/no. (c) "How many people are labelled?" bins (class 3).
Verdict: **USE** (med; origin inferred; face risk flagged).


#### D34.4 — keremberke/construction-safety-object-detection (rank 1)  _(slice 4)_
1. https://huggingface.co/datasets/keremberke/construction-safety-object-detection ; Roboflow https://universe.roboflow.com/roboflow-universe-projects/construction-site-safety [CARD]
2. README.dataset.txt "License: CC BY 4.0" [CARD]
3. open
4. 27.7 MB total; train.zip 22.3 MB [CARD]
5. first-rows full/train [ROW]: image_id 180 (416x416) 64 objects incl. categories 4 (hardhat), 7 (no-mask); image_id 109: [4,4,3,3,12,12,7,7,…]; image_id 242: [4,8,7,9] (hardhat, no-safety vest, no-mask, person)
6. category names: barricade, dumpster, excavators, gloves, hardhat, mask, no-hardhat, no-mask, no-safety vest, person, safety net, safety shoes, safety vest, dump truck, mini-van, truck, wheel loader [ROW]
7. human [INFERRED]. Frames come from YouTube videos and a cloned Roboflow project [CARD]
8. vest missing = any category 8; hat missing = any 6; mask missing = any 7
9. 307/57/34 images. Negatives per item UNVERIFIED (row 109 has no "no-safety vest", so they exist [ROW])
10. multi; image-level presence
11. **416 px** (soft at 1536). YouTube frames. Faces.
12. "Is anyone missing a safety vest?"; "Which item is missing: hardhat / mask / vest / none?" (only when exactly one 'no-' class); "Is heavy machinery present?" (excavators, wheel loader, dump truck).
Verdict: **USE** (med; small images).


#### D35.3 / D35.4 — Turki-Alshuaibi/haris-weapon-detection-dataset-curated (rank 1)  _(slice 4)_
1. https://huggingface.co/datasets/Turki-Alshuaibi/haris-weapon-detection-dataset-curated
2. `license: cc-by-4.0` (YAML only) [CARD]. Upstream sources include Roboflow exports and **UCF-Crime** (its licence is UNVERIFIED and may be research-only).
3. open
4. 2,683 MB, 23,049 files; individual images and labels [CARD]
5. Proof (label viewer) [ROW]: `0 0.642249 0.448207 0.080718 0.086321`; `0 0.393479 0.528552 0.033081 0.037185`; `0 0.526465 0.466135 0.039697 0.034529`
6. YOLO; data.yaml `names: ['gun','knife']`, with comments listing sources ds_1…ds_9 incl. "ds_9_hardneg: 534 images — UCF-Crime hard negatives (empty labels)" [ROW]
7. human [INFERRED] (merged Roboflow annotations). Not stated.
8. weapon = non-empty label. Type = class set ({0} gun, {1} knife).
9. **Real negatives: yes.** Empty label files 2,072 train + 710 val; non-empty 7,650 + 1,091 [ROW]
10. image-level. Drop images with both classes for the pick-one.
11. CCTV and staged scenes; faces present. UCF-Crime terms. Sensitive content (violence).
12. "Is a weapon visible?" yes/no; "gun / knife / none"; "How many weapons?" 1/2/3+.
Verdict: **USE** (med). Flag the UCF-Crime licence for human check. Consider excluding ds_9 frames if the licence is restrictive.


#### D36.1 — dronefreak/PKLot (rank 1)  _(slice 4)_
1. https://huggingface.co/datasets/dronefreak/PKLot ; owner https://web.inf.ufpr.br/vri/databases/parking-lot-database/ ; paper https://doi.org/10.1016/j.eswa.2015.02.009 [CARD]
2. "Unofficial redistribution… under the original CC BY 4.0 license" (`license: cc-by-4.0`) [CARD]
3. open
4. 3,909.7 MB; per-image JPG and YOLO txt; `data/images/train/metadata.jsonl` 15.5 MB holds all train labels [CARD]
5. first-rows default/train [ROW]: `{"file_name":"PUCPR_2012-09-11_15_16_58.jpg","objects":{"bbox":[[278,185,46,45],[310,185,45,48],…+91],"categories":[1,0,1,0,1,1,0,0,…+91]}}`; `PUCPR_2012-09-11_15_27_08.jpg` same layout; `PUCPR_2012-09-11_15_29_29.jpg` same layout
6. file_name; objects.bbox (COCO px); objects.categories int (0 = vacant, 1 = occupied per data.yaml and card) [ROW]
7. human. "Every frame has an XML descriptor marking each parking space and whether it is occupied" [CARD]
8. occupied_frac = mean(categories). "more than half full" = occupied_frac > 0.5. vacant_count = #0.
9. 693,755 labelled spaces; 8,346 / 1,981 / 2,089 images. Both classes are in every frame [ROW/CARD]
10. One answer per image for aggregate questions.
11. Card warns: fixed cameras, near-identical frames, 25,773 unlabelled spaces left as background [CARD]. Cars are far away, so plates are not readable [INFERRED]. 1280x720. Very well known (training overlap likely).
12. (a) "Is the lot more than half full?" yes/no. (b) "About how many spaces are free?" 0–10 / 11–30 / 31–60 / 61+. (c) "Which camera view (PUCPR / UFPR04 / UFPR05)?" from the filename prefix.
Verdict: **USE** (high).


#### D36.2 — cute-face/bike-helmet-dataset (COCO part) (rank 1)  _(slice 4)_
1. https://huggingface.co/datasets/cute-face/bike-helmet-dataset
2. `license: cc-by-4.0` (YAML). The README gives CC BY 4.0 for the VOC part and "Unknown / Web Collection" for the Google/harvested folders [CARD]. Use only the root COCO and `helmet_voc` parts.
3. open
4. 773.4 MB; `valid/_annotations.coco.json` (127 images) is small [ROW]
5. Proof (valid COCO JSON) [ROW]: ann `{id:1,image_id:0,category_id:2,bbox:[137,3,84,70]}`; `{id:2,image_id:1,category_id:1,bbox:[144,17,48,105]}`; `{id:3,image_id:1,category_id:1,bbox:[114,52,38,85]}`
6. COCO categories: 0 rider-helmet-bike (super), 1 "With Helmet", 2 "Without Helmet" [ROW]
7. human [INFERRED] (Roboflow export)
8. all helmeted = no annotation with category 2
9. Valid: only-with 74, only-without 38, both 15 [ROW]. **Negatives yes.**
10. Pick images with a single category for clean pick-one.
11. **416 px**; rider faces. The viewer's `label` column is the split name, not a label (do not use it).
12. "Is every rider wearing a helmet?"; "How many riders without helmet?"; "with / without / mixed".
Verdict: **USE** (med; small images).


#### D37.1 / D37.2 / D37.3 — morzel85/synthetic-medical-document-recognition-benchmark (rank 1)  _(slice 4)_
1. https://huggingface.co/datasets/morzel85/synthetic-medical-document-recognition-benchmark ; files …/tree/main/data/png
2. `license: cc-by-4.0` [CARD]. "intended for software development and benchmarking, not for clinical use" [CARD]
3. open
4. 31,211 MB total; 7,384 PNGs (23,853 MB); smallest PNG 0.08 MB; `data/manifest.json` about 0 MB [CARD]
5. Proof: the generator values are in the filenames (blob listing) and the FHIR JSON [ROW]:
   - `data/png/synthetic_Adam_Hirthe_1ce276e5_clinical_timeline_type_1_p_10_of_13_dpi_300_clear_ver_1.png`
   - `…_clinical_timeline_type_1_p_11_of_13_dpi_300_clear_ver_1.png`
   - `…_clinical_timeline_type_1_p_12_of_13_dpi_300_clear_ver_1.png`
   - manifest: `"file_counts": {"html":150,"pdf":2100,"png":7384,…}` [ROW]; viewer rows: image 2550x3301 ×3 [ROW]
6. Filename grammar [CARD]: `<patient>_<category>_type_<n>[_p_<i>_of_<n>]_dpi_300_<variant>_ver_<k>`. variant tokens: `clear`, `photocopy_{str,rot,mis…}`, `photo_{ske,sta,cli,mis…}`. `cli` = "Clipped: part of the page extends beyond the image boundary"; `ske` = skewed photograph. type_1/2/3 = date style (US numeric / abbreviated month / ISO) [CARD]
7. **generator**. "synthetic… medical records rendered as documents… Every degraded page is derived from its corresponding clear page" [CARD]
8. 37.1 category = filename token before `_type_`. 37.2 capture = clear / photocopy / photo token. 37.3 clipped = `cli` in tokens. Date style = type_n.
9. Categories seen in clear pages: contact_form, contact_info, notes, observation, report, survey, vaccination_history, diagnostic, clinical_timeline, email (per card) [ROW/CARD]. 13 variant configs × 568 rows each [ROW]. Negatives for clipped: the clear/str/ske variants.
10. one answer per page
11. Only **5 synthetic patients**, so templates repeat; "synthetic" watermarks give shortcuts [CARD]. Names are synthetic. Large 300-dpi pages. **"diagnostic" pages contain clinical content**, so ask only admin questions (no diagnosis).
12. (a) "What kind of document is this page?" contact info / observation / vaccination history / survey / notes / report. (b) "How was this page captured?" clean / photocopy / photo. (c) "Which date format does the page use?" 08/24/2026 / Aug 24, 2026 / 2026-08-24.
Verdict: **USE** (high).


#### D38.1 — twinkle-ai/tw-drug-labels-vision (rank 1)  _(slice 4)_
1. https://huggingface.co/datasets/twinkle-ai/tw-drug-labels-vision ; source TFDA open data (data.gov.tw) [CARD]
2. "**License:** CC BY 4.0" [CARD]
3. open
4. 12,513 MB; parquet shards 147–1,954 MB (smallest `data/train-00007-of-00008.parquet` 147 MB); `sample.json` 0.01 MB [CARD]. The two shard sets (…of-00008 and …of-00018) may overlap; which one the config uses is UNVERIFIED.
5. first-rows [ROW]: `{images:[744x1053,744x1053], license_id:"內衛成製字第000039號", drug_name_en:"RIVANOL SOLUTION 0.2%", dosage_form:"外用液劑", strength:"0.2%", source_type:"leaflet"}`; `{images:[1053x744], license_id:"內衛成製字第000040號", drug_name_en:"Hydrogen Peroxide Solution 3%", strength:"3%", active_ingredients:[{name:"HYDROGEN PEROXIDE", amount:"30mg/ml"}]}`; `{images:[744x1053], license_id:"內衛成製字第000044號", drug_name_en:"Liquor Cresolis Saponatus", strength:"50%"}`
6. images (list of WebP pages, 90 dpi); 17 text fields (license_id, names zh/en, dosage_form, strength, active_ingredients, indications…, package, manufacturer, marketing_holder, `source_type` ∈ {leaflet, carton}, source_urls) [ROW/CARD]
7. **mixed**. `source_type` and `license_id` come from the TFDA registry spreadsheet (human/administrative) [CARD]. The other 16 fields were "抽取" (extracted) from the PDFs with OCR clean-up mentioned, so **machine** [CARD].
8. carton/leaflet = `source_type`. Imported = `license_id` contains "輸" (licence-number convention, [INFERRED]). Do NOT trust dosage_form or strength as Tier A.
9. source_type: leaflet 26,574 / carton 15,630 in the stats sample [ROW]; card says 21,959 cartons of 44,663 [CARD]
10. one record per drug document (multi-page). Use the first page.
11. 90 dpi (about 750x1050). Chinese text. Machine-extracted fields. Public regulatory docs (no PII).
12. (a) "Is this an outer carton or a package leaflet?" (b) "Is this drug imported?" yes/no (from licence prefix). (c) "Which licence-type prefix is printed?" 衛部藥製 / 衛部藥輸 / 內衛成製 / other.
Verdict: **USE for (a)–(c) only** (registry-derived); **MAYBE** for any extracted field. Confidence med.


#### D38.2 — LibreYOLO/pills-sxdht (Roboflow 100)  _(slice 4)_
1. https://huggingface.co/datasets/LibreYOLO/pills-sxdht ; Roboflow https://universe.roboflow.com/roboflow-100/pills-sxdht [CARD]
2. "License: CC BY 4.0" (README.dataset.txt and data.yaml) [CARD]
3. open
4. 24.6 MB total, 907 files [CARD]
5. Proof: raw `test/labels/*.txt` [ROW]: `20210702_161114…txt: 7 0.49765625 0.453125 0.13515625 0.1296875`; `20210702_161207…txt: 6 0.47890625 0.53046875 0.18359375 0.21875`; `20210702_161707…txt: 4 0.4875 0.515625 0.1421875 0.221875`
6. names: Cipro 500, Ibuphil 600 mg, Ibuphil Cold 400-60, Xyzall 5mg, blue, pink, red, white [ROW]
7. human [INFERRED] ("Provided by a Roboflow user", RF100) [CARD]
8. product = class name if class ∈ 0–3; colour if 4–7
9. 316/90/45 images; no empty label files (no negatives) [ROW]
10. Single pill per image in the rows seen.
11. **Taxonomy mixes product names and colours**, so a pill gets a colour label OR a product label, never both. Small images (≤0.2 MB).
12. "What colour is this pill?" blue/pink/red/white (only colour-labelled images); "Which product?" 4 names (only product-labelled images); "How many pills?"
Verdict: **USE** (med), restricted to the two clean sub-tasks.


#### D38.3 — ApyHTML19/Medication_Boxes_Arabe_Latin (rank 1)  _(slice 4)_
1. https://huggingface.co/datasets/ApyHTML19/Medication_Boxes_Arabe_Latin
2. `license: mit` [CARD]
3. open
4. 91.8 MB; `annotations/instances_val.json` small (<1 MB) [ROW]
5. Proof (instances_val.json) [ROW]: `{id:1,image_id:1,category_id:1,bbox:[287.99,144.8,135.73,71.22],area:9222}`; `{id:2,image_id:2,category_id:1,bbox:[190.62,262.78,147.0,160.43]}`; `{id:12,image_id:7,category_id:1,bbox:[578.15,357.83,212.1,269.43]}`; images have `source`, `original_split`, `original_file`
6. COCO, one category `medicine_box` [ROW]
7. human [INFERRED]. Original annotations were "YLO-seg 4-point polygons" and "COCO polygons (24 drug classes merged)" [CARD]
8. count = #annotations per image_id
9. 676 images / 1,027 instances (train 540/806, val 68/121, test 68/100) [CARD]. Every image has at least 1 box (no zero-count images).
10. count question
11. Arabic/French text. Real product boxes. 640 px and up.
12. "How many medicine boxes?" 1/2/3/4+; "Is more than one box shown?" yes/no; "Which source: Arabic-French or medicine_packv2?" (from `source`).
Verdict: **USE** (med).


#### D39.1 / D39.2 — timm/oxford-iiit-pet (rank 1)  _(slice 4)_
1. https://huggingface.co/datasets/timm/oxford-iiit-pet ; original (Parkhi et al. 2012) [PAPER, UNVERIFIED link]
2. `license: cc-by-sa-4.0` [CARD]
3. open
4. 790.3 MB; train parquet 377.6 MB, test 412.7 MB [CARD]
5. first-rows [ROW]: `{"image":389x500,"label":20,"image_id":"Maine_Coon_204","label_cat_dog":0}`; `{"image":333x500,"label":1,"image_id":"american_bulldog_138","label_cat_dog":1}`; `{"image":500x375,"label":18,"image_id":"keeshond_112","label_cat_dog":1}`
6. label (37 breeds), image_id, label_cat_dog [cat, dog] [ROW]
7. human [INFERRED/PAPER, UNVERIFIED quote]
8. cat/dog = label_cat_dog; breed = label
9. Train: cat 1,188 / dog 2,492; about 100 per breed (bombay 96, egyptian_mau 93, …) [ROW]
10. one pet per image (mostly)
11. About 500 px (moderate). **Very likely in model training data.** Owners sometimes appear in the photo.
12. cat or dog; breed 4-way (same-species distractors); "Is this a long-haired cat breed (persian, maine_coon, birman, ragdoll)?" yes/no.
Verdict: **USE** (high). Note the overlap risk.


#### D40.2 / D40.3 — imageomics/2018-NEON-beetles (rank 1)  _(slice 4)_
1. https://huggingface.co/datasets/imageomics/2018-NEON-beetles ; NEON https://www.neonscience.org/ [CARD]
2. `license: cc-by-sa-4.0` [CARD]
3. open
4. 5,866 MB; `BeetleMeasurements.csv` 19.5 MB; individual PNGs and group JPGs separately fetchable [CARD]
5. first-rows individual_specimens [ROW]: `{"image":128x207,"NEON_sampleID":"SERC_010.20180523.CHLAES.01","scientificName":"Chlaenius aestivus","siteID":"SERC","plotID":"SERC_010","individualImageFilePath":"individual_specimens/part_000/A00000001831_specimen_1.png","groupImageFilePath":"group_images/A00000001831.jpg"}`; same with `_specimen_10` (144x201); same with `_specimen_11` (123x195)
6. NEON_sampleID, scientificName, siteID, site_name, plotID, individualImageFilePath, groupImageFilePath
7. human. Group images were annotated in Notes from Nature ("group_images_resized… used for annotation in Notes from Nature") [CARD]. Species ID is from NEON taxonomists [INFERRED].
8. 40.2 tray count = number of individual_specimens rows sharing groupImageFilePath (e.g. A00000051605.jpg → 142; A00000046075.jpg → 1) [ROW stats]. 40.3 genus = first word of scientificName.
9. 577 group images; 11,654 individual specimens. Species e.g. Synuchus impunctatus 1,172, Pterostichus melanarius 364, Chlaenius aestivus 342 [ROW]. "Each image contains a collection of beetles of the same species" [CARD], so one species per tray.
10. Group image = one species and one count. Individual crops are **tiny (about 130x200 px)**, so use group images only.
11. Count completeness assumes every beetle was cropped [UNVERIFIED]. Ethanol-preserved specimens. No people.
12. (a) "How many beetles are in this tray?" bins. (b) "Which genus?" Pterostichus / Synuchus / Chlaenius / Carabus / Amara. (c) "Was this collected at a forest site?" No: site type needs an external map. Use "Are there more than 20 beetles?" yes/no instead.
Verdict: **USE** (med) for group-image count and genus.


#### D41.1 / D41.2 / D41.3: ScreenSpot-Pro (rank 1). One dataset, three tasks  _(slice 5)_
1. **Landing**: https://huggingface.co/datasets/likaixin/ScreenSpot-Pro · GitHub https://github.com/likaixin2000/ScreenSpot-Pro-GUI-Grounding · **Files**: https://huggingface.co/api/datasets/likaixin/ScreenSpot-Pro/tree/main/annotations · repo id `likaixin/ScreenSpot-Pro` [CARD]
2. **Licence**: HF card YAML `license: mit` [CARD]. GitHub LICENSE: "MIT License … Copyright (c) 2026 Kaixin Li" (https://raw.githubusercontent.com/likaixin2000/ScreenSpot-Pro-GUI-Grounding/main/LICENSE) [CARD]. No research restriction and no form.
3. **Access**: open (`gated: False`) [CARD]
4. **Size**: 1,619 files, 3,376 MB total. 26 annotation JSONs, one per app/OS; smallest `annotations/illustrator_windows.json` = 0.02 MB. Each screenshot is its own PNG (largest 22.9 MB). Not a single archive. [CARD]
5. **Sample-first proof**: `curl -L https://huggingface.co/datasets/likaixin/ScreenSpot-Pro/resolve/main/annotations/illustrator_windows.json` (31 entries) [ROW]
   - `{"img_filename": "illustrator_windows/screenshot_2024-11-29_17-39-25.png", "bbox": [2618, 193, 2790, 221], "instruction": "select ellipse tool", "id": "illustrator_windows_0", "application": "illustrator", "platform": "windows", "img_size": [5120, 1440], "ui_type": "text", "group": "Creative"}`
   - `{"img_filename": "illustrator_windows/screenshot_2024-11-29_17-42-44.png", "bbox": [2802, 623, 2868, 649], "instruction": "group the selected contents", "id": "illustrator_windows_1", "application": "illustrator", "platform": "windows", "img_size": [5120, 1440], "ui_type": "text", "group": "Creative"}`
   - `{"img_filename": "illustrator_windows/screenshot_2024-11-29_17-54-35.png", "bbox": [3632, 639, 3758, 662], "instruction": "don't use compression", "id": "illustrator_windows_2", "application": "illustrator", "platform": "windows", "img_size": [5120, 1440], "ui_type": "text", "group": "Creative"}`
6. **Schema**: `img_filename` str; `bbox` [x1,y1,x2,y2] target element; `instruction` str (grounding command, not used here); `application` str (app id); `platform` str (windows/macos/linux); `img_size` [w,h]; `ui_type` text/icon; `group` str (Dev/Creative/CAD/Scientific/Office/OS) [ROW]
7. **Label origin**: human. Annotators captured screenshots of real professional apps that they operate (the card's app table lists version and OS) [CARD]. The paper's annotation method was not read [UNVERIFIED]. `application`, `platform` and `group` are the capture context, not model output [INFERRED].
8. **Answer rule**: D41.1 answer = `application` (dedupe by `img_filename`). D41.2 answer = `platform`. D41.3 answer = `group`.
9. **Classes**: 23 apps + common_{windows,macos,linux}. Card table: VS Code, PyCharm, Android Studio, Quartus, VMware, Photoshop, Premiere, Illustrator, Blender, FL Studio, Unreal, DaVinci, AutoCAD, SolidWorks, Inventor, Vivado, MATLAB, Origin, Stata, EViews, Word, PowerPoint, Excel [CARD]. Each app appears on exactly one OS in the table [CARD], so D41.2 is confounded with app (see risks). Pick-one, so negatives are not applicable.
10. **Per-image fit**: one app per screenshot [INFERRED from per-app folders]. Several instructions point to the same image, so dedupe on `img_filename`.
11. **Risks**: very large images (5120×1440 and up); downscaling to 1536 px makes small text unreadable, but app identity survives [INFERRED]. Possible user names or file paths in screenshots [INFERRED]. ScreenSpot-Pro is a popular GUI benchmark, so contamination risk is high. OS is perfectly correlated with app, so D41.2 can be solved by app recognition; balance with the `common_*` OS screenshots.
12. **Templates**: "Which application is open? {Excel, Word, PowerPoint, VS Code}" · "Which OS is this screenshot from? {Windows, macOS, Linux}" · "Which category of software is shown? {Development, Creative, CAD, Scientific, Office, Operating system}".
- **Verdict**: USE (high).


#### D42.1 / D42.2: Enrico (rank 1)  _(slice 5)_
1. **Landing**: https://github.com/luileito/enrico · **Files**: https://raw.githubusercontent.com/luileito/enrico/master/design_topics.csv. Screenshots: http://userinterfaces.aalto.fi/enrico/resources/screenshots.zip, or HF mirror `Leonardo6/enrico` (https://huggingface.co/datasets/Leonardo6/enrico) [CARD]
2. **Licence**: GitHub LICENSE "MIT License · Copyright (c) 2020 Luis A. Leiva, Asutosh Hota, Antti Oulasvirta" (https://raw.githubusercontent.com/luileito/enrico/master/LICENSE) [CARD]. Mirror says apache-2.0 [CARD], which differs from the owner. Use the owner's MIT.
3. **Access**: open
4. **Size**: labels CSV 1,461 lines (<0.1 MB) [ROW]. Screenshots SINGLE ARCHIVE 110 MB (README) [CARD]. HF mirror parquet 125.8 MB [CARD]. Single images can be fetched through datasets-server `/rows` (signed image URL per row) [INFERRED]
5. **Sample-first proof**: `curl -L .../design_topics.csv | head` [ROW]
   - `screen_id,topic` / `50245,tutorial`
   - `320,list`
   - `39729,login`
   - Mirror rows also fetched (first-rows of `Leonardo6/enrico`): assistant answers "tutorial", "list", "login" with images 1080×1920, 1080×1920, 540×960 [ROW]
6. **Schema**: `screen_id` int (RICO screen id), `topic` str (one of 20 design topics) [ROW/CARD]
7. **Label origin**: human. "We have manually curated a random sample of 10k UIs from Rico … 1460 UIs classified according to 20 design topics" [CARD]. Screenshots come from RICO; the RICO *view-hierarchy annotations* were rejected as machine labels, but these topic labels are manual.
8. **Answer rule**: D42.1 answer = `topic` (restrict to a 4–6 option subset, e.g. {login, list, form, gallery, settings, tutorial}). D42.2: yes if `topic == "login"`, no otherwise.
9. **Classes** [CARD]: bare 76, dialer 6, camera 8, chat 11, editor 18, form 103, gallery 144, list 265, login 141, maps 9, mediaplayer 32, menu 79, modal 67, news 59, other 52, profile 63, search 35, settings 90, terms 39, tutorial 163. D42.2 has real negatives: 141 yes vs 1,319 no.
10. **Per-image fit**: one topic per screen [CARD]. Drop `other` and `bare`.
11. **Risks**: RICO apps date from about 2017, so the look is dated. Screens may hold user names or emails [INFERRED]. The categories are somewhat subjective, e.g. list vs news [INFERRED]. RICO is common in training data. 540×960 resolution is acceptable.
12. **Templates**: "What type of screen is this? {login, list, form, gallery, settings, tutorial}" · "Is this a login screen? {yes, no}" · "Is this an onboarding/tutorial screen? {yes, no}".
- **Verdict**: USE (high).


#### D43.1 / D43.2 / D43.3: ChartBench (rank 1)  _(slice 5)_
1. https://huggingface.co/datasets/SincereX/ChartBench · repo `SincereX/ChartBench` · files `test.jsonl`, `data/test.zip` [CARD]
2. **Licence**: card YAML `license: mit` [CARD]. The card also carries an `extra_gated_prompt` ("You agree to not use the dataset to conduct experiments that cause harm to human subjects…"), but the API reports `gated: False` and files downloaded without login [CARD/ROW].
3. **Access**: open
4. **Size**: total 10,449 MB. `test.jsonl` 3.86 MB. Test images are a SINGLE ARCHIVE `data/test.zip` of 227.67 MB. A 64 KB tail range read found the zip end-of-central-directory: 10,552 entries, central directory 1.29 MB. Single images can therefore be pulled by HTTP range ("remote zip") [ROW]; the per-file extraction itself was not tested [UNVERIFIED].
5. **Proof**: downloaded `test.jsonl` (10,500 records) [ROW]
   - `{"id": 1000, "image": "./data/test/bar/horizontal_percent_stacked/chart_1/image.png", "type": {"chart": "bar", "image": "horizontal_percent_stacked", "task": "CR", "QA": "Acc+"}, "conversation": [{"label": "Yes", "query": "This graph is a bar chart, instead of others chart."}, {"label": "No", "query": "This graph is a others chart, instead of bar chart."}]}`
   - `{"id": 1001, … "task": "VE" …, "conversation": [{"label": "Yes", "query": "According to this chart, the percentage of Malaysia at Year 2022 is 5.78."}, {"label": "No", "query": "According to this chart, the percentage of Malaysia at Year 2022 is 14.80."}]}`
   - `{"id": 1002, … "task": "VC" …, "conversation": [{"label": "Yes", "query": "According to this chart, at Year 2016, the percentage of Philippines is higher than Vietnam."}, {"label": "No", "query": "According to this chart, at Year 2016, the percentage of Vietnam is higher than Philippines."}]}`
6. **Schema**: `id` int; `image` path inside the zip; `type.chart` (9 coarse types); `type.image` (42 subtypes); `type.task` ∈ {CR chart recognition, VE value extraction, VC value comparison, GC global conception, NQA numeric QA}; `conversation[]` = {`query` assertion, `label` Yes/No or a number for NQA} [ROW]
7. **Label origin**: generator. Charts are plotted from known data, and assertions are built from that data (paired true/false) [INFERRED from paired templates; paper not read, UNVERIFIED].
8. **Answer rule**: D43.1 answer = `type.chart` (choose 4–6 options from the 9). D43.2: take a `task=="VC"` record and pick either conversation item; answer = `label`. D43.3: same, with `task=="VE"`.
9. **Classes**: chart counts (records) bar 3250, line 1250, pie 1250, combination 1000, radar 1000, area 750, box 750, scatter 750, node_link 500. Tasks 2,100 each. Yes 8,456 / No 8,444, so real negatives are balanced by construction. 2,100 unique images [ROW]
10. **Per-image fit**: one chart type per image; each assertion has a single answer.
11. **Risks**: synthetic look. Data values were possibly LLM-generated [UNVERIFIED]. The "combination" type is ambiguous for chart-type questions, so exclude it. The CR assertion "instead of others chart" is odd phrasing, so build our own question from `type.chart`.
12. **Templates**: "What type of chart is this? {bar, line, pie, area, scatter, box}" · "At Year 2016, is Philippines higher than Vietnam? {yes, no}" · "Does the chart show Malaysia at Year 2022 = 5.78? {yes, no}".
- **Verdict**: USE (med; the archive is sampleable but per-file extraction was not tested).


#### D43.4 / D43.5: CharXiv (rank 1)  _(slice 5)_
1. https://huggingface.co/datasets/princeton-nlp/CharXiv (owner org) · templates in https://raw.githubusercontent.com/princeton-nlp/CharXiv/main/src/constants.py [CARD]
2. **Licence**: card YAML `license: cc-by-sa-4.0` [CARD]. Charts are arXiv figures whose copyright varies [INFERRED].
3. **Access**: open
4. **Size**: 375.9 MB total; `images.zip` 141.45 MB; `test.parquet` 91.67 MB. validation parquet size UNVERIFIED (<92 MB by elimination [INFERRED]). Single rows via `/rows`.
5. **Proof**: first-rows (validation) [ROW]
   - `{"figure_path":"images/0.jpg","num_subplots":2,"subplot_row":1,"subplot_col":2,"descriptive_q1":7,"descriptive_a1":"60","descriptive_q3":11,"descriptive_a3":"Yes","reasoning_q":"Which model shows a greater decline in accuracy from Session 1 to Session 9…","reasoning_a":"Joint-CNN"}` (image 1024×496)
   - `{"figure_path":"images/2.jpg","num_subplots":1,"descriptive_q1":2,"descriptive_a1":"W_H","descriptive_q2":8,"descriptive_a2":"0.1","descriptive_q3":7,"descriptive_a3":"0.12"}` (1024×760)
   - `{"figure_path":"images/3.jpg","num_subplots":2,"descriptive_q1":18,"descriptive_a1":"1 by 2","descriptive_q3":19,"descriptive_a3":"2"}` (1024×502)
6. **Schema**: `descriptive_qK` int = template id (1–19, e.g. 11 "Do any lines intersect?", 18 "layout of the subplots", 19 "number of subplots" [CARD constants.py]); `descriptive_aK` str answer; `num_subplots` int16; `reasoning_q/a` str [ROW]
7. **Label origin**: human. Answers are human-curated per the benchmark design [INFERRED; paper not read, UNVERIFIED].
8. **Answer rule**: D43.4: find K where `descriptive_qK == 11`; answer = `descriptive_aK` (Yes/No). D43.5: answer = `num_subplots` bucketed {1,2,3,4,5+}, or `descriptive_aK` where q=19.
9. **Classes**: Yes/No balance for q11 UNVERIFIED (row 0 shows "Yes"). Subplot counts include 1 and 2 [ROW].
10. **Per-image fit**: one answer per template per figure.
11. **Risks**: test-split answers may be withheld [UNVERIFIED], so use validation. Real arXiv figures are likely in pretraining.
12. **Templates**: "Do any lines intersect? {yes, no}" · "How many subplots? {1,2,3,4,5+}" · "What is the subplot layout? {1 by 1, 1 by 2, 2 by 2, …}"
- **Verdict**: USE (med; label origin is inferred from the benchmark design).


#### D45.1 / D45.3 / D45.4: ScienceQA (rank 1)  _(slice 5)_
1. Owner https://github.com/lupantech/ScienceQA · HF `derek-thomas/ScienceQA` (linked from the owner README as the official HF copy) [CARD]
2. **Licence**: **conflict**. HF YAML `cc-by-sa-4.0` [CARD]. The owner README has an "MIT license" badge, then "This work is licensed under a [MIT License](http://creativecommons.org/licenses/by-nc-sa/4.0/)" and a CC BY-NC-SA 4.0 badge [CARD]. Treat it as CC BY-NC-SA 4.0 (non-commercial, fine for testing).
3. **Access**: open
4. **Size**: 626.5 MB; test parquet 122.39 MB (single file per split) [CARD]. `/rows` serves single items.
5. **Proof**: first-rows (train) [ROW]
   - `{"question":"Which of these states is farthest north?","choices":["West Virginia","Louisiana","Arizona","Oklahoma"],"answer":0,"task":"closed choice","grade":"grade2","subject":"social science","topic":"geography","skill":"Read a map: cardinal directions"}`
   - `{"question":"Identify the question that Tom and Justin's experiment can best answer.","choices":["Do ping pong balls stop rolling … 30° angle or a 45° angle?","Do ping pong balls travel farther … 45° angle?"],"answer":1,"subject":"natural science"}`
   - `{"question":"Identify the question that Kathleen and Bryant's experiment can best answer.","choices":["…wax or when it does not have a layer of wax?","…thin layer of wax or a thick layer of wax?"],"answer":0}`
6. **Schema**: `image` (nullable), `question`, `choices[]`, `answer` int8 index, `hint`, `task` (closed choice / yes or no / true-or false), `grade`, `subject`, `topic`, `category`, `skill`, `lecture`, `solution` [ROW]
7. **Label origin**: human (curriculum questions; the source curriculum is UNVERIFIED) [INFERRED]
8. **Answer rule**: D45.1 answer = `choices[answer]`. D45.3 answer = `subject`. D45.4: filter `task == "yes or no"`, answer = `choices[answer]`. Keep only rows with a non-null image.
9. **Classes** (test, 4,241 rows): subject natural 2,252 / language 1,100 / social 889. task closed choice 4,090, yes or no 113, true-or false 38 [statistics]. Image-bearing share UNVERIFIED.
10. **Per-image fit**: one answer per item.
11. **Risks**: licence conflict. Many items are answerable from text alone, so filter items whose `hint` is empty and the question requires the image [INFERRED]. Widely trained on. Small images [UNVERIFIED].
12. **Templates**: "Which choice answers the question? {choices}" · "What subject is this item? {natural science, language science, social science}" · "Which grade band? {1–3, 4–6, 7–9, 10–12}"
- **Verdict**: USE (med; licence conflict flagged, both licences allow research).


#### D46.1 / D46.2: DocLayNet (rank 1)  _(slice 5)_
1. Owner https://github.com/DS4SD/DocLayNet · HF `docling-project/DocLayNet-v1.2` (owner org) and the smaller re-pack `pierreguillou/DocLayNet-base` [CARD]
2. **Licence**: owner LICENSE: "Community Data License Agreement – Permissive – Version 1.0 … grant(s) to You a worldwide, non-exclusive, irrevocable … right to: (a) Use Data; and (b) Publish Data" (https://raw.githubusercontent.com/DS4SD/DocLayNet/main/LICENSE) [CARD]. Permissive.
3. **Access**: open
4. **Size**: v1.2 39,770.6 MB, smallest shard 266.5 MB [CARD]. `pierreguillou/DocLayNet-base` converted parquet test = **187.2 MB**. `pierreguillou/DocLayNet-small` test parquet = **17.0 MB** but only 49 pages [/parquet endpoint]. Use `/rows` for single pages.
5. **Proof**: `/rows?dataset=pierreguillou/DocLayNet-base&config=DocLayNet_2022.08_processed_on_2023.01&split=test` [ROW]
   - `{'id':'0','doc_category':'financial_reports','collection':'ann_reports_00_04_fancy','original_filename':'OTC_NSANY_2004.pdf','page_no':17,'coco_width':1025,'coco_height':1025} categories=[9,9,9,9,9,9,9,9,9,4,4,4,5,5,5]`
   - `{'id':'1','doc_category':'financial_reports','original_filename':'NASDAQ_FFIN_2002.pdf','page_no':10} categories=[9 ×25…]`
   - `{'id':'2','doc_category':'manuals','collection':'manuals','original_filename':'IBM-i-s5445349.pdf','page_no':437} categories=[4,4]`
   - v1.2 first-rows also seen: `category_id [10,10,10,7,8,10,10,5,7]`, `metadata.doc_category "financi…"` [ROW]
6. **Schema** (base): `categories` list of ClassLabel {0 Caption, 1 Footnote, 2 Formula, 3 List-item, 4 Page-footer, 5 Page-header, 6 Picture, 7 Section-header, 8 Table, 9 Text, 10 Title}; `bboxes_block`; `doc_category` str; `collection`; `original_filename`; `page_no` [ROW]. (v1.2 uses `category_id` with a different id base [INFERRED].)
7. **Label origin**: human. "DocLayNet is hand-annotated by well-trained experts" and "Annotations are crowdsourced" [CARD v1.2]. `doc_category` is a source-collection label [INFERRED].
8. **Answer rule**: D46.1 answer = `doc_category`. D46.2: yes if 8 (Table) ∈ `categories`, no otherwise.
9. **Classes** (base test 499 pages): financial_reports 172, scientific_articles 103, laws_and_regulations 86, manuals 77, patents 32, government_tenders 29 [statistics]. Table yes/no counts UNVERIFIED, but rows 0–2 have no Table, so real negatives exist [ROW].
10. **Per-image fit**: one category per page. Table presence is unambiguous given full human labelling.
11. **Risks**: renders are 1025×1025. Real company names appear in public filings (low risk). DocLayNet is widely used in training.
12. **Templates**: "What kind of document is this page from? {financial report, scientific article, law/regulation, government tender, manual, patent}" · "Does the page contain a table? {yes,no}" · "Does the page contain a picture? {yes,no}"
- **Verdict**: USE (high).

> **Merge note (DocLayNet).** This card replaces slice 1's DocLayNet card (D6.2 / D6.3 / D7.2), which had weaker licence evidence (v1.1 card line, not the owner LICENSE). Facts carried over from slice 1: the licence line on the v1.1 card reads "License: [CDLA-Permissive-1.0](https://cdla.io/permissive-1-0/)" [CARD]. `pierreguillou/DocLayNet-small` has a 17.0 MB test parquet (49 pages: financial_reports 20, scientific_articles 10, laws_and_regulations 8, manuals 7, government_tenders 2, patents 2) [ROW], plus a DocLayNet-small row `{"original_filename":"EN-Declaration on Honour.pdf","page_no":4,"num_pages":6,"collection":"eu_tenders","doc_category":"government_tenders"}` [ROW]. Slice-1 answer rules: D6.2 = `doc_category` (6 options); D7.2 yes if `doc_category == government_tenders`; D6.3 yes if the Table class id is in the category list (id 8 in the base/small ClassLabel; the v1.2 COCO 1-based mapping is [UNVERIFIED]). Re-checked 2026-10-01: base test rows 0–2 match.


#### D46.3: LoC Beyond Words (rank 1)  _(slice 5)_
1. https://huggingface.co/datasets/biglam/loc_beyond_words · files `data/val_20_percent.json` [CARD]
2. **Licence**: card YAML `license: cc0-1.0` [CARD]. biglam is a mirror; the LoC Labs original licence page was not fetched [UNVERIFIED]. The underlying Chronicling America pages are public-domain-era newspapers (WWI) [CARD].
3. **Access**: open
4. **Size**: 2,394 MB total; **COCO annotation JSON val 1.43 MB**, train 5.56 MB; validation parquet 238.31 MB; `images.zip` 1,193 MB. Image URLs inside the JSON point to `s3.amazonaws.com/ndnp-jpeg-surrogates/...` (one page each) [ROW]
5. **Proof**: downloaded `val_20_percent.json` (712 images, 9,931 annotations) [ROW]
   - image `{'file_name': '7.jpg', 'url': 'http://s3.amazonaws.com/ndnp-jpeg-surrogates/pst_davey_ver01/data/sn83045211/00237287678/1917110301/0875.jpg', 'height': 1134, 'width': 898, 'id': 7}`
   - annotation `{'id': 1790, 'bw_id': '5da8f595ebaf180001004056', 'image_id': 7, 'category_id': 1, 'bbox': [773, 68, 117, 408], 'area': 47736}`
   - annotation `{'id': 2186, 'bw_id': '5d98848aebaf180001003669', 'image_id': 7, 'category_id': 1, 'bbox': [552, 144, 110, 140], 'area': 15400}`
   - (first-rows train row 0: objects with `category_id` 0 and 6 on a 912×1330 page)
6. **Schema**: COCO `images[]{id,file_name,url,width,height}`, `annotations[]{image_id, category_id, bbox, area, bw_id}`, `categories` 0 Photograph, 1 Illustration, 2 Map, 3 Comics/Cartoon, 4 Editorial Cartoon, 5 Headline, 6 Advertisement [ROW]
7. **Label origin**: human, crowdsourced. "Volunteers marked seven types of visual content" [CARD]
8. **Answer rule**: yes if any annotation on the page has `category_id == k`, no otherwise.
9. **Classes** (val 712 pages, pages with ≥1 box): Photograph 489 yes / 223 no; Illustration 154/558; Map 32/680; Comics 109/603; Editorial cartoon 53/659; Headline 618/94; Advertisement 510/202 [ROW]. Real negatives exist, but see risk.
10. **Per-image fit**: multi-label page. The yes/no per class is clean if the marking is complete.
11. **Risks**: crowdsourcing may miss regions, so a "no" can be a missed mark. Use Photograph/Map/Comics, where misses are less likely [INFERRED]. Old scans at about 900×1300 px are low-res for small text. Old photos may show identifiable people (historical, not identified).
12. **Templates**: "Does this page contain a photograph? {yes,no}" · "Does it contain a map? {yes,no}" · "Which of these is NOT present? {photograph, map, advertisement, comic}"
- **Verdict**: USE (med; possible missed marks).


#### D46.4: Early printed books font groups (rank 1)  _(slice 5)_
1. https://huggingface.co/datasets/biglam/early_printed_books_font_detection. Mirror of Zenodo "Dataset of Pages from Early Printed Books with Multiple Font Groups" (DOI 10.5281/zenodo.33666…, truncated in card) [CARD]
2. **Licence**: card YAML `cc-by-nc-sa-4.0` [CARD]. Zenodo record not fetched [UNVERIFIED].
3. **Access**: open
4. **Size**: 44,768.8 MB; shards 438–592 MB [CARD]. Single pages via `/rows`.
5. **Proof**: first-rows [ROW]: `{"labels":[7]}` (fraktur, 1761×3221); `{"labels":[8]}` (schwabacher, 2000×2663); `{"labels":[11]}` (gotico_antiqua, 1137×1623)
6. **Schema**: `image`, `labels` list of ClassLabel {greek, antiqua, other_font, not_a_font, italic, rotunda, textura, fraktur, schwabacher, hebrew, bastarda, gotico_antiqua} [ROW]
7. **Label origin**: human: "each labelled by experts with the font group or groups used on the page"; YAML `annotations_creators: expert-generated` [CARD]
8. **Answer rule**: keep pages with `len(labels)==1`; answer = that label name.
9. **Classes**: test 4,554 pages; labels per page min 1, max 4, mean 1.11 [statistics]. Per-class counts UNVERIFIED.
10. **Per-image fit**: about 90% single-label [INFERRED from mean 1.11]. Filter on `len==1`.
11. **Risks**: non-commercial. Large images (fine). Fine-grained typography is hard. Little web overlap [INFERRED].
12. **Templates**: "Which typeface group is used? {antiqua, italic, textura, fraktur, schwabacher, rotunda}" · "Is this page set in a blackletter type? {yes,no}" · "Does the page contain Greek type? {yes,no}"
- **Verdict**: USE (med; Zenodo licence not confirmed).


#### D46.5: biglam/illustrated_ads (rank 1)  _(slice 5)_
1. https://huggingface.co/datasets/biglam/illustrated_ads [CARD]
2. **Licence**: YAML `cc0-1.0` [CARD]
3. **Access**: open
4. **Size**: **single parquet 48.05 MB** (whole dataset, under the cap) [CARD]
5. **Proof**: first-rows [ROW]
   - `{"file":"pst_fenske_ver02_data_sn84026497_00280776129_1880042101_0834_002_6_96.jpg","label":0,"pub_date":"1880-04-21","score":0.9609,"ocr":"H. II. IIASLKT & SOXN, Dealers in General Merchandise…","place_of_publication":"Tionesta, Pa.","image":388x395}`
   - `{"file":"scu_carlacox_ver01_…_007_6_93.jpg","label":0,"pub_date":"1870-04-14","place_of_publication":"Anderson Court House, S.C.","image":503x292}`
   - `{"file":"in_england_ver02_…_004_6_97.jpg","label":0,"pub_date":"1865-12-13","name":"The Indianapolis daily herald.","image":487x1665}`
6. **Schema**: `label` ClassLabel {text-only, illustrations}; `box` and `score` (Newspaper Navigator **detector** crop box and confidence, machine); `ocr` (machine); metadata [ROW]
7. **Label origin**: mixed. Crops are machine-located ("The adverts were located by Newspaper Navigator"), but the `label` is human: "annotations_creators: expert-generated", "Sampling and annotation used nnanno" [CARD]. The label we use is human.
8. **Answer rule**: yes if `label == 1` (illustrations).
9. **Classes**: 549 total; text-only 376, illustrations 173 [/rows count]
10. **Per-image fit**: one label per crop.
11. **Risks**: small crops (about 300–500 px), so they blur at 1536 (tiny-image risk). Card calls it "a realistic rather than clean example" [CARD].
12. **Templates**: "Does this advert contain an illustration? {yes,no}" · "Which decade? {1860s,1870s,1880s,1890s,1900}" (from `pub_date`) · "Text-only advert? {yes,no}"
- **Verdict**: USE (med; small images).


#### D47.3 / D47.5 / D48.5 / D49.1 / D49.2 / D50.1 / D50.2 / D50.3: Open Images V7 human-verified image-level labels (rank 1). Full card here; per-task rows below  _(slice 5)_
1. **Landing**: https://storage.googleapis.com/openimages/web/factsfigures_v7.html · **Files**: https://storage.googleapis.com/openimages/v7/oidv7-val-annotations-human-imagelabels.csv, https://storage.googleapis.com/openimages/v7/oidv7-class-descriptions.csv, https://storage.googleapis.com/openimages/2018_04/validation/validation-images-with-rotation.csv. Images: `https://open-images-dataset.s3.amazonaws.com/validation/<ImageID>.jpg` (checked: HTTP 200, 232,515 bytes for `041ec0633447b467`) [ROW]
2. **Licence**: "The annotations are licensed by Google LLC under CC BY 4.0 license. The images are listed as having a CC BY 2.0 license." Plus the caveat "we make no representations or warranties regarding the license status of each image" [CARD]
3. **Access**: open
4. **Size**: val human labels CSV **28.39 MB** (downloaded); test labels 93.6 MB (not fetched); class descriptions 0.50 MB; val image metadata 15.2 MB; images are one file each (about 0.2–1 MB) [ROW, Content-Length]
5. **Proof**: rows below per task (format `ImageID,Source,LabelName,Confidence`) [ROW]
6. **Schema**: `ImageID`; `Source` ∈ {verification, crowdsource-verification}; `LabelName` (MID, map via class descriptions); `Confidence` 1 = human-verified present, 0 = human-verified **absent** [ROW]
7. **Label origin**: human. Every val row is human verification (539,987 `verification` + 78,197 `crowdsource-verification`) [ROW]. Candidate labels to verify were machine-proposed [INFERRED], so negatives are hard negatives.
8. **Answer rule**: for class C: yes if a row (ImageID, C, 1) exists; no if a row (ImageID, C, 0) exists; **skip** if no row exists.
9. **Classes and balance** (val, 41,620 images; positives / verified negatives) [ROW]: Weapon 192/196 · Handgun 20/47 · Rifle 99/29 · Knife 83/19 · Firearm 93/87 · Alcoholic beverage 279/98 · Beer 96/70 · Wine 96/56 · Cocktail 153/80 · Brand 166/329 · Logo 79/9 · Advertising 110/97 · Billboard 32/9 · Poster 263/100 · Screenshot 116/330 · Mobile phone 119/46 · Laptop 77/59 · Computer monitor 88/52 · Lipstick 51/53 · Cosmetics 55/117 · Dress 788/217 · Handbag 71/59 · Sunglasses 134/102 · Cigarette 6/0 (too few) · "Nudity" class absent.
10. **Per-image fit**: presence yes/no is clean per class. For pick-one (D49.2) use images with exactly one positive among {Mobile phone, Laptop, Computer monitor} and no positive for the others. The others may be unverified, a risk.
11. **Risks**: Flickr photos of people (faces present; do not ask identity). The images-with-rotation CSV holds Flickr author names (exclude). Some original URLs are dead (use the S3 mirror). Open Images is heavily used in pretraining. Verification of a machine-proposed label can miss small objects.
12. **Templates**: "Does the image contain a weapon? {yes,no}" · "Is an alcoholic beverage shown? {yes,no}" · "Which device is shown? {mobile phone, laptop, computer monitor}"
- Rows per task [ROW]:
  - D50.1 Weapon `/m/083kb`: `041ec0633447b467,verification,/m/083kb,1.0` · `044a3e7c7b006202,verification,/m/083kb,1.0` · `01ff40138b875524,verification,/m/083kb,0.0`
  - D50.2 Alcoholic beverage `/m/012mj`: `00101a0160a05d31,verification,/m/012mj,1.0` · `009dfe7e81b732cb,verification,/m/012mj,1.0` · `01d160559286c930,verification,/m/012mj,0.0`
  - D50.3 Brand `/m/01cd9`: `02deba0102b5ce2a,verification,/m/01cd9,1.0` · `02f42085acfad7bc,verification,/m/01cd9,1.0` · `008e12a039f69f8a,verification,/m/01cd9,0.0`
  - D47.3 Advertising `/m/011s0`: `02f5d2bc887486c6,crowdsource-verification,/m/011s0,1` · `0349ccadeb208cbc,verification,/m/011s0,1.0` · `02f42085acfad7bc,verification,/m/011s0,0.0`
  - D47.5 Billboard `/m/01knjb`: `03c35bdfffbea53f,verification,/m/01knjb,1.0` · `083b651122889187,verification,/m/01knjb,1.0` · `2595ea3831d8da6a,verification,/m/01knjb,0.0`
  - D48.5 Lipstick `/m/06c7f7`: `05ae3737394ad03a,crowdsource-verification,/m/06c7f7,1` · `08f80f26c1d57ba1,crowdsource-verification,/m/06c7f7,1` · `01d715f1c31014df,verification,/m/06c7f7,0.0`
  - D49.1 Screenshot `/m/01zbnw`: `007f71665b0812a7,verification,/m/01zbnw,1.0` · `012dc31b561d4214,verification,/m/01zbnw,1.0` · `008e12a039f69f8a,verification,/m/01zbnw,0.0`
  - D49.2 Mobile phone `/m/050k8` / Laptop `/m/01c648` / Computer monitor `/m/02522`: `012dc31b561d4214,crowdsource-verification,/m/050k8,1` · `00a36f96e31731c4,crowdsource-verification,/m/01c648,1` · `00ec4ba83d648c33,verification,/m/02522,0.0`
- **Verdict**: USE (high) for D50.1, D50.2, D50.3, D47.3, D48.5, D49.1. USE (med) for D47.5 (only 9 negatives in val; add the test CSV) and D49.2 (pick-one exclusivity is partly unverified).


#### D48.1 / D48.2 / D48.3: Fashionpedia (rank 1)  _(slice 5)_
1. Owner https://fashionpedia.github.io/home/index.html · GitHub https://github.com/cvdfoundation/fashionpedia · HF `detection-datasets/fashionpedia` [CARD]
2. **Licence**: HF card: "Fashionpedia is licensed under a Creative Commons Attribution 4.0 International License" [CARD]. The owner home page has a "Terms of Use" link whose text could not be extracted [UNVERIFIED].
3. **Access**: open
4. **Size**: 3,478.9 MB; train shards about 480–490 MB; val split 1,158 images (via `/rows`) [CARD]
5. **Proof** (first-rows, train) [ROW]
   - `{"image_id":23,"width":682,"height":1024,"objects":{"category":[23,23,33,10],"bbox":[[445,910,505,983],…]}}` (shoe, shoe, neckline, dress)
   - `{"image_id":25,"width":683,"height":1024,"objects":{"category":[2,33,31,31,13,7,22,22,23,23]}}` (sweater, neckline, sleeve×2, glasses, shorts, sock×2, shoe×2)
   - `{"image_id":26,"width":1024,"height":683,"objects":{"category":[13,29,28,32,32,31,31,0,31,31,18,4,6,23,23]}}`
6. **Schema**: `objects.category` ClassLabel over 46 names (0 shirt/blouse … 10 dress, 13 glasses, 14 hat, 24 bag/wallet, 31 sleeve …), `bbox`, `area` [ROW]
7. **Label origin**: human: "a dataset with everyday and celebrity event fashion images annotated with segmentation masks…" (ontology "built by fashion experts") [CARD]
8. **Answer rule**: D48.1: yes if 10 ∈ categories, no otherwise. D48.3: yes if 24 ∈ categories. D48.2: among garment ids 0–12, if exactly one distinct id is present, answer = it.
9. **Classes** (val 1,158 images, by `/rows`): dress 506 (so 652 negatives), bag 205, hat 74, glasses 130, pants 313, skirt 162, jacket 179. Images with exactly one garment class: 496 [ROW]
10. **Per-image fit**: multi-object. Use the rules above. For D48.2 use the 496 single-garment images.
11. **Risks**: people and celebrities are visible (no identity questions). Exhaustive labelling is assumed for negatives [INFERRED]. Images about 1024 px.
12. **Templates**: "Is the person wearing a dress? {yes,no}" · "What is the main garment? {dress, pants, skirt, jacket, shirt/blouse, coat}" · "Is there a bag? {yes,no}"
- **Verdict**: USE (high).

> **Merge note (Fashionpedia).** This card replaces slice 2's Fashionpedia card (D12.3), which had no class counts. Facts carried over from slice 2: smallest unit `data/val-00000-of-00001.parquet` 84.85 MB [CARD]. The D12.3 rule keeps images where exactly one of {dress=10, pants=6, skirt=8, shorts=7} is present. Slice 2 rated the yes/no templates "Tier B with caution" because exhaustive annotation is [UNVERIFIED]. Some images are celebrity event photos, so never ask identity questions [CARD]. Re-checked 2026-10-01: first-rows match.


### B2. MAYBE, SKIP and GATED candidates, one line each, with the test each one failed

The full field values for each line are in the combined CSV (Appendix D). "Failed test" uses the spec's USE tests: licence stated, open access, pasted rows, human or generator label origin, answer computable, real negatives (yes/no), plus the known traps.

| Task(s) | Dataset (repo or landing) | Verdict | Failed test (from the slice card) |
|---|---|---|---|
| D1.2 | shivalikasingh/cheques_sample_data | MAYBE | no licence; tiny 512×256 images; label origin UNVERIFIED |
| D1.2 | aniketVerma07/handwritten_cheque_vqa_dataset | MAYBE | tiny 512×256 cheque images; mixed non-cheque VQA rows; origin UNVERIFIED |
| D1.5 | Bankstatemently/bank-statement-parsing-benchmark | MAYBE | only 5 documents; PDFs need rendering |
| D1.6 | Panhapich/bank-statement-detection | MAYBE | real negatives unverified; 406–508 MB shards |
| D3.1 | Kaggle anujms/car-damage-detection | MAYBE | licence "Unknown"; login; no rows pasted |
| D3.4 | gigwegbe/damaged-car-dataset-annotated | MAYBE | no licence; positives only; possible CarDD (consent-gated) mirror |
| D3.4 | tugberkkalay/autodamageiq-vehicle-damage-dataset | SKIP | machine labels (GPT-4o HITL) plus CarDD |
| D3.5, D23.3 | tanganke/stanford_cars (card kept: slice 1) | MAYBE | no licence on card; tiny images (85×64) present; origin UNVERIFIED |
| D4.1, D4.2, D4.4 | QCRI/MEDIC | MAYBE | label origin not stated (merged sources; "unlabelled" file carries labels); terms-of-use.txt unread |
| D5.1 | Symage/coherent-forms-1040-cms1500-i9 | GATED | login + accept terms (see GATED table) |
| D5.2 | chinmays18/medical-prescription-dataset | MAYBE | no licence; empty card; origin unknown |
| D5.4 | sansverse/medical-bill-samples | SKIP | no labels (answer cannot be computed) |
| D6.1 | tech4humans/signature-detection | GATED | login + accept terms |
| D6.2, D9.4, D7.4 | nutrientdocs/document-classification-benchmark | MAYBE | dataset-level licence only "other" (per-row tags given); 453.7 MB single parquet |
| D7.1 | mturski/CheckboxQA | MAYBE | mirror with no images (PDFs off-site, multi-page); page index not given, so the answer needs a person to find the page |
| D7.3 | konfuzio/funsd_plus | GATED | consent prompt and unread FUNSD+ LICENSE |
| D7.3 | nielsr/funsd | MAYBE | licence unverified; no question–answer links in the mirror |
| D8.3, D8.5 | zimka/midv-DoB-mini | MAYBE | no licence stated |
| D8.4 | cactuslab/IDNet-2025 | MAYBE | SINGLE ARCHIVE per country (≥1,354 MB); no rows |
| D8.4 | zodumair/sifta-document-forgery-dataset | MAYBE | no licence; document type unknown; origin UNVERIFIED |
| D8.6 | cloverx-id/indonesian-id-card-dummy (config `augmented`) | MAYBE | negatives are third-party real photos that may contain real IDs; licence chain unclear |
| D10 | d4rk3r/resumes-raw-pdf | SKIP | label is a folder name, not a checkable visual fact |
| D10.2, D10.3 | ilovelevi/business_card_dataset | MAYBE | no licence; origin unknown; `is_business_card` all true |
| D11.1, D11.6 | shelfwise-by-form/SKUs_on_shelves_PL | SKIP | single huge archive (11,422 MB); no annotation rows |
| D11.2 | openfoodfacts/price-tag-classification | MAYBE | licence not stated |
| D11.4 | openfoodfacts/price-tag-extraction | SKIP | machine labels (Gemini 3 Flash); no licence |
| D11.5 | benjamintli/retail-product-checkout (RPC) | MAYBE | label origin unverified; licence version conflict (NC-SA 4.0 text vs 2.0 tag) |
| D12.1 | suvadityamuk/amazon-berkeley-objects | MAYBE | images only in ≥172 MB shards or 256 px; label origin inferred; NC file in source bucket |
| D12.2, D48.4 | ashraq/fashion-product-images-small (card kept: slice 5) | SKIP | tiny 60×80 images; no licence; Kaggle original login-gated |
| D13.1 | Densu341/Fresh-rotten-fruit | SKIP | single archive 3,053.59 MB; openrail licence for data unclear; likely duplicate of the used AgML set |
| D13.1 | jojogo9/freshness | SKIP | 100 px tiny images; label-map conflict |
| D13.2, D31.5 | darthraider/fruit-ripeness-detection-dataset (card kept: slice 2) | MAYBE | label origin unverified; licence from mirror only |
| D13.3 | marcusklasson/GroceryStoreDataset | MAYBE | no licence stated |
| D14.1 | ethz/food101 | MAYBE | licence is "scientific fair use" only; train labels are machine-assigned |
| D14.2 | ybli/yolo-kitchen-hygiene-safety-detection | SKIP | mirror with no images (off-site link) |
| D14.3 | Voxel51/food-waste-dataset | SKIP | machine-generated annotations |
| D16.1 | howell0123/shipping_container | MAYBE | no licence; unknown origin; positives only |
| D16.2 | Guztavu/container-damage | GATED | login + accept terms |
| D16.3 | HassanBinAli/Damaged_Parcel_boxes | SKIP | mirror with no images (Google Drive paths) |
| D16.3 | Parcel3D (Zenodo 8032204) | SKIP | single huge archive (45,838.3 MB); `other-nc` |
| D17.1 | OliseNS/person-face-package-home-security-detection | SKIP | single archive (22,658 MB); likely machine-assisted labels; face data |
| D18.1, D19.5 | Voxel51/IndoorSceneRecognition (MIT Indoor-67) | MAYBE | licence conflict (MIT tag vs "research purposes only"); D18.2 polygons not exhaustive (no negatives) |
| D18.1 | keremberke/indoor-scene-classification | MAYBE | same licence conflict; 416 px resize |
| D19.2 | CubiCasa5K original (Zenodo 2613548) | SKIP | single archive 5,469.5 MB |
| D19.2 | OldDelorean/FloorplanQA-Layouts | MAYBE | no images (must be rendered; becomes a generator task) |
| D19.3 | murai-lab/WorcesterMA_Housing_Facades | MAYBE | card itself warns redistribution clearance is unconfirmed; street addresses |
| D19.4 | Jonathandav/facade-styles | MAYBE | labels are text-to-image prompt specs, not verified renders |
| D19.6 | Voxel51/FloorPlanCAD | MAYBE | licence conflict (BY-SA tag vs BY-NC text); fewer than 3 full rows; JSON over cap |
| D20.1 | steveharianto/waste-garbage-management-dataset | SKIP | tiny images (~200 px); scraped; origin unknown |
| D20.2 | DroneWaste (Zenodo 17045559) | MAYBE | images only as a 3,882.5 MB single archive; annotator type UNVERIFIED |
| D20.3 | pedropro/TACO | MAYBE | no licence stated; positives only for "litter present" |
| D20.4 | Akhila-9849/Garbage_Bin_overflow_images | SKIP | positives only; no annotations |
| D21.1, D21.2 | Voxel51/severstal_steel_defects | MAYBE | licence unverifiable (Kaggle rules behind login) |
| D21.4, D21.5 | iluvvatar/wood_surface_defects | MAYBE | label origin not quoted |
| D21.6 | rikkarth/welding-defect-object-detection | MAYBE | label origin not documented |
| D22.2 | RobotHuman/PCB_defect (HRIPCB) | MAYBE | licence provenance (MIT claim on re-upload); positives only |
| D22.3 | keremberke/pcb-defect-segmentation | MAYBE | label origin; positives only; counts |
| D24.1 | Voxel51/FGVC-Aircraft | MAYBE | label origin UNVERIFIED; non-commercial research only |
| D25.1 | Dhika/defect_rail | SKIP | licence unknown; tiny 224×224; origin UNVERIFIED |
| D26.1 | keremberke/excavator-detector | MAYBE | label origin |
| D26.2, D30.5 | mohammadnajeeb/concrete_crack_images | SKIP | tiny 227×227 images |
| D26.3 | tsrobcvai/ROI-1555 rebar | MAYBE | no licence; label semantics ("straight-N") unverified |
| D26.4 | LouisChen15/ConstructionSite | GATED | login + accept terms |
| D27.1 | moondream/synthetic-gauges-v6 | MAYBE | no licence |
| D27.1 | Mileeena/synthetic-analog-gauges | GATED | login + accept terms |
| D27.2 | rsnogueira/Watermeter | MAYBE | no licence; origin unverified; value leaks via filename |
| D27.2 | UniDataPro/water-meters | MAYBE | no rows pasted (first-rows 500); preview of a paid set; NC-ND |
| D27.3 | Praekelt/ElectricityMeterReadings1o4 | MAYBE | no licence; origin unverified |
| D27.4 | utilitimetersai/Annotated-Mechanical-And-LCD-Utility-Meter-Dials-Dataset | GATED | manual approval |
| D28.1 | ELPV (zae-bayern; bardroh/elpv-el-defects) | MAYBE | label origin not quoted; 300×300 px (near tiny) |
| D28.2 | silera/broken-insulators-synthetic-detection | MAYBE | positives only |
| D28.4 | metalmerge/solar-panel-inspection | MAYBE | no licence; origin; folder-only proof |
| D28.5 | jonathan-roberts1/Airbus-Wind-Turbines-Patches | SKIP | tiny 128×128; presence only, no damage label |
| D28.6 | Manishsahu53/Solar-Panel-Thermal-Drone-UAV-Images | SKIP | single archives 2.25–8.56 GB; no labels |
| D29.1 | LibreYOLO/corrosion-bi3q3 | MAYBE | label origin; few negatives (5/105) |
| D29.2 | ZhiyaYang/sewer-defect-crack-dataset | MAYBE | no licence; origin |
| D29.2 | SRuibo/Sewer-pipe-defects | MAYBE | class codes unexplained; positives only |
| D29.3 | samhormozian/GasLeakPlumes | SKIP | no licence; effectively positives only; 480×296 near-duplicate video frames |
| D30.3 | Arpitraj01/Pothole_classification | MAYBE | label origin; severity criteria undocumented |
| D30.4, D30.6 | Voxel51/dacl10k | MAYBE | label origin not quoted on card |
| D30.5 | CODEBRIM (Zenodo 2620293; h4tem/codebrim) | GATED | licence agreement; single archives 7.9–12.2 GB |
| D31.4 | Project-AgML/maize_weed_detection | MAYBE | zero-weed negatives unverified (count question is USE-able) |
| D31.6 | EnmmmmOvO/insect-pest-dataset | SKIP | tiny images; unnamed integer labels |
| D31.7, D33.5 | timm/eurosat-rgb | SKIP | 64×64 tiny images |
| D32.4 | imageomics/fish-vista | MAYBE | no dataset-level licence; per-row CC BY-NC |
| D32.5 | Francesco/aquarium-qlnqy | MAYBE | licence version unstated ("cc") |
| D33.4 | Simuletic/Long_Distance_Wildfire_Smoke_Detection_Dataset | SKIP | positives only (239/239); licence conflict |
| D34.2 | jhboyo/ppe-dataset | SKIP | likely duplicate of the used hard-hat source; no label rows |
| D34.5 | c3rl/seatbelt-detection-v2 | MAYBE | image and label origin undocumented (possibly generated) |
| D34.6, D35.5 | Simuletic/CCTV_Incident_Dataset_Fall_Lying_Down_Detection | SKIP | no label rows; likely positives only |
| D34.7 | ccclllwww/smoking_classification | SKIP | viewer cannot load; no labels seen |
| D35.1, D35.2 | badsaarow/d-fire (D-Fire) | MAYBE | no licence stated anywhere; class-id map unverified |
| D35.1 | Vertex-Test/FireSmokeDataset | MAYBE | label/image origin undocumented (possible AI-generated images); 5% negatives |
| D35.1 | seawsurf/fire_smoke_dataset_fasdd_cv | SKIP | single archive 3,410.6 MB |
| D35.3 | Subh775/WeaponDetection | MAYBE | 29 messy classes; negatives unverified |
| D35.3 | jsalazar/US-Real-time-gun-detection-in-CCTV… | MAYBE | NC; no label rows (zip > 50 MB) |
| D36.3 | Francesco/vehicles-q0x2v | MAYBE | licence version unstated |
| D36.4 | dronefreak/LISA-Traffic-Lights | MAYBE | NC-SA; tiny lights (6–16 px); class map unverified |
| D36.5 | GTSRB (tanganke/gtsrb, bazyl/GTSRB) | not carded | tiny crops; found in search only (Gap) |
| D36.6 | Voxel51/fisheye8k | MAYBE | NC-SA; label rows not pasted |
| D36.x | emb-ai/traffic-sign-bench | SKIP | map scenes, not photos of signs |
| D37.4 | hmnshudhmn24/noisy-medical-document-images-ocr | MAYBE | no licence; real hospital names on fake documents |
| D37.4 | RootCauseAnalytics/synthetic-australian-medical-documents-sample | MAYBE | NC; sales sample; PDFs need rendering; contains diagnosis fields |
| D37.x | Ronysalem/medical-forms-dataset | SKIP | real clinical notes (privacy, diagnosis content); 8 images |
| D38.4 | Pjshana/pill-reference-images | MAYBE | no licence; labels need an external NDC lookup |
| D38.x | wony98/healtheat-pill-yolo | GATED | upstream AI Hub / Kaggle terms |
| D38.5 | ABINSHA/blister_data | SKIP | no licence, no README, image-only rows |
| D39.1 | microsoft/cats_vs_dogs | MAYBE | licence unknown |
| D39.3 | Voxel51/StanfordDogs | MAYBE | no licence; label rows not pasted |
| D40.1 | sosiklab/NES-plankton-classifier-2022-dataset | SKIP | tiny 40–100 px images (excellent expert labels otherwise) |
| D40.1 | bloombio/phytoplankton-microscopy | MAYBE | no rows (first-rows "Not found") |
| D40.4 | rotsl/colony-cfu-counting-coco | GATED | manual approval |
| D40.5 | Etiiir/Pollen | SKIP | 64 px renders; rows are camera poses; NC |
| D42.3 | osunlp/Multimodal-Mind2Web | MAYBE | label origin inferred; OpenRAIL fit for data unclear |
| D42.4 | zxy6654/multiwindow-gui-defect-benchmark | SKIP | no label column (answer cannot be computed) |
| D43.2, D43.6 | FigureQA (vikhyatk/figureqa mirror) | GATED | owner click-through agreement; mirror has no licence |
| D43.6 | DVQA (vikhyatk/dvqa) | MAYBE | no licence |
| D44.1–D44.3 | FloodNet Track 2 (takara-ai mirror) | MAYBE | licence only on the mirror |
| D44.4 | jonathan-roberts1/WHU-RS19 | MAYBE | licence not from owner; imagery rights |
| D44.5 | Voxel51/VisDrone2019-DET | MAYBE | licence conflict (BY-SA tag vs NC-SA text) |
| D44.6 | jonathan-roberts1/PatternNet | SKIP | 256 px tiny images |
| D45.2 | lmms-lab-encoder/ai2d | MAYBE | no licence |
| D46.6 | biglam/icdar2021-historical-document-dating | MAYBE | owner licence and label origin not verified |
| D47.1, D47.2 | Pitt Image Ads (Mindykkyan/PittadsDB-AdsPics; dchen278/pitt-ads-full) | MAYBE | no licence found; mirror path mapping unconfirmed |
| D50.4 | axonstan/LogoDet-3K | MAYBE | licence only on the mirror |
| D50.5 | prithivMLmods/Watermark-or-Not-20K | MAYBE | label origin unknown |

**Other probes rejected without full cards (verbatim lists from the slices).**

Slice 1:
- **Naiscorp/car-damage-dataset:** labels are opaque folder ids "001"…"N" (`{"label":0}`) [ROW]; licence `other` [CARD] → SKIP.
- **ikuldeep1/vehicle-damage-fraud-image-balanced:** labels "0"/"1" with no card [ROW][CARD] → SKIP.
- **Reverb/CarDamage:** despite the name, the classes are `frontJOimages`, `backQAimages1`, `frontUAEimages`… with files `card_175.png` [ROW][CARD]. These look like front/back **identity cards from Jordan, Qatar and UAE**, possibly real; the README is 24 bytes → SKIP (personal-data risk).
- **erickcrus/BID_Dataset:** 20 rows of Brazilian ID ground truth [ROW]; no licence [CARD] → SKIP (too small; licence).
- **GIGAParviz/stamp_detection2:** label txt files only, no images in the viewer [ROW]; no licence → SKIP.
- **FrenchCastle/xray-baggages-customs:** licence `other`; zips of 6.4–7.2 GB each; viewer 501 [CARD] → SKIP (single huge archives; security screening, not customs paperwork).
- **unc061/cz-stk-odometer:** a tabular VIN → km index from Czech inspections, not images [CARD] → not applicable to D3.6.

Slice 3:
- `tugberkkalay/autodamageiq-vehicle-damage-dataset`: CarDD (rejected) plus "HITL (GPT-4o labeled)", i.e. machine labels.
- `Naiscorp/car-damage-dataset`: card says "**Unlabeled**".
- `ybli/yolo-railway-track-defect-object-detection` and `ybli/yolo-car-brake-pad-flaw-detection`: README only, 0 files (a mirror with no images).
- `saluslab/Rail-VIVID`: CC BY 4.0, 109 GB of vibration CSVs and frames, no image-level defect labels.
- `KeenForgeAI/NEU-DET-corrected`: "Upstream license: none stated", and 200 px images.
- `tutitata/PCB_COMPONENTS_LABELLED`: no licence, 8.4 GB, partial upload per its card.
- `LouisChen15/ConstructionSite`: `gated=auto`, cc-by-nc-4.0, so GATED (login + accept).
- `Synanthropic/reading-analog-gauge`: two zips of 1.2–1.4 GB, the licence file was not read, and the viewer labels are just folder names. Cannot verify.
- `cvtechniques/Road_Damage_Detection_USA`: 13.3 GB plus 444 MB zips (single archive), superseded by dronefreak.



## Appendix C. Part C question-expansion recipes (USE datasets)

Reproduced from each slice. Three recipes appear twice because their datasets were carded twice: DocLayNet (slices 1 and 5), Fashionpedia (slices 2 and 5) and the forklift set (slices 2 and 4). Both versions are kept because they list different Tier B items. Where they overlap, the slice-5 (DocLayNet, Fashionpedia) and slice-2 (forklift) versions match the kept cards. All slices share the Tier C rules: `label_origin: model` tag, a separate score column, blind agreement from a second model of a different family, and the model under test never writes or validates questions.


### C1. Slice 1 — Money and paperwork (D1–D10)

General rule for every dataset: Tier A and B rows carry `label_origin: human|generator` and `tier: A|B`. Tier C rows always carry `label_origin: model`, `tier: C`, and the writer model's id. They are stored in a separate file and never pooled into Tier A/B scores. A Tier C question is kept only if a second, different model answers it identically, blind to the first model's answer. The model under test never writes questions. The most useful Tier C outputs are (1) rewordings of Tier A questions (for robustness), (2) harder distractors that are still verifiably wrong under the Tier A rule, and (3) natural-language variety in locale or phrasing.

**jaganadhg/cheque-synthetic-images (D1.1)**
- A: bank (4).
- B: (1) "Is the signature box in the lower-right quadrant?" (`sign.xmin > W/2 and sign.ymin > H/2`); (2) "Which field is topmost? date / IFSC / name" (min ymin); (3) "Is the amount box wider than the account-number box?" (width compare); (4) "Which field is NOT where it usually is?" Skip this one: there is no variation.
- C: rewordings ("Which bank printed this cheque leaf?"); distractor bank names from other Indian banks (must not be the 4 truths). Avoid asking for printed account numbers (personal data).

**jsdnrs/ICDAR2019-SROIE (D2.1)**
- A: total (4 options); date (4); company (4).
- B: (1) "Is the total above RM 50?" (`float(total) > 50`); (2) "Is the receipt dated in 2018?" (parse date); (3) "Which of these strings does NOT appear on the receipt?" (3 from `words` plus 1 from another receipt); (4) "Does the word 'INVOICE' or 'TAX INVOICE' appear?" (substring in `words`; note that `words` is human transcript, not OCR); (5) "How many text lines does the receipt have? <30 / 30–50 / >50" (`len(words)`).
- C: rephrase questions in Malay or English; distractor totals that also appear on the receipt (subtotal, cash tendered), validated against `entities.total`.

**albertobarnabo/synthetic-receipts-ocr (D2.2, D2.3)**
- A: payment class; locale; tax_included.
- B: (1) item count bucket (`n_items`); (2) "Is a loyalty line printed?" (`loyalty != null`); (3) "Was change given?" (`change != null`); (4) "Which item is the most expensive? 4 names" (`argmax lines.total`); (5) "Is the VAT rate 22%? yes/no" (from `taxes.rate`). Also pair `image_clean` with `image_photo` to test degradation robustness.
- C: locale-specific rephrasings; distractors from same-locale payment words.

**HV09/synthetic-bilingual-invoices-200 (D2.4, D2.5)**
- A: PO present; Hijri date; currency; language style.
- B: (1) "Is VAT about 5% of subtotal?" (`abs(vat/subtotal - 0.05) < 0.001`); (2) "Is quantity above 200?" (`qty`); (3) "Which total is correct? 4 numbers" (`total` plus perturbed values); (4) "Which invoice number is printed? 4" (`invoice_number`).
- C: Arabic rewordings; Eastern-Arabic numeral distractors. The second model must agree.

**katanaml-org/invoices-donut-data-v1 (D2.6)**
- A: line-item count; invoice number.
- B: (1) VAT rate class (`item_vat`); (2) "Is gross total above $1,000?" (parse summary); (3) "Which invoice date year? 4 years"; (4) "Does an IBAN appear?" (`header.iban` non-empty).
- C: rewordings; item-description distractors.

**DrBimmer/comprehensive-car-damage (D3.1–D3.3)**
- A: damaged yes/no; front/rear; none/breakage/crushed.
- B: (1) "Is this an undamaged rear view?" (label == R_Normal); (2) "Which of these is NOT shown: front breakage / rear crush / front normal?" (one true, two false); (3) a pair task, "Do these two images show the same end of the car?" (only if two-image prompts are allowed; otherwise skip).
- C: claims-adjuster phrasing ("Would you file this as a front-end collision?"), kept separate. Distractors such as "flood damage" are unverifiable, so they are disallowed in A/B.

**QCRI/CrisisMMD (D4.1, D4.3)**
- A: damage severity (3); infrastructure damage yes/no (from `label_image`).
- B: (1) "Is there any damage (mild or severe)?" (label ≠ little_or_no); (2) disaster type from `event_name` (hurricane_harvey/irma/maria → hurricane; california_wildfires → wildfire; mexico/iraq_iran earthquake → earthquake; srilanka_floods → flood); (3) "Which event is this from? 4 events" (`event_name`). Note: the event label is metadata, not a visual property, so it is weaker.
- C: rewordings; never use the tweet text as a question source (personal data).

**DocLayNet (D6.2, D6.3, D7.2)**
- A: doc_category (6); government tender yes/no.
- B: (1) table present; (2) picture present; (3) "How many tables? 0 / 1 / 2 / 3+" (count of the class id); (4) "Is there a formula?" (Formula id); (5) "Which element is largest by area? text / table / picture" (`area` argmax per class).
- C: legal-review phrasing ("Is this a statute page?"); distractor categories that are near synonyms (borrow nutrientdocs OOV synonyms).

**cloverx-id/indonesian-id-card-dummy flat (D8.1)**
- A: sex; blood type; marital status.
- B: (1) "Is the card valid for life (SEUMUR HIDUP)?" (`berlaku_hingga`); (2) "Which province? 4" (`provinsi`); (3) "Is the holder born before 1980?" (parse `tempat_tanggal_lahir`); (4) "Which occupation is printed? 4" (`pekerjaan`). Avoid `agama` (religion).
- C: English rewordings of Indonesian field names.

**Voxel51/synthetic_us_passports_easy (D8.2, D8.3)**
- A: expiry after issue; nationality; sex.
- B: (1) "Is the holder over 18 on the issue date?" (dob vs date_of_issue); (2) "Is the passport expired as of 2026-10-01?" (date_of_expiration < ref); (3) "Which passport number is printed? 4" (distractors with one digit changed); (4) "Does place of birth equal nationality?" (compare labels).
- C: KYC-analyst phrasing; distractor countries close in name.

**hyturing/US_tax_forms_donut (D9.1)**
- A: form face (6 within a family).
- B: (1) page 1 vs 2; (2) Schedule vs numbered form; (3) "Which form family? 1040 / 4562 / 2106 / 6251" (prefix).
- C: rewordings ("Which IRS attachment is this?").

**singhsays/fake-w2 (D9.2, D9.3)**
- A: box 13 statutory; state in box 15.
- B: (1) "Is federal withholding above 30% of wages?" (box2/box1); (2) "How many box-12 codes are filled? 0–4" (count of non-"None" codes); (3) "Is there a second state line?" (`box_15_2_state` not None); (4) "Which box-12a code? 4".
- C: payroll-clerk phrasing.

### C2. Slice 2 — Goods, places and logistics (D11–D20)

General rules for all datasets:
- Tier C questions are always stored with `label_origin: model` and kept in a separate table and score column. They are never merged into Tier A/B accuracy.
- A second model from a different family must agree on the answer, or the item is dropped.
- The model under test never writes or validates questions.
- The most useful Tier C content: rewordings of Tier A/B questions, harder distractor options drawn from the same class list, and natural-language variety (shopper, auditor or driver voice).

#### D11.3 price-tag-detection
- **A:** none directly (detection only). The count of boxes is effectively Tier A for counting because the boxes are human.
- **B:**
  - (1) count bins: n = len(category_id)
  - (2) "Is any tag cut off at the edge?": any bbox coordinate ≤ 0.001 or ≥ 0.999
  - (3) "Are the tags in a single row?": the spread of y-centres is under 0.1
  - (4) "Is the largest tag more than 10% of the image?": max (y2−y1)(x2−x1) > 0.1
  - (5) "More tags in the top or bottom half?": compare y-centre counts
- **C:** price-reading questions ("what is the price on the left-most tag?"). These are model-written and need dual-model agreement. Distractors: nearby prices.

#### D12.3 Fashionpedia
- **A:** garment set present (the 27 garment classes).
- **B:**
  - (1) "Which of these is NOT worn?" with 3 present and 1 absent class. Only use absent classes, and caution because exhaustiveness is unverified.
  - (2) shoe count bins
  - (3) "Is the dress larger than the jacket?" by bbox area
  - (4) "Does the outfit include an accessory (bag, hat, glasses, watch, belt)?"
  - (5) "Topmost garment: hat vs glasses vs none"
- **C:** style/occasion wording and colour questions (untrusted). Never ask about the person's identity.

#### D12.4 ABO-Edit
- **A:** white-background yes/no (generator); `product_type` (catalogue).
- **B:**
  - (1) "Is the tilt ≥ N°?" from `simplified_rotation_prompt` (target only)
  - (2) "Is this the lifestyle or the studio version of the product?"
  - (3) Pairing: "Is the product in image 1 the same type as …?" Not allowed, because the spec requires one image per question, so skip it.
  - (4) "Which product type is NOT shown: LAMP / CHAIR / SOFA / TABLE?" with 3 distractors from other rows
- **C:** material and colour questions (the `object_description` field is VLM-written, so it counts as Tier C at best).

#### D13.4 grocery-images-5class
- **A:** item class.
- **B:**
  - (1) "fruit vs non-fruit" (apple/banana vs bread_roll/cheese)
  - (2) "baked good?"
  - (3) "dairy?"
  - (4) "Which is NOT shown?" with 1 true class and 3 others as options
- **C:** quantity ("how many bananas?"), ripeness and packaging questions (model-written, verified by a second model).

#### D15.1 forklift
- **A:** person present (yes/no).
- **B:**
  - (1) forklift count bins
  - (2) person count bins
  - (3) "Is the person larger than 10% of the forklift's box area?"
  - (4) "Is the person to the left or right of the forklift?" by comparing bbox x-centres
  - (5) "Does the forklift fill more than half the frame?"
- **C:** "Is the forklift carrying a load?", "Is the operator seated?" (untrusted).

#### D15.2 cardboard box anomaly
- **A:** damaged yes/no.
- **B:**
  - (1) "Floor or conveyor?" from `loc-`
  - (2) "Which conveyor, b1 or b2?" (low value)
  - (3) Restrict to each box's own images: "Is this the same box id as reference X?" This is single-image only if X is described in text, so skip it.
  - Keep B to (1).
- **C:** defect type ("crushed corner / tear / wet / open flap"). This is model-written and especially valuable, but it must be agreed by two models.

#### D19.1 CubiCasa5K-YOLO
- **A:** door count, window count (human polygons).
- **B:**
  - (1) "More windows than doors?"
  - (2) wall-segment count bins
  - (3) "Is there a window on the top edge of the plan?": any class-2 polygon with min y < 0.1
  - (4) "Total openings (doors + windows) above 15?"
  - (5) "Which is most common: wall segments / doors / windows?"
- **C:** room-name reading (OCR-like: "Is there a sauna?"), which is common in Finnish plans. Untrusted.

#### D20.1 TrashNet
- **A:** material class.
- **B:**
  - (1) recyclable vs trash
  - (2) fibre vs non-fibre
  - (3) "Is this item glass or plastic?" (hard pair)
  - (4) "Which stream is NOT correct for this item?" (3 wrong options + 1 right, inverted)
- **C:** object name ("is it a bottle, a can or a box?") and "is it crushed?" (untrusted).

### C3. Slice 3 — Industry and infrastructure (D21–D30)

**Common Tier C rules for all USE datasets.**
- Every model-written question is stored with `label_origin: model` and kept in a separate table. It is never scored together with Tier A or Tier B.
- A second model from a different vendor must answer each question independently and agree before the question is kept.
- The model under test never writes or validates questions for itself.
- The most useful Tier C outputs are:
  - rewordings of the Tier A question (plain operator language, e.g. "Would you scrap this part?");
  - harder distractors, e.g. visually similar defect names;
  - natural-language variety.
- Tier C never introduces new facts.

#### KolektorSDD (D21.3)
- **Tier A:** "Does this surface show a crack?", answered from `has_defect`.
- **Tier B:**
  1. Board-level: "Do any of the 8 surfaces of board kosNN show a defect?" Answer = any(`has_defect`) grouped by `board_id`.
  2. "Which of these two images (same board) is defective?" The pair has one defective and one clean image.
  3. "How many of these k images are defective?" Count of `has_defect`.
  4. Defect size bucket "small / large" from the mask area of `ground_truth`. This requires decoding the mask but no person looking.
- **Tier C:** reword as an accept/reject decision, or ask a model to describe the crack location. That is not trusted.

#### DeepPCB (D22.1)
- **Tier A:** test image means yes, template means no.
- **Tier B:**
  1. "Is there an open-circuit defect?" (type 1 ∈ lines).
  2. "Which defect type is most frequent here?" Use the argmax of the type counts, keeping only images with a unique max.
  3. "How many defects: 1–3 / 4–7 / 8+?" (line count).
  4. "Which defect type is NOT present: open / short / spur / pin-hole?" Use images where exactly one of the 4 types is absent.
  5. "Is there a defect in the top-left quadrant?" From the box coordinates.
- **Tier C:** distractor names such as "solder bridge" or "lifted pad" to test vocabulary robustness.

#### Tyres (D23.1)
- **Tier A:** good vs defective.
- **Tier B:** the schema has only one label, so Tier B is limited to two forms. (1) A paired question: "Which of these two tyres is defective?" (one from each repo). (2) A set count: "How many of these 4 tyres are defective?"
- **Tier C:** ask a model to name the defect type (crack, bulge, tread wear) as an *untrusted* label. This needs dual-model agreement and is never scored as truth.

#### Powerline components and faults (D28.2/D28.3)
- **Tier A:** broken insulator yes/no and broken cable yes/no.
- **Tier B:**
  1. "How many insulators (class 3 + class 1) are visible: 1–2 / 3–5 / 6+?"
  2. "Is vegetation present near the line?" (class 5).
  3. "Is a tower visible?" (class 4).
  4. "Which fault is present: broken insulator only / broken cable only / both / neither?" From label sets.
  5. "Are there more cables than insulators?" Compare the counts.
- **Tier C:** severity wording ("Should this span be scheduled for repair?") and distractor faults such as "flashover marks" or "bird nest". Untrusted.

#### Synthetic meter reading (D27.1)
- **Tier A:** "What does the gauge read?" Answer = `synth_dial_value`, with 3 distractors at ±1–3 minor ticks.
- **Tier B:**
  1. "What is the maximum value on the scale?" (from `range_answer`/`minmax_answer`).
  2. "Is the reading above half of full scale?" (value vs (min+max)/2).
  3. "Is the reading below zero / below the minimum mark?" (value < min).
  4. "Which quarter of the scale is the needle in?" (4 bins).
  5. "Is the needle in the right half of the image?" (`needle_bbox` centre x > width/2).
- **Tier C:** unit wording (bar, psi), operator phrasing ("Is pressure within 0–8?") and rounding variants. Untrusted.

#### RDD2022 (D30.1/D30.2)
- **Tier A:** pothole yes/no, and the damage type for single-class images.
- **Tier B:**
  1. "Is there any crack (D00, D10 or D20)?"
  2. "How many damage instances: 0 / 1–2 / 3+?"
  3. "Which damage type is NOT present (from 4)?" Use images with exactly 3 types absent and 1 present, or the reverse.
  4. "Is the damage mostly longitudinal or transverse?" Compare counts of class 0 vs class 1.
  5. "Which country/platform is this?" (from the `file_name` prefix, e.g. China_Drone). This is metadata, not damage, so use it as a control.
- **Tier C:** reword as maintenance priority ("Does this need urgent repair?"). Untrusted, because it is a judgement. Distractors can be "rutting" or "patch".

### C4. Slice 4 — Living systems and safety (D31–D40)

Rules for every dataset below. Tier C items always carry `label_origin: model` and are scored in a separate column. They are never merged into Tier A/B scores. They count only when a second, different model family independently gives the same answer. The model under test never writes questions. The most useful Tier C outputs are paraphrases of the Tier A question, harder same-category distractors (e.g. look-alike breeds or species), and natural-language variety ("Would a site inspector flag this photo?" mapped back to the Tier A rule).

**Project-AgML/crop_pest_disease_classification (D31.1).** A: healthy yes/no; problem label. B: (1) crop identity from `crop`; (2) "Is the problem caused by an insect (fall armyworm, grasshoper, green mite, leaf beetle, leaf miner) or a disease?" via a fixed lookup; (3) "Which of these problems does NOT occur on {crop}?" from the crop×label co-occurrence table; (4) pairwise "Are these two images the same crop?". C: symptom wording, distractors from the same crop.

**Project-AgML/plant_seedlings_aarhus (D31.2).** A: species. B: (1) crop vs weed; (2) grass-like (black_grass, loose_silkybent, common_wheat, maize) vs broadleaf; (3) "Which of these species is NOT a crop?"; (4) monocot/dicot lookup. C: farmer-style paraphrase ("Should the sprayer hit this plant?").

**Project-AgML/oil_palm_fruit_ripeness_classification (D31.3).** A: grade. B: (1) harvest-ready (Ripe) yes/no; (2) reject at mill (Damaged/Empty) yes/no; (3) "Is it past ripe?" (Overripe) yes/no. C: grader paraphrases.

**AGRARIAN/greek_sheep_goats_dataset (D32.1).** A: goats present; majority. B: (1) total animal count bins; (2) "Are there more than N sheep?"; (3) "Is any animal at the image edge?" (bbox x_c±w/2 near 0 or 1); (4) "Is the largest animal a goat?" (by w·h); (5) empty patch yes/no. C: herder wording.

**keremberke/aerial-sheep-object-detection (D32.2).** A: count. B: (1) >10 yes/no; (2) any sheep touching the edge; (3) largest-sheep quadrant (top-left/…) from bbox centre. C: none needed.

**anilbhujel/viewpoint-aware-pig-posture-recognition (D32.3).** A: posture per bbox; per-image counts. B: (1) any standing; (2) count lying (0,1,4); (3) majority posture; (4) "Are more pigs lying than standing?"; (5) which camera type (turret/orb) from the image_id token. C: welfare-inspector phrasing.

**lila-bc-community/channel-islands-camera-traps (D33.1).** A: species. B: (1) count bins; (2) "Is the animal in the left or right half?" (bbox centre); (3) "Is it a mammal?" (fox/rodent/skunk vs bird); (4) "Does the animal fill more than a quarter of the frame?" (area/(W·H)). C: ranger phrasing; distractor species from the same island list.

**Project-AgML/tree_species_classification_slovak_normal_cropped (D33.3).** A: species. B: (1) conifer vs broadleaf; (2) "Which of these is NOT shown?" (3 absent species plus the true one); (3) genus-level lookup. C: forester paraphrase.

**VincentGOURBIN/ppe-detection (D34.1/34.2).** A: no-vest, no-helmet. B: (1) person count bins (class 3); (2) "Are all helmeted persons also vested?" (count helmet ≥ person and no no-vest); (3) "How many people lack a helmet?"; (4) "Which item is missing: helmet / vest / both / neither?". C: safety-officer wording.

**keremberke/forklift-object-detection (D34.3).** A: person with forklift. B: (1) forklift count; (2) "Is the person closer to the left or right of the forklift?" (centre x); (3) "Is the forklift larger than the person?" (area). C: incident-report phrasing.

**keremberke/construction-safety-object-detection (D34.4).** A: per-item missing. B: (1) machinery present (excavators, wheel loader, dump truck); (2) count persons; (3) "Which of these is NOT present: barricade / dumpster / safety net / gloves?"; (4) more hardhats than no-hardhats?. C: inspector wording.

**Turki-Alshuaibi/haris-weapon-detection-dataset-curated (D35.3).** A: weapon yes/no; gun/knife. B: (1) weapon count; (2) "Is the weapon in the upper half?" (y_c); (3) "Is the weapon larger than 5% of the frame?". C: guard paraphrase. Keep severity judgements out of Tier C.

**dronefreak/PKLot (D36.1).** A: per-space occupancy. B: (1) more than half full; (2) free-space bins; (3) camera id from filename; (4) "Are there more vacant than occupied spaces?"; (5) full lot (zero vacant) yes/no. C: driver phrasing ("Will I find a space?" mapped to free > 0).

**cute-face/bike-helmet-dataset (D36.2).** A: all helmeted. B: (1) rider count; (2) riders without helmet count; (3) with / without / mixed. C: traffic-police phrasing.

**morzel85/synthetic-medical-document-recognition-benchmark (D37.1–37.3).** A: category, capture type, clipped. B: (1) page i of n ("Is this the first page?" from `p_1_of_n`); (2) multi-page document yes/no; (3) date format (type_n); (4) skewed yes/no (`ske`); (5) stained yes/no (`sta`). Also exact fields (patient birth date, organisation name) from the FHIR JSON, as generator truth. C: routing-clerk wording. Never ask about diagnoses.

**twinkle-ai/tw-drug-labels-vision (D38.1).** A: source_type; licence prefix. B: (1) imported vs domestic; (2) number of pages (len(images)); (3) "Is this a multi-panel carton?" (len>1 and carton). C: Text fields (drug name, strength) are machine-extracted, so they are Tier C only (`label_origin: machine`, kept separate).

**LibreYOLO/pills-sxdht (D38.2).** A: product or colour. B: (1) pill count; (2) "Is it an Ibuphil product?"; (3) "Which of these products is NOT shown?". C: pharmacist paraphrase.

**ApyHTML19/Medication_Boxes_Arabe_Latin (D38.3).** A: box count. B: (1) more than one box; (2) largest box position (left/right); (3) source subset; (4) "Does any box cover more than 20% of the image?". C: language-of-text questions (unverified).

**timm/oxford-iiit-pet (D39.1/39.2).** A: species, breed. B: (1) "Which of these is NOT a cat breed?"; (2) same-species 4-way distractors; (3) long-haired cat yes/no lookup; (4) terrier group yes/no lookup. C: adoption-listing phrasing; harder look-alike distractors (american_pit_bull_terrier vs staffordshire_bull_terrier).

**imageomics/2018-NEON-beetles (D40.2/40.3).** A: tray count, species. B: (1) >20 beetles; (2) genus; (3) NEON site code from siteID (pick 4); (4) "Are all specimens one species?" (always yes, so use as a sanity control). C: curator phrasing.

### C5. Slice 5 — Digital and knowledge work (D41–D50)

**Rules for all datasets:**
- Tier C items always carry `label_origin: model` and are never mixed into Tier A or B scores.
- A Tier C item is kept only if a second, different-family model answers it the same way without seeing the first model's answer.
- The model under test never writes questions.
- The most useful Tier C work is rewording, harder distractors (visually confusable options) and natural-language variety (ticket-style phrasing).

#### ScreenSpot-Pro (D41.1–3)
- **A**: application, platform, group per screenshot.
- **B**:
  1. "Which of these apps is NOT open?" — the 3 distractors come from other apps in the same `group`.
  2. "Is this a Creative app?" — `group == Creative`.
  3. "Is the screen wider than 3000 px?" — from `img_size` (a metadata check; use sparingly).
  4. "Does this screenshot contain the element '<instruction target>'?" — yes for the paired image. No only if that instruction belongs to another app's annotation file, so it is safe only across apps.
- **C**: ticket-style rewordings ("User says Excel is frozen. Is the screenshot from Excel?"); confusable distractors (Word vs Pages, PyCharm vs IntelliJ).

#### Enrico (D42.1–2)
- **A**: topic.
- **B**:
  1. Yes/no per topic ("Is this a settings screen?").
  2. "Which is NOT this screen's type?" — 3 options from other topics.
  3. Group mapping: {login, form} → "input screen" yes/no.
- **C**: UX-review phrasing; distractors among adjacent topics (list vs news vs gallery).

#### ChartBench (D43.1–3)
- **A**: type.chart, VC and VE assertion labels.
- **B**:
  1. Flip the pair: use the No assertion as the question; the answer is no.
  2. Coarse type: is it a "bar family" chart (bar / combination with bar)?
  3. Subtype pick-one from `type.image`, e.g. horizontal vs vertical stacked.
  4. NQA numeric answer bucketed into 3–4 ranges as pick-one.
- **C**: business phrasing ("Did Platform A outperform B in Month 5?"); distractor values near the true value.

#### CharXiv (D43.4–5)
- **A**: descriptive answers for templates 11 (intersect) and 19 (subplot count).
- **B**:
  1. Layout pick-one (template 18).
  2. "Does the plot have a legend?" — no if the template 12 answer is "Not Applicable", yes otherwise.
  3. "Does it have a colorbar?" — the same rule on template 14/15.
  4. Trend pick-one (template 16) only where the answers are categorical.
- **C**: rewording; harder distractors for layout.

#### ScienceQA (D45.1, 45.3, 45.4)
- **A**: choices[answer], subject, yes/no items.
- **B**:
  1. "Which option is NOT correct?" — pick one of the wrong choices as the answer when there are 3+ choices; the question phrasing must say this.
  2. Topic pick-one (`topic`, e.g. geography / physics / chemistry).
  3. Grade band from `grade`.
  4. Category yes/no ("Is this a map-reading item?" from `skill`).
- **C**: teacher-style rewording; plausible distractor answers written by a model (validated by a second model plus the original key).

#### DocLayNet (D46.1–2)
- **A**: doc_category; table presence.
- **B**:
  1. Presence yes/no for Picture, Formula, Footnote, Title.
  2. "Which element is NOT on this page?" — from present and absent sets.
  3. "Are there more than N text blocks?" — count of id 9.
  4. "Is the table larger than the largest picture?" — compare bbox areas.
  5. Page count bucket from `num_pages` (metadata).
- **C**: archivist rewording; distractor categories (e.g. tender vs law).

#### LoC Beyond Words (D46.3)
- **A**: presence per category.
- **B**:
  1. Counts: "How many photographs? {0, 1, 2, 3+}" from annotation counts.
  2. "Which is NOT present?" over {Photograph, Map, Comics, Advertisement}.
  3. "Is there more advertising area than photo area?" from summed `area`.
  4. Decade of issue from the URL date.
- **C**: research-librarian phrasing.

#### Early printed books fonts (D46.4)
- **A**: single label.
- **B**:
  1. Blackletter family yes/no ({textura, rotunda, bastarda, schwabacher, fraktur} vs roman/italic).
  2. "Does the page mix 2+ font groups?" — `len(labels) > 1`.
  3. "Is Greek present?"
- **C**: limited value; rewording only.

#### illustrated_ads (D46.5)
- **A**: label.
- **B**:
  1. Decade pick-one from `pub_date`.
  2. "Was this published in the 1880s or later?" yes/no.
  3. State pick-one from `place_of_publication`. This is metadata, not visible, so avoid it except as a control.
- **C**: rewording.

#### Open Images V7 (D47.3, D47.5, D48.5, D49.1, D49.2, D50.1–3)
- **A**: explicit per-class 1/0 rows.
- **B**:
  1. Parent/child roll-up: Handgun/Rifle/Shotgun = 1 → Weapon yes. Use only explicit rows, and do not infer negatives through the hierarchy.
  2. "Which of these is present?" — exactly one verified positive and the other options verified 0 on the same image.
  3. "Which of these is NOT present?" — the inverse of 2.
  4. Brand-safety composite: "Does the image contain alcohol OR a weapon?" — yes if either is 1. No only if both are verified 0.
- **C**: moderation-policy phrasing ("Would this image violate a no-weapons ad policy?"). Model-written distractor classes are useful here.

#### Fashionpedia (D48.1–3)
- **A**: category presence.
- **B**:
  1. Count shoes/sleeves bucketed.
  2. "Which accessory is present?" among {bag, hat, glasses, belt} — exactly one present.
  3. "Which garment is NOT worn?"
  4. "Is the dress the largest garment by area?" from `area`.
  5. Upper vs lower garment presence.
- **C**: catalogue-attribute phrasing ("Tag this listing: does it show a dress?"); confusable distractors (cardigan vs sweater, coat vs jacket).


## Appendix D. Combined CSV (all five slices, de-duplicated)

Exact spec columns, 212 rows sorted by domain. Two slice-5 rows had unquoted commas in `answer_rule`; they were re-quoted. For the six duplicate datasets, the dataset-level fields (licence, access, sizes, proof URL, label origin, risk, confidence, unverified fields) on every row come from the kept card. Each row keeps its own task, answer rule, negatives and classes. The cardboard-box row now lists `D15.2;D16.3`, as its card heading does. No verdict changed in the re-check.

```csv
domain,task_id,task,dataset,landing_url,repo_id,licence,licence_quote_url,access,total_mb,smallest_fetch_mb,single_archive,sample_proof_url,rows_pasted,label_origin,answer_rule,has_negatives,classes,one_answer_per_image,personal_data_risk,verdict,confidence,unverified_fields
1,D1.1,Cheque issuing bank,IDRBT synthetic cheques,https://huggingface.co/datasets/jaganadhg/cheque-synthetic-images,jaganadhg/cheque-synthetic-images,apache-2.0,https://huggingface.co/datasets/jaganadhg/cheque-synthetic-images/raw/main/README.md,open,466.1,76.11,no,https://datasets-server.huggingface.co/first-rows?dataset=jaganadhg/cheque-synthetic-images&config=default&split=train,yes,generator,answer=bank,n/a,axis|canara|icici|syndicate,yes,medium (real field patches),USE,high,IDRBT upstream terms
1,D1.2,Amount words vs figures,cheques_sample_data,https://huggingface.co/datasets/shivalikasingh/cheques_sample_data,shivalikasingh/cheques_sample_data,none,UNVERIFIED,open,58.9,5.87,no,https://datasets-server.huggingface.co/first-rows?dataset=shivalikasingh/cheques_sample_data&config=default&split=train,yes,UNVERIFIED,yes if words2num(amt_in_words)==amt_in_figures,UNVERIFIED,match|mismatch,yes,low (fake names),MAYBE,low,licence;label_origin;balance;tiny 512x256
1,D1.2,Amount words vs figures,handwritten_cheque_vqa_dataset,https://huggingface.co/datasets/aniketVerma07/handwritten_cheque_vqa_dataset,aniketVerma07/handwritten_cheque_vqa_dataset,apache-2.0,https://huggingface.co/datasets/aniketVerma07/handwritten_cheque_vqa_dataset,open,481.6,50.19,no,https://datasets-server.huggingface.co/first-rows?dataset=aniketVerma07/handwritten_cheque_vqa_dataset&config=default&split=train,yes,UNVERIFIED,filter cheque queries then words2num compare,yes (611 vs 1070 seen),match|mismatch,yes,low,MAYBE,low,label_origin;balance;tiny images
1,D1.5,Statement type,Bankstatemently benchmark,https://huggingface.co/datasets/Bankstatemently/bank-statement-parsing-benchmark,Bankstatemently/bank-statement-parsing-benchmark,MIT,https://huggingface.co/datasets/Bankstatemently/bank-statement-parsing-benchmark,open,0.4,0.02,no,https://datasets-server.huggingface.co/first-rows?dataset=Bankstatemently/bank-statement-parsing-benchmark&config=default&split=train,yes,generator,answer=documentType,n/a,bank-statement|credit-card,yes,none,MAYBE,med,only 5 docs
1,D1.6,Transaction table on page,bank-statement-detection,https://huggingface.co/datasets/Panhapich/bank-statement-detection,Panhapich/bank-statement-detection,MIT,https://huggingface.co/datasets/Panhapich/bank-statement-detection,open,3534.8,406.22,no,https://datasets-server.huggingface.co/first-rows?dataset=Panhapich/bank-statement-detection&config=default&split=train,yes,generator,yes if len(objects.category)>0,UNVERIFIED,table,yes,none,MAYBE,med,negatives
2,D2.1,Receipt total,ICDAR2019 SROIE,https://huggingface.co/datasets/jsdnrs/ICDAR2019-SROIE,jsdnrs/ICDAR2019-SROIE,CC-BY-4.0,https://huggingface.co/datasets/jsdnrs/ICDAR2019-SROIE/raw/main/README.md,open,509.8,191.05,no,https://datasets-server.huggingface.co/first-rows?dataset=jsdnrs/ICDAR2019-SROIE&config=default&split=train,yes,human,correct=entities.total; distractors=other money strings in words,n/a,n/a,yes,medium (cashier names),USE,high,annotation workflow
2,D2.2;D2.3,Payment method; receipt country,synthetic-receipts-ocr,https://huggingface.co/datasets/albertobarnabo/synthetic-receipts-ocr,albertobarnabo/synthetic-receipts-ocr,apache-2.0,https://huggingface.co/datasets/albertobarnabo/synthetic-receipts-ocr/raw/main/README.md,open,4084.7,227.56,no,https://datasets-server.huggingface.co/rows?dataset=albertobarnabo/synthetic-receipts-ocr&config=default&split=eval&offset=0&length=100,yes,generator,map fields.payment to cash|card|contactless|wallet; locale,n/a,US|UK|DE|IT|FR; payment strings,yes,none,USE,high,full class counts
2,D2.4;D2.5,PO present; Hijri date,synthetic-bilingual-invoices-200,https://huggingface.co/datasets/HV09/synthetic-bilingual-invoices-200,HV09/synthetic-bilingual-invoices-200,CC-BY-4.0,https://huggingface.co/datasets/HV09/synthetic-bilingual-invoices-200/raw/main/README.md,open,7.4,0.1,no,https://huggingface.co/datasets/HV09/synthetic-bilingual-invoices-200/resolve/main/data/metadata.jsonl,yes,generator,yes if po_reference not null; yes if date_calendar==hijri,yes (70 no-PO; 185 gregorian),po 130/70; hijri 15/185,yes,none,USE,high,none
2,D2.6,Line-item count,Sparrow invoices,https://huggingface.co/datasets/katanaml-org/invoices-donut-data-v1,katanaml-org/invoices-donut-data-v1,MIT,https://huggingface.co/datasets/katanaml-org/invoices-donut-data-v1/raw/main/README.md,open,197.5,10.44,no,https://datasets-server.huggingface.co/first-rows?dataset=katanaml-org/invoices-donut-data-v1&config=default&split=train,yes,human,len(items) bucketed,n/a,UNVERIFIED,yes,low (fake tax ids),USE,med,count distribution; Mendeley licence
3,D3.1,Car damaged,Kaggle car-damage-detection,https://www.kaggle.com/datasets/anujms/car-damage-detection,,Unknown,https://www.kaggle.com/api/v1/datasets/view/anujms/car-damage-detection,login,130.0,130.0,yes,none,no,UNVERIFIED,folder damaged|whole,UNVERIFIED,damaged|whole,yes,UNVERIFIED,MAYBE,low,licence;rows;access
3,D3.1;D3.2;D3.3,Car damaged; front/rear; damage kind,comprehensive-car-damage,https://huggingface.co/datasets/DrBimmer/comprehensive-car-damage,DrBimmer/comprehensive-car-damage,MIT,https://huggingface.co/datasets/DrBimmer/comprehensive-car-damage/raw/main/README.md,open,668.8,0.01,no,https://datasets-server.huggingface.co/first-rows?dataset=DrBimmer/comprehensive-car-damage&config=default&split=train,yes,human,damaged if label not *_Normal; F_/R_ prefix; suffix,yes (800 normal),F_Breakage 500|F_Crushed 400|F_Normal 500|R_Breakage 300|R_Crushed 300|R_Normal 300,yes,medium (plates),USE,med,image provenance
3,D3.4,Damage type,damaged-car-dataset-annotated,https://huggingface.co/datasets/gigwegbe/damaged-car-dataset-annotated,gigwegbe/damaged-car-dataset-annotated,none,UNVERIFIED,open,1288.9,404.47,no,https://datasets-server.huggingface.co/first-rows?dataset=gigwegbe/damaged-car-dataset-annotated&config=default&split=train,yes,UNVERIFIED,single category per image,no,crack|dent|glass shatter|lamp broken|scratch|tire flat,no,medium,MAYBE,low,licence;origin (possible CarDD)
3,D3.4,Damage type,AutoDamageIQ,https://huggingface.co/datasets/tugberkkalay/autodamageiq-vehicle-damage-dataset,tugberkkalay/autodamageiq-vehicle-damage-dataset,CC-BY-4.0,https://huggingface.co/datasets/tugberkkalay/autodamageiq-vehicle-damage-dataset/raw/main/README.md,open,557.7,0.01,no,none (viewer 500),no,machine (GPT-4o) + CarDD,n/a,no,6 classes,no,medium,SKIP,high,n/a
3,D3.5,Body style,Stanford Cars,https://huggingface.co/datasets/tanganke/stanford_cars,tanganke/stanford_cars,none,UNVERIFIED,open,6016.5,3.74,no,https://datasets-server.huggingface.co/first-rows?dataset=tanganke/stanford_cars&config=default&split=train,yes,UNVERIFIED,body token in class name,n/a,196,yes,medium (plates),MAYBE,low,licence;tiny images
4,D4.1,Damage severity,CrisisMMD v2 damage,https://huggingface.co/datasets/QCRI/CrisisMMD,QCRI/CrisisMMD,CC-BY-NC-SA-4.0,https://huggingface.co/datasets/QCRI/CrisisMMD/raw/main/README.md,open,1941.0,3.07,no,https://datasets-server.huggingface.co/first-rows?dataset=QCRI/CrisisMMD&config=damage&split=train,yes,human,answer=label (image label),yes (little_or_no 333 train),little 333|mild 587|severe 1548 (train),yes,medium (faces; tweets),USE,high,none
4,D4.1;D4.2;D4.4,Severity; disaster type; flood,MEDIC,https://huggingface.co/datasets/QCRI/MEDIC,QCRI/MEDIC,CC-BY-NC-SA-4.0,https://huggingface.co/datasets/QCRI/MEDIC/raw/main/README.md,open,10940.1,163.45,no,https://datasets-server.huggingface.co/first-rows?dataset=QCRI/MEDIC&config=default&split=train,yes,UNVERIFIED (mixed sources),disaster_types; damage_severity,yes (not_disaster 8885 test),7 disaster types; 3 severities,yes,medium,MAYBE,med,label origin; terms-of-use.txt
4,D4.3,Infrastructure damage,CrisisMMD v2 humanitarian (label_image),https://crisisnlp.qcri.org/data/crisismmd/crisismmd_datasplit_all.zip,QCRI/CrisisMMD,CC-BY-NC-SA-4.0,https://huggingface.co/datasets/QCRI/CrisisMMD/raw/main/README.md,open,1941.0,3.07,no,https://datasets-server.huggingface.co/first-rows?dataset=QCRI/CrisisMMD&config=humanitarian&split=test,yes,human,yes if label_image==infrastructure_and_utility_damage; no if not_humanitarian,yes (849 not_humanitarian test),8 humanitarian classes,yes,medium,USE,med,label_image values not printed
5,D5.1,Claim form type,coherent-forms-1040-cms1500-i9,https://huggingface.co/datasets/Symage/coherent-forms-1040-cms1500-i9,Symage/coherent-forms-1040-cms1500-i9,other,https://huggingface.co/datasets/Symage/coherent-forms-1040-cms1500-i9,manual approval,1971.4,394.46,no,none (401),no,UNVERIFIED,UNVERIFIED,UNVERIFIED,UNVERIFIED,UNVERIFIED,UNVERIFIED,GATED,low,all
5,D5.2,Medication count,medical-prescription-dataset,https://huggingface.co/datasets/chinmays18/medical-prescription-dataset,chinmays18/medical-prescription-dataset,none,UNVERIFIED,open,983.8,0.01,no,https://datasets-server.huggingface.co/first-rows?dataset=chinmays18/medical-prescription-dataset&config=default&split=train,yes,UNVERIFIED,count '- <drug>' entries,n/a,3|4 seen,yes,low (fictional),MAYBE,low,licence;origin
5,D5.4,Itemised bill,medical-bill-samples,https://huggingface.co/datasets/sansverse/medical-bill-samples,sansverse/medical-bill-samples,none,UNVERIFIED,open,31.0,0.23,no,https://datasets-server.huggingface.co/first-rows?dataset=sansverse/medical-bill-samples&config=default&split=train,yes,none,cannot compute,no,none,n/a,UNVERIFIED,SKIP,high,n/a
6,D6.1,Document signed,signature-detection,https://huggingface.co/datasets/tech4humans/signature-detection,tech4humans/signature-detection,apache-2.0 (tag),https://huggingface.co/datasets/tech4humans/signature-detection,manual approval,147.4,17.21,no,none (401),no,UNVERIFIED,UNVERIFIED,UNVERIFIED,signature,UNVERIFIED,medium (signatures),GATED,low,all
6,D6.2;D6.3;D7.2,Page category; table present; tender page,DocLayNet,https://github.com/DS4SD/DocLayNet,pierreguillou/DocLayNet-base; docling-project/DocLayNet-v1.2,CDLA-Permissive-1.0,https://raw.githubusercontent.com/DS4SD/DocLayNet/main/LICENSE,open,39770.6,17.0 (small test) / 187.2 (base test),no,https://datasets-server.huggingface.co/rows?dataset=pierreguillou/DocLayNet-base&config=DocLayNet_2022.08_processed_on_2023.01&split=test&offset=0&length=3,yes,human,doc_category; Table id in category_id,yes,6 doc categories; 11 layout classes,yes,low,USE,high,
6,D6.2;D9.4;D7.4,Doc type incl IRS forms,document-classification-benchmark,https://huggingface.co/datasets/nutrientdocs/document-classification-benchmark,nutrientdocs/document-classification-benchmark,other (per-row tags),https://huggingface.co/datasets/nutrientdocs/document-classification-benchmark/raw/main/README.md,open,453.7,453.67,yes,https://datasets-server.huggingface.co/rows?dataset=nutrientdocs/document-classification-benchmark&config=default&split=test&offset=377&length=2,yes,mixed (generator forms; human DocLayNet),answer=label,n/a,34 labels,yes,low,MAYBE,med,dataset-level licence
7,D7.1,Checkbox state,CheckboxQA,https://huggingface.co/datasets/mturski/CheckboxQA,mturski/CheckboxQA,CC-BY-NC-4.0,https://huggingface.co/datasets/mturski/CheckboxQA/raw/main/README.md,open (docs off-site),0.3,0.04,no,https://huggingface.co/datasets/mturski/CheckboxQA/resolve/main/data/test-00000-of-00001.parquet,yes,UNVERIFIED (human per paper),values==[Yes]/[No] but page unknown,yes (163 No / 87 Yes),yes|no|other,no (multi-question multi-page),medium (real filings),MAYBE,med,page index; PDFs
7,D7.3,Unanswered field,FUNSD+,https://huggingface.co/datasets/konfuzio/funsd_plus,konfuzio/funsd_plus,FUNSD+ license (unread),https://huggingface.co/datasets/konfuzio/funsd_plus/blob/main/LICENSE,form or email request,195.2,19.78,no,https://datasets-server.huggingface.co/first-rows?dataset=konfuzio/funsd_plus&config=default&split=train,yes,UNVERIFIED,question group with no linked answer,yes (18.3% per card),header|question|answer,no,medium (names),GATED,med,licence text
7,D7.3,Form fields,FUNSD (nielsr),https://huggingface.co/datasets/nielsr/funsd,nielsr/funsd,UNVERIFIED,https://guillaumejaume.github.io/FUNSD/,open,16.6,4.38,no,https://datasets-server.huggingface.co/first-rows?dataset=nielsr/funsd&config=default&split=train,yes,UNVERIFIED,count B-QUESTION tags,n/a,O|HEADER|QUESTION|ANSWER,yes,medium (names),MAYBE,low,licence;origin;links
8,D8.1,Printed sex / blood type on synthetic KTP,indonesian-id-card-dummy (flat),https://huggingface.co/datasets/cloverx-id/indonesian-id-card-dummy,cloverx-id/indonesian-id-card-dummy,CC-BY-4.0,https://huggingface.co/datasets/cloverx-id/indonesian-id-card-dummy/raw/main/README.md,open,34990.2,65.36,no,https://datasets-server.huggingface.co/first-rows?dataset=cloverx-id/indonesian-id-card-dummy&config=flat&split=train,yes,generator,jenis_kelamin; golongan_darah,n/a,M 55/F 45; A29 O26 AB25 B20 (sample),yes,medium (morphed real faces),USE,med,full counts
8,D8.2;D8.3,Expiry after issue; nationality,synthetic_us_passports_easy,https://huggingface.co/datasets/Voxel51/synthetic_us_passports_easy,Voxel51/synthetic_us_passports_easy,Apache-2.0,https://huggingface.co/datasets/Voxel51/synthetic_us_passports_easy/raw/main/README.md,open,17472.3,10.05,no,https://huggingface.co/datasets/Voxel51/synthetic_us_passports_easy/resolve/main/samples.json,yes,generator,date_of_expiration>date_of_issue; nationality.label,yes (row 0 expiry<issue),nationality many; sex F|M,yes,low,USE,med,third row; balance
8,D8.3;D8.5,Issuing country; passport vs ID,midv-DoB-mini,https://huggingface.co/datasets/zimka/midv-DoB-mini,zimka/midv-DoB-mini,none,UNVERIFIED,open,267.3,35.68,no,https://datasets-server.huggingface.co/first-rows?dataset=zimka/midv-DoB-mini&config=default&split=template,yes,UNVERIFIED,'passport' in original_image_path; template_name,n/a,~50 templates,yes,low (specimens),MAYBE,low,licence
8,D8.4,Tampered ID,IDNet-2025,https://huggingface.co/datasets/cactuslab/IDNet-2025,cactuslab/IDNet-2025,CC-BY-4.0,https://huggingface.co/datasets/cactuslab/IDNet-2025/raw/main/README.md,open,124933.5,1354.22,yes,none (no splits),no,generator,positive vs fraud5/fraud6 folders,yes (by design),genuine|inpaint_rewrite|crop_replace,yes,none (synthetic),MAYBE,med,rows; meta JSON fields
8,D8.4,Forged document,sifta-document-forgery,https://huggingface.co/datasets/zodumair/sifta-document-forgery-dataset,zodumair/sifta-document-forgery-dataset,none,UNVERIFIED,open,196.5,26.14,no,https://datasets-server.huggingface.co/first-rows?dataset=zodumair/sifta-document-forgery-dataset&config=default&split=train,yes,UNVERIFIED,answer=label_name,yes (real 16/forged 13 test),real|forged,yes,UNVERIFIED,MAYBE,low,licence;origin;doc type
8,D8.6,KTP present in photo,indonesian-id-card-dummy (augmented),https://huggingface.co/datasets/cloverx-id/indonesian-id-card-dummy,cloverx-id/indonesian-id-card-dummy,CC-BY-4.0 (third-party negatives),https://huggingface.co/datasets/cloverx-id/indonesian-id-card-dummy/raw/main/README.md,open,34990.2,65.36,no,https://datasets-server.huggingface.co/info?dataset=cloverx-id/indonesian-id-card-dummy&config=augmented,no,generator + third-party,yes if nik non-empty,yes (12804 negatives per card),ktp|none,yes,high (real IDs in negatives),MAYBE,low,negative rows; licences of negatives
9,D9.1,Tax form page,NIST SD2 (US tax forms donut),https://huggingface.co/datasets/hyturing/US_tax_forms_donut,hyturing/US_tax_forms_donut,MIT (HF card); NIST no charge,https://huggingface.co/datasets/hyturing/US_tax_forms_donut/raw/main/README.md,open,947.0,95.3,no,https://datasets-server.huggingface.co/first-rows?dataset=hyturing/US_tax_forms_donut&config=default&split=train,yes,generator,answer=label,n/a,20 form faces (counts in card),yes,none (synthesized),USE,high,NIST SRD terms
9,D9.2;D9.3,W-2 state; box 13,fake W-2,https://huggingface.co/datasets/singhsays/fake-w2-us-tax-form-dataset,singhsays/fake-w2-us-tax-form-dataset,CC0 (upstream Kaggle),https://www.kaggle.com/api/v1/datasets/view/mcvishnu1/fake-w2-us-tax-form-dataset,open,309.6,15.47,no,https://datasets-server.huggingface.co/rows?dataset=singhsays/fake-w2-us-tax-form-dataset&config=default&split=test&offset=0&length=1,yes,generator,box_13_statutary_employee=='x'; box_15_1_state,yes (x and None both seen),state codes; x|None,yes,low (fake SSNs),USE,med,balance; HF card licence absent
10,D10,Resume domain,resumes-raw-pdf,https://huggingface.co/datasets/d4rk3r/resumes-raw-pdf,d4rk3r/resumes-raw-pdf,MIT,https://huggingface.co/datasets/d4rk3r/resumes-raw-pdf,open,832.4,0.02,no,https://datasets-server.huggingface.co/first-rows?dataset=d4rk3r/resumes-raw-pdf&config=default&split=train,yes,folder,not a visual fact,n/a,all-domains|it-domain,yes,high (resumes),SKIP,high,n/a
10,D10.2;D10.3,Card shows email / mobile,business_card_dataset,https://huggingface.co/datasets/ilovelevi/business_card_dataset,ilovelevi/business_card_dataset,none,UNVERIFIED,open,40.1,0.39,no,https://huggingface.co/datasets/ilovelevi/business_card_dataset/resolve/main/labels/labels.json,yes,UNVERIFIED (likely generator),email!=''; mobile_phone!='',UNVERIFIED,is_business_card all true,yes,medium (names),MAYBE,low,licence;origin;balance
11,D11.1,shelf gap / SKU,SKUs_on_shelves_PL,https://huggingface.co/datasets/shelfwise-by-form/SKUs_on_shelves_PL,shelfwise-by-form/SKUs_on_shelves_PL,CC-BY-4.0,https://huggingface.co/datasets/shelfwise-by-form/SKUs_on_shelves_PL,open,11422.6,11422.09,yes,https://datasets-server.huggingface.co/first-rows?dataset=shelfwise-by-form/SKUs_on_shelves_PL&config=default&split=train,no,UNVERIFIED,needs COCO json in archive,unknown,~8k SKUs,no,low,SKIP,high,label origin;schema
11,D11.2,price tag readability,OFF price-tag-classification,https://huggingface.co/datasets/openfoodfacts/price-tag-classification,openfoodfacts/price-tag-classification,NOT STATED,https://huggingface.co/datasets/openfoodfacts/price-tag-classification,open,48.5,9.87,no,https://datasets-server.huggingface.co/first-rows?dataset=openfoodfacts/price-tag-classification&config=default&split=train,yes,human,label name,n/a,invalid 534/medium 220/high 893,yes,low,MAYBE,med,licence;annotator count
11,D11.3,price tag count,OFF price-tag-detection,https://huggingface.co/datasets/openfoodfacts/price-tag-detection,openfoodfacts/price-tag-detection,CC-BY-SA-4.0,https://huggingface.co/datasets/openfoodfacts/price-tag-detection,open,399.2,44.16,no,https://datasets-server.huggingface.co/first-rows?dataset=openfoodfacts/price-tag-detection&config=default&split=train,yes,human,len(objects.category_id) binned,unverified (count task),price-tag,yes,low,USE,med,zero-tag images
11,D11.4,discount flag,OFF price-tag-extraction,https://huggingface.co/datasets/openfoodfacts/price-tag-extraction,openfoodfacts/price-tag-extraction,NOT STATED,https://huggingface.co/datasets/openfoodfacts/price-tag-extraction,open,12947.2,180.2,no,https://datasets-server.huggingface.co/first-rows?dataset=openfoodfacts/price-tag-extraction&config=default&split=train,yes,machine,output.prices[].price_is_discounted,yes,JSON fields,yes,low,SKIP,high,
11,D11.5,checkout item count,RPC (benjamintli mirror),https://huggingface.co/datasets/benjamintli/retail-product-checkout,benjamintli/retail-product-checkout,CC BY-NC-SA 4.0 (tag says 2.0),https://huggingface.co/datasets/benjamintli/retail-product-checkout,open,15279.1,315.9,no,https://datasets-server.huggingface.co/rows?dataset=benjamintli/retail-product-checkout&config=default&split=validation&offset=0&length=100,yes,UNVERIFIED,len(objects.category) binned; supercategory suffix,n/a,200 SKUs/17 supercats,yes,low,MAYBE,med,label origin;licence version
12,D12.1,product type,ABO (suvadityamuk mirror),https://huggingface.co/datasets/suvadityamuk/amazon-berkeley-objects,suvadityamuk/amazon-berkeley-objects,CC-BY-4.0 (bucket also has NC file),https://huggingface.co/datasets/suvadityamuk/amazon-berkeley-objects,open,617650.7,12.09 (listings) / 172.3 (original images),no,https://datasets-server.huggingface.co/first-rows?dataset=suvadityamuk/amazon-berkeley-objects&config=listings&split=train,yes,human (catalogue) inferred,product_type via main_image_id join,n/a,product_type enum,yes,low,MAYBE,med,class counts;label origin
12,D12.2,colour attribute,Fashion Product Images small,https://www.kaggle.com/datasets/paramaggarwal/fashion-product-images-small,ashraq/fashion-product-images-small,UNVERIFIED,https://huggingface.co/datasets/ashraq/fashion-product-images-small,open mirror / Kaggle login,271.5,135.4,no,https://datasets-server.huggingface.co/first-rows?dataset=ashraq/fashion-product-images-small&config=default&split=train,yes,human (catalogue; inferred),baseColour,n/a,many,yes,low,SKIP,high,licence; tiny 60x80 images
12,D12.3,garment worn,Fashionpedia,https://fashionpedia.github.io/home/index.html,detection-datasets/fashionpedia,CC BY 4.0,https://huggingface.co/datasets/detection-datasets/fashionpedia,open,3478.9,84.85 (val parquet; per slice-2 card) / single rows via /rows,no,https://datasets-server.huggingface.co/first-rows?dataset=detection-datasets/fashionpedia&config=default&split=train,yes,human,exactly one of {dress pants skirt shorts} in objects.category,n/a (pick-one),46 classes,filterable,med (people/celebrities),USE,high,owner Terms of Use text
12,D12.4,white background main image,ABO-Edit,https://huggingface.co/datasets/amazon/ABO-Edit,amazon/ABO-Edit,CC-BY-4.0,https://huggingface.co/datasets/amazon/ABO-Edit,open,18288.6,505,no,https://datasets-server.huggingface.co/first-rows?dataset=amazon/ABO-Edit&config=default&split=train,yes,generator (target renders) + human product_type,xtarget=yes / xsource=no,yes,white/lifestyle; product_type,yes,low-med,USE,med,row count
13,D13.1,fresh vs rotten,Densu341 Fresh-rotten-fruit,https://huggingface.co/datasets/Densu341/Fresh-rotten-fruit,Densu341/Fresh-rotten-fruit,openrail (no text),https://huggingface.co/datasets/Densu341/Fresh-rotten-fruit,open,3053.6,3053.59,yes,https://datasets-server.huggingface.co/first-rows?dataset=Densu341/Fresh-rotten-fruit&config=default&split=train,yes,UNVERIFIED,label startswith rotten,yes,22 classes,yes,low,SKIP,high,origin;overlap with AgML
13,D13.1,fresh vs rotten,jojogo9 freshness,https://huggingface.co/datasets/jojogo9/freshness,jojogo9/freshness,MIT,https://huggingface.co/datasets/jojogo9/freshness,open,191.8,38.19,no,https://datasets-server.huggingface.co/first-rows?dataset=jojogo9/freshness&config=default&split=train,yes,UNVERIFIED,label startswith rotten,yes,6 classes,yes,low,SKIP,high,label map conflict
13,D13.2,ripeness,fruit-ripeness-detection-dataset,https://huggingface.co/datasets/darthraider/fruit-ripeness-detection-dataset,darthraider/fruit-ripeness-detection-dataset,Apache-2.0 (mirror),https://huggingface.co/datasets/darthraider/fruit-ripeness-detection-dataset,open,390.9,35.48,no,https://datasets-server.huggingface.co/first-rows?dataset=darthraider/fruit-ripeness-detection-dataset&config=default&split=train,yes,UNVERIFIED,label startswith Ripe_,yes,4 classes x250 (test),yes,low,MAYBE,med,label origin;upstream licence
13,D13.3,produce variety,GroceryStoreDataset,https://github.com/marcusklasson/GroceryStoreDataset,,NOT STATED,https://github.com/marcusklasson/GroceryStoreDataset,open,UNVERIFIED,<0.1 (txt),no,https://raw.githubusercontent.com/marcusklasson/GroceryStoreDataset/master/dataset/test.txt,yes,human inferred,classes.csv[fine_id],n/a,81 fine/42 coarse,yes,low,MAYBE,med,licence;total size
13,D13.4,grocery item,grocery-images-5class,https://huggingface.co/datasets/Primusvandalus/grocery-images-5class,Primusvandalus/grocery-images-5class,Pexels licence,https://huggingface.co/datasets/Primusvandalus/grocery-images-5class,open,63.4,0.17,no,https://datasets-server.huggingface.co/first-rows?dataset=Primusvandalus/grocery-images-5class&config=default&split=train,yes,human,label name,n/a,apple300/banana260/bread260/cheese260/tomato260,yes,low,USE,high,
14,D14.1,dish identity,Food-101,https://huggingface.co/datasets/ethz/food101,ethz/food101,fair use only (Foodspotting ToS),https://huggingface.co/datasets/ethz/food101,open,5060,413.15,no,https://datasets-server.huggingface.co/first-rows?dataset=ethz/food101&config=default&split=train,yes,human (val) / machine (train),label name,n/a,101x(750+250),yes,low,MAYBE,high,
14,D14.2,hand hygiene,ybli kitchen hygiene,https://huggingface.co/datasets/ybli/yolo-kitchen-hygiene-safety-detection,ybli/yolo-kitchen-hygiene-safety-detection,NOT STATED,,unknown (off-site),0,0,no,,no,UNVERIFIED,n/a,n/a,Performing-Hand-Hygiene,n/a,high,SKIP,high,everything
14,D14.3,plate waste,Voxel51 food-waste,https://huggingface.co/datasets/Voxel51/food-waste-dataset,Voxel51/food-waste-dataset,MIT,https://huggingface.co/datasets/Voxel51/food-waste-dataset,open,309.6,16.57,no,https://datasets-server.huggingface.co/first-rows?dataset=Voxel51/food-waste-dataset&config=default&split=train,no,machine,n/a,n/a,n/a,n/a,low,SKIP,high,
15,D15.1,person near forklift,keremberke forklift,https://huggingface.co/datasets/keremberke/forklift-object-detection,keremberke/forklift-object-detection,CC BY 4.0,https://huggingface.co/datasets/keremberke/forklift-object-detection,open,20.4,2.77,no,https://datasets-server.huggingface.co/first-rows?dataset=keremberke/forklift-object-detection&config=full&split=train,yes,human inferred,yes if 1 in objects.category,yes (194 forklift-only),forklift/person,yes,med (people),USE,med,box exhaustiveness
15,D15.2;D16.3,damaged carton,cardboard-box-anomaly-detection,https://huggingface.co/datasets/Gabriel8/cardboard-box-anomaly-detection,Gabriel8/cardboard-box-anomaly-detection,CC BY-NC-SA 4.0,https://huggingface.co/datasets/Gabriel8/cardboard-box-anomaly-detection,open,2042.9,1.42,no,https://datasets-server.huggingface.co/rows?dataset=Gabriel8/cardboard-box-anomaly-detection&config=default&split=test&offset=0&length=100,yes,human,label==bad,yes (166 good),bad 386/good 166,yes,low,USE,high,
16,D16.1,container defect type,howell0123 shipping_container,https://huggingface.co/datasets/howell0123/shipping_container,howell0123/shipping_container,NOT STATED,https://huggingface.co/datasets/howell0123/shipping_container,open,224.6,224.52,no,https://datasets-server.huggingface.co/rows?dataset=howell0123/shipping_container&config=default&split=train&offset=0&length=100,yes,UNVERIFIED,single-defect answer string,no (positives only),Rusty367/Dent133/Scratch129/Deframe46/Hole14 singles,filter singles,low,MAYBE,med,licence;origin
16,D16.2,container damaged,Guztavu container-damage,https://huggingface.co/datasets/Guztavu/container-damage,Guztavu/container-damage,UNVERIFIED,,login + accept terms,339,39,no,,no,UNVERIFIED,UNVERIFIED,likely (bbox_nodmg.zip),UNVERIFIED,UNVERIFIED,low,GATED,low,all
16,D16.3,damaged parcel,HassanBinAli Damaged_Parcel_boxes,https://huggingface.co/datasets/HassanBinAli/Damaged_Parcel_boxes,HassanBinAli/Damaged_Parcel_boxes,MIT,https://huggingface.co/datasets/HassanBinAli/Damaged_Parcel_boxes,open,0.03,0.02,no,https://datasets-server.huggingface.co/first-rows?dataset=HassanBinAli/Damaged_Parcel_boxes&config=default&split=train,yes,UNVERIFIED,n/a (no images),unknown,5 ints,n/a,low,SKIP,high,
16,D16.3,damaged parcel,Parcel3D,https://zenodo.org/records/8032204,,other-nc,https://zenodo.org/records/8032204,open,45838.3,45838.3,yes,,no,generator,UNVERIFIED,yes (per title),damaged/intact,UNVERIFIED,low,SKIP,high,schema
17,D17.1,parcel at door,OliseNS home-security,https://huggingface.co/datasets/OliseNS/person-face-package-home-security-detection,OliseNS/person-face-package-home-security-detection,multi-source aggregated terms,https://huggingface.co/datasets/OliseNS/person-face-package-home-security-detection/blob/main/LICENSE,open,22701.7,22658 (sample folder small),yes,https://huggingface.co/datasets/OliseNS/person-face-package-home-security-detection/raw/main/sample/data.yaml,no,machine-assisted inferred,class 5 present,UNVERIFIED,9 classes incl face,no,high,SKIP,med,label origin
18,D18.1,room type,MIT Indoor-67 (Voxel51),https://huggingface.co/datasets/Voxel51/IndoorSceneRecognition,Voxel51/IndoorSceneRecognition,MIT tag vs original research-only,https://huggingface.co/datasets/Voxel51/IndoorSceneRecognition,open,2602.9,22.47 (json) / per-image,no,https://huggingface.co/datasets/Voxel51/IndoorSceneRecognition/resolve/main/samples.json,yes,human,ground_truth.label,n/a,kitchen734/living706/bed662/dining274/bath197,yes,low,MAYBE,med,licence
18,D18.1,room type,keremberke indoor-scene,https://huggingface.co/datasets/keremberke/indoor-scene-classification,keremberke/indoor-scene-classification,MIT (quotes research-only),https://huggingface.co/datasets/keremberke/indoor-scene-classification,open,470.3,46.53,no,https://datasets-server.huggingface.co/first-rows?dataset=keremberke/indoor-scene-classification&config=full&split=train,yes,human,labels name,n/a,67,yes,low,MAYBE,med,licence
19,D19.1,floorplan door count,cubicasa5k-yolo,https://huggingface.co/datasets/v1nz/cubicasa5k-yolo,v1nz/cubicasa5k-yolo,CC BY-NC 4.0 (Zenodo says BY-NC-SA 4.0),https://zenodo.org/records/2613548,open,1762.8,4.4 (one png+txt),no,https://datasets-server.huggingface.co/first-rows?dataset=v1nz/cubicasa5k-yolo&config=default&split=train,yes,human (auto-converted),count lines with class 1,n/a,wall/door/window,yes,low,USE,med,conversion fidelity;door distribution
19,D19.2,bedroom count,CubiCasa5K original,https://zenodo.org/records/2613548,,CC BY-NC-SA 4.0,https://zenodo.org/records/2613548,open,5469.5,5469.5,yes,,no,human,room polygons in SVG,n/a,80+ categories,yes,low,SKIP,high,
19,D19.2,room layout (generator),FloorplanQA-Layouts,https://huggingface.co/datasets/OldDelorean/FloorplanQA-Layouts,OldDelorean/FloorplanQA-Layouts,CC BY 4.0,https://huggingface.co/datasets/OldDelorean/FloorplanQA-Layouts,open,16,<0.1,no,https://datasets-server.huggingface.co/first-rows?dataset=OldDelorean/FloorplanQA-Layouts&config=default&split=train,yes,generator,len(openings.windows) etc,n/a,bedroom692/kitchen622/living600,yes,none,MAYBE,high,no images (must render)
19,D19.3,construction era,WorcesterMA_Housing_Facades,https://huggingface.co/datasets/murai-lab/WorcesterMA_Housing_Facades,murai-lab/WorcesterMA_Housing_Facades,MIT (card warns clearance unconfirmed),https://huggingface.co/datasets/murai-lab/WorcesterMA_Housing_Facades,open,14162,0.01-3.7 (per image),no,https://datasets-server.huggingface.co/first-rows?dataset=murai-lab/WorcesterMA_Housing_Facades&config=default&split=train,yes,human (registry),class_label or year_built bins,yes,c1 11254/c2 4958/c3 2967/c4 1288,yes,med (addresses),MAYBE,med,image rights
19,D19.4,architectural style,facade-styles,https://huggingface.co/datasets/Jonathandav/facade-styles,Jonathandav/facade-styles,MIT,https://huggingface.co/datasets/Jonathandav/facade-styles,open,357.2,0.07 (manifest) / 0.46 (png),no,https://huggingface.co/datasets/Jonathandav/facade-styles/resolve/main/plate_manifest.parquet,yes,generator (text-to-image spec),style_name / view,yes,20 styles x50,yes,none,MAYBE,med,render fidelity
19,D19.6,CAD symbol count,FloorPlanCAD (Voxel51),https://huggingface.co/datasets/Voxel51/FloorPlanCAD,Voxel51/FloorPlanCAD,CC-BY-SA tag vs BY-NC text,https://huggingface.co/datasets/Voxel51/FloorPlanCAD,open,454.2,0.46 (png) / 60.4 (json),no,https://huggingface.co/datasets/Voxel51/FloorPlanCAD/resolve/main/samples.json (range),no (partial),UNVERIFIED,count detections by label,n/a,30,yes,low,MAYBE,low,licence;origin;rows
20,D20.1,recycling stream,TrashNet,https://huggingface.co/datasets/garythung/trashnet,garythung/trashnet,MIT,https://huggingface.co/datasets/garythung/trashnet,open,3677,42.83,no,https://datasets-server.huggingface.co/first-rows?dataset=garythung/trashnet&config=default&split=train,yes,human inferred,label name,n/a,cb806/gl1002/me820/pa1188/pl964/tr274,yes,none,USE,med,label origin text
20,D20.1,waste class 10,waste-garbage-management,https://huggingface.co/datasets/steveharianto/waste-garbage-management-dataset,steveharianto/waste-garbage-management-dataset,MIT,https://huggingface.co/datasets/steveharianto/waste-garbage-management-dataset,open,789.8,<0.01,no,https://datasets-server.huggingface.co/first-rows?dataset=steveharianto/waste-garbage-management-dataset&config=default&split=train,yes,UNVERIFIED,label name,n/a,10 classes,yes,low,SKIP,high,origin
20,D20.2,illegal dumping (aerial),DroneWaste,https://zenodo.org/records/17045559,,CC BY 4.0,https://zenodo.org/records/17045559,open,3891.3,8.8 (json) / 3882.5 images,yes,https://zenodo.org/records/17045559/files/dronewaste_v1.0.json,yes,UNVERIFIED (annotated),image has >=1 annotation,yes (3822 empty),20 materials,filterable,none,MAYBE,med,annotator type
20,D20.3,litter material,TACO,https://github.com/pedropro/TACO,,NOT STATED,https://github.com/pedropro/TACO,open,UNVERIFIED,annotations json small; images per-file 0.1-5 MB,no,https://raw.githubusercontent.com/pedropro/TACO/master/data/annotations.json,yes,human,supercategory of single annotation,no for presence,60 cats/28 supercats,610 single-object,low-med,MAYBE,med,licence
20,D20.4,bin overflowing,Garbage_Bin_overflow_images,https://huggingface.co/datasets/Akhila-9849/Garbage_Bin_overflow_images,Akhila-9849/Garbage_Bin_overflow_images,CC BY 4.0,https://huggingface.co/datasets/Akhila-9849/Garbage_Bin_overflow_images,open,111.8,0.01,no,https://datasets-server.huggingface.co/first-rows?dataset=Akhila-9849/Garbage_Bin_overflow_images&config=default&split=train,no (images only),none,n/a,no,none,n/a,low,SKIP,high,
21,D21.1,Steel sheet defect yes/no,Severstal steel defects (Voxel51),https://huggingface.co/datasets/Voxel51/severstal_steel_defects,Voxel51/severstal_steel_defects,UNVERIFIED (Kaggle competition rules),https://www.kaggle.com/competitions/severstal-steel-defect-detection,open,1758,0.2,no,https://huggingface.co/datasets/Voxel51/severstal_steel_defects/resolve/main/samples.json,yes,human (inferred),yes if has_defect,yes (~63%),defect classes 1-4,yes for yes/no; filter len(defect_classes)==1 for pick-one,none,MAYBE,med,licence;label_origin
21,D21.2,Steel defect class,Severstal steel defects (Voxel51),https://huggingface.co/datasets/Voxel51/severstal_steel_defects,Voxel51/severstal_steel_defects,UNVERIFIED,https://www.kaggle.com/competitions/severstal-steel-defect-detection,open,1758,0.2,no,https://huggingface.co/datasets/Voxel51/severstal_steel_defects/resolve/main/samples.json,yes,human (inferred),defect_classes[0] when single,n/a,1;2;3;4,filter single class,none,MAYBE,med,licence;label_origin;class counts
21,D21.3,Commutator crack yes/no,KolektorSDD (box release),https://www.vicos.si/resources/kolektorsdd/,Voxel51/Kolektor_Surface_Defect,CC BY-NC-SA 4.0,https://huggingface.co/datasets/Voxel51/Kolektor_Surface_Defect,open,106.6,0.27,no,https://huggingface.co/datasets/Voxel51/Kolektor_Surface_Defect/resolve/main/samples.json,yes,human,yes if has_defect,yes (347 neg / 52 pos),defect;no defect,yes,none,USE,high,
21,D21.4,Wood surface defect yes/no,Wood surface defects (Kodytek),https://huggingface.co/datasets/iluvvatar/wood_surface_defects,iluvvatar/wood_surface_defects,CC BY 4.0,https://huggingface.co/datasets/iluvvatar/wood_surface_defects,open,2202.9,439.65,no,https://datasets-server.huggingface.co/rows?dataset=iluvvatar/wood_surface_defects&config=default&split=train&offset=5000&length=40,yes,UNVERIFIED,yes if len(objects)>0,yes (~5-7% empty sampled),Live_Knot;Dead_Knot;... (full list UNVERIFIED),filter single label for type,none,MAYBE,med,label_origin;full class list
21,D21.6,Weld good/bad,Welding Defect Object Detection,https://huggingface.co/datasets/rikkarth/welding-defect-object-detection,rikkarth/welding-defect-object-detection,CC0 1.0,https://huggingface.co/datasets/rikkarth/welding-defect-object-detection,open,104.1,0.056,no,https://huggingface.co/datasets/rikkarth/welding-defect-object-detection/resolve/main/coco/test.json,yes,UNVERIFIED,good if categories=={Good Weld}; bad if Bad Weld or Defect and no Good Weld,yes (56/126 test good-only),Bad Weld;Good Weld;Defect,filter (24/126 mixed),none,MAYBE,med,label_origin
22,D22.1,Bare PCB defect yes/no,DeepPCB,https://github.com/tangsanli5201/DeepPCB,,MIT (README adds research-only),https://github.com/tangsanli5201/DeepPCB/blob/master/LICENSE,open,UNVERIFIED,0.023,no,https://raw.githubusercontent.com/tangsanli5201/DeepPCB/master/PCBData/group00041/00041_not/00041000.txt,yes,human (artificial defects),yes for *_test.jpg; no for *_temp.jpg,yes (1500 templates),open;short;mousebite;spur;copper;pin-hole,yes,none,USE,high,total_mb
22,D22.2,Bare PCB defect type,HRIPCB PCB_defect,https://huggingface.co/datasets/RobotHuman/PCB_defect,RobotHuman/PCB_defect,MIT (re-upload; upstream UNVERIFIED),https://huggingface.co/datasets/RobotHuman/PCB_defect,open,960.5,0.002,no,https://datasets-server.huggingface.co/rows?dataset=RobotHuman/PCB_defect&config=default&split=train&offset=300&length=1,yes,generator-like (Photoshop-inserted),distinct object name,no (positives only),missing_hole;mouse_bite;open_circuit;short;spur;spurious_copper,yes,none,MAYBE,med,upstream licence;per-class counts
22,D22.3,Assembled PCB defect type,pcb-defect-segmentation (Roboflow),https://huggingface.co/datasets/keremberke/pcb-defect-segmentation,keremberke/pcb-defect-segmentation,CC BY 4.0,https://huggingface.co/datasets/keremberke/pcb-defect-segmentation,open,9.7,0.155,no,https://datasets-server.huggingface.co/first-rows?dataset=keremberke/pcb-defect-segmentation&config=full&split=train,yes,UNVERIFIED,single distinct category,no,dry_joint;incorrect_installation;pcb_damage;short_circuit,filter,none,MAYBE,low,label_origin;counts
23,D23.1,Tyre defective/good,Digital images of defective and good condition tyres,https://data.mendeley.com/datasets/bn7ch8tvyp,NMiriams/Good_Tires + NMiriams/Defective_Tires,CC BY 4.0,https://data.mendeley.com/datasets/bn7ch8tvyp,open,2917.7,1.5,no,https://datasets-server.huggingface.co/first-rows?dataset=NMiriams/Defective_Tires&config=default&split=train,yes (image-only; label=repo),human,label = source repo,yes (828 good),good;defective,yes,low,USE,med,annotator identity
23,D23.3,Vehicle make,Stanford Cars,https://huggingface.co/datasets/tanganke/stanford_cars,tanganke/stanford_cars,none,UNVERIFIED,open,6016.5,3.74,no,https://datasets-server.huggingface.co/first-rows?dataset=tanganke/stanford_cars&config=default&split=train,yes,UNVERIFIED,make from label name,n/a,196 make-model-year,yes,medium (plates),MAYBE,low,licence;tiny images
24,D24.1,Aircraft manufacturer/family,FGVC-Aircraft (Voxel51),https://huggingface.co/datasets/Voxel51/FGVC-Aircraft,Voxel51/FGVC-Aircraft,non-commercial research only (other),https://huggingface.co/datasets/Voxel51/FGVC-Aircraft,open,2775.5,0.08,no,https://huggingface.co/datasets/Voxel51/FGVC-Aircraft/resolve/main/samples.json,yes,UNVERIFIED,manufacturer field,n/a,41 manufacturers;70 families;102 variants,yes,low,MAYBE,med,label_origin
25,D25.1,Rail defect type,Dhika/defect_rail,https://huggingface.co/datasets/Dhika/defect_rail,Dhika/defect_rail,unknown,https://huggingface.co/datasets/Dhika/defect_rail,open,6.3,0.008,no,https://datasets-server.huggingface.co/rows?dataset=Dhika/defect_rail&config=default&split=train&offset=150&length=1,yes,UNVERIFIED,label name,no,corrugation;crack;putus;spalling;squat,yes,none,SKIP,high,licence;label_origin
26,D26.1,Construction machine type,excavator-detector (Roboflow),https://huggingface.co/datasets/keremberke/excavator-detector,keremberke/excavator-detector,CC BY 4.0,https://huggingface.co/datasets/keremberke/excavator-detector,open,193.4,0.161,no,https://datasets-server.huggingface.co/first-rows?dataset=keremberke/excavator-detector&config=full&split=train,yes,UNVERIFIED,single distinct category,n/a,excavators;dump truck;wheel loader,filter,low,MAYBE,med,label_origin;image counts
26,D26.2,Concrete crack yes/no,METU concrete crack images,https://huggingface.co/datasets/mohammadnajeeb/concrete_crack_images,mohammadnajeeb/concrete_crack_images,CC BY 4.0,https://huggingface.co/datasets/mohammadnajeeb/concrete_crack_images,open,244.9,49.06,no,https://datasets-server.huggingface.co/rows?dataset=mohammadnajeeb/concrete_crack_images&config=default&split=train&offset=12000&length=1,yes,UNVERIFIED,yes if Positive,yes (12000/12000),Negative;Positive,yes,none,SKIP,high,label_origin
26,D26.3,Rebar count,ROI-1555 rebar,https://huggingface.co/datasets/tsrobcvai/ROI-1555_Rebar_Detection_and_Instance_Segmentation_Dataset,tsrobcvai/ROI-1555_Rebar_Detection_and_Instance_Segmentation_Dataset,UNVERIFIED,https://huggingface.co/datasets/tsrobcvai/ROI-1555_Rebar_Detection_and_Instance_Segmentation_Dataset,open,586.5,0.06,no,https://datasets-server.huggingface.co/first-rows?dataset=tsrobcvai/ROI-1555_Rebar_Detection_and_Instance_Segmentation_Dataset&config=default&split=test,yes,UNVERIFIED,count shapes,n/a,straight-N (semantics UNVERIFIED),count,none,MAYBE,low,licence;label semantics
26,D26.4,Construction site VQA,ConstructionSite,https://huggingface.co/datasets/LouisChen15/ConstructionSite,LouisChen15/ConstructionSite,CC BY-NC 4.0,https://huggingface.co/datasets/LouisChen15/ConstructionSite,login,4497.7,1375.1,no,none (401),no,UNVERIFIED,UNVERIFIED,UNVERIFIED,UNVERIFIED,UNVERIFIED,workers visible,GATED,low,most fields
27,D27.1,Gauge reading,Meter_Reading (synthetic),https://huggingface.co/datasets/goodcoffee/Meter_Reading,goodcoffee/Meter_Reading,Apache-2.0,https://huggingface.co/datasets/goodcoffee/Meter_Reading,open,2449.3,0.022,no,https://datasets-server.huggingface.co/first-rows?dataset=goodcoffee/Meter_Reading&config=default&split=train,yes,generator,answer = synth_dial_value,n/a,continuous value,yes,none,USE,med,value diversity
27,D27.1,Gauge reading,synthetic-gauges-v6,https://huggingface.co/datasets/moondream/synthetic-gauges-v6,moondream/synthetic-gauges-v6,UNVERIFIED (none on card),https://huggingface.co/datasets/moondream/synthetic-gauges-v6,open,20578.5,458.4,no,https://datasets-server.huggingface.co/first-rows?dataset=moondream/synthetic-gauges-v6&config=default&split=train_0,yes,generator,answer = facts.units.outer.value,n/a,continuous,yes,none,MAYBE,med,licence
27,D27.1,Gauge reading,synthetic-analog-gauges,https://huggingface.co/datasets/Mileeena/synthetic-analog-gauges,Mileeena/synthetic-analog-gauges,CC BY 4.0,https://huggingface.co/datasets/Mileeena/synthetic-analog-gauges,login,2545.4,0.138,no,none (401),no,generator (inferred),UNVERIFIED,n/a,UNVERIFIED,UNVERIFIED,none,GATED,low,most fields
27,D27.2,Water meter reading,Watermeter,https://huggingface.co/datasets/rsnogueira/Watermeter,rsnogueira/Watermeter,UNVERIFIED (none on card),https://huggingface.co/datasets/rsnogueira/Watermeter,open,1104.6,0.289,no,https://huggingface.co/datasets/rsnogueira/Watermeter/resolve/main/data.csv,yes,UNVERIFIED,answer = value,n/a,continuous,yes,low,MAYBE,low,licence;label_origin
27,D27.2,Water meter reading,UniData water meters preview,https://huggingface.co/datasets/UniDataPro/water-meters,UniDataPro/water-meters,CC BY-NC-ND 4.0 (preview of paid set),https://huggingface.co/datasets/UniDataPro/water-meters,open,17.3,0.005,no,UNVERIFIED,no,UNVERIFIED,UNVERIFIED,n/a,UNVERIFIED,UNVERIFIED,low,MAYBE,low,rows;schema;origin
27,D27.3,Electricity meter reading,ElectricityMeterReadings1o4,https://huggingface.co/datasets/Praekelt/ElectricityMeterReadings1o4,Praekelt/ElectricityMeterReadings1o4,UNVERIFIED (none on card),https://huggingface.co/datasets/Praekelt/ElectricityMeterReadings1o4,open,44.2,44.2,no,https://datasets-server.huggingface.co/first-rows?dataset=Praekelt/ElectricityMeterReadings1o4&config=default&split=train,yes,UNVERIFIED,answer = reading,n/a,continuous,yes,low,MAYBE,low,licence;label_origin
27,D27.4,Meter type,utilitimetersai annotated dials,https://huggingface.co/datasets/utilitimetersai/Annotated-Mechanical-And-LCD-Utility-Meter-Dials-Dataset,utilitimetersai/Annotated-Mechanical-And-LCD-Utility-Meter-Dials-Dataset,CC BY-NC 4.0,https://huggingface.co/datasets/utilitimetersai/Annotated-Mechanical-And-LCD-Utility-Meter-Dials-Dataset,manual approval,3.2,0.002,no,none (401),no,UNVERIFIED,UNVERIFIED,UNVERIFIED,UNVERIFIED,UNVERIFIED,UNVERIFIED,GATED,low,most fields
28,D28.1,PV cell EL defect yes/no,ELPV,https://github.com/zae-bayern/elpv-dataset,bardroh/elpv-el-defects,CC BY-NC-SA 4.0,https://github.com/zae-bayern/elpv-dataset,open,90.3,9.1,no,https://raw.githubusercontent.com/zae-bayern/elpv-dataset/master/src/elpv_dataset/data/labels.csv,yes,human (inferred),yes if prob==1.0; no if 0.0,yes (1508 neg),prob 0/0.33/0.67/1; mono/poly,yes,none,MAYBE,med,label_origin
28,D28.2,Broken insulator yes/no,Powerline components and faults,https://huggingface.co/datasets/docmhvr/powerline-components-and-faults,docmhvr/powerline-components-and-faults,MIT,https://huggingface.co/datasets/docmhvr/powerline-components-and-faults,open,122.2,2.29,no,https://datasets-server.huggingface.co/first-rows?dataset=docmhvr/powerline-components-and-faults&config=default&split=train,yes,human,yes if 'Broken Insulator' in labels; no if Insulators present without it,yes (830 neg / 663 pos),Broken Cable;Broken Insulator;Cable;Insulators;Tower;Vegetation,yes (presence),none,USE,high,augmentation duplicates
28,D28.2,Broken insulator,broken-insulators-synthetic,https://huggingface.co/datasets/silera/broken-insulators-synthetic-detection,silera/broken-insulators-synthetic-detection,CC BY 4.0,https://huggingface.co/datasets/silera/broken-insulators-synthetic-detection,open,221.7,0.006,no,https://datasets-server.huggingface.co/first-rows?dataset=silera/broken-insulators-synthetic-detection&config=default&split=train,yes,generator (images),count boxes,no,UNVERIFIED names,yes,none,MAYBE,low,category names;negatives
28,D28.3,Broken cable yes/no,Powerline components and faults,https://huggingface.co/datasets/docmhvr/powerline-components-and-faults,docmhvr/powerline-components-and-faults,MIT,https://huggingface.co/datasets/docmhvr/powerline-components-and-faults,open,122.2,2.29,no,https://datasets-server.huggingface.co/first-rows?dataset=docmhvr/powerline-components-and-faults&config=default&split=train,yes,human,yes if 'Broken Cable' in labels,yes (887 neg / 907 pos),same,yes (presence),none,USE,high,augmentation duplicates
28,D28.4,Solar panel condition,solar-panel-inspection,https://huggingface.co/datasets/metalmerge/solar-panel-inspection,metalmerge/solar-panel-inspection,UNVERIFIED (none),https://huggingface.co/datasets/metalmerge/solar-panel-inspection,open,247.8,0.3,no,https://huggingface.co/api/datasets/metalmerge/solar-panel-inspection,folder listing only,UNVERIFIED,answer = folder name,yes (Clean),Bird-drop;Clean;Dusty;Snow-Covered;Electrical-damage;Physical-Damage,yes,low,MAYBE,low,licence;origin
28,D28.5,Wind turbine present,Airbus Wind Turbine Patches,https://www.kaggle.com/datasets/airbusgeo/airbus-wind-turbines-patches,jonathan-roberts1/Airbus-Wind-Turbines-Patches,CC BY-NC-SA 4.0,https://huggingface.co/datasets/jonathan-roberts1/Airbus-Wind-Turbines-Patches,open,147.7,147.7,yes,https://datasets-server.huggingface.co/rows?dataset=jonathan-roberts1/Airbus-Wind-Turbines-Patches&config=default&split=train&offset=71000&length=1,yes,UNVERIFIED,label,yes,no wind turbine;wind turbine,yes,none,SKIP,high,label_origin
28,D28.6,Thermal hotspot,Solar-Panel-Thermal-Drone-UAV-Images,https://huggingface.co/datasets/Manishsahu53/Solar-Panel-Thermal-Drone-UAV-Images,Manishsahu53/Solar-Panel-Thermal-Drone-UAV-Images,Apache-2.0,https://huggingface.co/datasets/Manishsahu53/Solar-Panel-Thermal-Drone-UAV-Images,open,19093.5,2250.9,yes,https://datasets-server.huggingface.co/first-rows?dataset=Manishsahu53/Solar-Panel-Thermal-Drone-UAV-Images&config=default&split=train,no labels,none,cannot compute,UNVERIFIED,none,UNVERIFIED,none,SKIP,high,labels
29,D29.1,Corrosion present/type,RF100 corrosion,https://universe.roboflow.com/roboflow-100/corrosion-bi3q3,LibreYOLO/corrosion-bi3q3,CC BY 4.0,https://huggingface.co/datasets/LibreYOLO/corrosion-bi3q3,open,67.4,0.001,no,https://huggingface.co/datasets/LibreYOLO/corrosion-bi3q3/raw/main/test/labels/KwanLoneDSCN1716_JPG_jpg.rf.554fa608f97c8382b117b87f478ba00a.txt,yes,UNVERIFIED,yes if class 1 present,few (5/105 test empty),Slippage;corrosion;crack,filter,none,MAYBE,low,label_origin;counts
29,D29.2,Sewer defect type,sewer-defect-crack-dataset,https://huggingface.co/datasets/ZhiyaYang/sewer-defect-crack-dataset,ZhiyaYang/sewer-defect-crack-dataset,UNVERIFIED (none),https://huggingface.co/datasets/ZhiyaYang/sewer-defect-crack-dataset,open,194.5,31.1,no,https://datasets-server.huggingface.co/first-rows?dataset=ZhiyaYang/sewer-defect-crack-dataset&config=default&split=train,yes,UNVERIFIED,label name,no,blockage;corrosion;crack,yes,none,MAYBE,low,licence;origin
29,D29.2,Sewer defect type,Sewer-pipe-defects,https://huggingface.co/datasets/SRuibo/Sewer-pipe-defects,SRuibo/Sewer-pipe-defects,CC BY 4.0,https://huggingface.co/datasets/SRuibo/Sewer-pipe-defects,open,2374.1,0.001,no,https://huggingface.co/datasets/SRuibo/Sewer-pipe-defects/raw/main/Sewer%20pipe%20defects/labels/train/PL_186_000.txt,yes,UNVERIFIED,single distinct class code,no (0 empty label files),CK;PL;SG;SL;TL;ZW (meanings UNVERIFIED),filter,none,MAYBE,low,class semantics;origin
29,D29.3,Gas plume present,GasLeakPlumes,https://huggingface.co/datasets/samhormozian/GasLeakPlumes,samhormozian/GasLeakPlumes,UNVERIFIED (none),https://huggingface.co/datasets/samhormozian/GasLeakPlumes,open,706.5,2.996,no,https://huggingface.co/datasets/samhormozian/GasLeakPlumes/resolve/main/dataset%20copy/annotations.json,yes,UNVERIFIED,yes if annotated,no (5487/5515 positive),Gas Leak Day;Gas Leak night,yes,none,SKIP,high,licence
30,D30.1,Pothole yes/no,RDD2022,https://github.com/sekilab/RoadDamageDetector,dronefreak/RDD2022,CC BY 4.0 (Figshare) / CC BY-SA 4.0 (HF card),https://figshare.com/articles/dataset/RDD2022_-_The_multi-national_Road_Damage_Dataset_released_through_CRDDC_2022/21431547,open,11078.8,0.37,no (HF) / yes official 13264 MB,https://huggingface.co/datasets/dronefreak/RDD2022/resolve/main/data/images/train/shard_000/metadata.jsonl,yes,human,yes if category 3 present,yes,longitudinal;transverse;alligator;pothole,yes for presence,faces/plates possible,USE,high,licence variant
30,D30.2,Road damage type,RDD2022,https://github.com/sekilab/RoadDamageDetector,dronefreak/RDD2022,CC BY 4.0 / CC BY-SA 4.0,https://figshare.com/articles/dataset/RDD2022_-_The_multi-national_Road_Damage_Dataset_released_through_CRDDC_2022/21431547,open,11078.8,0.37,no,https://huggingface.co/datasets/dronefreak/RDD2022/resolve/main/data/images/train/shard_000/metadata.jsonl,yes,human,single distinct category,n/a,D00;D10;D20;D40,filter single class,faces/plates possible,USE,high,licence variant
30,D30.3,Pothole severity,Pothole_classification,https://huggingface.co/datasets/Arpitraj01/Pothole_classification,Arpitraj01/Pothole_classification,MIT,https://huggingface.co/datasets/Arpitraj01/Pothole_classification,open,236.1,0.6,no,https://datasets-server.huggingface.co/rows?dataset=Arpitraj01/Pothole_classification&config=default&split=train&offset=100&length=1,yes,UNVERIFIED,label name,yes (none=36),low;medium;none;severe,yes,low,MAYBE,med,label_origin;severity criteria
30,D30.4,Bridge damage type,dacl10k,https://github.com/phiyodr/dacl10k-toolkit,Voxel51/dacl10k,CC BY 4.0,https://huggingface.co/datasets/Voxel51/dacl10k,open,5211.3,0.14,no,https://huggingface.co/datasets/Voxel51/dacl10k/resolve/main/samples.json (range 0-3MB),yes,UNVERIFIED,single damage label / presence per class,per-class yes; image-level no (2/381 empty),19 classes (13 damage + 6 objects),filter,graffiti text,MAYBE,med,label_origin
30,D30.5,Concrete defect,CODEBRIM,https://zenodo.org/records/2620293,h4tem/codebrim (mirror),other-nc + terms agreement,https://zenodo.org/records/2620293/files/license.md,form or terms agreement,36361,7907.8,yes,none,no,UNVERIFIED,UNVERIFIED,UNVERIFIED,UNVERIFIED,UNVERIFIED,none,GATED,med,rows
31,D31.1,crop healthy?,CCMT crop pest/disease (AgML),https://huggingface.co/datasets/Project-AgML/crop_pest_disease_classification,Project-AgML/crop_pest_disease_classification,CC-BY-4.0,https://huggingface.co/datasets/Project-AgML/crop_pest_disease_classification,open,8427,380,no,https://datasets-server.huggingface.co/first-rows?dataset=Project-AgML/crop_pest_disease_classification&config=raw&split=train,yes,human(inferred),yes iff label==healthy,yes (3235 healthy),18 labels x 4 crops,yes,none,USE,med,label_origin quote; overlap with used leaf-disease set
31,D31.2,seedling species / crop-or-weed,Aarhus plant seedlings,https://huggingface.co/datasets/Project-AgML/plant_seedlings_aarhus,Project-AgML/plant_seedlings_aarhus,CC-BY-SA-4.0,https://huggingface.co/datasets/Project-AgML/plant_seedlings_aarhus,open,1714.5,309.4,no,https://datasets-server.huggingface.co/first-rows?dataset=Project-AgML/plant_seedlings_aarhus&config=default&split=train,yes,human(inferred),label; crop iff in {maize;common_wheat;sugar_beet},yes (973 crop vs 4566 weed),12 species,yes,none,USE,med,label_origin quote
31,D31.3,oil palm FFB ripeness,Outdoor Tenera FFB (AgML),https://huggingface.co/datasets/Project-AgML/oil_palm_fruit_ripeness_classification,Project-AgML/oil_palm_fruit_ripeness_classification,CC-BY-4.0,https://huggingface.co/datasets/Project-AgML/oil_palm_fruit_ripeness_classification,open,1165.7,182.4,no,https://datasets-server.huggingface.co/first-rows?dataset=Project-AgML/oil_palm_fruit_ripeness_classification&config=default&split=train,yes,human(inferred),label,n/a (pick-one),Damaged15/Empty12/Overripe74/Ripe201/Unripe164,yes,none,USE,med,label_origin quote
31,D31.4,weed count maize field,Maize-Weed (AgML),https://huggingface.co/datasets/Project-AgML/maize_weed_detection,Project-AgML/maize_weed_detection,CC-BY-4.0,https://huggingface.co/datasets/Project-AgML/maize_weed_detection,open,817,402.3,no,https://datasets-server.huggingface.co/first-rows?dataset=Project-AgML/maize_weed_detection&config=default&split=train,yes,human(inferred),count(categories==1),UNVERIFIED,maize;weed,count only,none,MAYBE,med,zero-weed images; origin
31,D31.5,banana/mango ripe,fruit-ripeness-detection-dataset,https://huggingface.co/datasets/darthraider/fruit-ripeness-detection-dataset,darthraider/fruit-ripeness-detection-dataset,Apache-2.0 (mirror),https://huggingface.co/datasets/darthraider/fruit-ripeness-detection-dataset,open,390.9,35.48,no,https://datasets-server.huggingface.co/first-rows?dataset=darthraider/fruit-ripeness-detection-dataset&config=default&split=train,yes,UNVERIFIED,label startswith Ripe,yes,4,yes,low,MAYBE,med,label origin;upstream licence
31,D31.6,insect pest species,insect-pest-dataset,https://huggingface.co/datasets/EnmmmmOvO/insect-pest-dataset,EnmmmmOvO/insect-pest-dataset,MIT,https://huggingface.co/datasets/EnmmmmOvO/insect-pest-dataset,open,3188,299.4,no,https://datasets-server.huggingface.co/first-rows?dataset=EnmmmmOvO/insect-pest-dataset&config=default&split=train,yes,UNVERIFIED,needs class-name map,n/a,unnamed ints,yes,none,SKIP,med,class names; origin
31,D31.7,land cover tile,EuroSAT RGB,https://huggingface.co/datasets/timm/eurosat-rgb,timm/eurosat-rgb,MIT,https://huggingface.co/datasets/timm/eurosat-rgb,open,92.1,18.4,no,https://datasets-server.huggingface.co/first-rows?dataset=timm/eurosat-rgb&config=default&split=train,yes,human(inferred),label,n/a,10,yes,none,SKIP,high,tiny 64px
32,D32.1,goats present / majority,Greek sheep & goats drone,https://huggingface.co/datasets/AGRARIAN/greek_sheep_goats_dataset,AGRARIAN/greek_sheep_goats_dataset,Apache-2.0,https://huggingface.co/datasets/AGRARIAN/greek_sheep_goats_dataset,open,3627.7,0.5,no,https://huggingface.co/datasets/AGRARIAN/greek_sheep_goats_dataset/resolve/main/train/labels/0058dd32-DJI_20250224121827_0005_D_2260_6.txt,yes,human,any class0 line => goats,yes (890 empty label files),goat;sheep,presence/count,none,USE,high,overlapping patches
32,D32.2,sheep count drone,Aerial Sheep (Roboflow),https://huggingface.co/datasets/keremberke/aerial-sheep-object-detection,keremberke/aerial-sheep-object-detection,Public Domain,https://huggingface.co/datasets/keremberke/aerial-sheep-object-detection/blob/main/README.dataset.txt,open,451,UNVERIFIED (<393),no,https://datasets-server.huggingface.co/first-rows?dataset=keremberke/aerial-sheep-object-detection&config=default&split=train,yes,human(inferred),len(objects.category),UNVERIFIED,sheep,count,none,USE,med,3x augmented copies; valid zip size
32,D32.3,pig posture counts,Viewpoint-aware pig posture,https://huggingface.co/datasets/anilbhujel/viewpoint-aware-pig-posture-recognition,anilbhujel/viewpoint-aware-pig-posture-recognition,CC-BY-4.0,https://huggingface.co/datasets/anilbhujel/viewpoint-aware-pig-posture-recognition,open,1356.9,0.08,no,https://huggingface.co/datasets/anilbhujel/viewpoint-aware-pig-posture-recognition/resolve/main/viewpoint_aware_pig_posture_recognition/seenVP_test.csv,yes,human,group by image_id; count class_id,yes (per class),5 postures,count/presence,none,USE,med,per-class counts; label completeness
32,D32.4,fish family/species,Fish-Vista,https://huggingface.co/datasets/imageomics/fish-vista,imageomics/fish-vista,none at dataset level (per-row e.g. CC BY-NC),https://huggingface.co/datasets/imageomics/fish-vista,open,11895.9,0.1,no,https://datasets-server.huggingface.co/first-rows?dataset=imageomics/fish-vista&config=species_classification&split=train,yes,human(inferred),family/standardized_species,n/a,628+ species,yes,none,MAYBE,med,dataset licence
32,D32.5,aquarium animal type,RF100 aquarium,https://huggingface.co/datasets/Francesco/aquarium-qlnqy,Francesco/aquarium-qlnqy,cc (version unstated),https://huggingface.co/datasets/Francesco/aquarium-qlnqy,open,77.4,38.7,no,https://datasets-server.huggingface.co/first-rows?dataset=Francesco/aquarium-qlnqy&config=default&split=train,yes,human (crowdsourced),majority category,n/a,8,filter single-class,low (visitors),MAYBE,med,licence version
33,D33.1,camera-trap species,Channel Islands camera traps (LILA subset),https://huggingface.co/datasets/lila-bc-community/channel-islands-camera-traps,lila-bc-community/channel-islands-camera-traps,CDLA-Permissive-1.0,https://huggingface.co/datasets/lila-bc-community/channel-islands-camera-traps,open,3675.4,415.2,no,https://datasets-server.huggingface.co/first-rows?dataset=lila-bc-community/channel-islands-camera-traps&config=default&split=train,yes,human,unique objects.category,no (empties removed),bird;fox;other;rodent;skunk,mostly,low (humans removed),USE,high,class balance
33,D33.3,tree species,Slovak tree species (AgML),https://huggingface.co/datasets/Project-AgML/tree_species_classification_slovak_normal_cropped,Project-AgML/tree_species_classification_slovak_normal_cropped,CC-BY-4.0,https://huggingface.co/datasets/Project-AgML/tree_species_classification_slovak_normal_cropped,open,2430.9,393.7,no,https://datasets-server.huggingface.co/first-rows?dataset=Project-AgML/tree_species_classification_slovak_normal_cropped&config=default&split=train,yes,human(inferred),label,n/a,beech300/fir337/spruce396/oak334,yes,none,USE,med,label_origin quote
33,D33.4,wildfire smoke yes/no,Simuletic long-distance wildfire,https://huggingface.co/datasets/Simuletic/Long_Distance_Wildfire_Smoke_Detection_Dataset,Simuletic/Long_Distance_Wildfire_Smoke_Detection_Dataset,CC-BY-NC-4.0 (yaml) vs CC BY 4.0 (text),https://huggingface.co/datasets/Simuletic/Long_Distance_Wildfire_Smoke_Detection_Dataset,open,431.3,2.3,no,https://datasets-server.huggingface.co/first-rows?dataset=Simuletic/Long_Distance_Wildfire_Smoke_Detection_Dataset&config=default&split=train,yes,generator,non-empty label,no (239/239 positive),smoke,yes,none,SKIP,high,licence conflict
34,D34.1,no safety vest,PPE detection (VincentGOURBIN),https://huggingface.co/datasets/VincentGOURBIN/ppe-detection,VincentGOURBIN/ppe-detection,CC-BY-4.0,https://huggingface.co/datasets/VincentGOURBIN/ppe-detection/blob/main/data.yaml,open,174.3,0.05,no,https://huggingface.co/datasets/VincentGOURBIN/ppe-detection/tree/main/valid/labels,yes,human(inferred),any class2 (no-vest),yes (95/164 valid without),helmet;no-helmet;no-vest;person;vest,yes (image-level any),high (faces; WIDER-like group photos),USE,med,label_origin quote
34,D34.2,no helmet,PPE detection (VincentGOURBIN),https://huggingface.co/datasets/VincentGOURBIN/ppe-detection,VincentGOURBIN/ppe-detection,CC-BY-4.0,https://huggingface.co/datasets/VincentGOURBIN/ppe-detection/blob/main/data.yaml,open,174.3,0.05,no,https://huggingface.co/datasets/VincentGOURBIN/ppe-detection/tree/main/valid/labels,yes,human(inferred),any class1 (no-helmet),yes (133/164 valid without),same,yes,high (faces),USE,med,label_origin quote
34,D34.2b,no helmet (merged Kaggle),ppe-dataset (jhboyo),https://huggingface.co/datasets/jhboyo/ppe-dataset,jhboyo/ppe-dataset,MIT (upstream unverified),https://huggingface.co/datasets/jhboyo/ppe-dataset,open,1862,0.01,no,https://datasets-server.huggingface.co/first-rows?dataset=jhboyo/ppe-dataset&config=default&split=train,no,human(inferred),any 'head',few (49 empty),helmet;head;vest,yes,med (faces),SKIP,med,dup of used hard-hat source; no label rows
34,D34.3,person with forklift,keremberke forklift,https://huggingface.co/datasets/keremberke/forklift-object-detection,keremberke/forklift-object-detection,CC BY 4.0,https://huggingface.co/datasets/keremberke/forklift-object-detection,open,20.4,2.77,no,https://datasets-server.huggingface.co/first-rows?dataset=keremberke/forklift-object-detection&config=full&split=train,yes,human inferred,any person and any forklift,yes (forklift-only images),forklift;person,yes,med (people),USE,med,box exhaustiveness
34,D34.4,construction PPE missing,Construction Site Safety (Roboflow),https://huggingface.co/datasets/keremberke/construction-safety-object-detection,keremberke/construction-safety-object-detection,CC-BY-4.0,https://huggingface.co/datasets/keremberke/construction-safety-object-detection/blob/main/README.dataset.txt,open,27.7,22.3,no,https://datasets-server.huggingface.co/first-rows?dataset=keremberke/construction-safety-object-detection&config=full&split=train,yes,human(inferred),any no-* class,yes (per item),17,yes (image-level),med (faces; YouTube),USE,med,416px; per-item negative counts
34,D34.5,seat belt worn,seatbelt-detection-v2,https://huggingface.co/datasets/c3rl/seatbelt-detection-v2,c3rl/seatbelt-detection-v2,Apache-2.0 (yaml only),https://huggingface.co/datasets/c3rl/seatbelt-detection-v2,open,3190.3,0.61,no,https://datasets-server.huggingface.co/first-rows?dataset=c3rl/seatbelt-detection-v2&config=default&split=train,yes,UNVERIFIED (likely generated),label,yes (1000 no/1500 yes),2,yes,med (faces),MAYBE,low,image+label origin
34,D34.6,person lying,Simuletic CCTV fall,https://huggingface.co/datasets/Simuletic/CCTV_Incident_Dataset_Fall_Lying_Down_Detection,Simuletic/CCTV_Incident_Dataset_Fall_Lying_Down_Detection,CC-BY-4.0,https://huggingface.co/datasets/Simuletic/CCTV_Incident_Dataset_Fall_Lying_Down_Detection,open,171.8,1.0,no,https://datasets-server.huggingface.co/first-rows?dataset=Simuletic/CCTV_Incident_Dataset_Fall_Lying_Down_Detection&config=default&split=train,no,generator,UNVERIFIED,likely no,laying,UNVERIFIED,none (synthetic),SKIP,med,label rows; negatives
34,D34.7,smoking,smoking_classification,https://huggingface.co/datasets/ccclllwww/smoking_classification,ccclllwww/smoking_classification,Apache-2.0,https://huggingface.co/datasets/ccclllwww/smoking_classification,open,1106.5,0.001,no,https://datasets-server.huggingface.co/first-rows?dataset=ccclllwww/smoking_classification&config=default&split=train,no,UNVERIFIED,UNVERIFIED,UNVERIFIED,UNVERIFIED,UNVERIFIED,high (faces),SKIP,low,labels
35,D35.1,fire or smoke yes/no,D-Fire (mirror),https://github.com/gaiasd/DFireDataset,badsaarow/d-fire,NONE STATED,https://github.com/gaiasd/DFireDataset,open (mirror),4208.1,0.001,no,https://datasets-server.huggingface.co/first-rows?dataset=badsaarow/d-fire&config=default&split=train,yes,human(inferred),label != '',yes (9838 none per owner),fire;smoke (id map unverified),yes,low,MAYBE,med,licence; class id map
35,D35.1b,fire or smoke yes/no,FireSmokeDataset (Vertex-Test),https://huggingface.co/datasets/Vertex-Test/FireSmokeDataset,Vertex-Test/FireSmokeDataset,Apache-2.0 (yaml only),https://huggingface.co/datasets/Vertex-Test/FireSmokeDataset,open,381.3,0.1,no,https://datasets-server.huggingface.co/first-rows?dataset=baizhanquan/firesafety-fire-smoke&config=default&split=train,yes,UNVERIFIED (Roboflow; some SD images),non-empty label,yes (483 empty),fire;smoke,yes,low,MAYBE,low,label/image origin
35,D35.1c,fire or smoke yes/no,FASDD_CV,https://huggingface.co/datasets/seawsurf/fire_smoke_dataset_fasdd_cv,seawsurf/fire_smoke_dataset_fasdd_cv,CC-BY-4.0,https://huggingface.co/datasets/seawsurf/fire_smoke_dataset_fasdd_cv,open,3410.6,3410.6,yes,https://datasets-server.huggingface.co/splits?dataset=seawsurf/fire_smoke_dataset_fasdd_cv,no,UNVERIFIED,UNVERIFIED,UNVERIFIED,UNVERIFIED,UNVERIFIED,low,SKIP,high,single archive
35,D35.3,weapon visible / gun vs knife,HARIS weapon detection curated,https://huggingface.co/datasets/Turki-Alshuaibi/haris-weapon-detection-dataset-curated,Turki-Alshuaibi/haris-weapon-detection-dataset-curated,CC-BY-4.0 (UCF-Crime upstream unverified),https://huggingface.co/datasets/Turki-Alshuaibi/haris-weapon-detection-dataset-curated,open,2683.2,0.001,no,https://datasets-server.huggingface.co/first-rows?dataset=Turki-Alshuaibi/haris-weapon-detection-dataset-curated&config=default&split=train,yes,human(inferred),non-empty label; class set,yes (2782 empty),gun;knife,yes,high (faces; violence),USE,med,upstream licences; origin quote
35,D35.3b,weapon type,WeaponDetection (Subh775),https://huggingface.co/datasets/Subh775/WeaponDetection,Subh775/WeaponDetection,CC-BY-4.0,https://huggingface.co/datasets/Subh775/WeaponDetection,open,583,74.2,no,https://datasets-server.huggingface.co/first-rows?dataset=Subh775/WeaponDetection&config=default&split=train,yes,human(inferred),category lookup,UNVERIFIED,29 messy,mostly,med,MAYBE,low,negatives; class merge
35,D35.3c,gun in CCTV,US Real-time gun detection CCTV,https://huggingface.co/datasets/jsalazar/US-Real-time-gun-detection-in-CCTV-An-open-problem-dataset,jsalazar/US-Real-time-gun-detection-in-CCTV-An-open-problem-dataset,CC-BY-NC-4.0,https://huggingface.co/datasets/jsalazar/US-Real-time-gun-detection-in-CCTV-An-open-problem-dataset,open,2718,68.3,no,https://datasets-server.huggingface.co/first-rows?dataset=jsalazar/US-Real-time-gun-detection-in-CCTV-An-open-problem-dataset&config=default&split=train,no,UNVERIFIED,UNVERIFIED,UNVERIFIED,UNVERIFIED,UNVERIFIED,high,MAYBE,low,labels; NC
36,D36.x,traffic sign (map scenes),traffic-sign-bench,https://huggingface.co/datasets/emb-ai/traffic-sign-bench,emb-ai/traffic-sign-bench,ODbL,https://huggingface.co/datasets/emb-ai/traffic-sign-bench,open,626.7,0.001,no,https://datasets-server.huggingface.co/first-rows?dataset=emb-ai/traffic-sign-bench&config=catalog&split=train,yes,generator,n/a (map not photo),n/a,25 signs,n/a,none,SKIP,high,not a sign photo
36,D36.1,parking lot occupancy,PKLot (redistribution),https://web.inf.ufpr.br/vri/databases/parking-lot-database/,dronefreak/PKLot,CC-BY-4.0,https://huggingface.co/datasets/dronefreak/PKLot,open,3909.7,0.001,no,https://datasets-server.huggingface.co/first-rows?dataset=dronefreak/PKLot&config=default&split=train,yes,human,mean(categories)>0.5 etc.,yes (both classes every frame),vacant;occupied,yes (aggregate),low (distant cars),USE,high,none
36,D36.2,rider helmet,Bike helmet (cute-face COCO),https://huggingface.co/datasets/cute-face/bike-helmet-dataset,cute-face/bike-helmet-dataset,CC-BY-4.0 (COCO/VOC parts only),https://huggingface.co/datasets/cute-face/bike-helmet-dataset,open,773.4,0.1,no,https://huggingface.co/datasets/cute-face/bike-helmet-dataset/resolve/main/valid/_annotations.coco.json,yes,human(inferred),no category 2 => all helmeted,yes (74/127 valid all-helmeted),With Helmet;Without Helmet,mostly (15/127 mixed),med (faces),USE,med,416px; origin quote
36,D36.3,vehicle class,RF100 vehicles,https://huggingface.co/datasets/Francesco/vehicles-q0x2v,Francesco/vehicles-q0x2v,cc (version unstated),https://huggingface.co/datasets/Francesco/vehicles-q0x2v,open,440.4,UNVERIFIED,no,https://datasets-server.huggingface.co/first-rows?dataset=Francesco/vehicles-q0x2v&config=default&split=train,yes,human (crowdsourced),majority coarse class,n/a,13,no (multi),low,MAYBE,med,licence version
36,D36.4,traffic light state,LISA traffic lights,https://huggingface.co/datasets/dronefreak/LISA-Traffic-Lights,dronefreak/LISA-Traffic-Lights,CC-BY-NC-SA-4.0,https://huggingface.co/datasets/dronefreak/LISA-Traffic-Lights,open,5057.8,0.001,no,https://datasets-server.huggingface.co/first-rows?dataset=dronefreak/LISA-Traffic-Lights&config=default&split=train,yes,human,category lookup,UNVERIFIED,UNVERIFIED names,multi,low,MAYBE,low,class names; NC; tiny objects
36,D36.6,road-user count fisheye,FishEye8K (Voxel51),https://huggingface.co/datasets/Voxel51/fisheye8k,Voxel51/fisheye8k,CC-BY-NC-SA-4.0,https://huggingface.co/datasets/Voxel51/fisheye8k,open,14415.4,39.4,no,https://datasets-server.huggingface.co/first-rows?dataset=Voxel51/fisheye8k&config=default&split=train,no,human,count by class,UNVERIFIED,UNVERIFIED,multi,low,MAYBE,low,labels not pasted; NC
37,D37.1,medical page document type,Synthetic Medical Document Recognition Benchmark,https://huggingface.co/datasets/morzel85/synthetic-medical-document-recognition-benchmark,morzel85/synthetic-medical-document-recognition-benchmark,CC-BY-4.0,https://huggingface.co/datasets/morzel85/synthetic-medical-document-recognition-benchmark,open,31211.3,0.08,no,https://huggingface.co/api/datasets/morzel85/synthetic-medical-document-recognition-benchmark?blobs=true,yes,generator,filename category token,n/a,~10 categories,yes,none (synthetic),USE,high,none
37,D37.2,capture type / clipped,Synthetic Medical Document Recognition Benchmark,https://huggingface.co/datasets/morzel85/synthetic-medical-document-recognition-benchmark,morzel85/synthetic-medical-document-recognition-benchmark,CC-BY-4.0,https://huggingface.co/datasets/morzel85/synthetic-medical-document-recognition-benchmark,open,31211.3,0.08,no,https://huggingface.co/api/datasets/morzel85/synthetic-medical-document-recognition-benchmark?blobs=true,yes,generator,variant token (clear/photocopy/photo; cli),yes,13 variants,yes,none,USE,high,none
37,D37.4,bill vs discharge summary,noisy medical document images,https://huggingface.co/datasets/hmnshudhmn24/noisy-medical-document-images-ocr,hmnshudhmn24/noisy-medical-document-images-ocr,NONE STATED,https://huggingface.co/datasets/hmnshudhmn24/noisy-medical-document-images-ocr,open,316.2,0.19,no,https://datasets-server.huggingface.co/first-rows?dataset=hmnshudhmn24/noisy-medical-document-images-ocr&config=default&split=train,yes,generator,label,yes (500/500),bills;discharge_summaries,yes,low (real hospital names),MAYBE,med,licence
37,D37.4b,medical doc type (AU),synthetic Australian medical docs sample,https://huggingface.co/datasets/RootCauseAnalytics/synthetic-australian-medical-documents-sample,RootCauseAnalytics/synthetic-australian-medical-documents-sample,CC-BY-NC-4.0,https://huggingface.co/datasets/RootCauseAnalytics/synthetic-australian-medical-documents-sample,open,23.7,0.004,no,https://huggingface.co/datasets/RootCauseAnalytics/synthetic-australian-medical-documents-sample/resolve/main/ground_truth.csv,yes,generator,document_type column,n/a,~10 doc types,yes,none (synthetic),MAYBE,med,NC; PDF render step
38,D38.x,pill detection (KR),healtheat-pill-yolo,https://huggingface.co/datasets/wony98/healtheat-pill-yolo,wony98/healtheat-pill-yolo,Apache-2.0 + AI Hub terms,https://huggingface.co/datasets/wony98/healtheat-pill-yolo,login (upstream AI Hub),18793,0.001,no,https://datasets-server.huggingface.co/first-rows?dataset=wony98/healtheat-pill-yolo&config=default&split=train,yes,human(inferred),class lookup,UNVERIFIED,UNVERIFIED,multi,none,GATED,low,upstream terms
38,D38.1,carton vs leaflet / imported,TW drug labels vision (TFDA),https://huggingface.co/datasets/twinkle-ai/tw-drug-labels-vision,twinkle-ai/tw-drug-labels-vision,CC-BY-4.0,https://huggingface.co/datasets/twinkle-ai/tw-drug-labels-vision,open,12512.9,147,no,https://datasets-server.huggingface.co/first-rows?dataset=twinkle-ai/tw-drug-labels-vision&config=default&split=train,yes,mixed (registry human; text fields machine),source_type; license_id contains 輸,yes,carton;leaflet,yes,none,USE,med,shard-set duplication; import-prefix rule
38,D38.2,pill product / colour,RF100 pills,https://huggingface.co/datasets/LibreYOLO/pills-sxdht,LibreYOLO/pills-sxdht,CC-BY-4.0,https://huggingface.co/datasets/LibreYOLO/pills-sxdht/blob/main/data.yaml,open,24.6,0.001,no,https://huggingface.co/datasets/LibreYOLO/pills-sxdht/tree/main/test/labels,yes,human(inferred),class name lookup,n/a,4 products + 4 colours,yes,none,USE,med,origin quote
38,D38.3,count medicine boxes,Medication Boxes Arabic/Latin,https://huggingface.co/datasets/ApyHTML19/Medication_Boxes_Arabe_Latin,ApyHTML19/Medication_Boxes_Arabe_Latin,MIT,https://huggingface.co/datasets/ApyHTML19/Medication_Boxes_Arabe_Latin,open,91.8,0.5,no,https://huggingface.co/datasets/ApyHTML19/Medication_Boxes_Arabe_Latin/resolve/main/annotations/instances_val.json,yes,human(inferred),count annotations per image,no zero-box images,medicine_box,yes,low,USE,med,origin quote
38,D38.4,pill reference,pill-reference-images,https://huggingface.co/datasets/Pjshana/pill-reference-images,Pjshana/pill-reference-images,NONE STATED,https://huggingface.co/datasets/Pjshana/pill-reference-images,open,1023.9,0.17,no,https://datasets-server.huggingface.co/first-rows?dataset=Pjshana/pill-reference-images&config=default&split=train,no,external (NDC lookup),needs RxNav lookup,n/a,NDC,yes,none,MAYBE,low,licence; labels
38,D38.5,blister,blister_data,https://huggingface.co/datasets/ABINSHA/blister_data,ABINSHA/blister_data,NONE STATED,https://huggingface.co/datasets/ABINSHA/blister_data,open,39.3,0.001,no,https://datasets-server.huggingface.co/first-rows?dataset=ABINSHA/blister_data&config=default&split=train,no,UNVERIFIED,n/a,n/a,n/a,n/a,none,SKIP,high,everything
39,D39.1,cat or dog / breed,Oxford-IIIT Pet (timm),https://huggingface.co/datasets/timm/oxford-iiit-pet,timm/oxford-iiit-pet,CC-BY-SA-4.0,https://huggingface.co/datasets/timm/oxford-iiit-pet,open,790.3,377.6,no,https://datasets-server.huggingface.co/first-rows?dataset=timm/oxford-iiit-pet&config=default&split=train,yes,human(paper),label_cat_dog; label,n/a (both classes),37 breeds; cat1188/dog2492,yes,low (owners),USE,high,label_origin quote
39,D39.1b,cat or dog,cats_vs_dogs (Asirra),https://huggingface.co/datasets/microsoft/cats_vs_dogs,microsoft/cats_vs_dogs,unknown,https://huggingface.co/datasets/microsoft/cats_vs_dogs,open,721.7,330.3,no,https://datasets-server.huggingface.co/first-rows?dataset=microsoft/cats_vs_dogs&config=default&split=train,yes,human (crowdsourced),labels,n/a,cat11741/dog11669,yes,low,MAYBE,med,licence
39,D39.3,dog breed 120,Stanford Dogs (Voxel51),https://huggingface.co/datasets/Voxel51/StanfordDogs,Voxel51/StanfordDogs,NONE STATED,https://huggingface.co/datasets/Voxel51/StanfordDogs,open,789.8,7.0,no,https://datasets-server.huggingface.co/first-rows?dataset=Voxel51/StanfordDogs&config=default&split=train,no,human(ImageNet),samples.json lookup,n/a,120,yes,low,MAYBE,low,licence; label rows
40,D40.1,plankton taxon,NES plankton IFCB,https://huggingface.co/datasets/sosiklab/NES-plankton-classifier-2022-dataset,sosiklab/NES-plankton-classifier-2022-dataset,CC-BY-4.0,https://huggingface.co/datasets/sosiklab/NES-plankton-classifier-2022-dataset,open,1576.4,UNVERIFIED (<232.7),no,https://datasets-server.huggingface.co/first-rows?dataset=sosiklab/NES-plankton-classifier-2022-dataset&config=default&split=train,yes,human (expert),classname,yes (detritus etc.),~100 taxa,yes,none,SKIP,high,tiny 40-100px
40,D40.1b,phytoplankton species,Bloombio phytoplankton microscopy,https://huggingface.co/datasets/bloombio/phytoplankton-microscopy,bloombio/phytoplankton-microscopy,CC-BY-4.0,https://huggingface.co/datasets/bloombio/phytoplankton-microscopy,open,42152.3,42.7,no,https://datasets-server.huggingface.co/first-rows?dataset=bloombio/phytoplankton-microscopy&config=classification&split=validation,no,UNVERIFIED,species column,UNVERIFIED,43 species,UNVERIFIED,none,MAYBE,low,rows; schema; origin
40,D40.2,beetle tray count / genus,NEON 2018 beetles,https://huggingface.co/datasets/imageomics/2018-NEON-beetles,imageomics/2018-NEON-beetles,CC-BY-SA-4.0,https://huggingface.co/datasets/imageomics/2018-NEON-beetles,open,5866.1,19.5,no,https://datasets-server.huggingface.co/first-rows?dataset=imageomics/2018-NEON-beetles&config=individual_specimens&split=train,yes,human,rows per groupImageFilePath; genus=first word,n/a,many species,yes (one species per tray),none,USE,med,count completeness
40,D40.4,colony count,colony-cfu-counting-coco,https://huggingface.co/datasets/rotsl/colony-cfu-counting-coco,rotsl/colony-cfu-counting-coco,MIT,https://huggingface.co/datasets/rotsl/colony-cfu-counting-coco,manual approval,287.1,UNVERIFIED,no,https://datasets-server.huggingface.co/splits?dataset=rotsl/colony-cfu-counting-coco,no,UNVERIFIED,count annotations,UNVERIFIED,UNVERIFIED,UNVERIFIED,none,GATED,low,all labels
40,D40.5,pollen taxon,Pollen (renders),https://huggingface.co/datasets/Etiiir/Pollen,Etiiir/Pollen,CC-BY-NC-4.0,https://huggingface.co/datasets/Etiiir/Pollen,open,211.1,0.001,no,https://datasets-server.huggingface.co/first-rows?dataset=Etiiir/Pollen&config=default&split=train,yes,generator(render),folder name,n/a,many,yes,none,SKIP,med,tiny 64px; NC
41,D41.1,Which application is shown,ScreenSpot-Pro,https://huggingface.co/datasets/likaixin/ScreenSpot-Pro,likaixin/ScreenSpot-Pro,MIT,https://raw.githubusercontent.com/likaixin2000/ScreenSpot-Pro-GUI-Grounding/main/LICENSE,open,3376,0.02,no,https://huggingface.co/datasets/likaixin/ScreenSpot-Pro/resolve/main/annotations/illustrator_windows.json,yes,human,answer=application (dedupe img_filename),n/a,23 apps + 3 OS-common,yes,low (paths/usernames possible),USE,high,paper annotation method
41,D41.2,Which OS,ScreenSpot-Pro,https://huggingface.co/datasets/likaixin/ScreenSpot-Pro,likaixin/ScreenSpot-Pro,MIT,https://raw.githubusercontent.com/likaixin2000/ScreenSpot-Pro-GUI-Grounding/main/LICENSE,open,3376,0.02,no,https://huggingface.co/datasets/likaixin/ScreenSpot-Pro/resolve/main/annotations/illustrator_windows.json,yes,human,answer=platform,n/a,windows/macos/linux,yes,low,USE,high,OS confounded with app
41,D41.3,Software category,ScreenSpot-Pro,https://huggingface.co/datasets/likaixin/ScreenSpot-Pro,likaixin/ScreenSpot-Pro,MIT,https://raw.githubusercontent.com/likaixin2000/ScreenSpot-Pro-GUI-Grounding/main/LICENSE,open,3376,0.02,no,https://huggingface.co/datasets/likaixin/ScreenSpot-Pro/resolve/main/annotations/illustrator_windows.json,yes,human,answer=group,n/a,Dev/Creative/CAD/Scientific/Office/OS,yes,low,USE,high,
42,D42.1,Screen type,Enrico,https://github.com/luileito/enrico,Leonardo6/enrico (mirror),MIT,https://raw.githubusercontent.com/luileito/enrico/master/LICENSE,open,236,0.05,yes (screenshots zip 110MB; per-row via /rows),https://raw.githubusercontent.com/luileito/enrico/master/design_topics.csv,yes,human,answer=topic,n/a,20 topics (list 265 … dialer 6),yes,low,USE,high,
42,D42.2,Is login screen,Enrico,https://github.com/luileito/enrico,Leonardo6/enrico (mirror),MIT,https://raw.githubusercontent.com/luileito/enrico/master/LICENSE,open,236,0.05,yes (110MB zip),https://raw.githubusercontent.com/luileito/enrico/master/design_topics.csv,yes,human,yes if topic==login,yes (141 vs 1319),login/other,yes,low,USE,high,
42,D42.3,Website vertical,Multimodal-Mind2Web,https://huggingface.co/datasets/osunlp/Multimodal-Mind2Web,osunlp/Multimodal-Mind2Web,openrail,https://huggingface.co/datasets/osunlp/Multimodal-Mind2Web,open,13577,217.7,no,https://datasets-server.huggingface.co/first-rows?dataset=osunlp/Multimodal-Mind2Web&config=default&split=train,yes,human (inferred),answer=domain,n/a,Travel/Shopping/Entertainment,yes,low-med,MAYBE,med,label origin; licence fit for data
42,D42.4,UI visual defect,multiwindow-gui-defect-benchmark,https://huggingface.co/datasets/zxy6654/multiwindow-gui-defect-benchmark,zxy6654/multiwindow-gui-defect-benchmark,cc-by-4.0,https://huggingface.co/datasets/zxy6654/multiwindow-gui-defect-benchmark,open,92.5,0.01,no,https://datasets-server.huggingface.co/first-rows?dataset=zxy6654/multiwindow-gui-defect-benchmark&config=default&split=train,yes (image only),UNVERIFIED,cannot compute (no label column),unknown,none,unknown,low,SKIP,high,label origin; labels
43,D43.1,Chart type,ChartBench,https://huggingface.co/datasets/SincereX/ChartBench,SincereX/ChartBench,MIT,https://huggingface.co/datasets/SincereX/ChartBench,open,10449,3.86,yes (test.zip 227.7MB; range-readable),https://huggingface.co/datasets/SincereX/ChartBench/resolve/main/test.jsonl,yes,generator,answer=type.chart,n/a,bar/line/pie/combination/radar/area/box/scatter/node_link,yes,none,USE,med,per-file zip extraction; data-generation method
43,D43.2,Is A higher than B,ChartBench,https://huggingface.co/datasets/SincereX/ChartBench,SincereX/ChartBench,MIT,https://huggingface.co/datasets/SincereX/ChartBench,open,10449,3.86,yes (227.7MB range-readable),https://huggingface.co/datasets/SincereX/ChartBench/resolve/main/test.jsonl,yes,generator,task==VC; answer=conversation[i].label,yes (balanced pairs),Yes/No,yes,none,USE,med,
43,D43.2,Is A higher than B,FigureQA,https://www.microsoft.com/en-us/research/project/figureqa-dataset/,vikhyatk/figureqa (mirror),UNVERIFIED (click-through),https://www.microsoft.com/en-us/research/project/figureqa-dataset/download/,manual approval (agree & download),2218,321.4,no,https://datasets-server.huggingface.co/first-rows?dataset=vikhyatk/figureqa&config=default&split=train,yes,generator,answer=qa.answer,yes,Yes/No,yes,none,GATED,med,licence text
43,D43.3,Value-claim check,ChartBench,https://huggingface.co/datasets/SincereX/ChartBench,SincereX/ChartBench,MIT,https://huggingface.co/datasets/SincereX/ChartBench,open,10449,3.86,yes (227.7MB range-readable),https://huggingface.co/datasets/SincereX/ChartBench/resolve/main/test.jsonl,yes,generator,task==VE; answer=label,yes,Yes/No,yes,none,USE,med,
43,D43.4,Do any lines intersect,CharXiv,https://huggingface.co/datasets/princeton-nlp/CharXiv,princeton-nlp/CharXiv,cc-by-sa-4.0,https://huggingface.co/datasets/princeton-nlp/CharXiv,open,375.9,91.7,no,https://datasets-server.huggingface.co/first-rows?dataset=princeton-nlp/CharXiv&config=default&split=validation,yes,human (inferred),descriptive_qK==11 -> descriptive_aK,yes (balance unverified),Yes/No,yes,low,USE,med,label origin quote; q11 balance
43,D43.5,Number of subplots,CharXiv,https://huggingface.co/datasets/princeton-nlp/CharXiv,princeton-nlp/CharXiv,cc-by-sa-4.0,https://huggingface.co/datasets/princeton-nlp/CharXiv,open,375.9,91.7,no,https://datasets-server.huggingface.co/first-rows?dataset=princeton-nlp/CharXiv&config=default&split=validation,yes,human (inferred),bucket(num_subplots),n/a,1/2/3/4/5+,yes,low,USE,med,class counts
43,D43.6,Which series/bar is max,DVQA,https://github.com/kushalkafle/DVQA_dataset,vikhyatk/dvqa (mirror),UNVERIFIED,https://github.com/kushalkafle/DVQA_dataset,open,4272.5,473.3,no,https://datasets-server.huggingface.co/first-rows?dataset=vikhyatk/dvqa&config=default&split=train,yes,generator,answer=qa.answer for 'largest value' question,n/a,bar labels,yes,none,MAYBE,med,licence
43,D43.6,Which series is max,FigureQA,https://www.microsoft.com/en-us/research/project/figureqa-dataset/,vikhyatk/figureqa (mirror),UNVERIFIED (click-through),https://www.microsoft.com/en-us/research/project/figureqa-dataset/download/,manual approval,2218,321.4,no,https://datasets-server.huggingface.co/first-rows?dataset=vikhyatk/figureqa&config=default&split=train,yes,generator,yes/no 'Is X the maximum?',yes,colour names,yes,none,GATED,med,licence text
44,D44.1,Is area flooded,FloodNet Track 2,https://github.com/BinaLab/FloodNet-Challenge-EARTHVISION2021,takara-ai/FloodNet_2021-Track_2_Dataset_HF,cc-by-sa-4.0 (mirror only),https://huggingface.co/datasets/takara-ai/FloodNet_2021-Track_2_Dataset_HF,open,12310,0.001 (ann json); 7 (image),no,https://huggingface.co/datasets/takara-ai/FloodNet_2021-Track_2_Dataset_HF/resolve/main/train_image/ann/10170.JPG.json,yes,human,overall condition == flooded,yes (~17% flooded),flooded/non flooded,yes,low,MAYBE,med,owner licence
44,D44.2,Is entire road flooded,FloodNet Track 2,https://github.com/BinaLab/FloodNet-Challenge-EARTHVISION2021,takara-ai/FloodNet_2021-Track_2_Dataset_HF,cc-by-sa-4.0 (mirror only),https://huggingface.co/datasets/takara-ai/FloodNet_2021-Track_2_Dataset_HF,open,12310,0.001,no,https://huggingface.co/datasets/takara-ai/FloodNet_2021-Track_2_Dataset_HF/resolve/main/train_image/ann/10171.JPG.json,yes,human,Yes_No answer (invert for 'non flooded' phrasing),yes,Yes/No,yes,low,MAYBE,med,owner licence
44,D44.3,Building count bucket,FloodNet Track 2,https://github.com/BinaLab/FloodNet-Challenge-EARTHVISION2021,takara-ai/FloodNet_2021-Track_2_Dataset_HF,cc-by-sa-4.0 (mirror only),https://huggingface.co/datasets/takara-ai/FloodNet_2021-Track_2_Dataset_HF,open,12310,0.001,no,https://huggingface.co/datasets/takara-ai/FloodNet_2021-Track_2_Dataset_HF/resolve/main/train_image/ann/10170.JPG.json,yes,human,bucket(Simple_Counting),n/a,0/1-3/4-6/7+,yes,low,MAYBE,low,owner licence; count noise
44,D44.4,Land-use type,WHU-RS19,https://huggingface.co/datasets/jonathan-roberts1/WHU-RS19,jonathan-roberts1/WHU-RS19,cc-by-4.0 (mirror only),https://huggingface.co/datasets/jonathan-roberts1/WHU-RS19,open,113.3,113.3,no,https://datasets-server.huggingface.co/rows?dataset=jonathan-roberts1/WHU-RS19&config=default&split=train&offset=560&length=1,yes,human (inferred),answer=label,n/a,19 classes ~50 each,yes,none,MAYBE,med,owner licence; imagery rights
44,D44.5,Truck present (drone),VisDrone2019-DET,https://github.com/VisDrone/VisDrone-Dataset,Voxel51/VisDrone2019-DET,conflict: cc-by-sa-3.0 yaml vs CC BY-NC-SA 3.0 text,https://huggingface.co/datasets/Voxel51/VisDrone2019-DET,open,2059.8,0.02 (image); 118.5 (samples.json; range-readable),no,https://huggingface.co/datasets/Voxel51/VisDrone2019-DET/resolve/main/samples.json,yes,human (inferred),any detection label==truck,yes (unquantified),10 object classes,yes,med (pedestrians),MAYBE,med,owner licence; negatives count
44,D44.6,Rooftop solar,PatternNet,https://huggingface.co/datasets/jonathan-roberts1/PatternNet,jonathan-roberts1/PatternNet,other,https://huggingface.co/datasets/jonathan-roberts1/PatternNet,open,1422.1,697.6,no,https://datasets-server.huggingface.co/first-rows?dataset=jonathan-roberts1/PatternNet&config=default&split=train,yes,human (inferred),label==solar panel,yes,38 classes,yes,none,SKIP,high,tiny 256px images
45,D45.1,Auto-mark MCQ item,ScienceQA,https://github.com/lupantech/ScienceQA,derek-thomas/ScienceQA,conflict: CC BY-NC-SA 4.0 (owner) / cc-by-sa-4.0 (HF),https://raw.githubusercontent.com/lupantech/ScienceQA/main/README.md,open,626.5,122.4,no,https://datasets-server.huggingface.co/first-rows?dataset=derek-thomas/ScienceQA&config=default&split=train,yes,human (inferred),answer=choices[answer],n/a,2-5 choices,yes,none,USE,med,label origin quote; image share
45,D45.2,Diagram question,AI2D (lmms-lab),https://huggingface.co/datasets/lmms-lab-encoder/ai2d,lmms-lab-encoder/ai2d,UNVERIFIED,https://huggingface.co/datasets/lmms-lab-encoder/ai2d,open,139.5,62.3,no,https://datasets-server.huggingface.co/first-rows?dataset=lmms-lab-encoder/ai2d&config=default&split=test,yes,human (inferred),answer=options[int(answer)],n/a,4 options,yes,none,MAYBE,med,licence
45,D45.3,Worksheet subject,ScienceQA,https://github.com/lupantech/ScienceQA,derek-thomas/ScienceQA,conflict: CC BY-NC-SA 4.0 / cc-by-sa-4.0,https://raw.githubusercontent.com/lupantech/ScienceQA/main/README.md,open,626.5,122.4,no,https://datasets-server.huggingface.co/first-rows?dataset=derek-thomas/ScienceQA&config=default&split=train,yes,human,answer=subject,n/a,natural 2252/language 1100/social 889 (test),yes,none,USE,med,
45,D45.4,Yes/no worksheet item,ScienceQA,https://github.com/lupantech/ScienceQA,derek-thomas/ScienceQA,conflict: CC BY-NC-SA 4.0 / cc-by-sa-4.0,https://raw.githubusercontent.com/lupantech/ScienceQA/main/README.md,open,626.5,122.4,no,https://datasets-server.huggingface.co/first-rows?dataset=derek-thomas/ScienceQA&config=default&split=train,yes,human,task=='yes or no' -> choices[answer],yes (counts unverified),yes/no,yes,none,USE,low,yes/no balance; image share (113 test items)
46,D46.1,Document category,DocLayNet,https://github.com/DS4SD/DocLayNet,pierreguillou/DocLayNet-base; docling-project/DocLayNet-v1.2,CDLA-Permissive-1.0,https://raw.githubusercontent.com/DS4SD/DocLayNet/main/LICENSE,open,39770.6,17.0 (small test) / 187.2 (base test),no,https://datasets-server.huggingface.co/rows?dataset=pierreguillou/DocLayNet-base&config=DocLayNet_2022.08_processed_on_2023.01&split=test&offset=0&length=3,yes,human,answer=doc_category,n/a,6 categories (base test 499),yes,low,USE,high,
46,D46.2,Page has table,DocLayNet,https://github.com/DS4SD/DocLayNet,pierreguillou/DocLayNet-base,CDLA-Permissive-1.0,https://raw.githubusercontent.com/DS4SD/DocLayNet/main/LICENSE,open,39770.6,17.0,no,https://datasets-server.huggingface.co/rows?dataset=pierreguillou/DocLayNet-base&config=DocLayNet_2022.08_processed_on_2023.01&split=test&offset=0&length=3,yes,human,yes if 8 in categories,yes,11 layout classes,yes,low,USE,high,table counts
46,D46.3,Newspaper page has photo/map/ad,LoC Beyond Words,https://huggingface.co/datasets/biglam/loc_beyond_words,biglam/loc_beyond_words,cc0-1.0,https://huggingface.co/datasets/biglam/loc_beyond_words,open,2394.1,1.43,no,https://huggingface.co/datasets/biglam/loc_beyond_words/resolve/main/data/val_20_percent.json,yes,human (crowd),yes if any annotation category_id==k,yes (e.g. Photo 489/223),7 classes,yes,low (historic photos),USE,med,LoC original licence; missed marks
46,D46.4,Typeface group,Early printed books font groups,https://huggingface.co/datasets/biglam/early_printed_books_font_detection,biglam/early_printed_books_font_detection,cc-by-nc-sa-4.0,https://huggingface.co/datasets/biglam/early_printed_books_font_detection,open,44768.8,438.2,no,https://datasets-server.huggingface.co/first-rows?dataset=biglam/early_printed_books_font_detection&config=default&split=train,yes,human (expert),len(labels)==1 -> label,n/a,12 classes,mostly (mean 1.11),none,USE,med,Zenodo licence; per-class counts
46,D46.5,Illustrated advert,biglam/illustrated_ads,https://huggingface.co/datasets/biglam/illustrated_ads,biglam/illustrated_ads,cc0-1.0,https://huggingface.co/datasets/biglam/illustrated_ads,open,48.05,48.05,no,https://datasets-server.huggingface.co/first-rows?dataset=biglam/illustrated_ads&config=default&split=train,yes,mixed (human label on machine crops),yes if label==1,yes (376/173),text-only/illustrations,yes,none,USE,med,
46,D46.6,Manuscript century,ICDAR2021 document dating,https://huggingface.co/datasets/biglam/icdar2021-historical-document-dating,biglam/icdar2021-historical-document-dating,cc-by-4.0 (mirror),https://huggingface.co/datasets/biglam/icdar2021-historical-document-dating,open,28014,394,no,https://datasets-server.huggingface.co/first-rows?dataset=biglam/icdar2021-historical-document-dating&config=default&split=train,yes,human (inferred),century(date_mid) if same century,n/a,centuries,yes,none,MAYBE,low,owner licence; label origin
47,D47.1,Restricted-category ad,Pitt Image Ads,https://people.cs.pitt.edu/~kovashka/ads/,Mindykkyan/PittadsDB-AdsPics; dchen278/pitt-ads-full,UNVERIFIED,https://people.cs.pitt.edu/~kovashka/ads/,open,11881.7,2.31 (Topics.json); per-image ~0.01+,yes (owner zips per subfolder),https://huggingface.co/datasets/Mindykkyan/PittadsDB-AdsPics/resolve/main/image_annotations/image/Topics.json,yes,human (MTurk 3-5 votes),"majority topic in {6 alcohol, 29 gambling}",yes,39 topics,yes after majority filter,med (celebrities in ads),MAYBE,med,licence; mirror path mapping
47,D47.2,Ad topic,Pitt Image Ads,https://people.cs.pitt.edu/~kovashka/ads/,Mindykkyan/PittadsDB-AdsPics,UNVERIFIED,https://people.cs.pitt.edu/~kovashka/ads/,open,11881.7,2.31,yes,https://huggingface.co/datasets/Mindykkyan/PittadsDB-AdsPics/resolve/main/image_annotations/image/Topics.json,yes,human,majority topic id -> name,n/a,clothing 8341/cars 7051/beauty 5826…,yes after filter,med,MAYBE,med,licence
47,D47.3,Image contains advertising,Open Images V7 (human-verified labels),https://storage.googleapis.com/openimages/web/factsfigures_v7.html,,annotations CC BY 4.0; images CC BY 2.0,https://storage.googleapis.com/openimages/web/factsfigures_v7.html,open,28.4 (val labels) + images,28.4 (labels); ~0.2 per image,no,https://storage.googleapis.com/openimages/v7/oidv7-val-annotations-human-imagelabels.csv,yes,human (verification),Advertising conf 1 -> yes; 0 -> no; absent -> skip,yes (110/97),Advertising,yes,med (faces),USE,high,
47,D47.5,Billboard present,Open Images V7,https://storage.googleapis.com/openimages/web/factsfigures_v7.html,,annotations CC BY 4.0; images CC BY 2.0,https://storage.googleapis.com/openimages/web/factsfigures_v7.html,open,28.4,28.4,no,https://storage.googleapis.com/openimages/v7/oidv7-val-annotations-human-imagelabels.csv,yes,human,Billboard conf 1/0,yes (32/9 val; few),Billboard,yes,med,USE,med,test-split counts
48,D48.1,Wearing a dress,Fashionpedia,https://fashionpedia.github.io/home/index.html,detection-datasets/fashionpedia,CC BY 4.0,https://huggingface.co/datasets/detection-datasets/fashionpedia,open,3478.9,84.85 (val parquet; per slice-2 card) / single rows via /rows,no,https://datasets-server.huggingface.co/first-rows?dataset=detection-datasets/fashionpedia&config=default&split=train,yes,human,yes if 10 in objects.category,yes (506/652 val),46 categories,yes,med (people/celebrities),USE,high,owner Terms of Use text
48,D48.2,Main garment,Fashionpedia,https://fashionpedia.github.io/home/index.html,detection-datasets/fashionpedia,CC BY 4.0,https://huggingface.co/datasets/detection-datasets/fashionpedia,open,3478.9,84.85 (val parquet; per slice-2 card) / single rows via /rows,no,https://datasets-server.huggingface.co/first-rows?dataset=detection-datasets/fashionpedia&config=default&split=train,yes,human,single distinct garment id 0-12 -> name,n/a,garments 0-12,496 of 1158 val,med,USE,high,
48,D48.3,Bag present,Fashionpedia,https://fashionpedia.github.io/home/index.html,detection-datasets/fashionpedia,CC BY 4.0,https://huggingface.co/datasets/detection-datasets/fashionpedia,open,3478.9,84.85 (val parquet; per slice-2 card) / single rows via /rows,no,https://datasets-server.huggingface.co/first-rows?dataset=detection-datasets/fashionpedia&config=default&split=train,yes,human,yes if 24 in categories,yes (205/953 val),bag/wallet,yes,med,USE,high,
48,D48.4,Catalogue category,Fashion Product Images small,https://www.kaggle.com/datasets/paramaggarwal/fashion-product-images-small,ashraq/fashion-product-images-small,UNVERIFIED,https://huggingface.co/datasets/ashraq/fashion-product-images-small,open mirror / Kaggle login,271.5,135.4,no,https://datasets-server.huggingface.co/first-rows?dataset=ashraq/fashion-product-images-small&config=default&split=train,yes,human (catalogue; inferred),answer=masterCategory,n/a,Apparel/Accessories/Footwear/Personal Care,yes,low,SKIP,high,licence; tiny 60x80 images
48,D48.5,Lipstick present,Open Images V7,https://storage.googleapis.com/openimages/web/factsfigures_v7.html,,annotations CC BY 4.0; images CC BY 2.0,https://storage.googleapis.com/openimages/web/factsfigures_v7.html,open,28.4,28.4,no,https://storage.googleapis.com/openimages/v7/oidv7-val-annotations-human-imagelabels.csv,yes,human,Lipstick conf 1/0,yes (51/53),Lipstick,yes,med (faces),USE,high,
49,D49.1,Is this a screenshot,Open Images V7,https://storage.googleapis.com/openimages/web/factsfigures_v7.html,,annotations CC BY 4.0; images CC BY 2.0,https://storage.googleapis.com/openimages/web/factsfigures_v7.html,open,28.4,28.4,no,https://storage.googleapis.com/openimages/v7/oidv7-val-annotations-human-imagelabels.csv,yes,human,Screenshot conf 1/0,yes (116/330),Screenshot,yes,low,USE,high,
49,D49.2,Which device,Open Images V7,https://storage.googleapis.com/openimages/web/factsfigures_v7.html,,annotations CC BY 4.0; images CC BY 2.0,https://storage.googleapis.com/openimages/web/factsfigures_v7.html,open,28.4,28.4,no,https://storage.googleapis.com/openimages/v7/oidv7-val-annotations-human-imagelabels.csv,yes,human,"exactly one positive among {Mobile phone, Laptop, Computer monitor}",n/a,3 devices (119/77/88 pos),only after filter,med,USE,med,exclusivity of unverified classes
50,D50.1,Weapon present,Open Images V7,https://storage.googleapis.com/openimages/web/factsfigures_v7.html,,annotations CC BY 4.0; images CC BY 2.0,https://storage.googleapis.com/openimages/web/factsfigures_v7.html,open,28.4,28.4,no,https://storage.googleapis.com/openimages/v7/oidv7-val-annotations-human-imagelabels.csv,yes,human,Weapon conf 1 -> yes; 0 -> no,yes (192/196),Weapon (+Handgun/Rifle/Knife),yes,med,USE,high,
50,D50.2,Alcohol present,Open Images V7,https://storage.googleapis.com/openimages/web/factsfigures_v7.html,,annotations CC BY 4.0; images CC BY 2.0,https://storage.googleapis.com/openimages/web/factsfigures_v7.html,open,28.4,28.4,no,https://storage.googleapis.com/openimages/v7/oidv7-val-annotations-human-imagelabels.csv,yes,human,Alcoholic beverage conf 1/0,yes (279/98),Alcoholic beverage/Beer/Wine/Cocktail,yes,med,USE,high,
50,D50.3,Brand/logo visible,Open Images V7,https://storage.googleapis.com/openimages/web/factsfigures_v7.html,,annotations CC BY 4.0; images CC BY 2.0,https://storage.googleapis.com/openimages/web/factsfigures_v7.html,open,28.4,28.4,no,https://storage.googleapis.com/openimages/v7/oidv7-val-annotations-human-imagelabels.csv,yes,human,Brand conf 1/0,yes (166/329),Brand (Logo 79/9),yes,med,USE,high,
50,D50.4,Logo industry,LogoDet-3K,https://github.com/Wangjing1551/LogoDet-3K-Dataset,axonstan/LogoDet-3K,MIT (mirror only),https://huggingface.co/datasets/axonstan/LogoDet-3K,open,3116.5,311.7,no,https://datasets-server.huggingface.co/first-rows?dataset=axonstan/LogoDet-3K&config=default&split=train,yes,human,answer=industry_name,n/a,9 industries (Food 10670 … Medical 788),yes,low,MAYBE,med,owner licence
50,D50.5,Visible watermark,Watermark-or-Not-20K,https://huggingface.co/datasets/prithivMLmods/Watermark-or-Not-20K,prithivMLmods/Watermark-or-Not-20K,apache-2.0,https://huggingface.co/datasets/prithivMLmods/Watermark-or-Not-20K,open,2643,74.1,no,https://datasets-server.huggingface.co/first-rows?dataset=prithivMLmods/Watermark-or-Not-20K&config=default&split=train,yes,UNVERIFIED,label==1,yes (10000/10000),No Watermark/Watermark,yes,low,MAYBE,med,label origin
```


## Appendix E. Gaps: tasks with no acceptable dataset, and whether a generator is realistic

Reproduced from each slice. Merge-step corrections: **D23.4** (vehicle body damage) is no longer a gap, because slice 1's `DrBimmer/comprehensive-car-damage` (USE, 800 undamaged negatives) answers it. **D16.3** (parcel damaged) has a real-photo USE set in `Gabriel8/cardboard-box-anomaly-detection`. Slice 2 suggested replacing domain 14 in the merge, but the merge step may not add datasets, so domain 14 stays and is marked "human photos" in the coverage matrix.


### E1. Slice 1 — Money and paperwork (D1–D10)

| task | why no dataset | generator realistic? how |
|---|---|---|
| D1.3 Cheque signed | jaganadhg always has a `sign` box, so there are no negatives [ROW]. | **Yes.** Reuse the jaganadhg blank bank templates (or draw cheque leaves) and paste or omit a signature patch. Signatures can be synthetic handwriting fonts. Answer = whether the patch was pasted. |
| D1.4 Stale-dated cheque | shivalikasingh dates are constant "06/05/22" [ROW]. | **Yes.** Render random dates on cheque templates. Answer = date vs reference. |
| D3.6 Odometer reading | Only tabular odometer data was found (cz-stk) [CARD]. | **Partly.** Render digital odometer LCD crops with known values. Realism of dashboard photos is limited. Real photos are needed for production fidelity. |
| D4.5 Roof damage (ground level) | Only aerial sets, and xBD was rejected. | **No** for a realistic look; human photos are needed. CrisisMMD/MEDIC severity is the nearest proxy. |
| D5.1/D5.3 CMS-1500 / UB-04 form type, signed | Symage is GATED. | **Yes.** CMS-1500 is a public form. Fill a blank PDF with Faker values, optionally sign box 12/13/31, and render it. Answers come from the generator. Very realistic. |
| D5.4 Itemised bill | No labelled data. | **Yes.** Render hospital bills with or without line items. |
| D5.5 Insurance card plan type | None found. | **Yes.** Draw member cards with HMO/PPO text. Use fake payers only, never real brands (brand impersonation risk). |
| D6.1 Signed page | tech4humans is GATED. | **Yes.** Render contract pages from public-domain templates and add or omit a signature image in the signature block. |
| D6.4 Stamp / seal | No licensed, image-bearing set (GIGAParviz has no images or licence). | **Yes.** Draw generic round or rectangular stamps (fake org names) onto DocLayNet-style pages. |
| D6.5 Redaction | None. | **Yes.** Black-box random text spans on rendered pages. Answer = whether boxes were drawn. Trivial and realistic. |
| D7.5 Permit validity | None. | **Yes.** Render generic permit templates with issue and expiry dates. |
| D9.5 Customs declaration (CN22/CN23) | None found on HF. | **Yes.** CN22/CN23 layouts are public (UPU); fill category ticks, contents and values with a generator. |
| D10.1 I-9 Section 2 signed | Symage is GATED. | **Yes.** The I-9 is a public USCIS form; fill and sign or leave blank. |
| D10.4 Timesheet total hours | None. | **Yes.** Render weekly timesheets (printed or handwritten font) with known hours. Answer = the sum. |
| D10.5 Badge expired | None. A real badge would show a face, so identifying a person is a risk. | **Yes, faceless.** Draw badges with a silhouette avatar and expiry date. |
| D8.6 ID present in photo (clean) | cloverx negatives are third-party real photos. | **Yes.** Composite synthetic KTP/passport renders onto desk backgrounds with and without cards. |

### E2. Slice 2 — Goods, places and logistics (D11–D20)

| Task | Why no acceptable dataset | Generator / drawn version realistic? How |
|---|---|---|
| D11.1 out-of-stock gap | SKU-110K rejected. SKUs_on_shelves_PL is an 11.4 GB single archive. No open labelled "empty facing" set was found on HF ("empty shelf" / "out-of-stock" searches returned nothing). | **Yes, medium realism.** Render shelves procedurally (Blender or Unity) with textured product boxes in a grid, delete k facings, and record which slots are empty. The answer is the generator value. Real-photo fidelity is limited, so prefer a human pulling only the COCO JSON from SKUs_on_shelves_PL. |
| D11.4 discount flag | Only machine (Gemini) labels. | **Yes, high.** Draw price-tag templates (HTML to PNG) with known price, unit price and a promo badge. Add camera noise. |
| D11.6 planogram category | None found. | Partly: from the same shelf renderer, assign category textures per shelf. |
| D12.2 colour | Only tiny 60×80 images; ABO colour is free text. | Partly: normalise ABO `color_en` to about 10 colours (Tier B-like, needs mapping), or render ABO 3D assets with a known material colour (generator). |
| D13.1 fresh vs rotten | The open sets are tiny, a single archive, or a duplicate of the used AgML set. | Not realistic to draw decay convincingly. Needs human photos. |
| D13.5 produce grade, D13.6 date legible | None found. | Date legibility: **yes**. Render date labels with controlled blur and occlusion; the answer is the blur level. |
| D14.2 gloves/hairnet, D14.4 pests, D14.5 surface clean | Only an off-site mirror (ybli). No open kitchen-hygiene set with negatives. | Gloves/hairnet: needs human photos, with faces as a privacy risk. Pest: compositing is possible but unrealistic. **Domain 14 is the weakest; consider replacing it in the merge.** |
| D14.3 plate waste | Machine labels only. | No. |
| D15.3 / D15.4 pallet and box counts | Nothing found (lettuce-pallets is hydroponics, not logistics). | **Yes, high.** The projectsim/warehouse-manipulation-and-states CC BY 4.0 assets (cardboard boxes, pallet_boxes GLBs; 33–37 MB each [CARD]) can be rendered in stacks with known counts. |
| D15.5 aisle obstruction | None. | Partly: render warehouse aisles with or without objects. |
| D16.2 container damaged yes/no | Guztavu is GATED; howell0123 is positives only with no licence. | No. A human should review the GATED repo. |
| D16.3 parcel damaged | Parcel3D is a 45.8 GB archive. | Parcel3D itself is synthetic (Blender, damaged vs intact), so the generator route is proven. A human could pull a subset, or we re-render using CBTex textures (Zenodo 8041823, CC BY 4.0, 1.47 GB zip). Gabriel8 cardboard covers the real-photo version. |
| D16.4 container ID / D16.5 barcode | Nothing qualified. | **Yes, high.** Generate ISO 6346 codes (owner code + serial + computed check digit) painted on container-like panels; generate Code128/QR labels on parcel textures. The answer comes from the generator values. |
| D17.1–D17.5 delivery proof | Only OliseNS (archive, machine-assisted, face data). | Partly. Composite parcel renders onto doorstep photos (needs CC0 doorstep backgrounds) for "parcel visible"; blur levels for "photo usable". Placement (doorstep/mailbox/locker) needs human photos. |
| D18.3 bed made, D18.4 tidy, D18.5 damage | None found. | Bed made / tidy: **medium**. 3D room render with cloth simulation states. Damage: no. |
| D18.2 amenity yes/no | MIT Indoor polygons are not exhaustive. | Use Tier B only for positives, or render bathrooms with or without towels. |
| D19.2 bedroom count | CubiCasa5K SVGs only inside a 5.4 GB archive. | **Yes, high.** Render FloorplanQA-Layouts JSON (CC BY 4.0) or procedural multi-room plans with room labels; the count comes from the generator. A human could also pull CubiCasa5K once. |
| D20.4 bin overflowing, D20.5 wet floor | Overflow set is positives only and unlabelled; no spill set found. | Spill: partly (decals on floor renders). Overflow: needs human photos with negatives. |

### E3. Slice 3 — Industry and infrastructure (D21–D30)

| task | why no acceptable dataset | drawn/generator version realistic? how |
|---|---|---|
| D21.7 assembly completeness (missing screw/clip) | MVTec LOCO and AD 2 are rejected. No open, licensed, sampled alternative found in this session | **Yes**: render CAD assemblies (Blender/BlenderProc) with parts randomly removed. Store the removed part list as the answer |
| D22.4 component presence | `tutitata/PCB_COMPONENTS_LABELLED` has no licence and is a partial upload | **Partly**: procedurally generate board layouts with KiCad, then render with known component lists |
| D22.5 solder joint quality | none found | Hard to draw realistically. Needs human photos |
| D23.4 vehicle body damage | DrBimmer used, CarDD rejected, AutoDamageIQ uses GPT-4o labels and CarDD | No (photoreal damage is hard). Needs a new human-labelled source |
| D23.5 dashboard warning light | none found | **Yes**: composite ISO 2575 icons onto rendered cluster backgrounds. The icon set is the answer |
| D23.6 brake-pad wear | `ybli` repo is empty | Partly: render pad thickness from known mm values |
| D24.2–D24.5 aviation skin corrosion, borescope, FOD, aircraft tyre | none found on HF. FOD-A (GitHub) was not probed | Corrosion: no. FOD: **yes**, composite known objects onto runway photos and keep the object list as the answer. Borescope: no |
| D25.2–D25.4 rail obstruction, fasteners, catenary | RailSem19 needs a form [UNVERIFIED, not fetched]. `aurora0403/Railway_Foreign_Object_Dataset` was not probed | Fasteners: **yes**, render a sleeper with clips present or absent. Obstruction: composite objects onto track frames |
| D26.4 construction stage | ConstructionSite is GATED | No. Needs human photos |
| D27.4 meter type | only a GATED candidate | **Yes**: render mechanical-odometer vs LCD meter faces |
| D27.5 needle in red zone | derived from D27.1 generator (Tier B) | **Yes**: already covered by goodcoffee and moondream generators |
| D28.5 wind blade damage | only 128 px turbine-presence patches. `ybli` wind-blade repo not probed | No |
| D28.6 PV thermal hotspot | the Manishsahu53 set is unlabeled | Partly: synthetic thermal grids with hot cells at known positions (diagram-like) |
| D29.4 oil spill, D29.5 conveyor belt | not probed / none found | Belt: no. Oil spill (SAR): no |
| D21.1/2 Severstal licence | Kaggle rules not readable without login | n/a. A person should read the competition rules |

### E4. Slice 4 — Living systems and safety (D31–D40)

| task | why no acceptable dataset | generator realistic? how |
|---|---|---|
| D31.6 insect pest species | Only candidate is tiny and has unnamed labels | Partly. Render museum-style insect images? Not realistic; photos are needed. Check IP102 owner page or iNaturalist research-grade exports (licence per photo). |
| D31.7 / D33.5 land cover | EuroSAT is 64 px | No for real imagery. Higher-res options (e.g. BigEarthNet patches) not checked. |
| D32.6 cattle count | No candidate verified | No. Needs drone photos. |
| D33.2 camera-trap empty vs animal | HF LILA subset dropped empty frames | No generator. The full LILA Channel Islands metadata JSON (with `empty`) on lila.science is the likely fix (not fetched). |
| D33.6 flooded road | FloodNet is a 12.8 GB single archive | No. |
| D34.6 / D35.5 person lying | Only synthetic positives | Yes. A 3D/CCTV renderer (pose → standing/lying label) gives generator truth; Simuletic shows it is feasible. |
| D34.7 smoking | No labels fetched | No (people photos). |
| D35.1 fire/smoke with clean licence | D-Fire has negatives but no licence; FASDD is a single archive | Partly. Synthetic fire/smoke composites exist but look artificial. Better: ask GAIA about D-Fire terms. |
| D35.6 intrusion | Not searched in depth | Yes. Render empty vs person-present CCTV scenes. |
| D36.4 traffic light colour | LISA is NC-SA with tiny lights | Yes. Draw or render a traffic light with a known lit lamp at a large scale. |
| D36.5 traffic sign | GTSRB crops are tiny | Yes. Paste vector sign templates (public-domain MUTCD/Vienna signs) onto street photos at large size. Label = template id. |
| D37.5 wristband / insurance card | None | Yes. HTML/PDF template generator with fake values (as morzel85 does). |
| D38.4 pill imprint/shape/colour | Labels need an external NDC lookup | Partly. NLM RxImage plus the RxNav API gives shape/colour/imprint as authority data (licence check needed). Rendering pills is possible but low-realism. |
| D38.5 blister empty cavity | None usable | Yes. Simple 2D/3D render of a blister grid with N empty cavities is realistic enough for counting. |
| D39.5 animal count | None | No (use COCO-style sets outside this slice). |
| D40.1 HAB taxon at usable resolution | NES images are tiny; bloombio has no rows | No generator. Fetch bloombio detection shard footer (42.7 MB) next. |
| D40.4 colony count | Only candidate GATED | Yes. Synthetic agar plates with drawn colonies (count = generator value) are realistic and common in the literature [INFERRED]. |
| D40 lab instrument reading | Not in slice data; gauges sit in slice 3 | Yes (gauge/needle rendering). |

### E5. Slice 5 — Digital and knowledge work (D41–D50)

| task | why no data | drawn/generator version realistic? how |
|---|---|---|
| D41.4 Error dialog present | No open, human- or generator-labelled set of real error screenshots found on the HF Hub (searches: "screenshot error", "error message screenshot", "blue screen"). | **Yes, high realism.** Render native-looking dialogs (Windows/macOS/GTK themes via HTML/CSS or Qt) over real app screenshots from ScreenSpot-Pro (MIT). Label = whether a dialog was injected; option lists can add dialog type (error / warning / info / update prompt). Hard negatives: non-error modals. |
| D41.5 Dark mode | No labels found. | **Yes.** Render the same HTML app mock in light and dark CSS themes. Label = theme. Low value. |
| D42.4 Overlap/truncation defect | Only candidate (zxy6654) has no labels (SKIP). The OwlEyes/Nighthawk display-issue sets were not located on open hosts [UNVERIFIED]. | **Yes.** Take WebSight-style HTML or Enrico wireframes and inject a defect (negative margins, `overflow:hidden` truncation, z-index occlusion, missing image). Label = defect type or none. Screenshot with headless Chrome. |
| D42.5 Placeholder text | None. | **Yes.** Swap real strings for "Lorem ipsum" / "TODO" / "[Title]" in rendered HTML. Label known. |
| D42.6 Low-contrast text | None with labels. | **Yes, exact.** Render text with controlled foreground/background colours. Label = WCAG contrast ratio < 4.5:1, computed (generator). |
| D44.6 Rooftop solar | PatternNet is 256 px (SKIP). The Cyrille37 IGN set has only positive polygons (676 files, 29.8 MB, MIT); negatives UNVERIFIED. | **Partial.** Synthetic aerial is weak. Better: an owner dataset with negatives (e.g. Bradbury et al. Duke solar, licence UNVERIFIED), not checked. |
| D45.5 Handwritten answer correct | Handwriting candidates (MathWriting copies, CROHME copies, HumynLabs notes) were not probed; licences and labels UNVERIFIED. | **Yes.** Render worksheet items with handwriting fonts, or stroke data from MathWriting (if its licence allows) for answers. Label = whether the written answer equals the key (known at generation). |
| D46.7 Page rotated | Not needed as a dataset. | **Yes, exact.** Rotate DocLayNet pages (CDLA-Permissive) by 0/90/180/270. Label = rotation. |
| D47.4 Disclosure label visible | No dataset found. | **Yes.** Composite "#ad" / "Sponsored" / "Paid partnership" overlays at varied size, contrast and position onto CC images (Open Images). Label = present / absent, or "conspicuous" via size/contrast thresholds computed at generation. |
| D49.3 Photo usable (blur/dark) | No labelled set. | **Yes, exact.** Apply Gaussian/motion blur or underexposure with known parameters to Open Images device photos. Label = parameter above or below a threshold. |
| D49.4 Cracked screen | Only `34data/ai-generated-ecommerce-damaged-phone-screen` (AI-generated, text modality; not probed). Roboflow sets need login (GATED). | **Weak.** Overlaying crack textures on phone photos is feasible but looks artificial. A human photo set is needed. |
| D49.5 Error message on device screen | None. | **Yes.** Composite rendered error screens (D41.4 generator) into phone/monitor screen regions of Open Images photos via a homography. Label known. |
| D50.6 Counterfeit product | No open labelled data (only tiny unprobed HF uploads). The OECD shows the business value. | **No.** Counterfeit status is not visible from generator parameters. It needs brand-owner ground truth. |
| (D41.2 balance) | OS is confounded with app in ScreenSpot-Pro. | Add the `common_{windows,macos,linux}` screenshots, or render the same web page in three OS browser chromes. |


## Appendix F. Cannot verify

### F0. Merge step (this report)

- The re-check did not re-open the CrisisMMD humanitarian TSV `label_image` values (D4.3), the powerline 1,794-row balance, the forklift negative count (194), or the 166 `good` cardboard images. These remain as recorded in the slice notes.
- The HARIS weapons and CubiCasa5K-YOLO viewer proofs expose label text without filenames. Tying a label to its image needs the per-file label path, which was not re-fetched for those two.
- Cross-domain task links marked `*` in the coverage matrix (D23.2, D23.4, D26.5, D27.5, D39.4) are merge-step judgements that a dataset carded for one domain answers a task in another. They are not new fetches.
- Every training-data overlap statement remains `[INFERRED]`. No contamination test was run.


### F1. Slice 1 — Money and paperwork (D1–D10)

- **Kaggle anujms/car-damage-detection:** the file list is empty in the anonymous API and the download needs login [CARD]. No rows.
- **tech4humans/signature-detection** and **Symage/coherent-forms-1040-cms1500-i9:** README and viewer return 401 (gated "auto"). Content, classes and real licence text are unknown.
- **konfuzio/funsd_plus LICENSE** was not opened. The card asks users to agree to it with personal details, so I treated it as GATED.
- **FUNSD licence:** the owner page has a "License" nav item but no licence text rendered in fetched HTML.
- **MIDV-500 / zimka mirror licence:** no licence found. The paper snippet only covers the source images.
- **MEDIC label origin** and the `terms-of-use.txt` content were not read. The arXiv abstract does not describe the annotation process.
- **CrisisMMD `label_image` values:** the column's presence comes from the Readme; I did not print humanitarian TSV rows.
- **IDNet-2025 meta JSON fields:** inside tar.gz archives of 1.35 GB or more, so not sampled.
- **datasets-server `/statistics` returned HTTP 500** for cloverx-id, HV09 and albertobarnabo. I used sampled or file-based counts instead (marked).
- **tugberkkalay/autodamageiq:** `/splits` returned 500, so no rows (SKIP stands on card evidence).
- **NIST SRD licence terms** for SD2 were not read (the page shows "Price: No charge").
- **Value-reason sources:** the FinCEN, APQC, Coalition, Swiss Re, CMS, IRS, WorldCC and FATF figures come from web-search result summaries citing those pages, not from full-page reads. The I-9 penalty source is secondary (Experian) and conflicting amounts appeared in search snippets, so treat it as [UNVERIFIED primary].
- **Voxel51 passports:** the listing says `samples.json` is 23.38 MB but the fetched file was 10.05 MB (possibly compressed transfer or a different revision). Only 2 full rows were pasted.
- **Training-data overlap** statements are [INFERRED] throughout. No contamination check was run.

### F2. Slice 2 — Goods, places and logistics (D11–D20)

- **Annotator details from papers:** RPC (arXiv 1901.07249) label origin; the Fashionpedia annotation protocol and exhaustiveness; the TrashNet collection method; the FloorPlanCAD annotators; the DroneWaste annotation method. The arXiv API query returned nothing from this machine.
- **Original-owner licence pages:** MIT Indoor (web.mit.edu), ABO official page, Food-101 ETH page, Mendeley ripeness dataset, Roboflow Universe pages, tacodataset.org. None were fetched; I relied on mirror cards.
- **Value-reason statistics** (IHL, OSHA, USDA ERS, Recycling Partnership, SafeWise, NAR): seen only as search-result snippets, not opened.
- **Guztavu/container-damage:** README returns 401 (gated). Contents are known only from the file listing.
- **Per-class counts not run:** ABO `product_type`, Fashionpedia categories, CubiCasa-YOLO door distribution, ABO-Edit row count.
- **openfoodfacts price-tag-extraction benchmark v2.0** (claimed human-validated, on GitHub): not fetched. It may make D11.4 viable.
- **Not checked:** devmandan/syn10k-huawei-barcodes (possible generator barcodes, CC BY 4.0 tag), 123metro/barcode-datasets, Fnhid/indory-waybill-ocr-640x480, UniDataPro/grocery-shelves (cc-by-nc-nd sample), Kos1976/9-facades-doors-windows-50-commercial.
- **GroceryStoreDataset** total size: the GitHub API returned null.
- **FloorPlanCAD samples.json** (60.4 MB) is over the cap; only a range was read.

### F3. Slice 3 — Industry and infrastructure (D21–D30)

- **Kaggle licences and rules.** The Severstal competition rules returned API 401. Only public dataset metadata (tyres) was readable.
- **Annotation method for these datasets.** The cards and the text I fetched do not say how the labels were made: wood surface defects (F1000 paper text did not yield a box-annotation statement), ELPV (README says only "annotated"), dacl10k (`annotations_creators: []`), FGVC-Aircraft, excavator-detector, welding, RF100 corrosion, Pothole_classification, the sewer sets and the meter sets.
- **DeepPCB total repo size.** The GitHub API call failed in this session.
- **RDD2022 official S3 file list.** Returned AccessDenied. The Figshare (CC BY 4.0) and HF card (CC BY-SA 4.0) licence statements conflict.
- **Missing rows.** UniDataPro water-meters `/first-rows` returned 500. RF100 corrosion `/first-rows` returned 500, so raw label files were used instead.
- **Not opened.** The full class list for the wood dataset; per-class image counts for HRIPCB, keremberke PCB and excavator; the CODEBRIM contents; FOD-A, RailSem19, the Railway_Foreign_Object_Dataset, and oil-spill sets.
- **Value-reason sources.** Most come from search-result snippets and are tagged [UNVERIFIED-snippet]. The pages were not opened, and many tasks have "No source fetched".

### F4. Slice 4 — Living systems and safety (D31–D40)

- **D-Fire licence**: neither the GitHub repo (API `license: None`) nor the HF mirror states one. The class-id map (0 = smoke, 1 = fire) was not found on the fetched README.
- **Label-origin quotes** for Project-AgML sets (seedlings, crop pest, oil palm, maize weed, tree species): the cards only cite the source. Annotation method not quoted.
- **Oxford-IIIT Pet** label origin: from the paper, not fetched.
- **Roboflow-derived sets** (VincentGOURBIN PPE, keremberke, cute-face, LibreYOLO pills, Turki weapons): no annotation statement beyond "Provided by a Roboflow user".
- **Turki weapons**: UCF-Crime upstream licence not checked.
- **Vertex-Test FireSmoke**: whether images are AI-generated (inferred from SD-style filenames).
- **c3rl seatbelt**: image provenance.
- **bloombio phytoplankton**: `/first-rows` returned "Not found". No rows. The schema is not seen.
- **Voxel51 fisheye8k / StanfordDogs**: labels sit in `samples.json` (39.4 MB / 7.0 MB), not parsed.
- **LISA traffic lights**: class names for ids 0..n.
- **keremberke aerial-sheep / construction-safety / forklift**: per-zip sizes of the valid/test splits (only the train zip size printed). Negatives per item.
- **tw-drug-labels-vision**: whether the two parquet shard sets (…of-00008, …of-00018) duplicate each other. The "輸 = imported" licence-prefix rule comes from TFDA naming convention [INFERRED], not a fetched page.
- **Value sources**: most "why it matters" lines use secondary reporting of FAO/NFPA/OSHA/NHTSA/INRIX/ISMP figures (links above). Domains 32, 36.2–36.6, 37, 39 and 40.2–40.5 have **no source**.
- **rotsl colony counting**: GATED (manual approval). Nothing inspected.

### F5. Slice 5 — Digital and knowledge work (D41–D50)

- **FigureQA owner licence text.** It sits behind "Agree & Download" on the Microsoft page; not accepted. GATED.
- **DVQA, AI2D, Pitt Ads, LogoDet-3K, FloodNet and WHU-RS19 owner licences.** None was found on the owner README or page. The licences shown come from mirrors only.
- **Fashionpedia owner "Terms of Use".** The link text could not be extracted. The HF card says CC BY 4.0.
- **VisDrone owner terms.** The mirror card is self-contradictory (cc-by-sa-3.0 YAML vs NC-SA text).
- **Label-origin quotes from papers** (ScreenSpot-Pro, CharXiv, ChartBench, Mind2Web, ScienceQA). Papers were not read; marked [INFERRED].
- **ChartBench single-file extraction from `test.zip`.** The central directory is reachable by range read (10,552 entries), but extracting one PNG was not attempted.
- **Per-class counts** for the CharXiv q11 yes/no, the DocLayNet Table yes/no, the font-detection classes, and the ScienceQA yes/no image share.
- **Hateful Memes (Facebook)** was found as HF mirrors but not probed. The original requires accepting a licence, so it is likely GATED [UNVERIFIED].
- **The `dchen278/pitt-ads-full` path mapping** (`images/0XX/<id>`) to the owner annotation keys (`<subfolder>/<id>`) was not confirmed.
- **GitHub REST API** was blocked in this session (add_repo required). Licences were read via raw.githubusercontent.com instead.
- **Value sources.** Several are vendor or secondary (unthread, Bluestone PIM, Grypp, Verato citing Gartner, law-firm FTC summaries). No primary brand-safety source for weapons was found.
