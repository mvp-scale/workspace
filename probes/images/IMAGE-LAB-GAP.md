# Image lab gap

A function is one decision a person makes from one picture. Five are listed for each new domain, taken from the questions in the task atlas.

The cutoff: two kinds of question are below the line.

- **Present.** Is the thing in the picture? Signature, logo, fire, vest, pothole, person, weapon.
- **Identity.** Is this the kind of thing we named? Document type, app name, species, product, chart type.

Both are "say whether the label matches." A result there does not show that the model can read, compare, count, or grade.

Above the line:

- **Read** a value that is in the picture (amount, date, gauge, a named box).
- **Compare** two of those values (words against figures, expiry against issue).
- **Count** how many, including bins that require a count.
- **Grade** a scale (little / mild / severe, how full, how much is left).

Receipt capture is above the line. Document type and signature present are below it.

## Current domains

| Domain | Function | Line |
|---|---|---|
| Finance and admin | Read the receipt total | Above. 13/13. |
| Finance and admin | Read the cheque amount | Above. 25/25, and the true amount is one of four choices. |
| Finance and admin | Count the receipt lines | Above. 9/12. |
| Finance and admin | Read a number off a chart | Above. 22/25. |
| Finance and admin | Read a handwritten line | Above. 25/25, and the full sentence is one of four choices. |
| Finance and admin | What type of document is this | Below. Identity. 22/25. |
| Finance and admin | Has the form been signed, ticked, or named | Below. Present. 25/25 on forms we drew. |
| Insurance and claims | Is the vehicle damaged | Below. Present. 12/25, and the undamaged label is weak. |
| Insurance and claims | Which part is damaged | Above, if the part has to be named from damage. No data. |
| Insurance and claims | Is the roof or wall damaged | Below. Present. No photos. |
| Retail | How many objects | Above. 13/25. Fails from seven upward. |
| Retail | Is there an empty shelf gap | Below. Present. No label. |
| Retail | Is the fruit rotten | Below. A two-step identity. 22/25. |
| Retail | Which brand logo | Below. Identity. 24/25. |
| Logistics | What is the plate number | Above. A read. No text column. |
| Logistics | What condition is the parcel in | Above if it is intact / dented / crushed / torn. No photos. Yes/no damaged is below the line. |
| Safety and compliance | Is anyone without a hard hat | Below. Present. 20/25. |
| Safety and compliance | Is there fire or smoke | Below. Present. No negatives with a stated licence. |
| Safety and compliance | Is there a spill | Below. Present. No photos. |
| Manufacturing and field | Which defect is on the steel | Below. Identity. The file is on disk and not run. |
| Manufacturing and field | What does the gauge read | Above. A read. No images yet. |
| Manufacturing and field | Which disease is on the leaf | Below. Identity. 18/25, and the plant gives it away. |
| IT and property | Which element is on the screen | Below. Identity. The public sets do not name an element. |
| IT and property | What kind of room is this | Below. Identity. No exterior class. |

## New domains

Five questions each, from the atlas. "Above" is a read, a comparison, a count, or a grade. A domain with no row above the line cannot be tested at the layer you want, even though it has pictures.

### Utilities

| Function | Question | Line |
|---|---|---|
| Read the gauge | What does the gauge read? | Above |
| Read the water meter | Which value does this meter show? | Above. Same skill as the gauge if both are digit reads. |
| Read the electricity meter | Which reading is shown? | Above. Repeat of the row above. |
| Name the meter type | Mechanical or LCD? | Below. Identity. |
| Say the needle is out of range | Is the needle past halfway? | Above. A comparison, once the reading is known. |

Three sit above the line, and two of those are the same read.

### Roads and bridges

| Function | Question | Line |
|---|---|---|
| Pothole present | Is there a pothole? | Below. Present. |
| Name the crack | Longitudinal, transverse, alligator, or pothole? | Below. Identity. |
| Grade the pothole | None, low, medium, or severe? | Above. Grade. |
| Name the bridge defect | Spalling, rust, crack, or exposed rebar? | Below. Identity. |
| Crack or exposed rebar present | Does the concrete show a crack? Is rebar exposed? | Below. Present. |

One of five clears the line. RDD2022 can score the pothole grade only if severity is in the file. The checked label is present-or-not, so the grade may not be testable. Treat the grade as unproven until the severity column is seen.

### Energy

