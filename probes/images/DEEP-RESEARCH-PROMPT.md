# Deep research prompt: Image lab task atlas

How to use: paste **Part 1** (the master prompt) and then **one slice from Part 2** into each research agent (five agents, ten domains each). When all five return, paste the five answers into one agent with **Part 3** (the merge prompt).

---

## Part 1. Master prompt (same for every agent)

You are helping build a test bench that measures a vision model on real business image tasks. I need two things back: **(A)** a map of the most valuable image tasks in each business domain I give you, and **(B)** for each task, datasets that I can trust and can **test for fit before downloading anything big**.

### What a "task" is
A task is a repeated business decision made from a picture. Example: "is this vehicle damaged?", "what amount is on this cheque?", "is the person wearing a hard hat?". It must be answerable as ONE typed question about ONE image, in one of two shapes:
- **yes/no**
- **pick one of 2 to 6 named options**
The right answer must be a fact that can be checked, not an opinion. Skip tasks that need a medical diagnosis, a legal judgement, or identifying a real person.

### Part A. The task map
For each domain in my slice, list the **top 5 to 8 tasks**, ranked by business value (how often a company makes this decision, and what a wrong answer costs). For each task give:
- task name, the exact typed question, the answer options
- why it matters, in one sentence, with one source (an industry report, a vendor page, a regulator page). No source means say so.
- the image type (photo, scan, screenshot, drawing, aerial, video frame)

### Part B. Dataset qualification (the part that matters most)
For each task find up to 3 candidate datasets. Rank them. For **each** candidate fill in a **Qualification Card** with every field below. Do not skip fields. If you cannot get a field from a primary source, write `UNVERIFIED` instead of guessing.

