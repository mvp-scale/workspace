# t09_vehicle_damage

Status: READY

## Recon

Source: `DrBimmer/car-parts-and-damage-dataset` (MIT). The full tree is about 3.31 GB, so only the annotation JSON files were downloaded (1,815), plus the 25 images used below.

Class titles in the annotations match the card. Damage classes: Dent, Cracked, Scratch, Flaking, Broken part, Paint chip, Missing part, Corrosion. Part classes: Windshield, Back-windshield, Front-window, Back-window, Front-door, Back-door, Front-wheel, Back-wheel, Front-bumper, Back-bumper, Headlight, Tail-light, Hood, Trunk, License-plate, Mirror, Roof, Grille, Rocker-panel, Quarter-panel, Fender.

814 files have only damage classes. 998 files have only part classes. 3 files have no objects. No file has both. The directory name is not the label: `Car damages dataset` is mostly part annotations.

A sample damage file (`Car parts dataset/File1/ann/Car damages 101.png.json`) lists Broken part, Scratch and Dent. A sample parts file (`Car damages dataset/File1/ann/Car damages 100.png.json`) lists Back-bumper, Back-door, wheels, windows and the other part names. Images sit in the sibling `img/` folder; the checked file is a PNG.

## Labels

Yes/no: "Is this vehicle visibly damaged?" Yes when `classTitle` is one of the eight damage classes. No when the file has only part classes. Seed 9 takes 13 yes and 12 no. Chance rate 50%.

`label_origin`: presence of a damage classTitle. `rederive` reads that JSON again. URL: https://huggingface.co/datasets/DrBimmer/car-parts-and-damage-dataset

## Caveats

A parts-only annotation is the negative. Those images were annotated for parts, not given a class named undamaged, so a part photo can still show damage the file does not mark. Damage-only images do not say which part is damaged (see t10).