| Function | Question | Line |
|---|---|---|
| Solar cell defective | Is this cell defective? | Below. Present. |
| Broken insulator | Is an insulator broken? | Below. Present. |
| Broken cable | Is a cable broken? | Below. Present. Repeat of the row above. |
| Name the panel condition | Clean, dusty, bird drop, snow, electrical, or physical? | Below. Identity. |
| Blade or hotspot | Does the blade show damage? Does the thermal image show a hotspot? | Below. Present. |

None clear the line.

### Safety, beyond the hard hat

| Function | Question | Line |
|---|---|---|
| Vest missing | Is any worker without a vest? | Below. Present. |
| Hard hat missing | Is any worker without a helmet? | Below. Present. This is t18 again. |
| Person with a forklift | Is a person in frame with the forklift? | Below. Present. Two things at once is still presence. |
| Which PPE is missing | Hard hat, mask, vest, or none? | Below. Identity of what is absent. |
| Seat belt, person down, smoking | Is the belt on? Is someone lying down? Is someone smoking? | Below. Present. |

None clear the line.

### Warehousing

| Function | Question | Line |
|---|---|---|
| Person with a forklift | Is a person visible with the forklift? | Below. Present. |
| Carton damaged | Is this box damaged? | Below. Present. |
| Count the pallets | How many pallets are in view? | Above. Count. No usable dataset in the atlas. |
| Count the boxes on a pallet | How many boxes are on this pallet? | Above. Count. No usable dataset. |
| Aisle blocked | Is the aisle blocked? | Below. Present. |

The two counts are the real functions. Neither has a dataset we can score.

### Pharmacy

| Function | Question | Line |
|---|---|---|
| Carton or leaflet | Is this an outer carton or a leaflet? | Below. Identity. |
| Import or domestic | Is this an imported pack? | Below. Identity. |
| Which tablet | Which product is this tablet? | Below. Identity. |
| Count the boxes | How many medicine boxes are in the photo? | Above. Count. |
| Empty blister | Is any blister cavity empty? | Below. Present. No dataset. |

One of five clears the line.

### Parking and traffic

| Function | Question | Line |
|---|---|---|
| How many spaces are free | Bins of labelled empty spaces | Above. Count. PKLot can score this. |
| Lot more than half full | Is occupancy over half? | Above. A comparison built from that count. |
| Rider wearing a helmet | Is every rider helmeted? | Below. Present. |
| Which vehicle class | Car, bus, or truck? | Below. Identity. |
| What colour is the signal | Red, yellow, or green? | Above. A read of a state, closer to a gauge than to "what object is this." No dataset that clears the atlas rules. |

Two of five can be tested, and they are the same parking count.

### Livestock

| Function | Question | Line |
|---|---|---|
| Goat or sheep | Which animal is most numerous? | Below. Identity. |
| Count the sheep | How many sheep are visible? | Above. Count. |
| Pigs standing | How many pigs in the pen are standing? | Above. Count of a pose. |
| Fish family | Which family is this fish? | Below. Identity. |
| Count the cattle | How many cattle? | Above. Count. No verified dataset. |

Two counts have data in the atlas (sheep and goats, pig posture). Cattle does not.

### Property drawings

| Function | Question | Line |
|---|---|---|
| Count the doors | How many doors does the plan show? | Above. Count. |
| Count the bedrooms | How many bedrooms? | Above. Count. Same kind of count as doors. |
| When the house was built | Era of the facade | Below. Identity. |
| Architectural style | Which style is this facade? | Below. Identity. |
| What room is this | Kitchen, bath, bedroom, living room | Below. Identity. This is t25. |

Two counts, one drawing set, and that set is non-commercial.

### Catastrophe claims

| Function | Question | Line |
|---|---|---|
| Grade the damage | Little or none, mild, or severe? | Above. Grade. CrisisMMD. Non-commercial. |
| What disaster | Earthquake, flood, hurricane, fire, or none? | Below. Identity. |
| Buildings or roads damaged | Does the image show infrastructure damage? | Below. Present. |
| Flooding visible | Is flooding visible? | Below. Present. |
| Roof damaged | Is the roof damaged? | Below. Present. No dataset. |

One of five clears the line.

### Identity documents, synthetic only

| Function | Question | Line |
|---|---|---|
| Read the sex field | What sex is printed? | Above. A field read. The set uses real faces that were morphed. Skip it. |
| Expiry after issue | Is the expiry later than the issue date? | Above. A comparison. Synthetic passports. |
| Read the nationality | Which nationality is printed? | Above. A field read. Repeat of reading a field. |
| Tampered | Has this ID been altered? | Below. A judgement, and the atlas did not clear a dataset. |
| Passport or card | Which document is this? | Below. Identity. |

