# Image lab data pipeline: hand-off for Cursor

Read this whole file before you touch anything. Work slowly, one task at a time, and stop at every **STOP** marker.
If something does not match what this file says, do not improvise: write what you saw in the task's `.md` file, mark the task `BLOCKED`, and move to the next task.

## 1. What we are building (and why)

We have a local vision model (Winnow-12B, served at `http://127.0.0.1:8091`) that answers **typed questions about images** and returns one probability per option. We want to find out which **real business tasks** it handles well and which it does not.

To do that we need a small, reproducible test set per task:

- **25 images per task, 25 tasks, about 600 images in total.**
- Each image has one typed question and one **known right answer**.
- The right answer must come from **a dataset's own human annotations**, or from a **generator script we wrote that draws the image from known values**. It must never come from a person or a model looking at the image and deciding.

You are building the **pipeline** (download, sample, build, validate, report). You are not running the model. Someone else runs the model later.

### Non-goals (do not do these)

- Do **not** label images by eye. Do not ask a model to label images. Do not "fix" a label you disagree with.
- Do **not** start, stop or restart any server. Do not use the GPU.
- Do **not** run `git commit`, `git push` or change any git config.
- Do **not** edit anything outside `/workspace/probes/images/` and `/workspace/data/image-lab/` and `/workspace/data/sources/image-lab/`. Read other folders freely, but never change them.
- Do **not** commit or copy third-party images into any git-tracked folder. All images stay in git-ignored `/workspace/data/`.

## 2. The machine you are on

| Thing | Where |
|---|---|
| Python with Pillow and pyarrow | `/workspace/kev/.venv/bin/python` (use this; do not `pip install` into it) |
| Hugging Face downloads | `uv run --with huggingface_hub python3 -c '...'` (works, no login needed for ungated data) |
| Raw downloaded sources | `/workspace/data/sources/image-lab/<name>/` (already there: `cord-v2`, `fatura2`, `countbench`, `hard-hat`, `mmmu`) |
| HF cache for new downloads | set `HF_HOME=/workspace/data/sources/hf-cache` |
| Your code | `/workspace/probes/images/` |
| Built images | `/workspace/data/image-lab/images/<task_id>/` |
| Existing scripts you may **read and import** | `/workspace/probes/vision/suite.py` (`ask`, `canvas`, `font`), `/workspace/probes/vision/business.py` (`render_doc`, `render_form`, `degrade`), `/workspace/probes/vision/real_pilot.py` (how CORD and CountBench were read) |
| Existing set format to copy | `/workspace/probes/v2/*.jsonl` and `/workspace/probes/v2/build_phishing.py`, `_common.py` |

Facts learned the hard way:

1. The model server rejects big images: `HTTP 400 "Image exceeds the microbatch"`. **Resize every saved image so its longer side is at most 1536 px** (keep the aspect ratio, save as JPEG quality 88, or PNG for line art and documents).
2. Image limit per request is 24 MiB. Ours will be far smaller.
3. Some datasets are **gated** (need a login to accept terms) or their licence is not stated. Follow the rules in section 6.
4. The shared ledger file in `/workspace/data/probe-runs-v2/` is huge and slows runs. Not your concern while building, but never point anything at it.
5. `lmms-lab/...` datasets on Hugging Face moved to `lmms-lab-encoder/...`. Use the new name.

## 3. Output you must produce

For every task `T` (ids in section 7, for example `t01_invoice_fields`):

```
/workspace/probes/images/
  _imgcommon.py                 shared helpers (section 5, built once)
  build_T.py                    one builder script per task
  T.jsonl                       the 25 items (committed-style, no images inside)
  T.md                          source, licence, label rule, caveats, status
  validate.py                   checks every T.jsonl (section 8)
  STATUS.md                     table of all tasks (section 9)
/workspace/data/image-lab/images/T/   the 25 image files for task T
```

### Item format (one JSON object per line in `T.jsonl`)

It copies the existing `/workspace/probes/v2/*.jsonl` format, plus one new field, `images`:

```json
{
  "id": "t01_invoice_fields-007",
  "family": "t01_invoice_fields",
  "state": "An image is attached.",
  "images": ["t01_invoice_fields/007.jpg"],
  "question": {
    "type": "choice",
    "instructions": "What is the total amount on this invoice?",
    "criteria": {"441.14": null, "441.19": null, "541.14": null, "441.11": null}
  },
  "labels": ["441.14", "441.19", "541.14", "441.11"],
  "expected": "441.14",
  "split": "public",
  "group": null,
  "provenance": {
    "exclude_reason": null,
    "source": "FATURA2 (mathieu1256/FATURA2-invoices), test split",
    "source_id": "row 191",
    "url": "https://huggingface.co/datasets/mathieu1256/FATURA2-invoices",
    "license": "CC-BY-4.0",
    "retrieved": "2026-09-30",
    "label_origin": "tokens following the TOTAL tag in the dataset's own annotation",
    "notes": ""
  }
}
```

