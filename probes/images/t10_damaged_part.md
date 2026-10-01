# t10_damaged_part

Status: BLOCKED

## Recon

Same source as t09: `DrBimmer/car-parts-and-damage-dataset` (MIT). Annotation JSON files only were downloaded (1,815 files). Class titles in the files:

Damage: Scratch (3,242), Dent (1,664), Broken part (1,500), Paint chip (1,356), Missing part (632), Flaking (337), Corrosion (277), Cracked (76).

Parts: Back-window, Mirror, Front-window, Fender, Front-door, Headlight, Front-wheel, Back-wheel, Rocker-panel, Quarter-panel, Roof, Back-door, Tail-light, Hood, Front-bumper, Windshield, Grille, Back-bumper, Trunk, License-plate, Back-windshield.

814 files contain only damage classes. 998 files contain only part classes. 3 files have no objects. No file contains both a damage class and a part class, so no image shows a damage object and a part object together. Overlap cannot be computed, and there are 0 images with exactly one damage object and exactly one part object.

Folder names do not match the labels: the directory `Car damages dataset` is mostly part annotations, and `Car parts dataset` is mostly damage annotations. The count above uses `classTitle`, not the folder name.

## Why blocked

The question needs the part that overlaps the damage. No annotation has both.
