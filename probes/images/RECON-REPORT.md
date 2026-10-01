# Image lab gap recon

Read-only check of the 11 unbuilt tasks and the three weak built tasks. Nothing was built, and `STATUS.md` and the task notes were left as they were. Disk in use before this recon: 4.5 GB of the 15 GB cap, so about 10.5 GB is free. Peeks saved under `/workspace/data/sources/image-lab/` are small (CarDD annotations, NEU captions parquet at 70 MB, READMEs and one ScreenSpot JSON).

## t10_damaged_part

Verdict: RESCOPE

Best source: `harpreetsahota/CarDD`, https://huggingface.co/datasets/harpreetsahota/CarDD, no licence field on the card. The README says the images are not owned by the dataset and use requires agreeing to Flickr and Shutterstock terms, for non-commercial research and education. Hub size 2.20 GB, gated no. Original page: https://cardd-ustc.github.io.

Label: FiftyOne `detections.detections[].label`. `samples.json` (2,816 images) was read. The first image, `data/000001.jpg`, is labelled `scratch` and `tire flat`. Box totals: scratch 2,560, dent 1,806, crack 651, lamp broken 494, glass shatter 475, tire flat 225. There is no part name in this file.

Classes and balance: images with exactly one damage class: scratch 683, glass shatter 391, dent 359, tire flat 172, lamp broken 69, crack 58. Four of those classes can fill 25 items with no class over 40%. The already-downloaded DrBimmer damage files cannot: only 39 images have a single damage class (Broken part 23, Dent 7, Scratch 4, and the rest 1 or 2), and 775 mix classes.

Fits the spec question? No. The spec asks which part is damaged. CarDD answers which kind of damage is visible (dent, scratch, crack, glass shatter, tire flat, lamp broken).

Risks: dents and scratches are visually close, and the README says they are often intertwined. Faces and plates were meant to be mosaicked on the official release; this mirror was not re-checked image by image. Flickr and Shutterstock terms are a real condition even though the hub file is not marked gated.

Work to build it: after you accept the terms, download the images (2.20 GB) and sample 25 single-class images. No new package. The DrBimmer files already on disk are not enough for four types.

What the user must do: agree to a question change, and accept the Flickr and Shutterstock terms on https://cardd-ustc.github.io before a download.

Rejected candidates: DrBimmer car-parts-and-damage (no image has both a part and a damage mark; 39 single-class damage images is too few for four types).

## t11_property_damage

Verdict: RESCOPE

Best source: SDNET2018, https://doi.org/10.15142/T3TD19 (paper also at the Data in Brief article, which is CC BY 4.0). The paper says the images are free for academic purposes. One IEEE DataPort listing gives a zip of about 504 MB. Not on Hugging Face. Not gated on the hub because it is not there; the download site may still ask for an account.

Label: folder name, not a column we opened. The paper (Data in Brief, 2018) states cracked and uncracked folders for bridge decks (D), walls (W) and pavements (P). Wall counts in that paper: 3,851 cracked and 14,287 uncracked, 256×256 images. This recon did not download the zip, so those counts are the paper's, not a count of files on disk.

Classes and balance: yes and no both exist in the wall subset, in large numbers, so a 12/13 split is possible if the zip matches the paper.

Fits the spec question? No. The spec asks whether the roof or walls of a building show damage. SDNET2018 is close-up concrete (walls, decks, pavement) labelled crack or no crack. It is not a roof or a house exterior. Aerial damage sets were not used.

Risks: a crack-or-not result would be reported as a different task from "roof or walls". Academic-use wording may be tighter than CC BY 4.0 on the paper.

Work to build it: download the wall folders only if the zip allows that, else the ~0.5 GB zip, and take 13 cracked and 12 uncracked wall images. Confirm the site does not require a login first.

What the user must do: accept a question change to "Is there a crack in this concrete wall?" and accept academic-use terms if the download page asks.

Rejected candidates: `InspectorRoofing/roof-damage-negative-evidence` (CC BY 4.0) is a documentation schema, not photos. The README says real images should be added only after a privacy review. `mohammadnajeeb/concrete_crack_images` (CC BY 4.0, 0.24 GB) has no class names in its README, so the label was not used.