Rules for the format:

- `images` paths are relative to `/workspace/data/image-lab/images/`.
- **Yes/no questions** use `type: "noul"`, `labels: ["no","yes"]`, `expected: "yes"` or `"no"`, and `criteria: {"true": "<what yes means>", "false": "<what no means>"}` exactly as in `/workspace/probes/v2/phishing.jsonl`.
- **Pick-one questions** use `type: "choice"`, 2 to 6 options. The option names go in `criteria` (value may be `null` or a short description). `labels` lists the option names in the same order. `expected` must be one of the labels.
- Shuffle option order with the item's seed so the right answer is not always first.
- Write files with `write(path, rows)` from `/workspace/probes/v2/_common.py` (sorted keys, one object per line).

## 4. Order of work and gates

Work in this order. Do not skip ahead.

1. **Step 0, setup.** Create `_imgcommon.py` and `validate.py` (section 5 and 8). Run the validator on an empty folder and make sure it runs without crashing.
2. **Step 1, the "ready" tasks** (section 7, status **READY**): `t01`, `t02`, `t07`, `t09`, `t10`, `t14`, `t15`, `t16`, `t18`, `t23`, plus the synthetic tasks `t05`, `t06` (section 7 marks them SYNTH). For each task, follow the **per-task routine** below.
3. **Step 2, the "check first" tasks** (status **CHECK**): do the recon part of the routine. If the dataset does not fit, mark `BLOCKED` and move on.
4. **Step 3, the "no source" tasks** (status **NONE**): do not try to find data. Create the drop-in instructions (section 10) and mark `NEEDS_USER_IMAGES`.
5. **Step 4.** Run `validate.py` on everything, write `STATUS.md`, stop.

### Per-task routine (follow exactly, in this order)

1. **Recon.** Open the source. Print its columns and the first 3 rows (skip image bytes: print their length). Write what you saw into `T.md` under "Recon". **Compare it to the spec in section 7.** If the label column or file does not exist or means something different, set status `BLOCKED`, explain in `T.md`, and go to the next task. **STOP here for any surprise.**
2. **Sampling rule.** Choose 25 items with a fixed seed written in the script (`SEED = <the task number>`). For yes/no tasks take 12 or 13 of each answer (as balanced as the source allows). For pick-one tasks spread the right answers across options and classes; no option is correct in more than 40% of items.
3. **Build.** Write `build_T.py`. It must: read the source, apply the label rule from section 7 literally, save images (section 3 rules, max 1536 px long side), write `T.jsonl`, and be **re-runnable** (running it twice gives identical files).
4. **Write `T.md`** with: source name and URL, licence, how the answer is derived (name the exact column or field), how distractors were made, the **chance rate** (for example 25% for four options, 50% for yes/no), known weaknesses of the label, and the final status.
5. **Run `python validate.py T`.** Fix anything it reports. Only then go to the next task.

## 5. Shared helpers (`_imgcommon.py`)

Build these functions once, test each in a tiny script, and reuse them:

- `save_image(pil_image, task_id, index) -> relative_path`: converts to RGB, shrinks so the long side is at most 1536, saves to `/workspace/data/image-lab/images/<task_id>/<index:03d>.jpg` (quality 88). Returns the path relative to `/workspace/data/image-lab/images/`.
- `make_choice(question_text, options, correct, seed) -> (question_dict, labels, expected)`: shuffles with the seed, returns the structures from section 3.
- `make_yesno(question_text, yes_text, no_text, answer_bool) -> (question_dict, labels, expected)`.
- `provenance(source, source_id, url, license, label_origin, notes="")`: returns the provenance dict with today's date as `retrieved`.
- `decoy_numbers(value_string, n, seed)`: returns `n` wrong amounts that keep the same number of digits and the same decimal format (change one or two digits). Never return the right one.
- `wilson(k, n)`: 95% Wilson interval, for the report.

## 6. Rules for data sources

