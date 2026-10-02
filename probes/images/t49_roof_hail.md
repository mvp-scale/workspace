# t49_roof_hail: roof hail / storm damage

Status: BLOCKED

Planned question: yes/no, "Does this roof show hail or storm damage?" (or severity, 3 to 4 options). No `.jsonl` and no images were built. No open set with a verifiable human label origin, per-image roof labels and real undamaged roofs was found.

## What was checked (2026-10-01) and why each failed

| Candidate | Finding | Verdict |
|---|---|---|
| Roboflow Universe `hail-damage-zoom-5`, `roof-damage-detection` | `universe.roboflow.com` returns HTTP 403. Roboflow downloads need an account or API key, so this is GATED. Not attempted. Not on the Hugging Face search either (queries `roof-damage-detection`, `hail-damage-zoom` return nothing). | Gated |
| HF `InspectorRoofing/roof-damage-negative-evidence` (CC-BY-4.0) | A "dataset shell": README, schema, CSV template, `examples.jsonl`. Its own card says images are to be added later. 5 files, no images. | No images |
| HF `wbhorn/hail_and_wind_damage_chips` (CC-BY-4.0), `SevereWeather/...`, `severe-weather/...` | 30 m Landsat/Sentinel/SAR chips (256 px, about 7.7 km wide) with swath masks from the hwds_db climatology. Not roof photos, not human-inspected per roof. | Wrong modality |
| HF `jherng/storm-damage-detection` (MIT) | No README. Zip files only (`sdd.zip`, `raw.zip`, ...). It looks like the Caribbean aerial roof-material challenge, which labels materials, not damage. Label origin cannot be verified from the repo. | Unverifiable |
| HF `Abhijit85/InsuranceClaimImages` | Empty template card, no licence, folders such as `01-minor`. It appears to be car damage, not roofs. | Wrong subject, no card |
| HF `NarchAI1992/Roof_house`, `heangborin/roofGoogleSatelliteKh`, `farahsaad/satellite_Roofs_MASK*`, `Prahas10/roof-15`, `Prahas10/shingles` | Roof design, satellite segmentation or unlabelled with no damage label. | No damage label |
| Zenodo 20581719, Kucharczyk, Nesbit & Hugenholtz 2025 (CC-BY-4.0, named researchers, University of Calgary / San Francisco), "Automated Mapping of Post-Storm Roof Damage ... Caribbean" | The label origin is human and named, and the damage is hurricane (storm) damage. But: (a) the imagery is drone/aerial orthomosaics (1.5 to 26 GB zips), not roof photos; (b) the damage classes (roof decking exposed, roof hole) are polygons stored in Esri File Geodatabases (`.gdb`), which need GDAL/ArcGIS and are not readable with Pillow and pyarrow; (c) the damage is wind/hurricane roof loss, not hail; (d) images would need georeferenced cropping. I downloaded only `Polygons.zip` (15 MB, image boundary polygons only, no damage labels) and the metadata xlsx (33 KB) into `/workspace/data/sources/image-lab/roof-zenodo/`. | Not feasible with the allowed tools; not hail |
| HF searches: `roof`, `roofing`, `hail`, `shingle`, `storm-damage`, `roof-inspection`, `roof-condition`, `roof-classification`, `insurance-claim`, `tarp` | Nothing else relevant. Kaggle and Roboflow need an account. | none |

## Recon (3 real annotation rows, no image bytes)

From `InspectorRoofing/roof-damage-negative-evidence` `examples.jsonl` there are no usable rows (no image column). The relevant rows are the Zenodo image-boundary metadata, which has no damage field. The only damage labels are in the `.gdb` tables, which cannot be read here. So there are no annotation rows to quote.

## What the user must do to unblock (any one of these)

1. Create a free Roboflow account, open the Universe pages for `hail-damage-zoom-5` and `roof-damage-detection`, check the licence and the annotator, then export in COCO or YOLO format (or give an API key). Put the zip under `/workspace/data/sources/image-lab/roof-roboflow/`. Check that the set includes undamaged roofs (images with no damage annotation). Re-run this task.
2. Or supply 25 roof photos plus `labels.csv` (`image,question_id,answer`, answer `yes` or `no`) from an insurer or inspector under `/workspace/data/image-lab/user/t49_roof_hail/`. Do not use photos showing house numbers, faces or street signs.
3. Or accept the Zenodo hurricane set. This needs GDAL (a new package, which is not allowed here) and a change of question to "Is there roof decking exposed or a hole?". I do not recommend it for a hail question.

## Angle questions (derived from the annotation, not built)

None. The task was not built.
