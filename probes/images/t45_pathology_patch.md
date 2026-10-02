RESEARCH BENCHMARK ONLY, NOT FOR CLINICAL USE

# t45_pathology_patch

Status: READY

## Recon

Source: PatchCamelyon (PCam), owner Bas Veeling, https://github.com/basveeling/pcam. The README states: "The data is provided under the CC0 License, following the license of Camelyon16." Used mirror: Hugging Face `dpdl-benchmark/patch_camelyon` (parquet, no login, not gated). The original files are HDF5 (no h5py here), so the mirror was used. Only one shard was downloaded: `data/test-00000-of-00002.parquet` (375 MB, 16,384 rows, 8,173 positive). Columns: `image` (PNG bytes struct) and `label` (int 0/1). No other columns exist.

Three annotation rows (no image bytes), test shard 0:
- row 0: label 0
- row 1: label 1
- row 2: label 0

Image size: 96 x 96 px, H&E lymph-node sections, 10x undersampled from 0.243 micron/px. Saved at native 96 x 96 (very small).

## Labels

Yes/no: "Does this lymph-node tissue patch contain tumour (metastasis)?" Yes when label = 1. Seed 45 takes 13 yes and 12 no from the test shard, shuffled. Chance rate 50%.

Label origin: PCam label is derived from the CAMELYON16 pathologist-drawn lesion annotations. Granularity is patch-level (a binary label per patch, computed from the slide's pixel-level annotation). A positive label means the CENTRE 32x32 px region holds at least one tumour pixel; tumour only in the outer ring does not count, so a visibly tumorous border can be labelled no. `label_origin`: "PCam binary label, derived from CAMELYON16 pathologist lesion annotations; patch-level". `rederive` re-reads the parquet row.

Licence: CC0-1.0 as stated by the owner.

## Caveats

- Very small patches (96 px). The tumour label depends on the centre 32 px only.
- Negatives were selected with hard-negative mining by a small CNN; this affects which patches are sampled, not the label, which comes from the annotation.
- Several patches can come from the same slide; slide id is not in the mirror.
- Research benchmark, not for clinical use.

## Angle questions (derived from the annotation, not built)

The mirror has only `label`, the row index and the decoded image header, so these are limited.
1. "Is the label of this patch tumour-positive?" Same as the built question; rule: label == 1.
2. "Is this patch from the positive half of a balanced pair?" Not computable; skipped.
3. Pick-one "Is the centre 32x32 px region tumour or non-tumour?" Rule: label 1 = tumour, 0 = non-tumour (same answer, different wording, a robustness check).
4. Yes/no "Is the image exactly 96 pixels wide?" Rule: width read from the PNG header (always yes; a sanity control).
5. Yes/no "Does this patch come from the first half of the shard?" Rule: row index < 8192 (position control, should be at chance for any real model).
6. Pick-one "Is this image a lymph-node patch, a vehicle or a document?" Rule: constant answer from the dataset card (modality control).