1. **Ungated and licence stated:** fine to download (CC-BY, CC0, MIT, Apache-2.0, ODbL).
2. **Licence not stated** (for example CountBench) **or non-commercial / GPL** (for example ChartQA, GPL-3.0): allowed for **local testing only**. Put `"license": "not stated, local use only"` (or the real licence) in the provenance and in `T.md`. Never copy these images anywhere git tracks.
3. **Gated** (Hugging Face asks you to log in or accept terms): **STOP.** Write in `T.md` what the user must do (which URL, which button), mark `NEEDS_USER_ACTION`, move on. Never try to work around a gate.
4. **Do not download** anything bigger than 3 GB for a single task. If the only way is bigger, download one shard only (list the repo files first) and write down which shard in `T.md`. **Total budget for this whole job: 15 GB.** Run `du -sh /workspace/data/sources/image-lab` after each download and stop at the budget.
5. **No personal data.** If an image shows a real identity document or a readable real person's details, do not use it; mark the task `BLOCKED` with the reason.

## 7. The 25 tasks

Status codes: READY = a real source is known and probably fits. SYNTH = we draw the image from known values. CHECK = candidate source, recon may show it does not fit. NONE = no source found.
"Already on disk" means files are in `/workspace/data/sources/image-lab/`.

### Finance and admin

**t01_invoice_fields (READY).** Source: FATURA2 test split, already on disk at `fatura2/data/test-00000-of-00001.parquet` (columns `image`, `ner_tags`, `bboxes`, `tokens`, `id`; licence CC-BY-4.0). The `ner_tags` are integer ids; **find the id-to-name table** in the dataset README (`https://huggingface.co/datasets/mathieu1256/FATURA2-invoices/raw/main/README.md`) and record it in `t01.md`. Questions (mix across the 25, about 8 each): (a) choice, "What is the total amount on this invoice?" right answer = the tokens tagged TOTAL, decoys from `decoy_numbers`; (b) yes/no, "Is the total more than <threshold>?" choose a threshold per image so that the answer is yes for about half of them; (c) choice, "What is the invoice number?" right answer = the tokens tagged invoice number, decoys altered the same way. Only use rows where the tagged tokens form one clean value. Skip rows where they do not.

**t02_receipt_capture (READY).** Source: CORD v2 test, already on disk at `cord-v2/data/test-*.parquet` (columns `image`, `ground_truth`; `ground_truth` is a JSON string; licence CC-BY-4.0). Labels: `gt_parse.total.total_price` (string) and, for item counts, the length of `gt_parse.menu` (it is a dict when there is one item and a list otherwise; accept 1 to 8 items only). Questions: half "What is the total amount on this receipt?" (choice, `decoy_numbers`), half "How many different line items are on this receipt?" (choice 1 to 8). **Do not use a discount question**: we found our own discount label unreliable. **Resize every image** (some are 2304x4096).

**t03_document_type (CHECK).** Candidate: RVL-CDIP (16 document classes, human-labelled). The full set on Hugging Face (`aharley/rvl_cdip`) is about 84 GB: **do not download it**. Look for a small copy or a single shard (for example `hf-tuner/rvl-cdip-document-classification`). Recon: class names, licence, file size. Question: choice over 4 class names (the right class plus 3 others), "What type of document is this?". If you cannot get a sample of 25 under the size budget, mark `BLOCKED`.

**t04_signature_present (CHECK, gated).** Candidate: `tech4humans/signature-detection` (Apache-2.0, **gated**). Follow rule 6.3: write what the user must do and mark `NEEDS_USER_ACTION`. Planned question: yes/no, "Is there a handwritten signature on this page?", positives from images with a signature box annotation, negatives from images with none.

**t05_form_completeness (SYNTH).** Generator: import `render_form` and `degrade` from `/workspace/probes/vision/business.py` (they return the image plus a dict of true values: `signed`, `named`, `ticks`, `terms`, `count`). Questions, about 5 each: "Has the form been signed?" (yes/no), "Is the box for accepting the terms ticked?" (yes/no), "How many checkboxes are ticked?" (choice 0 to 4), "Is the full name field filled in?" (yes/no), and one more of your choice from the same dict. Use each of the four quality levels (`clean`, `skew`, `lowres`, `scan`) about equally. The right answer is the value the generator used to draw the image. Record `label_origin: "generator value"`.

**t06_cheque_amount (SYNTH or CHECK).** First look at `jaganadhg/cheque-synthetic-images` (Apache-2.0) and `alpha-brain/ocr-synthetic-cheque-datatset`. Keep whichever has a readable amount column. If neither does, write a small generator of your own with Pillow that draws a cheque with a payee, a date and an amount in digits, and use those values as labels. Question: choice, "What is the amount on this cheque?" with `decoy_numbers`.