## t12_package_condition

Verdict: NEEDS_USER

Best source: none that is open, ungated, and has intact / dented / crushed / open or torn.

Label: not verified on a file we could open without a login.

Classes and balance: not available under the rules.

Fits the spec question? The four-way question was not matched.

Risks: the closest public descriptions are two-class (damaged vs intact) or sit behind a login.

Work to build it: none until a source is chosen.

What the user must do: either supply 25 photos, or accept a two-class question and a source that needs a login or a non-commercial licence.

Rejected candidates: Kaggle "Industrial Quality Control of Packages" (synthetic damaged vs intact, GPL-2.0, Kaggle login). Parcel3D on Zenodo (damaged vs intact, academic / non-commercial, mixed source licences). Roboflow "New Box Dataset" lists Crushed, Intact, Leaking, Punctured and Torn, but the page requires a sign-in, so it was not downloaded. HUST carton defects (breakage, crease, scratch, color, normal) are on Google Drive and Baidu, which is not an open pull, and the classes are not the four in the spec.

## t13_shelf_out_of_stock

Verdict: DROP

Best source: none.

Label: the shard already on disk (`adnankhan-11/smart-retail-shelf-auditing-v1`, valid-00000, 200 rows) has `objects.category_id` only, and every box in that shard is category 1 (29,876 boxes). No category name. No image with an empty object list.

Classes and balance: a yes and a no for "empty shelf gap" cannot be made from that file.

Fits the spec question? No.

Risks: treating category 1 as "product" or as "gap" would be a guess.

Work to build it: none.

What the user must do: nothing, unless you want to supply shelf photos yourself.

Rejected candidates: Hugging Face searches for "empty shelf", "out-of-stock" and "grocery shelf" returned no dataset with a gap class. `Voxel51/sku110k_test` is product boxes, about 11 GB, with no gap class (the label file alone is 7.7 GB). Another SKU110K repo is about 29 GB.

## t16_license_plate

Verdict: SYNTH

Best source: a generator in the same style as the form and cheque tasks. No download. Labels are the strings drawn on the plate.

Label: the string passed into the drawing (`label_origin`: generator value).

Classes and balance: each plate string is unique, so a four-option question stays under the 40% cap. Chance rate 25%.

Fits the spec question? Yes, the words of the question can stay "What is the plate number?" The photos will be drawn plates, not cars on a street.

Risks: this measures reading of clean drawn plates (a font, a simple background, optional tilt, blur and noise), not recognition of real plates in traffic. Pillow can warp a rectangle and blur it. It will not reproduce dirt, fasteners, or a real state's plate layout unless we draw those by hand, and even then it is still a drawing.

What the user must do: accept synthetic plates.

Rejected candidates: `keremberke/license-plate-object-detection` (CC BY 4.0, 0.23 GB) has one class, `license_plate`, and no transcription. Real-plate sets (CCPD, UFPR-ALPR) were not used: a readable plate is personal data under the handoff rules, and those sets are real vehicles. `abtExp/synthetic_license_plates` is an empty hub repo (README only).

## t18_hard_hat_worn

Verdict: label check on the built set (not a new source)

Best source: already built from `Voxel51/hard-hat-detection`, CC0-1.0.

Label: `ground_truth.detections[].label`. Checked every built item against `samples.json`. Every "yes" item has at least one `head` box. Every "no" item has zero `head` boxes. Examples: `t18_hard_hat_worn-000` is yes with `{head: 2}`; `-001` is yes with `{helmet: 1, head: 1}`; `-013` is no with `{helmet: 2}` and no `person` box.

Classes and balance: 13 yes, 12 no, as built.

Fits the spec question? The question is "Is there a person who is NOT wearing a hard hat?" The file records that as a `head` box, which is the dataset's no-helmet class, not as a `person` box with a missing helmet. Several yes images also contain a `helmet` box, so both kinds of head can be in one photo. The `person` class is not what the label uses: the four no examples looked at have no `person` box at all.