1. **Landing URL** (the owner's page) and **file listing URL** (where the files or rows can be seen). A Hugging Face repo id if one exists.
2. **Licence**, quoted from the owner's own page or card, with the URL. Say if it forbids research or testing use, or demands prior consent or a form.
3. **Access**: `open`, `login`, `form or email request`, `manual approval`, or `unknown`. We never log in, fill forms or request access. Those candidates are marked `GATED` and listed so a human can decide.
4. **Size**: total size, and **the smallest unit we can fetch on its own** (one shard, one split file, one annotation file), with its size in MB. If the only download is one big archive, say `SINGLE ARCHIVE` and its size.
5. **Sample-first proof.** Give a way to look at the labels **without downloading the images**, and actually do it. Acceptable: the Hugging Face dataset viewer or datasets-server `/first-rows`, `/rows` and `/info` endpoints, `HfApi.dataset_info(files_metadata=True)`, a raw annotation file (JSON or CSV) under 50 MB, or a range request into a parquet file. **Paste three real annotation rows** (leave out image bytes) from what you fetched. A candidate with no pasted rows cannot be rated above `UNVERIFIED`.
6. **Annotation schema**: the exact column or field names and types, and what each one means in your words after reading the card.
7. **Label origin**: `human`, `machine`, `generator` (the image was drawn from known values), or `mixed`. Quote the evidence (the card, the paper's annotation section). Labels produced by an OCR engine, a detector or a captioning model are `machine`.
8. **The answer rule**: the exact way to compute the right answer for our typed question from those columns. Example: "yes if any annotation has `category` in {dent, scratch}". If the answer cannot be computed from the columns alone (it needs someone to look at the image), say so.
9. **Classes and balance**: class names and counts from the metadata. For yes/no tasks, **are there real negatives?** Many damage and defect datasets contain only positives. Say how you know.
10. **Per-image fit**: is there exactly one answer per image, or can an image carry several (several defect types, several people)? State how to pick images with one clean answer.
11. **Risks**: personal data (faces, plates, names, emails), image size (very small or very large), likely overlap with common model training data, known label noise, and anything the paper admits is hard.
12. **Three question templates** that the columns can answer directly, with option lists.
13. **Evidence tag on every claim**: `[ROW]` seen in a fetched row, `[CARD]` read on the owner's page, `[PAPER]`, `[INFERRED]`, `[UNVERIFIED]`.

Rules for evidence:
- Do not rely on memory for licences, sizes, class lists or access. Fetch them. Where my earlier helpers did this from memory they got several facts wrong.
- Never download more than 50 MB for one candidate during research. Prefer previews and listings.
- Do not log in, accept terms, fill forms or ask for access.
- Prefer a repository or page that lists file sizes.

### Known traps (reject or flag candidates that have these)
- **Positives only**: a damage, defect or fire dataset with no undamaged or empty images. Cannot make a yes/no.
- **Machine labels**: annotations produced by OCR, a detector or a captioning model (for example screen-annotation formats built by an automatic pipeline).
- **Instruction-only labels**: the "label" is a free-text instruction, not a class or value.
- **A mirror with no images**: a Hub repo that only links off-site.
- **A single huge archive** that cannot be sampled.
- **Tiny images** (about 200 px): they blur when enlarged to our 1536 px limit.
- **Question cannot be computed**: the answer needs a person to look.
- **Consent required**: the owner asks users to email a form before use, even when a mirror is open. Mark `GATED` and say the mirror may be the same data.

### Already used or rejected: do not propose again
Used: FATURA2, CORD v2, CountBench, Voxel51 hard-hat-detection, ChartQA, IAM (FineVision), hf-tuner RVL-CDIP, DrBimmer car parts and damage, Project-AgML fresh/rotten fruit and plant leaf disease, logo-detection-dataset, alpha-brain synthetic cheques, ScreenSpot-v2 (found, public, Apache-2.0, not yet used).
Rejected: SKU-110K (no category, 13.6 GB single archive), MVTec D2S, DocVQA (sensitive documents, web-form access), RICO screen annotations (machine labels), xBD (aerial only), MVTec AD 2 and LOCO AD, CarDD (consent form required).

### Part C. Making more questions from a trusted dataset
For every task rated `USE`, add a **question expansion recipe** with three tiers, kept separate:
- **Tier A. Trusted answer**: the human annotation or generator value gives the answer directly.
- **Tier B. Derived from annotation**: more questions whose answer is **computed from the same columns** (counts, presence, class lookups, "is X larger than Y", "which of these is NOT present"). List 3 to 5 derived question types per dataset with the rule.
- **Tier C. Model-written**: a cheap frontier model reads the image and writes extra questions and distractor options. Their answers are **not trusted**. Say how to keep them separate (always a `label_origin: model` tag, never mixed into Tier A or B scores), how to validate them (a second, different model must agree, and the model under test never writes its own questions), and which are most useful (rewording, harder distractors, natural-language variety).

### Output format
Return, in this order:
1. **Task atlas**: one table per domain (task, typed question, options, image type, value reason with source).
2. **Dataset cards**: one block per candidate in the field order above, headed by its task id `D<domain number>.<task number>`.
3. **A CSV block** with one row per candidate and these columns, so I can sort it:
`domain, task_id, task, dataset, landing_url, repo_id, licence, licence_quote_url, access, total_mb, smallest_fetch_mb, single_archive, sample_proof_url, rows_pasted(yes/no), label_origin, answer_rule, has_negatives, classes, one_answer_per_image, personal_data_risk, verdict(USE/MAYBE/SKIP/GATED), confidence(high/med/low), unverified_fields`
4. **Gaps**: tasks with no acceptable dataset, and for each whether a drawn (generator) version is realistic and how.
5. **Cannot verify**: anything you could not fetch.

Rate each candidate `USE` only if: licence stated, access open, a sample-first proof with pasted rows, label origin human or generator, an answer rule that needs no one to look at the image, and (for yes/no) real negatives. Otherwise `MAYBE`, `SKIP` or `GATED`, and say which test it failed.

Keep going until each domain in your slice has 5 to 8 tasks and each task has at least one carded candidate or a clear entry in Gaps.

---

## Part 2. Domain slices (give each agent one)

**Slice 1. Money and paperwork**
1 Banking and payments documents (cheques, statements) · 2 Accounting and accounts payable (invoices, receipts) · 3 Insurance, motor · 4 Insurance, property and catastrophe · 5 Insurance, health and medical billing documents · 6 Legal and contracts · 7 Government forms and permits · 8 Identity and KYC (specimen or synthetic documents only) · 9 Tax and customs documents · 10 HR and recruiting (resumes, badges, timesheets)

**Slice 2. Goods, places and logistics**
11 Retail shelves and merchandising · 12 E-commerce product listings and catalogues · 13 Grocery and produce quality · 14 Food service and restaurant hygiene · 15 Warehousing and inventory · 16 Parcel, freight and container logistics · 17 Last-mile delivery proof · 18 Hospitality and room condition · 19 Real estate (exteriors, interiors, floorplans) · 20 Facilities, cleaning and waste

**Slice 3. Industry and infrastructure**
21 Manufacturing quality (surfaces, assembly) · 22 Electronics and PCB inspection · 23 Automotive repair and parts · 24 Aviation and aerospace maintenance · 25 Rail and transit · 26 Construction progress and sites · 27 Utilities meters and gauges · 28 Energy assets (solar, wind, power lines) · 29 Oil, gas and mining inspection · 30 Roads, bridges and public infrastructure

**Slice 4. Living systems and safety**
31 Agriculture and crops · 32 Livestock and fisheries · 33 Forestry and environment · 34 Workplace safety and PPE · 35 Fire, smoke and security video · 36 Traffic, parking and smart city · 37 Healthcare administration (documents, labels, forms; no diagnosis) · 38 Pharmacy (pills, packaging, labels) · 39 Veterinary and pets · 40 Laboratory and scientific (instruments, microscopy; no diagnosis)

**Slice 5. Digital and knowledge work**
41 IT support and software screenshots · 42 Web and mobile UI quality · 43 Dashboards, charts and business intelligence · 44 Maps, satellite and drone imagery · 45 Education (worksheets, handwriting, diagrams) · 46 Publishing, media and archives (scans, OCR) · 47 Marketing and ad compliance · 48 Fashion and beauty · 49 Customer service (photos of faults, error screens) · 50 Content moderation and brand safety (logos, counterfeits)

You may swap up to 3 domains in your slice if you can show another domain has far more usable data. Say which and why.

---

## Part 3. Merge prompt (run once after all five return)

You have five task-atlas reports. Merge them into one.
1. Combine the CSV blocks into one table. Remove duplicate datasets, keeping the card with the strongest evidence.
2. Re-check the 20 candidates rated `USE` that matter most: open each `sample_proof_url` and confirm that the pasted rows match. Downgrade any that do not match, and say so.
3. Build a **coverage matrix** of the 50 domains against these columns: number of tasks, number with a `USE` dataset, number only drawable by a generator, number needing human photos.
4. Pick a **first build list** of the 25 best tasks across the most domains: one per domain wherever possible, `USE` only, smallest fetch first, balanced between yes/no and pick-one.
5. List every `GATED` candidate with what a person must do (URL and action).
6. Recommend which Tier B question types to build first, which tasks are good for Tier C, and which datasets look most likely to overlap with model training data.
Do not add new datasets in the merge step.