The comparison is the one that is not another receipt-style read. No real identity documents.

### Content moderation

| Function | Question | Line |
|---|---|---|
| Weapon present | Does the image contain a weapon? | Below. Present. |
| Alcohol present | Is there an alcoholic drink? | Below. Present. |
| Logo present | Is a brand logo visible? | Below. Present. This is t17. |
| Logo's industry | Food, clothes, electronics, or other? | Below. Identity. |
| Watermark or counterfeit | Is there a watermark? Is the product fake? | Below. Present, or a judgement with no dataset. |

None clear the line.

### IT support and screens

| Function | Question | Line |
|---|---|---|
| Which application | Excel, Word, VS Code, or another named app? | Below. Identity. |
| Which operating system | Windows, macOS, or Linux? | Below. Identity. |
| Which kind of software | Office, CAD, development, or other? | Below. Identity. |
| Error dialog | Is an error showing? | Below. Present. No dataset. |
| What kind of mobile screen | Login, list, form, gallery, settings, or tutorial? | Below. Identity. |

None clear the line. The lab's screenshot task was this kind of question.

### Charts

| Function | Question | Line |
|---|---|---|
| What type of chart | Bar, line, pie, or scatter? | Below. Identity. We already read a number off a chart. |
| Is series A higher than B | At this point, is A above B? | Above. A comparison. |
| Does the chart show this value | Is the stated number actually there? | Above. A read, the same skill as t07. |
| Do the lines cross | Do any lines intersect? | Above. A comparison of two series. |
| How many panels | How many subplots? | Above. A count. |
| Which series is the maximum | Which named series peaks? | Above. A comparison. |

Chart type is the one to drop. The other four are the layer beyond t07, if the chart file stores the series values. ChartQA already supports the value check. The pairwise and crossing questions need a set such as FigureQA, and that download asks for a click-through licence.

### Facilities

| Function | Question | Line |
|---|---|---|
| Which bin | Cardboard, glass, metal, paper, plastic, or trash? | Below. Identity. |
| Dumped waste in an aerial tile | Is waste visible? | Below. Present. |
| What is the litter | Bottle, can, bag, or cup? | Below. Identity. |
| Bin overflowing | Is the bin overflowing? | Below. Present. |
| Spill on the floor | Is there a spill? | Below. Present. This is t20. |

None clear the line.

### Finance, the extra functions the atlas adds

These sit in a domain we already have. They are the five worth looking at, and they show the same split.

| Function | Question | Line |
|---|---|---|
| Do the cheque amounts agree | Does the amount in words match the figures? | Above. A comparison. Not tested. |
| Is a purchase order printed | Does the invoice show a PO number? | Below. Present. The file can also be used to read the number, which would be above the line. |
| Count the invoice lines | How many line items? | Above. A count. We already do this on receipts, 9/12. |
| Read the invoice total | Which amount is the total? | Above. A read we already pass. |
| Which bank, which country, cash or card | Bank name, country, payment method | Below. Identity. |

## What this leaves

Above the line, with a dataset we could score, the new work is small:

- Read a gauge or a meter.
- Count free parking spaces.
- Count animals in a drone frame or pigs standing in a pen.
- Count doors on a floor plan.
- Grade disaster damage as little, mild, or severe.
- Check that a synthetic passport expiry is after the issue date.
- On charts, compare two series or count the panels, past the number we already read.

Everything else in those domains is a presence check or a "what is this" label. That is the layer the current scores already cover, and it is the layer to stop adding.

## Where the pictures go

Everything scored today is under `data/image-lab/images/<task>/`, one folder per task, 25 files each. Twelve folders, 300 files. The lab page does not read a domain folder. It maps the task number: t01–t08 finance and admin, t09–t12 insurance and claims, t13–t17 retail and logistics, t18–t20 safety, t21–t23 manufacturing and field, t24–t25 IT and property.

Leave those folders as they are. A new source gets its own task folder, never mixed into `t02_receipt_capture` or the others. The table below is the check for a picture that looks wrong: folder, domain, what the file is supposed to be, and where it was fetched. Domain stays in this map. The folder name stays the task.

