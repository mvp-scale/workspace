# Image lab gap recon: plan for a second agent

Read `HANDOFF.md` first. Its rules (scope, naming, data-source rules in section 6, stop conditions in section 11) all still apply. This file only adds what to do about the gaps. Do recon first, then stop and report. Do not build anything until the user has read your report.

## 1. Why this exists

The Image lab page (`/imagelab`) lists 25 tasks in six business areas. Only 12 are built. Five areas are thin or empty, so the lab cannot yet say anything about them:

| Area | Built | Not built (reason from `STATUS.md`) |
|---|---|---|
| Insurance and claims | t09 vehicle damage (weak negatives) | t10 blocked: damage and parts never appear on the same image. t11, t12: no source |
| Retail and logistics | t14 count, t15 produce, t17 logo | t13 blocked: every box is `category_id 1`, no empty-gap label. t16 blocked: no plate-text column, repo is 12.4 GB |
| Safety and compliance | t18 hard hat (80%, Assist only) | t19 blocked: only fire and smoke, no negatives. t20: no source |
| Manufacturing and field | t23 crop disease (72%) | t21 blocked: Hub repo has no images. t22: no source |
| IT and property | none | t24 needs user action (Hub returned 401). t25: no source |

Goal of this job: for each of the 11 unbuilt tasks, find out whether a usable, openly obtainable source exists, and say exactly what it would take. Also rate the weak built tasks (t09, t18, t23) so the user knows which numbers to trust.

## 2. What counts as usable (the bar every candidate must clear)

1. **A label we did not make.** The right answer comes from the dataset's own annotation, or from a generator we write that draws the image from known values. Never from a person or model looking at the image.
2. **Both answers present.** Yes/no tasks need real negatives, not just positives. Choice tasks need at least 4 distinct classes with at least 3 images each (so 25 items can be sampled with no class over 40%).
3. **Licence stated and compatible.** Per HANDOFF 6: stated licence is fine; unstated, non-commercial or GPL is allowed for local use only; gated means STOP and write down what the user must click.
4. **Small enough.** At most 3 GB for one task, 30 GB for the whole job (raised by the user from 15 GB) (about 10.5 GB is still free; check `du -sh /workspace/data/sources/image-lab`).
5. **No personal data.** No readable real person, ID document or identifiable private property. This matters for t16 and t20 in particular (see below).
6. **Fits the typed question** in HANDOFF section 7 or, where that is impossible, a re-scoped question that the user approves.

## 3. Recon rules (this phase is read-only)

- **Peek, do not download.** List repo files, read the dataset card, read `README`/`dataset_infos`, fetch the first 3 rows or one small shard at most. Put anything you do fetch under `/workspace/data/sources/image-lab/<name>/`.
- Use `HF_HOME=/workspace/data/sources/hf-cache` and `uv run --with huggingface_hub`. Remember `lmms-lab/...` moved to `lmms-lab-encoder/...`.
- Candidate names in section 4 are **leads from memory, not verified facts**. Confirm that each exists, what its label column actually means, and its licence from the card. If a name is wrong, say so and search for a replacement on Hugging Face, Kaggle (only if it needs no login), GitHub, Zenodo or the dataset's own site.
- Do not edit `STATUS.md` yet. Write your findings in a new file, `RECON-REPORT.md` (format in section 6). Do not touch the existing `T.md` files either.
- Do not run any model, start or stop any server, or commit anything.

## 4. Per-gap brief

Priority order is by how much the user gains. Each entry gives the question to answer and leads to check. "Synth" means a generator we write ourselves, which is always allowed and has a known label by construction.

### A. Insurance and claims (3 gaps)

**t10 damaged part.** Dead end as specified. In the car dataset no image carries both a part box and a damage box, so there is no "part that is damaged" label. Recon questions:
- Is there a different public dataset with damage **and** part annotations on the same image (leads: CarDD for damage types; any "car damage with parts" set)?
- Cheaper alternative to propose to the user: **re-scope to damage type** ("What kind of damage is visible: dent, scratch, crack or broken part?"), using the 814 damage-only annotation files already downloaded for t09. Count how many have exactly one damage class present and how evenly the classes split. This needs no new download.

**t11 property damage (yes/no: visible damage to roof or walls).** Look for a dataset with damaged and undamaged building exteriors, or wall and roof defects with both classes. Leads: SDNET2018 (crack / no crack on walls, CC BY 4.0), roof hail or storm damage sets, concrete or masonry crack sets. Aerial or satellite damage sets (for example xBD) are not the same task: say so if that is all you find.

**t12 package condition (intact / dented / crushed / open or torn).** Look for a labelled damaged-parcel or packaging-defect dataset with at least these four states. Roboflow Universe and Kaggle sets often need a login or carry mixed licences; apply the gated rule. If nothing has all four states, report the best 2 or 3 state version.

### B. Retail and logistics (2 gaps)

**t13 shelf out of stock (yes/no: empty gap on shelf).** The one tried (`adnankhan-11/smart-retail-shelf-auditing-v1`) has a single category. Look for any shelf dataset with an explicit empty-space, gap or out-of-stock class (leads: out-of-stock or "empty shelf" detection sets, grocery shelf sets with a gap class). If the only route is sets with product boxes and no gap class, mark BLOCKED and say what is missing.