**t07_chart_reading (READY, local use).** Source: `HuggingFaceM4/ChartQA` (GPL-3.0; local use only). It has questions with short answers. Keep only items whose answer is a single number or a single label that appears in the chart. Turn each into a choice question with the true answer plus 3 plausible others (other numbers or labels from the same chart's question set; if you cannot do this mechanically, use `decoy_numbers` for numeric answers). Skip anything ambiguous.

**t08_handwritten_line (CHECK).** Candidate: `Voxel51/iam_handwriting_finevision` (licence tag just `cc`; read the card first). Question: choice, "Which text is written in the image?" with the true transcription plus 3 other transcriptions from other rows. Only use short lines (under 60 characters). Mark BLOCKED if the transcription is not a clean column.

### Insurance and claims

**t09_vehicle_damage (READY).** Source: `DrBimmer/car-parts-and-damage-dataset` (MIT). It has images plus annotation JSON files (format looks like Supervisely: `ann/<image>.json` with a list of objects and class titles). Recon: list the class titles. Question: yes/no, "Is this vehicle visibly damaged?". Right answer = whether the annotation contains at least one object of a damage class. Balance 12/13. If the dataset only has damaged cars (no undamaged), say so in `T.md` and mark `BLOCKED`: a yes/no with no negatives proves nothing.

**t10_damaged_part (READY, same source as t09).** Question: choice over 4 car part names, "Which part of the car is damaged?" Right answer = the part class of the object that overlaps the damage object most. If you cannot compute overlap from the annotations simply, use only images that show exactly one damaged part and exactly one damage object. Skip the rest.

**t11_property_damage (NONE).** **t12_package_condition (NONE).** Use section 10.

### Retail and logistics

**t13_shelf_out_of_stock (CHECK).** Candidate: `adnankhan-11/smart-retail-shelf-auditing-v1` (licence unstated). Recon first. Only use it if it has a per-image label you can turn into yes/no ("Is there an empty shelf gap?") with both answers present. Otherwise `BLOCKED`.

**t14_count_items (READY, local use).** Source: CountBench, already on disk at `countbench/data/*.parquet` (columns `image_url`, `text`, `number`, `image`; some rows have `image = None`: skip them; licence not stated, local use only). Label = `number` (2 to 10). Question as in `/workspace/probes/vision/real_pilot.py`: take the caption, replace the number word in it with `___`, ask "Which number belongs in the blank?" (choice over 2 to 10). Skip captions where the number is not found. Spread the right answers across 2 to 10 (2 or 3 items each).

**t15_produce_fresh_rotten (READY).** Source: `Project-AgML/fresh_rotten_fruit_classification` (CC-BY-4.0). Question: yes/no, "Is this fruit rotten?" Right answer from the dataset's class name. Balance 12/13. Recon: class names may include the fruit type too ("rotten_apple"); map by whether the name contains "rotten".

**t16_license_plate (READY).** Source: `mabo7237/license-plates-700k` (MIT). Question: choice, "What is the plate number?" with the true text plus 3 plates taken from other rows. Recon first: check the text column, and skip rows where the text is empty or the image is tiny (under 60 px wide).

**t17_logo_present (CHECK).** Candidate: `varun1212/logo-detection-dataset` (licence unstated). Recon only. Planned question: choice over 4 brand names. Mark BLOCKED if classes are not brand names.

### Safety and compliance

**t18_hard_hat_worn (READY).** Source: `Voxel51/hard-hat-detection` (CC0), already on disk at `hard-hat/` (about 5000 files, FiftyOne layout: look for `samples.json` or `data/` plus a labels file; recon first). Classes are probably `head`, `helmet` and `person` or similar. Question: yes/no, "Is there a person in this image who is NOT wearing a hard hat?" Right answer = the image has at least one "no-helmet" style object. Keep images with 1 to 3 people so the answer is not ambiguous. Balance 12/13.

**t19_fire_smoke (CHECK).** Candidates: `fireviewer/fire-smoke-detection-corpus-v2` (licence unstated), `Simuletic/CCTV-Smoke-Fire-Emergency-Detection-Dataset` (CC-BY-NC, local use only). Recon. Question: yes/no, "Is there fire or smoke visible?" Needs real negatives. Otherwise `BLOCKED`.

**t20_floor_hazard (NONE).** Use section 10.

### Manufacturing and field

**t21_surface_defect (CHECK).** Candidate: `ybli/yolo-neu-det-surface-defect-object-detection` (licence unstated). Question: choice over 4 defect types (for example "crazing", "patches", "inclusion", "scratches"), "Which defect is visible on this steel surface?". Right answer = the class of the annotation. Use images with exactly one defect class present.

**t22_gauge_reading (NONE).** Use section 10.

**t23_crop_disease (READY).** Source: `Project-AgML/plant_leaf_disease_classification` (CC-BY-4.0). Question: choice over 4 disease or health class names, "What condition does this leaf show?". Right answer = the class label. Use a mix of classes.

### IT and property

**t24_screenshot_triage (CHECK).** Candidate: `lmms-lab-encoder/ScreenSpot-v2` (UI screenshots with target elements; read the card). Recon first. Possible question: choice over 4 UI element names, "Which of these is shown on the screen?", right answer from the dataset's element text. Mark BLOCKED if no clean label.

**t25_room_type (NONE).** Use section 10.

## 8. Validator (`validate.py`)

`python validate.py T` (one task) or `python validate.py all`. It must check, for each `T.jsonl`:

1. Exactly **25** lines (fewer only if the task status is BLOCKED or NEEDS_*, and then it must say so).
2. Every line is valid JSON with all keys in section 3.
3. `expected` is in `labels`; `labels` equals the keys of `question.criteria` (for `noul`: `["no","yes"]` and criteria keys `true`,`false`).
4. No duplicate `id`. No two items share the same image file.
5. Every file in `images` exists, opens with Pillow, and has a long side of at most 1536 px.
6. Class balance: yes/no tasks have between 10 and 15 "yes" answers. Choice tasks: no single right answer is more than 40% of items.
7. `provenance` has `source`, `url`, `license`, `label_origin`.
8. **Re-derive check.** For READY tasks, a function in `build_T.py` named `rederive(item)` re-reads the source and recomputes the expected answer from the dataset's annotation. The validator calls it for every item and fails if any answer differs. (This proves the answer comes from the dataset and not from us.)

Print a clear PASS or FAIL per task with the reason. Exit code 0 only if everything passes.

## 9. Success criteria

### For the pipeline (you are done when all of these are true)

- `python validate.py all` passes for every task that is not BLOCKED / NEEDS_*.
- `STATUS.md` lists all 25 tasks with: status, item count, source, licence, chance rate, and a one-line reason for every task that is not READY.
- Every task has a `T.md` with the recon notes and caveats.
- At least **12 tasks** are fully built and passing. If fewer, say why in `STATUS.md`. Do not pad with invented data.
- Nothing outside the allowed folders has changed. Check with `git -C /workspace status --short` (it must show no new changes from you) and report the output.

### For the model run (later, not your job, but define it in `STATUS.md` so we use the same bar)

For each task, the runner will report: correct/25, the 95% Wilson interval, and the chance rate. Use these labels:

| Label | Rule |
|---|---|
| **Works** | point estimate 85% or more **and** the lower end of the interval above 70% |
| **Assist only** | point estimate 60% to 85% (human review needed) |
| **Not ready** | below 60%, or the interval includes the chance rate |
| **Could not run** | any image rejected by the server; count these separately, never as wrong |

Also write down, per task, the chance rate (yes/no 50%, four options 25%, and so on) so nobody reads 60% on a yes/no task as good.

## 10. Drop-in folder for tasks with no source (status NONE, NEEDS_USER_IMAGES)

For each of `t11`, `t12`, `t20`, `t22`, `t25` create `/workspace/data/image-lab/user/<task_id>/README.txt` saying:

```
Put 25 photos here (JPEG or PNG) and a labels.csv next to them with columns:
image,question_id,answer
Use one row per photo. The question and its allowed answers are listed in
/workspace/probes/images/<task_id>.md. Only use photos you are allowed to use.
```

and in `<task_id>.md` write the planned typed question and the 2 to 4 allowed answers:

- t11: yes/no, "Is there visible damage to the roof or walls?"
- t12: choice `intact` / `dented` / `crushed` / `open or torn`, "What is the condition of this package?"
- t20: yes/no, "Is there a spill or object on the floor that could cause a fall?"
- t22: choice over 4 numbers, "What value does the gauge show?" (the user supplies the 4 options per photo in `labels.csv` as an extra `options` column, pipe-separated)
- t25: choice `kitchen` / `bathroom` / `bedroom` / `living room` / `exterior`, "What kind of room or view is this?"

Also write a small `ingest_user.py` that turns such a folder into a `T.jsonl` in the section 3 format, with `label_origin: "supplied by user"`. Do not run it (there are no photos yet).

## 11. When to stop and ask

Stop and write a note at the top of `STATUS.md` if any of these happens:

- A download would pass the 15 GB total.
- A dataset needs a login or acceptance of terms.
- A licence forbids what we are doing (for example it says no research use).
- You are about to change a file outside the allowed folders.
- You cannot tell what a label column means after reading the dataset card. Do not guess.
- Any image looks like a real person's identity document or contains readable personal data.

Finish with a short list of what you built, what is blocked and what you need from the user.