| Folder now | Domain | What the 25 pictures are |
|---|---|---|
| t02_receipt_capture | Finance and admin | Real receipt photos. CORD. |
| t03_document_type | Finance and admin | Scanned pages. RVL-CDIP sample. |
| t05_form_completeness | Finance and admin | Drawn here. Not a source to extend. |
| t06_cheque_amount | Finance and admin | Synthetic cheques. Not a source to extend. |
| t07_chart_reading | Finance and admin | Chart images. ChartQA. |
| t08_handwritten_line | Finance and admin | Real handwriting. IAM. |
| t09_vehicle_damage | Insurance and claims | Real cars. The undamaged label is the weak one. |
| t14_count_items | Retail | Real photos. CountBench. |
| t15_produce_fresh_rotten | Retail | Real fruit. |
| t17_logo_present | Retail | Real logo photos. |
| t18_hard_hat_worn | Safety and compliance | Real site photos. |
| t23_crop_disease | Manufacturing and field | Real leaves. One plant per disease. |

## What can be brought in

From the atlas, only the real sets that sit above the line. Copy about 25 images and the matching label file into a new task folder. Do not download the multi-gigabyte archive when a single image is its own file.

| New folder | Domain | Source | Bring in? | What arrives with the picture |
|---|---|---|---|---|
| (new) parking spaces | Traffic and parking | dronefreak/PKLot. Lot cameras. The full repo is 3.9 GB. Labels for the training split are a 15.5 MB file. | Yes, 25 frames, not the whole set. Open licence, CC BY 4.0. | Each space marked occupied or empty, so a free-space count. |
| (new) sheep and goats | Livestock | AGRARIAN/greek_sheep_goats_dataset. Drone frames. 3.6 GB as separate files, about 0.5 MB each. | Yes, 25 images plus their text labels. Apache-2.0. | Hand-drawn boxes, goat or sheep. Empty label files are the empty frames. Patches overlap, so do not take 25 crops of one photo. |
| (new) pigs standing | Livestock | anilbhujel/viewpoint-aware-pig-posture-recognition. Barn cameras. 1.4 GB. The table of boxes is 7.6 MB. | Yes, 25 images. CC BY 4.0. | A box and a posture per pig. Count the standing class. Skip the camera-angle columns. |
| (new) floor-plan doors | IT and property | v1nz/cubicasa5k-yolo. Scanned plans. About 4.4 MB a plan. | Only if non-commercial is accepted. 25 plans. | Door count is the lines marked door. The viewer does not name the file, so pair each plan with its own label file. |
| (new) damage severity | Insurance and claims | QCRI/CrisisMMD. Real photos. One image is its own file. The label zip is 3 MB. The photo repo is 1.9 GB. | Only if non-commercial is accepted. 25 images. | Severity is little, mild, or severe, on the image, not on the tweet. Do not copy the tweet text into the task. |
| — | Utilities | goodcoffee/Meter_Reading | No. The value field is `synth_dial_value`. | Drawn gauges. Leave them out. |
| — | Identity | Synthetic passports | No. | Not real documents. |
| — | Charts | ChartQA, ChartBench, FigureQA | No, for a new fetch. | Plotted or generated. The charts already in t07 stay. |

## Plan

For each domain, use this file to see whether a real source already exists. If it does, take the images and the annotation that came with them. If it does not, keep looking for a real source. Do not fill the hole with a drawing.

Real means a photograph, a scan, or a frame from a real camera. A floor plan that was drawn by a person and then scanned counts. An invoice, cheque, gauge, car, or animal drawn by a model does not. Generating pictures with Gemini is not a fallback. A synthetic image will be scored as if the job were real.

Plan B, only after a real annotated source cannot be found: search for real pictures, then use a cheap model only to reject ones that are blurry, off the subject, or not the kind of view the question needs. That model does not write the answer. The score still needs an annotation that was not produced by the model under test. Extra questions on one image are kept only when they agree with a label the file already has.

| Function above the line | Source in the atlas | Real? | Next step |
|---|---|---|---|
| Read a gauge or a meter | goodcoffee Meter_Reading | No. It is a generator. | Find photographed meters with a reading written down. |
| Count free parking spaces | PKLot | Yes. Lot cameras. | Usable. |
| Count sheep or goats | AGRARIAN drone frames | Yes. | Usable. |
| Count pigs standing | Barn video frames | Yes. | Usable if the pose label is human. |
| Count doors on a floor plan | CubiCasa5K | Yes, as scans of plans. Non-commercial. | Usable only if that licence is accepted. |
| Grade disaster damage | CrisisMMD | Yes. Photos. Non-commercial. | Usable only if that licence is accepted. Confirm a severity grade is in the file, not only present or absent. |
| Passport expiry after issue | Synthetic passports | No. | Do not use. No real identity documents. |
| Compare two chart series | ChartQA is mostly plotted charts. FigureQA is generated. | No, for the plotted sets. | Prefer figures cut from real reports, and only where the number is printed in a table we can check. |