Risks: the score treats "head box" as "unprotected person". A head box that is not a person, or a person whose head was not boxed, would be wrong for that reason. The 80% Assist-only figure is the one already recorded for this task; it was not re-run here.

Work to build it: none.

What the user must do: nothing, unless you want the set rebuilt so that a `person` box is required as well.

Rejected candidates: none in this check.

## t19_fire_smoke

Verdict: FOUND

Best source: `badsaarow/d-fire`, https://huggingface.co/datasets/badsaarow/d-fire. No licence on the card (local use only). Full download listed as 3.12 GB in the dataset card and 4.21 GB of files, so the full set is over the 3 GB task cap. One test shard is 323 MB. Gated no.

Label: `label`, a string. The viewer’s first rows: `AoF00000.jpg` has `label` `""`; `AoF00001.jpg` has a line starting `1 0.216 ...`; `AoF00002.jpg` has a line starting `0 0.767 ...`. An empty string is no box. A non-empty string is a YOLO box. The original D-Fire project (https://github.com/gaia-solutions-on-demand/DFireDataset) states the image counts as only-fire 1,164, only-smoke 5,867, both 4,658, and none 9,838. A raw mirror states `0=smoke`, `1=fire`. That id map is not written on the `badsaarow` card, so a yes/no label should use empty vs non-empty, not the digit.

Classes and balance: the original project has thousands of "none" images, so a 12/13 split is plausible inside one shard. The shard itself still has to be counted before a build, because this recon did not download it.

Fits the spec question? Yes, if "yes" means the row has a box and "no" means the label is empty. It does not separately grade fire versus smoke.

Risks: licence is not stated. Class ids 0 and 1 must not be named in the question until the card or a file in that repo names them. Do not pair these positives with leaves or hard hats as fake negatives.

Work to build it: download `data/test-00000-of-00003.parquet` (323 MB), count empty vs non-empty, and stop if either answer is missing.

What the user must do: accept local-use-only for an unstated licence.

Rejected candidates: `Simuletic/CCTV-Smoke-Fire-Emergency-Detection-Dataset` (CC-BY-NC-4.0) has only `fire` and `smoke` in `data.yaml`. `fireviewer/fire-smoke-detection-corpus-v2` is about 28 GB. `Alleyp/fasdd_reduced` is an empty repo.

## t20_floor_hazard

Verdict: NEEDS_USER

Best source: none. Hugging Face searches for "wet floor" and "spill detection" returned no dataset.

Label: none found.

Classes and balance: no clean-floor class was found to pair with a spill class.

Fits the spec question? No source to compare.

Risks: drawing fake spill photos was not done; the plan forbids that.

Work to build it: none.

What the user must do: put 25 photos in `data/image-lab/user/t20_floor_hazard/` if you want this task.

Rejected candidates: no named set cleared the search.

## t21_surface_defect

Verdict: FOUND

Best source: `newguyme/neu_det_caption`, https://huggingface.co/datasets/newguyme/neu_det_caption. No licence on the card (local use only). 70 MB, one parquet, gated no. Already downloaded during this recon.

Label: `label_str`. First viewer row: `filename` `crazing_1.jpg`, `label_str` `crazing`. Full file, 1,440 rows: crazing, inclusion, patches, pitted_surface, rolled-in_scale, scratches, 240 each.

Classes and balance: any four of the six classes can supply 6 or 7 images each. No class needs to exceed 40%.

Fits the spec question? Yes. "Which defect is visible on this steel surface?" with four class names taken from `label_str`.

Risks: licence unstated. The set has 1,440 images, not the classic 1,800, and it also contains `blank_image` and map images that must not be used as the photo. Some class names use underscores (`pitted_surface`, `rolled-in_scale`).

Work to build it: sample 25 rows from the parquet already on disk. No further download.

What the user must do: accept local-use-only, or nothing if that is already acceptable.

Rejected candidates: `ybli/yolo-neu-det-surface-defect-object-detection` and `ybli/yolo-neu-det-surface-defect-classification` contain only a README pointing at https://www.data2.cn.

## t22_gauge_reading

Verdict: SYNTH

Best source: a Pillow dial (ticks, needle, a known value, two or three face styles, plus the existing clean / skew / blur treatments). No download. The value drawn is the label.

Label: generator value. Four options are the true reading and three nearby numbers from `decoy_numbers`.

Classes and balance: each true reading can be unique, so the 40% cap is easy. Chance rate 25%.

Fits the spec question? Yes, as a drawing of a gauge, not a photo of a plant gauge.

Risks: it measures reading a drawn dial. It will not include real glass, grime or odd scales unless those are coded. Variety is a handful of layouts, not a factory floor.

What the user must do: accept synthetic gauges.

Rejected as the default, not as impossible: `Mileeena/synthetic-analog-gauges` is gated (`gated=auto`), CC BY 4.0, 2.55 GB. Its README names `needle_value`, `scale_min`, `scale_max` and `scale_unit` on each COCO annotation. Those images were not downloaded. Accept terms at https://huggingface.co/datasets/Mileeena/synthetic-analog-gauges if you want that set instead. `Synanthropic/reading-analog-gauge` is MIT and about 2.6 GB, but the files are corner and keypoint zips, not a numeric reading.

## t23_crop_disease

Verdict: label check on the built set (not a new source)

Best source: already built from `Project-AgML/plant_leaf_disease_classification`, CC BY 4.0, first shard only.

Label: class name of `label`. The 25 items are Black Rot 7, Mosaic virus 6, Fresh leaf 6, Anthracnose 6. Options are always those four names.

Classes and balance: within the cap. The crop attached to the disease is not mixed: all 7 Black Rot images are cauliflower, all 6 Mosaic virus images are bitter gourd, all 6 Anthracnose images are bottle gourd. Fresh leaf is the only class spread across crops (bottle gourd, bitter gourd, cauliflower, 2 each).

Fits the spec question? The question text matches. The sample does not separate disease from crop. A model can answer "Black Rot" by recognising cauliflower.

Risks: mean colour of the saved images is similar (about RGB 62,60,41 for Black Rot, 95,98,81 for Mosaic virus, 64,69,55 for Fresh leaf, 74,80,58 for Anthracnose). That is not a one-colour shortcut, but Black Rot is the darkest. The 72% figure was not re-run here. The score should not be read as "disease recognition across crops".

Work to build it: none, unless you want a rebuild that holds the crop fixed or mixes crops inside each disease.

What the user must do: nothing, or ask for a rebuild.

Rejected candidates: none in this check.

## t24_screenshot_triage

Verdict: RESCOPE

Best source: `OS-Copilot/ScreenSpot-v2`, https://huggingface.co/datasets/OS-Copilot/ScreenSpot-v2, Apache-2.0, gated no. Images are `screenspotv2_image.zip`, 1.33 GB. The old id `lmms-lab-encoder/ScreenSpot-v2` is the one that returned 401. This id is a different repository and is public.

Label: JSON records, not a class column. `screenspot_desktop_v2.json` has 334 rows. The first is `img_filename` `pc_ede36f9b-1154-4f76-b7f8-c15d7d3f9b6e.png`, `instruction` `"close this window"`, `data_type` `"icon"`, plus a `bbox`. Desktop `data_type` counts: text 194, icon 140. Instructions are commands ("minimize this window", "open the Microsoft store"), not a choice of four element names.

Classes and balance: text vs icon can be balanced. There is no set of four element names.

Fits the spec question? No. "Which of these is shown on the screen?" needs an element-name label. This file has a pointing command and a box.

Risks: a yes/no or two-way question about icon vs text is a different task. Screenshots can contain names and message text; the desktop sample commands did not show an identity document, but a full scan was not done.

Work to build it: only after a new question is chosen. The zip is 1.33 GB. The three JSON files are already small enough to read without the zip (desktop was read; web and mobile were not downloaded).

What the user must do: nothing for the original question. If you want a screenshot task, pick a question this label can support.

Rejected candidates: `lmms-lab-encoder/ScreenSpot-v2` (401, not used). `HongxinLi/ScreenSpot_v2` is 0.48 GB of parquet and has no licence line on the card; it was not opened because the Apache-2.0 JSON above already shows the label shape.

## t25_room_type

Verdict: RESCOPE

Best source: `keremberke/indoor-scene-classification`, https://huggingface.co/datasets/keremberke/indoor-scene-classification. README says MIT. 0.47 GB (train 329 MB, valid 94 MB, test 47 MB), gated no. The class list in the README includes `kitchen`, `bathroom`, `bedroom` and `livingroom`. It does not include an exterior or house-exterior class. The README also says the export is the MIT Indoor Scene Recognition set (15,571 images, folder per class).

Label: folder / class name from that list. Per-class counts were not opened from the zip. The related Voxel51 card for the same collection says at least 100 images in each of 67 categories.

Classes and balance: four indoor classes are enough for 6 or 7 images each if the zip matches the README. Exterior cannot be taken from this set.

Fits the spec question? No. The spec has five answers, including `exterior`. This source covers the four rooms only.

Risks: these are photos of real rooms, so people and papers can appear; this recon did not open the image zip. The README's MIT line is the Roboflow export. The pictures are Quattoni and Torralba's indoor set, whose own project page has been the research release. Treat the stricter original terms as the ones to confirm before a build. `Voxel51/IndoorSceneRecognition` (card says MIT, 2.60 GB) is the same image collection and does not add exterior.

Work to build it: download the 0.47 GB export and sample the four room folders. Do not invent an exterior class from another dataset without a decision.

What the user must do: drop `exterior`, or supply exterior photos yourself, and confirm the original indoor-scene terms.

Rejected candidates: a full Places365 download was not proposed; it is far larger than one task needs, and mixing it in only to fill `exterior` would glue two sources together.

## Summary

| Task | Verdict | Extra download | Licence | User action |
|---|---|---|---|---|
| t10 damaged part | RESCOPE | 2.20 GB | Flickr / Shutterstock, non-commercial research | Accept damage-type question and those terms |
| t11 property damage | RESCOPE | about 0.5 GB | Academic use; paper is CC BY 4.0 | Accept "crack in a concrete wall?" |
| t12 package condition | NEEDS_USER | 0 | — | Photos, or a two-class set behind a login |
| t13 shelf gap | DROP | 0 | — | Nothing |
| t16 plate number | SYNTH | 0 | our drawing | Accept drawn plates |
| t18 hard hat | built, label checked | 0 | CC0-1.0 | Nothing |
| t19 fire or smoke | FOUND | 0.32 GB | not stated, local use | Accept local-use-only |
| t20 floor hazard | NEEDS_USER | 0 | — | Photos |
| t21 steel defect | FOUND | 0 (70 MB already here) | not stated, local use | Accept local-use-only |
| t22 gauge | SYNTH | 0 | our drawing | Accept drawn gauges. Optional gated set is 2.55 GB |
| t23 crop disease | built, label checked | 0 | CC BY 4.0 | Nothing, or ask for a rebuild |
| t24 screenshots | RESCOPE | 1.33 GB if wanted | Apache-2.0 | Original id was wrong; question still does not fit |
| t25 room type | RESCOPE | 0.47 GB | export says MIT; confirm original terms | Drop exterior |

Suggested build order, after you pick: t21 (already on disk), then drawn plates and drawn gauges (no download), then one D-Fire shard, then CarDD only if the terms and the new question are accepted, then concrete walls, then indoor rooms without exterior. Screenshots only if the question changes.

Those downloads together are about 3.5 GB without the screenshot zip, or about 4.8 GB with it. Either stays inside the 10.5 GB still free. The gated gauge set is not in that total.

Decisions left open:

- Synthetic images for plates and gauges, or not.
- Damage type instead of damaged part.
- A two-class package task, if you will use a source that needs a login.
- Local-use-only for the steel defects and the fire shard, where the card states no licence.
- Concrete crack instead of roof-or-wall damage.
- Indoor rooms without an exterior class.
- A screenshot question other than "which element name is shown".