**t16 license plate (choice: what is the plate number).** The tried repo has no text column and is 12.4 GB. Two routes to assess:
- **Real:** a plate dataset with a transcription column and a small download (leads: CCPD, UFPR-ALPR, OpenALPR benchmark). Real plates are arguably personal data (HANDOFF 6.5 and 11), so state clearly whether the set is anonymised or blurred, and recommend against it if not.
- **Synth (recommended to assess first):** draw plate crops on simple backgrounds from known strings, as t05 and t06 do. Safe, no licence problem, label by construction. Say what level of realism a Pillow generator can reach (fonts, perspective, blur) and that the result then measures reading on clean synthetic plates, not on photos.

### C. Safety and compliance (2 gaps, plus one weak task)

**t19 fire or smoke (yes/no).** The small set on disk (CCTV smoke/fire, CC-BY-NC-4.0) has only positives; the other corpus is 28 GB. Recon: find a set with fire/smoke **and** matched negative scenes, or one with labelled "none" images, in a size we can take one shard of (leads: D-Fire, FASDD and similar). Reject the shortcut of pairing our positives with negatives from an unrelated dataset (for example the leaf or hard-hat images): the model would just detect the domain change, so the test would prove nothing. Report that explicitly if it is the only option.

**t20 floor hazard (yes/no: spill or object that could cause a fall).** No source known. Check for wet-floor, spill, or obstruction detection datasets with a clean-floor class. If none, this stays NEEDS_USER_IMAGES. Do not synthesise photos of spills.

**t18 hard hat (built, 80%, Assist only).** Not a gap, but re-check the label: the notes say people are counted from head or helmet boxes. Look at 5 to 8 of the 25 built items' annotations and say whether "a person not wearing a hat" is really what the label records (for example a visible helmet versus a person whose head box is simply absent). Report only what you find.

### D. Manufacturing and field (2 gaps, plus one weak task)

**t21 surface defect (choice over 4 defect types).** The tried repo (`ybli/yolo-neu-det-surface-defect-object-detection`) has no images, only an off-site link. Recon: find a Hub mirror or other host of the NEU surface-defect database (6 classes: crazing, inclusion, patches, pitted surface, rolled-in scale, scratches), check its licence and whether the file is small (it is a few hundred MB at most). Other defect sets (for example metal surface or industrial anomaly sets) are acceptable if the class is per image.

**t22 gauge reading (choice over 4 numbers).** No public source assumed. Assess two routes:
- **Synth (recommended):** draw analogue dial gauges with a known needle value (Pillow, range, tick marks, a few styles and lighting degrades). The four options are the true reading plus three nearby values. Say how much variety is realistic.
- **Real:** any public analogue-gauge reading dataset with the value as a label. Note whether the label is a measured reading or an estimate.

**t23 crop disease (built, 72%, Assist only).** The first shard only was used. Check that the 25 items cover more than one crop and that the four options shown are not trivially separable by colour. Report only what you find.

### E. IT and property (2 gaps)

**t24 screenshot triage.** `lmms-lab-encoder/ScreenSpot-v2` returned 401. Check whether the id is wrong (try `OS-Copilot/ScreenSpot-v2` and the original release) or truly gated. If gated, write the exact URL and button the user must press and stop. Also check one alternative that is open (UI screenshot sets with element text or class per element, for example Rico-derived or web-UI sets). Confirm what the question would be: "which of these elements is shown" needs an element-text label per image.

**t25 room type (choice: kitchen / bathroom / bedroom / living room / exterior).** No source assumed. Leads: indoor-scene recognition sets with these room classes (for example MIT Indoor-67, a licence that is research-only, or Places365 scene classes, CC BY) and real-estate room-classification sets. Check each class has enough images and that "exterior" can be taken from a house-exterior class. Photos of real homes may show people or documents; sample a few and say so.

## 5. Decisions the user may need to make (list them, do not decide)

- Accept **synthetic** images for t16 and t22 (known labels, but not photos)?
- Re-scope t10 from "damaged part" to "damage type"?
- Allow a **two or three option** version of t12 if four states are not available?
- Accept **local-use-only** sources for tasks that have no open alternative?

## 6. What to deliver (`RECON-REPORT.md`)

One section per task, in this fixed order of fields, so it can be compared across tasks:

```
### tNN_name
Verdict: FOUND | SYNTH | RESCOPE | NEEDS_USER | DROP
Best source: <name, URL, licence as stated on the card, size to download, gated yes/no>
Label: <exact column or field, what it means, evidence you looked at it (cite the rows you read)>
Classes and balance: <counts, or why balance is possible>
Fits the spec question? <yes / no and how it differs>
Risks: <label noise, personal data, train-set overlap, domain shift>
Work to build it: <steps, rough download size, any new dependency (should be none)>
What the user must do: <or "nothing">
Rejected candidates: <name and the specific reason each failed>
```

End with a one-page summary table (task, verdict, size, licence, user action needed) and a ranked build order. State the total disk the plan would add against the 15 GB budget.

## 7. After the user approves

Build only the tasks the user selects, using HANDOFF section 4's per-task routine and validator. Then update `STATUS.md` keeping its table format exactly (the Image lab page reads that table to list not-built tasks and reads `tNN_*.jsonl` plus `data/image-lab/runs/<model>/<task>/results.jsonl` for built ones). Run the model with `run_winnow.py <task>`; the page picks the new task up with no code change.

## 8. Stop and ask if

- A candidate is gated, needs a login, or forbids research use.
- A download would pass the budget.
- You cannot tell what a label column means after reading the card. Do not guess.
- An image shows a readable real person, plate with an identifiable owner, ID document or private address.
- You are about to change any file outside `probes/images/` and `data/image-lab/`.
