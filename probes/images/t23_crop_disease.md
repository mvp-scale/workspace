# t23_crop_disease

Status: READY

## Recon

File: `/workspace/data/sources/image-lab/plant-leaf/data/train-00000-of-00002.parquet` (6,393 rows). The second shard was not downloaded. The full set is about 0.96 GB. Licence CC-BY-4.0.

Columns: `image`, `label` (ClassLabel), `plant_type` (ClassLabel). The class names are in the parquet metadata and the README:

Anthracnose, Anthracnose lesions, Black Rot, Downey mildew, Downy mildew, Eggplant Cercopora leaf spot, Eggplant begomovirus, Eggplant fresh leaf, Eggplant verticillium wilt, Fresh leaf, Fusarium wilt, Mosaic virus, Tomato Bacterial spot, Tomato Fresh leaf, Tomato leaf curl virus, Tomato spotted wilt.

Counts in this shard include Fresh leaf 1,595, Downey mildew 1,254, Downy mildew 746, Anthracnose 601, Mosaic virus 600, Black Rot 560, Anthracnose lesions 535, Fusarium wilt 502. Plant types: Bitter Gourd, Bottle gourd, Cauliflower, Cucumber, Eggplant, Tomato. First rows are `label` 3 (Downey mildew) and `plant_type` 0 (Bitter Gourd).

## Labels

Question: "What condition does this leaf show?" Options are always Fresh leaf, Black Rot, Anthracnose and Mosaic virus. The right answer is the `label` class name. Seed 23 takes 7 of one class and 6 of each of the other three (the order of classes is shuffled, so which class gets 7 changes only with the seed). Chance rate 25%. No class is the right answer more than 40% of the time.

`Downey mildew` and `Downy mildew` are separate names in the file. Neither is used here, so a spelling pair is not both offered as options.

`label_origin`: label class name. URL: https://huggingface.co/datasets/Project-AgML/plant_leaf_disease_classification

## Caveats

Only shard `train-00000-of-00002` is on disk. Some rows in the wider set name the plant in the class (Tomato Fresh leaf) and some do not (Fresh leaf). This sample uses Fresh leaf, not the tomato-specific fresh class.
